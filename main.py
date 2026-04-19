import logging
import threading

from application.app_factory import create_app

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_context = create_app()
app = _context.app
wm = _context.word_manager
typer = _context.typer
grid_reader = _context.grid_reader
ll_solver = _context.ll_solver
region_store = _context.region_store
autoplay_state = _context.autoplay_state
solver_cache = _context.solver_cache
screen_reader = _context.screen_reader
word_service = _context.word_service
preset_repository = _context.preset_repository
preset_service = _context.preset_service
letterlink_service = _context.letterlink_service
optional_auth_required = _context.optional_auth_required
set_ll_grid_region = _context.set_ll_grid_region
build_trie_bg = _context.build_trie_bg
get_or_build_solver = _context.get_or_build_solver
autoplay_config = autoplay_state.config
autoplay_logs = autoplay_state.logs
autoplay_config_lock = autoplay_state.config_lock
autoplay_logs_lock = autoplay_state.logs_lock


def load_presets():
    return preset_repository.load()


def save_presets(presets):
    return preset_repository.save(presets)


def run_flask():
    app.run(debug=False, port=5000, use_reloader=False)


if __name__ == "__main__":
    threading.Thread(target=build_trie_bg).start()

    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    logger.info("Starting Overlay Manager...")

    from overlay_manager import run_overlay

    def on_overlay_move(region):
        if screen_reader:
            screen_reader.prompt_region = region
            screen_reader.turn_region = region
            set_ll_grid_region(region)
            region_store.set_region(region)

    run_overlay(on_overlay_move)
