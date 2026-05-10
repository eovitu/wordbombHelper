import logging

from application.app_factory import create_app

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logging.getLogger("werkzeug").setLevel(logging.WARNING)

_context = create_app()
app = _context.app
wm = _context.word_manager
typer = _context.typer
region_store = _context.region_store
autoplay_state = _context.autoplay_state
screen_reader = _context.screen_reader
word_service = _context.word_service
preset_repository = _context.preset_repository
preset_service = _context.preset_service
optional_auth_required = _context.optional_auth_required
autoplay_config = autoplay_state.config
autoplay_logs = autoplay_state.logs
autoplay_config_lock = autoplay_state.config_lock
autoplay_logs_lock = autoplay_state.logs_lock


def load_presets():
    return preset_repository.load()


def save_presets(presets):
    return preset_repository.save(presets)


if __name__ == "__main__":
    logger.info("WordBomb Flask on http://127.0.0.1:5000")
    app.run(debug=False, port=5000, use_reloader=False)
