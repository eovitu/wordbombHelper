import logging

from application.app_factory import create_app
from shared.logging_config import setup_logging

# Configura logging (console + arquivo rotativo em logs/wordbomb.log).
# Nível do console via env WORDBOMB_LOG_LEVEL (default INFO); arquivo sempre em DEBUG.
setup_logging()
logger = logging.getLogger(__name__)

# `app` é exposto no nível do módulo para `flask run` (main:app). Toda a montagem
# (DI, threads do scanner, hotkeys) acontece dentro de create_app().
app = create_app().app


if __name__ == "__main__":
    logger.info("WordBomb Flask on http://127.0.0.1:5000")
    app.run(debug=False, port=5000, use_reloader=False, threaded=True)
