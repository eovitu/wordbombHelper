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
        # Sem hotkey de abort: a tecla Insert agora é o "próxima sugestão" (reroll).
        # O auto-type em andamento ainda pode ser abortado pelo pyautogui.FAILSAFE
        # (mouse no canto superior-esquerdo).

    def type_word(self, word: str, auto_tab: bool = True) -> None:
        """Digita a palavra imediatamente. Alt+Tab para o jogo se auto_tab=True."""
        if not self._lock.acquire(blocking=False):
            logger.debug("type_word ignorado: já digitando")
            return
        self.done_event.clear()
        try:
            t = threading.Thread(target=self._type_thread, args=(word, auto_tab), daemon=True)
            t.start()
        except Exception as exc:
            # Se a thread não nasce, _type_thread nunca roda seu finally — então liberamos
            # aqui o lock e o evento, senão TODA digitação futura fica travada para sempre.
            logger.error("Falha ao iniciar thread de digitação: %s", exc)
            self.done_event.set()
            self._lock.release()

    def _type_thread(self, word: str, auto_tab: bool) -> None:
        import time
        try:
            if auto_tab:
                pyautogui.hotkey("alt", "tab")
                time.sleep(0.08)  # aguarda foco da janela
            keyboard.write(word, delay=0)
            keyboard.press_and_release("enter")
            logger.debug("Digitou: '%s'", word)
        except Exception as e:
            logger.error("Erro na digitação: %s", e)
        finally:
            self.done_event.set()
            self._lock.release()
