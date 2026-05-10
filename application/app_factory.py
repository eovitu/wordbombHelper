import logging
import os
from dataclasses import dataclass

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
        optional_auth_required=optional_auth_required,
    )
