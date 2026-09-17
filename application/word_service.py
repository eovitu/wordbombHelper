"""WordService — orquestra: prompt → busca palavra → digita (se auto_type ativo)."""
import logging
import threading

from domain.word_selection import WordSelectionParams
from shared.parsing import to_int

logger = logging.getLogger(__name__)


class SuggestionSession:
    """Lista de sugestões do prompt atual, calculada UMA vez. A navegação (Reroll) só move
    um índice — não refaz busca, não marca nada. Índice 0 = escolha do solver."""
    __slots__ = ("prompt", "candidates", "index", "short_seen")

    def __init__(self, prompt, candidates):
        self.prompt = prompt
        self.candidates = candidates
        self.index = 0
        self.short_seen = {0}

    def current(self):
        return self.candidates[self.index] if self.candidates else ""

    def go(self, delta):
        """Move o índice (clamp nas pontas — sem wraparound). Retorna a palavra atual."""
        if not self.candidates:
            return ""
        self.index = max(0, min(len(self.candidates) - 1, self.index + delta))
        return self.candidates[self.index]

    def go_short(self):
        """Choose the shortest alternative that short reroll has not shown yet."""
        choices = (i for i in range(len(self.candidates))
                   if i != self.index and i not in self.short_seen)
        index = min(choices, key=lambda i: (len(self.candidates[i]), i), default=None)
        if index is not None:
            self.index = index
            self.short_seen.add(index)
        return self.current()

    @property
    def total(self):
        return len(self.candidates)

    @property
    def position(self):
        return self.index + 1 if self.candidates else 0


class WordService:
    def __init__(self, word_manager, typer, screen_reader, autoplay_state,
                 missing_prompts=None, match_summary=None):
        self.word_manager = word_manager
        self.typer = typer
        self.screen_reader = screen_reader
        self.autoplay_state = autoplay_state
        self.missing_prompts = missing_prompts  # registro de prompts sem palavra (manutenção)
        self.match_summary = match_summary
        self.last_summary = None
        self.reset_notice = ""
        self.action_notice = ""
        self.on_word_found_callback = None
        # Sessão de sugestões do prompt atual (feature Reroll). Recriada a cada novo prompt.
        self._session = None
        self._session_lock = threading.Lock()
        self._accepted_word = None

    def on_prompt_found(self, prompt_text):
        """Callback chamado pelo ScreenReader quando a sílaba é detectada.
        Cria uma SuggestionSession nova (descarta a navegação do prompt anterior)."""
        if not prompt_text:
            self.finish_turn()
            return False

        self.action_notice = ""

        with self._session_lock:
            previous_prompt = self._session.prompt if self._session else None
        if previous_prompt == prompt_text:
            # Uma tentativa vermelha mantém o prompt: tente a próxima sugestão
            # sem apagar a anterior do dicionário nem reiniciar a sessão.
            with self._session_lock:
                if self._session.index >= self._session.total - 1:
                    return False
            result = self.reroll_next()
            if not result:
                return False
            if self.autoplay_state.snapshot_config().get("auto_type", False):
                self.typer.type_word(result["word"], auto_tab=False)
                self.screen_reader.last_word_typed = result["word"]
                self.typer.done_event.wait(timeout=3)
            return True
        elif previous_prompt:
            self.finish_turn()

        self.autoplay_state.add_log(f"Prompt: '{prompt_text}'")

        config = self.autoplay_state.snapshot_config()
        if config.get("lang"):
            self.word_manager.current_language = config["lang"]

        self.word_manager.configure_recover(
            config.get("recover_mode", "casual"), config.get("recover_exclude", ""))

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
            if self.match_summary:
                self.match_summary.record_missing_prompt(prompt_text)
            # Manutenção do dicionário: prompt já confirmado pelo pipeline, mas sem palavra.
            if self.missing_prompts:
                self.missing_prompts.record(prompt_text)
            self._set_session(None)
            return False

        primary = candidates[0]
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
            self._accepted_word = None
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

    def reroll_short(self):
        with self._session_lock:
            if not self._session:
                return None
            word = self._session.go_short()
            self.screen_reader.suggested_word = word
            self.screen_reader.suggestion_index = self._session.position
            return {"word": word, "index": self._session.position,
                    "total": self._session.total}

    def observe_accepted_word(self, word):
        """Record a new green SOLVE word only if it belongs to this prompt."""
        normalized = self.word_manager.normalize_token(word)
        with self._session_lock:
            session = self._session
            prompt = self.word_manager.normalize_token(session.prompt) if session else ""
            if session and prompt and prompt in normalized and self._accepted_word is None:
                self._accepted_word = word
                return True
        return False

    def finish_turn(self):
        """Only a green SOLVE word confirms this turn; disappearance may be an explosion."""
        with self._session_lock:
            session = self._session
            accepted = self._accepted_word
            # Feche a janela de atribuição atomicamente: um scan atrasado não
            # pode anexar a palavra do próximo jogador ao turno encerrado.
            self._session = None
            self._accepted_word = None
            self.screen_reader.suggested_word = ""
            self.screen_reader.suggestion_index = 0
            self.screen_reader.suggestion_total = 0
        if session:
            if accepted:
                self.word_manager.confirm_own_word(accepted)
                self.autoplay_state.add_log(f"Palavra confirmada no SOLVE: '{accepted}'")
            else:
                self.action_notice = "Turno sem palavra verde confirmada; Recover preservado."
                self.autoplay_state.add_log("Turno sem confirmação no SOLVE; sugestão preservada.")
            if accepted and self.match_summary:
                self.match_summary.record_confirmed_word(
                    session.prompt, accepted, "solve_panel")

    def reject_current(self):
        """Exclude the displayed word from this match without advancing Recover."""
        with self._session_lock:
            if not self._session:
                return None
            rejected = self._session.current()
            self._session.candidates.pop(self._session.index)
            if not self._session.candidates:
                self._session = None
                self.screen_reader.suggested_word = ""
                self.screen_reader.suggestion_index = 0
                self.screen_reader.suggestion_total = 0
                result = {"word": "", "index": 0, "total": 0, "rejected": rejected}
            else:
                self._session.index = min(self._session.index, len(self._session.candidates) - 1)
                self._session.short_seen = {self._session.index}
                self.screen_reader.suggested_word = self._session.current()
                self.screen_reader.suggestion_index = self._session.position
                self.screen_reader.suggestion_total = self._session.total
                result = {"word": self._session.current(), "index": self._session.position,
                          "total": self._session.total, "rejected": rejected}
        self.word_manager.reject_word(rejected)
        self.action_notice = f"{rejected.upper()} foi removida do dicionário."
        self.autoplay_state.add_log(f"Palavra removida do dicionário: '{rejected}'")
        if self.match_summary:
            self.match_summary.record_rejection(self.screen_reader.preview_prompt, rejected)
        return result

    def correct_prompt(self, prompt):
        """Discard an OCR suggestion and search the user-confirmed prompt."""
        prompt = (prompt or "").strip().lower()
        if not 2 <= len(prompt) <= 6 or not all(c.isalpha() or c in "-'" for c in prompt):
            raise ValueError("Prompt inválido")
        self._set_session(None)
        self.screen_reader.override_prompt(prompt)
        self.on_prompt_found(prompt)
        with self._session_lock:
            if not self._session:
                return {"word": "", "index": 0, "total": 0}
            return {"word": self._session.current(), "index": self._session.position,
                    "total": self._session.total}

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

        self.word_manager.configure_recover(
            data.get("recover_mode", "casual"), data.get("recover_exclude", ""))
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
        if self.match_summary:
            self.last_summary = self.match_summary.reset()
        self.reset_notice = "Partida reiniciada"
        self.action_notice = ""
        self.word_manager.reset_used()
        self._set_session(None)
        self.screen_reader.last_suggested_prompt = ""
        self.screen_reader.preview_prompt = ""
