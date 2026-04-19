import logging
import os
import threading

from flask import Flask, render_template

from api.routes import create_api_blueprint
from application.autoplay_state_service import AutoplayStateService
from application.letterlink_service import LetterLinkService
from application.preset_service import PresetService
from application.region_store import RegionStore
from application.solver_cache_service import SolverCacheService
from application.word_service import WordService
from grid_reader import GridReader
from infrastructure.presets_repository import FilePresetRepository
from letter_link_solver import LetterLinkSolver
from screen_reader import ScreenReader
from shared.security import make_optional_auth_required
from typer import Typer
from word_manager import WordManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Legacy-compatible globals
wm = WordManager()
typer = Typer()
grid_reader = GridReader()
ll_solver = LetterLinkSolver()

# New layered services
region_store = RegionStore()
autoplay_state = AutoplayStateService()
solver_cache = SolverCacheService(wm)

SAFE_API_TOKEN = os.getenv("WORDBOMB_API_TOKEN", "").strip()
optional_auth_required = make_optional_auth_required(SAFE_API_TOKEN)

# Legacy region facade compatibility
ll_grid_region = None
ll_grid_region_lock = threading.RLock()


def set_ll_grid_region(region):
    global ll_grid_region
    with ll_grid_region_lock:
        ll_grid_region = region


def get_ll_grid_region():
    with ll_grid_region_lock:
        return ll_grid_region


# Callback wiring
screen_reader = ScreenReader(callback_found_word=None)
word_service = WordService(wm, typer, screen_reader, autoplay_state)


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

# Legacy-compatible shared state aliases
autoplay_config = autoplay_state.config
autoplay_logs = autoplay_state.logs
autoplay_config_lock = autoplay_state.config_lock
autoplay_logs_lock = autoplay_state.logs_lock

# Presets service
PRESETS_FILE = os.path.join(os.path.dirname(__file__), "presets.json")
preset_repository = FilePresetRepository(PRESETS_FILE)
preset_service = PresetService(preset_repository)
letterlink_service = LetterLinkService(grid_reader, screen_reader, solver_cache, region_store)


def load_presets():
    return preset_repository.load()


def save_presets(presets):
    return preset_repository.save(presets)


# Register API routes through blueprint
app.register_blueprint(
    create_api_blueprint(
        {
            "word_manager": wm,
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


def run_flask():
    app.run(debug=False, port=5000, use_reloader=False)


if __name__ == "__main__":
    # Initial Trie build on boot
    threading.Thread(target=build_trie_bg).start()

    # Start Flask in a separate thread
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    logger.info("Starting Overlay Manager...")

    # Run Tkinter Overlay in Main Thread
    from overlay_manager import run_overlay

    def on_overlay_move(region):
        if screen_reader:
            screen_reader.prompt_region = region
            screen_reader.turn_region = region
            set_ll_grid_region(region)
            region_store.set_region(region)

    run_overlay(on_overlay_move)
