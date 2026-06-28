"""WordService — orquestra: prompt → busca palavra → digita (se auto_type ativo)."""
import logging

from domain.word_selection import WordSelectionParams
from shared.parsing import to_int

logger = logging.getLogger(__name__)


class WordService:
    def __init__(self, word_manager, typer, screen_reader, autoplay_state):
        self.word_manager = word_manager
        self.typer = typer
        self.screen_reader = screen_reader
        self.autoplay_state = autoplay_state
        self.on_word_found_callback = None

    def on_prompt_found(self, prompt_text):
        """Callback chamado pelo ScreenReader quando a sílaba é detectada."""
        if not prompt_text:
            self.screen_reader.suggested_word = ""
            if self.on_word_found_callback:
                self.on_word_found_callback("")
            return False

        self.autoplay_state.add_log(f"Prompt: '{prompt_text}'")
        if self.on_word_found_callback:
            self.on_word_found_callback("")

        config = self.autoplay_state.snapshot_config()
        if config.get("lang"):
            self.word_manager.current_language = config["lang"]

        self.word_manager.set_recover_config(
            int(config.get("recover_target", 2)),
            config.get("recover_exclude", ""),
        )

        word = self.word_manager.get_word(
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

        if not word:
            self.autoplay_state.add_log(f"Nenhuma palavra para '{prompt_text}'")
            if self.on_word_found_callback:
                self.on_word_found_callback("")
            return False

        self.word_manager.mark_used(word)
        self.screen_reader.suggested_word = word
        if self.on_word_found_callback:
            self.on_word_found_callback(word)

        self.autoplay_state.add_log(f"Match ready: '{word}'")

        if config.get("auto_type", False):
            self.autoplay_state.add_log(f"Typing: '{word}'")
            self.typer.type_word(word, auto_tab=False)
            self.screen_reader.last_word_typed = word
            self.typer.done_event.wait(timeout=3)

        return True

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
        self.screen_reader.suggested_word = ""
        self.screen_reader.last_suggested_prompt = ""
        self.screen_reader.preview_prompt = ""
