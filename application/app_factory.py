import logging
import os
from dataclasses import dataclass

import pytesseract
from flask import Flask, render_template

from api.routes import create_api_blueprint
from application.autoplay_state_service import AutoplayStateService
from application.calibration_profiles import CalibrationProfiles
from application.missing_prompts_store import MissingPromptsStore
from application.match_summary import MatchSummary
from application.personal_dictionary import PersonalDictionary
from application.preset_service import PresetService
from application.practice_service import PracticeService
from application.region_store import RegionStore
from application.word_manager import WordManager
from application.word_service import WordService
from infrastructure.input.typer import Typer
from infrastructure.ocr.screen_reader import ScreenReader
from infrastructure.repositories.presets_repository import FilePresetRepository
from shared.security import make_optional_auth_required
from used_word_scanner import UsedWordScanner, OcrSolvePanelSource

logger = logging.getLogger(__name__)


def register_global_hotkeys(keyboard_module, word_service, screen_reader=None):
    """Registra somente teclas que não fazem parte da digitação de palavras."""
    keyboard_module.add_hotkey("insert", word_service.reroll_short, suppress=True)
    keyboard_module.add_hotkey("ctrl+r", word_service.reroll_prev, suppress=True)
    keyboard_module.add_hotkey("delete", word_service.reject_current, suppress=True)
    if screen_reader is not None:
        keyboard_module.add_hotkey("f8", screen_reader.capture_calibration_at_cursor, suppress=True)


@dataclass
class AppContext:
    app: Flask
    word_manager: WordManager
    personal_dictionary: PersonalDictionary
    calibration_profiles: CalibrationProfiles
    practice_service: PracticeService
    match_summary: MatchSummary
    typer: Typer
    region_store: RegionStore
    autoplay_state: AutoplayStateService
    screen_reader: ScreenReader
    word_service: WordService
    preset_repository: FilePresetRepository
    preset_service: PresetService
    used_word_scanner: object
    optional_auth_required: object


def create_app():
    template_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "templates"))
    static_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "static"))
    app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)

    personal_dictionary = PersonalDictionary(
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "personal_wordlists")))
    word_manager = WordManager(personal_dictionary=personal_dictionary)
    practice_service = PracticeService(word_manager)
    match_summary = MatchSummary()
    calibration_profiles = CalibrationProfiles(
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "calibration_profiles.json")))
    typer = Typer()
    region_store = RegionStore()
    autoplay_state = AutoplayStateService()

    safe_api_token = os.getenv("WORDBOMB_API_TOKEN", "").strip()
    optional_auth_required = make_optional_auth_required(safe_api_token)

    screen_reader = ScreenReader(autoplay_state=autoplay_state, callback_found_word=None)

    word_manager.current_language = autoplay_state.snapshot_config().get("lang") or word_manager.current_language

    try:
        persisted_region = region_store.get_region()
        if persisted_region:
            screen_reader.turn_region = persisted_region
            screen_reader.prompt_region = persisted_region
            logger.info("Loaded persisted calibration region: %s", persisted_region)
    except Exception as exc:
        logger.debug("Falha ao carregar região de calibração persistida: %s", exc)

    missing_prompts = MissingPromptsStore(os.path.join(os.getcwd(), "missing_prompts.json"))
    word_service = WordService(word_manager, typer, screen_reader, autoplay_state,
                               missing_prompts=missing_prompts,
                               match_summary=match_summary)

    def add_autoplay_log(msg):
        autoplay_state.add_log(msg)

    def on_prompt_found(prompt_text):
        return word_service.on_prompt_found(prompt_text)

    screen_reader.set_callback(on_prompt_found)
    screen_reader.set_log_callback(add_autoplay_log)
    # Persiste a região calibrada (inclusive via listener de mouse, que antes não salvava).
    screen_reader.on_region_calibrated = region_store.set_region

    # ── Hotkeys globais de apoio durante a partida ──────────────────────────────
    # Insert, Ctrl+R e Delete não são teclas digitadas em palavras.
    # suppress=True: a tecla NÃO vaza para o jogo/navegador — evita o Ctrl+R recarregar a
    # aba do jogo. Reusa o hook global do `keyboard` (já usado pelo Typer) — não cria thread.
    # Só navega a sessão; não marca nada, não toca OCR/Pipeline B.
    try:
        import keyboard
        register_global_hotkeys(keyboard, word_service, screen_reader)
        logger.info("Hotkeys ativos (Insert = mais curta, Ctrl+R = anterior, Delete = rejeitar)")
    except Exception as exc:
        logger.warning("Hotkeys de reroll indisponíveis (%s) — use os botões da interface", exc)

    # ── Pipeline B: scanner de palavras-usadas (independente, opcional) ──────────
    # Região do painel SOLVE persistida em arquivo próprio. Engine/captura próprios.
    # Se a região não for calibrada ou o OCR falhar, o scanner se autodesativa.
    solve_region_store = RegionStore(store_file=os.path.join(os.getcwd(), "solve_region.json"))
    active_profile = calibration_profiles.get_active_profile()
    if active_profile:
        region_store.set_region(active_profile["turn_region"])
        screen_reader.turn_region = active_profile["turn_region"]
        screen_reader.prompt_region = active_profile["turn_region"]
        if active_profile["solve_region"]:
            solve_region_store.set_region(active_profile["solve_region"])
        else:
            solve_region_store.clear_persistence()
    _tess_cmd = pytesseract.pytesseract.tesseract_cmd
    _tessdata = os.environ.get(
        "TESSDATA_PREFIX",
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "tessdata")))
    _solve_source = OcrSolvePanelSource(solve_region_store, _tess_cmd, _tessdata)
    # Registro persistente de leituras ambíguas (conservador não marcou) p/ revisão manual.
    ambiguous_store = MissingPromptsStore(os.path.join(os.getcwd(), "ambiguous_ocr.json"))
    used_word_scanner = UsedWordScanner(
        word_manager, _solve_source,
        lang_getter=lambda: autoplay_state.snapshot_config().get("lang"),
        interval=0.45,  # polling de fundo (aprende continuamente durante a partida)
        is_active=lambda: screen_reader.is_watching,  # só varre durante a partida
        ambiguous_store=ambiguous_store,
        personal_dictionary=personal_dictionary,
        match_summary=match_summary,
        on_accepted_word=word_service.observe_accepted_word,
    )
    screen_reader.on_solve_region_calibrated = solve_region_store.set_region
    # Catch-up dirigido por evento: ao iniciar meu turno, A pede um scan e espera ≤180ms.
    screen_reader.on_my_turn_started = lambda: used_word_scanner.request_catch_up(0.18)
    screen_reader.on_my_turn_ended = lambda: used_word_scanner.request_catch_up(0.18)
    used_word_scanner.start()  # thread própria; idle até calibrar + começar a observar

    preset_repository = FilePresetRepository(os.path.join(os.path.dirname(__file__), "..", "presets.json"))
    preset_repository.presets_file = os.path.abspath(preset_repository.presets_file)
    preset_service = PresetService(preset_repository)

    app.register_blueprint(
        create_api_blueprint(
            {
                "word_manager": word_manager,
                "personal_dictionary": personal_dictionary,
                "calibration_profiles": calibration_profiles,
                "solve_region_store": solve_region_store,
                "practice_service": practice_service,
                "match_summary": match_summary,
                "screen_reader": screen_reader,
                "word_service": word_service,
                "autoplay_state": autoplay_state,
                "preset_service": preset_service,
                "region_store": region_store,
                "used_word_scanner": used_word_scanner,
                "optional_auth_required": optional_auth_required,
            }
        )
    )

    @app.route("/")
    def index():
        return render_template("index.html")

    return AppContext(
        app=app,
        word_manager=word_manager,
        personal_dictionary=personal_dictionary,
        calibration_profiles=calibration_profiles,
        practice_service=practice_service,
        match_summary=match_summary,
        typer=typer,
        region_store=region_store,
        autoplay_state=autoplay_state,
        screen_reader=screen_reader,
        word_service=word_service,
        preset_repository=preset_repository,
        preset_service=preset_service,
        used_word_scanner=used_word_scanner,
        optional_auth_required=optional_auth_required,
    )
