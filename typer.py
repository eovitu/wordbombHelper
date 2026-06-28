"""Digitação instantânea — sem humanizador, sem delays artificiais."""
import logging
import threading

import keyboard
import pyautogui

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.0

logger = logging.getLogger(__name__)


class Typer:
    def __init__(self):
        self._lock = threading.Lock()
        self.done_event = threading.Event()
        self.done_event.set()
        self._abort = False
        keyboard.on_press_key("insert", lambda _: setattr(self, "_abort", True))

    def type_word(self, word: str, auto_tab: bool = True) -> None:
        """Digita a palavra imediatamente. Alt+Tab para o jogo se auto_tab=True."""
        if not self._lock.acquire(blocking=False):
            logger.debug("type_word ignorado: já digitando")
            return
        self._abort = False
        self.done_event.clear()
        t = threading.Thread(target=self._type_thread, args=(word, auto_tab), daemon=True)
        t.start()

    def _type_thread(self, word: str, auto_tab: bool) -> None:
        import time
        try:
            if auto_tab:
                pyautogui.hotkey("alt", "tab")
                time.sleep(0.08)  # aguarda foco da janela
            if self._abort:
                return
            keyboard.write(word, delay=0)
            if self._abort:
                return
            keyboard.press_and_release("enter")
            logger.debug("Digitou: '%s'", word)
        except Exception as e:
            logger.error("Erro na digitação: %s", e)
        finally:
            self._abort = False
            self.done_event.set()
            self._lock.release()
