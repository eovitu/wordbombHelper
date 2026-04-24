import logging
import os
import threading
from dataclasses import dataclass

from flask import Flask, render_template

from api.routes import create_api_blueprint
from application.autoplay_state_service import AutoplayStateService
from application.letterlink_service import LetterLinkService
from application.preset_service import PresetService
from application.region_store import RegionStore
from application.solver_cache_service import SolverCacheService
from application.word_manager import WordManager
from application.word_service import WordService
from infrastructure.input.typer import Typer
from infrastructure.ocr.grid_reader import GridReader
from infrastructure.ocr.screen_reader import ScreenReader
from infrastructure.repositories.presets_repository import FilePresetRepository
from letter_link_solver import LetterLinkSolver
from shared.security import make_optional_auth_required

logger = logging.getLogger(__name__)


@dataclass
class AppContext:
    app: Flask
    word_manager: WordManager
    typer: Typer
    grid_reader: GridReader
    ll_solver: LetterLinkSolver
    region_store: RegionStore
    autoplay_state: AutoplayStateService
    solver_cache: SolverCacheService
    screen_reader: ScreenReader
    word_service: WordService
    preset_repository: FilePresetRepository
    preset_service: PresetService
    letterlink_service: LetterLinkService
    optional_auth_required: object
    set_ll_grid_region: object
    build_trie_bg: object
    get_or_build_solver: object


def create_app():
    template_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "templates"))
    static_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "static"))
    app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)

    word_manager = WordManager()
    typer = Typer()
    grid_reader = GridReader()
    ll_solver = LetterLinkSolver()
    region_store = RegionStore()
    autoplay_state = AutoplayStateService()
    solver_cache = SolverCacheService(word_manager)

    safe_api_token = os.getenv("WORDBOMB_API_TOKEN", "").strip()
    optional_auth_required = make_optional_auth_required(safe_api_token)

    ll_grid_region = None
    ll_grid_region_lock = threading.RLock()

    def set_ll_grid_region(region):
        nonlocal ll_grid_region
        with ll_grid_region_lock:
            ll_grid_region = region

    def get_ll_grid_region():
        with ll_grid_region_lock:
            return ll_grid_region

    screen_reader = ScreenReader(callback_found_word=None)
    word_service = WordService(word_manager, typer, screen_reader, autoplay_state)

    def build_trie_bg(lang=None):
        return solver_cache.build_trie_bg(lang)

    def get_or_build_solver(lang):
        return solver_cache.get_or_build_solver(lang)

    def add_autoplay_log(msg):
        autoplay_state.add_log(msg)

    def on_prompt_found(prompt_text):
        return word_service.on_prompt_found(prompt_text)

    screen_reader.set_callback(on_prompt_found)
    screen_reader.set_log_callback(add_autoplay_log)

    preset_repository = FilePresetRepository(os.path.join(os.path.dirname(__file__), "..", "presets.json"))
    preset_repository.presets_file = os.path.abspath(preset_repository.presets_file)
    preset_service = PresetService(preset_repository)
    letterlink_service = LetterLinkService(grid_reader, screen_reader, solver_cache, region_store)

    app.register_blueprint(
        create_api_blueprint(
            {
                "word_manager": word_manager,
                "screen_reader": screen_reader,
                "word_service": word_service,
                "autoplay_state": autoplay_state,
                "solver_cache": solver_cache,
                "letterlink_service": letterlink_service,
                "preset_service": preset_service,
                "region_store": region_store,
                "set_ll_grid_region": set_ll_grid_region,
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
        grid_reader=grid_reader,
        ll_solver=ll_solver,
        region_store=region_store,
        autoplay_state=autoplay_state,
        solver_cache=solver_cache,
        screen_reader=screen_reader,
        word_service=word_service,
        preset_repository=preset_repository,
        preset_service=preset_service,
        letterlink_service=letterlink_service,
        optional_auth_required=optional_auth_required,
        set_ll_grid_region=set_ll_grid_region,
        build_trie_bg=build_trie_bg,
        get_or_build_solver=get_or_build_solver,
    )
