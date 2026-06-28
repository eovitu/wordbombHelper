"""Configuração central de logging do WordBomb Helper.

Objetivos:
- Console com nível configurável (env WORDBOMB_LOG_LEVEL, default INFO).
- Arquivo rotativo em `<raiz>/logs/wordbomb.log` SEMPRE em DEBUG (histórico completo
  pra depurar OCR/auto-play depois da partida, sem poluir o console).
- Formato consistente com timestamp, nível e módulo.
- Idempotente: chamar `setup_logging()` mais de uma vez não duplica handlers.

O diretório `logs/` fica relativo a este arquivo (raiz do projeto = pai de `shared/`),
então funciona mesmo que o CWD esteja errado — diferente do resto do projeto.
"""
import logging
import os
from logging.handlers import RotatingFileHandler

# Raiz do projeto = pai de shared/.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DEFAULT_LOG_DIR = os.path.join(_PROJECT_ROOT, "logs")

_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"
_DATEFMT = "%H:%M:%S"

_configured = False


def _resolve_level(level):
    """Aceita int, nome ('DEBUG') ou None (usa env WORDBOMB_LOG_LEVEL, default INFO)."""
    if isinstance(level, int):
        return level
    if isinstance(level, str) and level:
        return getattr(logging, level.upper(), logging.INFO)
    env_level = os.getenv("WORDBOMB_LOG_LEVEL", "").strip().upper()
    if env_level:
        return getattr(logging, env_level, logging.INFO)
    return logging.INFO


def setup_logging(console_level=None, log_dir=None, log_to_file=True):
    """Configura o root logger. Seguro chamar uma vez no boot (main.py).

    :param console_level: nível do console (int/str). None → env/INFO.
    :param log_dir: diretório dos arquivos de log. None → <raiz>/logs.
    :param log_to_file: se False, não cria o arquivo rotativo (útil em testes).
    :returns: o caminho do arquivo de log (ou None se desabilitado/falhou).
    """
    global _configured

    root = logging.getLogger()
    level = _resolve_level(console_level)

    # Root no menor nível necessário pra que o file handler (DEBUG) receba tudo.
    root.setLevel(logging.DEBUG if log_to_file else level)

    if _configured:
        # Já configurado: só ajusta o nível do console e sai.
        for h in root.handlers:
            if isinstance(h, logging.StreamHandler) and not isinstance(h, RotatingFileHandler):
                h.setLevel(level)
        return None

    formatter = logging.Formatter(_FORMAT, datefmt=_DATEFMT)

    console = logging.StreamHandler()
    console.setLevel(level)
    console.setFormatter(formatter)
    root.addHandler(console)

    log_path = None
    if log_to_file:
        try:
            target_dir = log_dir or _DEFAULT_LOG_DIR
            os.makedirs(target_dir, exist_ok=True)
            log_path = os.path.join(target_dir, "wordbomb.log")
            file_handler = RotatingFileHandler(
                log_path, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
            )
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(formatter)
            root.addHandler(file_handler)
        except OSError as e:
            # Falha de disco/permissão não deve impedir o app de subir.
            logging.getLogger(__name__).warning("Não foi possível criar log em arquivo: %s", e)
            log_path = None

    # Reduz ruído do servidor de desenvolvimento.
    logging.getLogger("werkzeug").setLevel(logging.WARNING)

    _configured = True
    logging.getLogger(__name__).info(
        "Logging configurado (console=%s, arquivo=%s)",
        logging.getLevelName(level),
        log_path or "desabilitado",
    )
    return log_path
