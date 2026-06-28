import logging
import os
from dataclasses import dataclass

import pytesseract
from flask import Flask, render_template

from api.routes import create_api_blueprint
from application.autoplay_state_service import AutoplayStateService
from application.preset_service import PresetService
from application.region_store import RegionStore
from application.word_manager import WordManager
from application.word_service import WordService
from infrastructure.input.typer import Typer
from infrastructure.ocr.screen_reader import ScreenReader
from infrastructure.repositories.presets_repository import FilePresetRepository
from shared.security import make_optional_auth_required
from used_word_scanner import UsedWordScanner, OcrSolvePanelSource

logger = logging.getLogger(__name__)


@dataclass
class AppContext:
    app: Flask
    word_manager: WordManager
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

    word_manager = WordManager()
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
    except Exception:
        pass

    word_service = WordService(word_manager, typer, screen_reader, autoplay_state)

    def add_autoplay_log(msg):
        autoplay_state.add_log(msg)

    def on_prompt_found(prompt_text):
        return word_service.on_prompt_found(prompt_text)

    screen_reader.set_callback(on_prompt_found)
    screen_reader.set_log_callback(add_autoplay_log)
    # Persiste a região calibrada (inclusive via listener de mouse, que antes não salvava).
    screen_reader.on_region_calibrated = region_store.set_region

    # ── Pipeline B: scanner de palavras-usadas (independente, opcional) ──────────
    # Região do painel SOLVE persistida em arquivo próprio. Engine/captura próprios.
    # Se a região não for calibrada ou o OCR falhar, o scanner se autodesativa.
    solve_region_store = RegionStore(store_file=os.path.join(os.getcwd(), "solve_region.json"))
    _tess_cmd = pytesseract.pytesseract.tesseract_cmd
    _tessdata = os.environ.get(
        "TESSDATA_PREFIX",
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "tessdata")))
    _solve_source = OcrSolvePanelSource(solve_region_store, _tess_cmd, _tessdata)
    used_word_scanner = UsedWordScanner(
        word_manager, _solve_source,
        lang_getter=lambda: autoplay_state.snapshot_config().get("lang"),
        interval=0.75,
        is_active=lambda: screen_reader.is_watching,  # só varre durante a partida
    )
    screen_reader.on_solve_region_calibrated = solve_region_store.set_region
    used_word_scanner.start()  # thread própria; idle até calibrar + começar a observar

    preset_repository = FilePresetRepository(os.path.join(os.path.dirname(__file__), "..", "presets.json"))
    preset_repository.presets_file = os.path.abspath(preset_repository.presets_file)
    preset_service = PresetService(preset_repository)

    app.register_blueprint(
        create_api_blueprint(
            {
                "word_manager": word_manager,
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
