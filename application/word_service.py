"""WordService — orquestra: prompt → busca palavra → digita (se auto_type ativo)."""
import logging
import threading

from domain.word_selection import WordSelectionParams
from shared.parsing import to_int

logger = logging.getLogger(__name__)


class SuggestionSession:
    """Lista de sugestões do prompt atual, calculada UMA vez. A navegação (Reroll) só move
    um índice — não refaz busca, não marca nada. Índice 0 = escolha do solver."""
    __slots__ = ("prompt", "candidates", "index")

    def __init__(self, prompt, candidates):
        self.prompt = prompt
        self.candidates = candidates
        self.index = 0

    def current(self):
        return self.candidates[self.index] if self.candidates else ""

    def go(self, delta):
        """Move o índice (clamp nas pontas — sem wraparound). Retorna a palavra atual."""
        if not self.candidates:
            return ""
        self.index = max(0, min(len(self.candidates) - 1, self.index + delta))
        return self.candidates[self.index]

    @property
    def total(self):
        return len(self.candidates)

    @property
    def position(self):
        return self.index + 1 if self.candidates else 0


class WordService:
    def __init__(self, word_manager, typer, screen_reader, autoplay_state, missing_prompts=None):
        self.word_manager = word_manager
        self.typer = typer
        self.screen_reader = screen_reader
        self.autoplay_state = autoplay_state
        self.missing_prompts = missing_prompts  # registro de prompts sem palavra (manutenção)
        self.on_word_found_callback = None
        # Sessão de sugestões do prompt atual (feature Reroll). Recriada a cada novo prompt.
        self._session = None
        self._session_lock = threading.Lock()

    def on_prompt_found(self, prompt_text):
        """Callback chamado pelo ScreenReader quando a sílaba é detectada.
        Cria uma SuggestionSession nova (descarta a navegação do prompt anterior)."""
        if not prompt_text:
            self._set_session(None)
            return False

        self.autoplay_state.add_log(f"Prompt: '{prompt_text}'")

        config = self.autoplay_state.snapshot_config()
        if config.get("lang"):
            self.word_manager.current_language = config["lang"]

        self.word_manager.set_recover_config(
            int(config.get("recover_target", 2)),
            config.get("recover_exclude", ""),
        )

        candidates = self.word_manager.get_candidates(
            prompt_text,
            config["lang"],
            config["min_len"],
            config["max_len"],
            config["strategy"],
            priority_letters=config.get("priority_letters", ""),
            exclude_letters=config.get("exclude_letters", ""),
            starts_with_letters=config.get("starts_with_letters", ""),
            finish_with_letters=config.get("finish_with_letters", ""),
            priority_min_len=int(config.get("priority_min_len", 1)),
            priority_max_len=int(config.get("priority_max_len", 46)),
            priority_sublist=config.get("priority_sublist", ""),
        )

        if not candidates:
            self.autoplay_state.add_log(f"Nenhuma palavra para '{prompt_text}'")
            # Manutenção do dicionário: prompt já confirmado pelo pipeline, mas sem palavra.
            if self.missing_prompts:
                self.missing_prompts.record(prompt_text)
            self._set_session(None)
            return False

        primary = candidates[0]
        # Mantém o comportamento existente: a sugestão primária é marcada como usada.
        # (O reroll NÃO marca — só navega.)
        self.word_manager.mark_used(primary)
        self._set_session(SuggestionSession(prompt_text, candidates))
        self.autoplay_state.add_log(f"Match ready: '{primary}'")

        if config.get("auto_type", False):
            self.autoplay_state.add_log(f"Typing: '{primary}'")
            self.typer.type_word(primary, auto_tab=False)
            self.screen_reader.last_word_typed = primary
            self.typer.done_event.wait(timeout=3)

        return True

    def _set_session(self, session):
        """Define a sessão atual e reflete a palavra/posição no ScreenReader (lido pela UI)."""
        with self._session_lock:
            self._session = session
            self.screen_reader.suggested_word = session.current() if session else ""
            self.screen_reader.suggestion_index = session.position if session else 0
            self.screen_reader.suggestion_total = session.total if session else 0

    def reroll(self, delta):
        """Navega a sessão (delta +1 = próxima / R, -1 = anterior / Shift+R). O(1), não
        marca nada, não toca OCR/Pipeline B. Retorna {word,index,total} ou None se sem sessão."""
        with self._session_lock:
            if not self._session:
                return None
            word = self._session.go(delta)
            self.screen_reader.suggested_word = word
            self.screen_reader.suggestion_index = self._session.position
            self.screen_reader.suggestion_total = self._session.total
            return {"word": word, "index": self._session.position, "total": self._session.total}

    def reroll_next(self):
        return self.reroll(1)

    def reroll_prev(self):
        return self.reroll(-1)

    def get_word_from_payload(self, data):
        """Endpoint /api/word — busca palavra e opcionalmente digita."""
        params = WordSelectionParams(
            prompt=data.get("prompt", ""),
            lang=data.get("lang", self.word_manager.current_language),
            min_len=to_int(data.get("min_len", 1), 1),
            max_len=to_int(data.get("max_len", 46), 46),
            strategy=data.get("strategy", "random"),
            priority_letters=data.get("priority_letters", ""),
            exclude_letters=data.get("exclude_letters", ""),
            starts_with_letters=data.get("starts_with_letters", ""),
            finish_with_letters=data.get("finish_with_letters", ""),
            priority_min_len=int(data.get("priority_min_len", 1)),
            priority_max_len=int(data.get("priority_max_len", 46)),
            priority_sublist=data.get("priority_sublist", ""),
            prefix=data.get("prefix", ""),
            suffix=data.get("suffix", ""),
        )

        self.word_manager.set_recover_config(
            to_int(data.get("recover_target", 2), 2),
            data.get("recover_exclude", ""),
        )
        self.word_manager.current_language = params.lang

        word = self.word_manager.get_word(
            params.prompt, params.lang, params.min_len, params.max_len, params.strategy,
            priority_letters=params.priority_letters,
            exclude_letters=params.exclude_letters,
            starts_with_letters=params.starts_with_letters,
            finish_with_letters=params.finish_with_letters,
            priority_min_len=params.priority_min_len,
            priority_max_len=params.priority_max_len,
            priority_sublist=params.priority_sublist,
            prefix=params.prefix,
            suffix=params.suffix,
        )

        if word:
            self.word_manager.mark_used(word)
            if data.get("auto_type", False):
                self.screen_reader.last_word_typed = word
                self.typer.type_word(word, auto_tab=True)

        return word

    def reset_words(self):
        self.word_manager.reset_used()
        self._set_session(None)
        self.screen_reader.last_suggested_prompt = ""
        self.screen_reader.preview_prompt = ""
