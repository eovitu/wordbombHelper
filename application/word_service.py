import logging

from domain.word_selection import WordSelectionParams
from shared.parsing import to_float, to_int

logger = logging.getLogger(__name__)


class WordService:
    def __init__(self, word_manager, typer, screen_reader, autoplay_state):
        self.word_manager = word_manager
        self.typer = typer
        self.screen_reader = screen_reader
        self.autoplay_state = autoplay_state
        self.on_word_found_callback = None

    def on_prompt_found(self, prompt_text):
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

        lang = config["lang"]
        min_len = config["min_len"]
        max_len = config["max_len"]
        strategy = config["strategy"]
        priority_letters = config.get("priority_letters", "")
        exclude_letters = config.get("exclude_letters", "")
        starts_with_letters = config.get("starts_with_letters", "")
        finish_with_letters = config.get("finish_with_letters", "")
        priority_min_len = int(config.get("priority_min_len", 1))
        priority_max_len = int(config.get("priority_max_len", 46))
        wpm = config["wpm"]
        error_rate = config["error_rate"]

        rec_target = int(config.get("recover_target", 2))
        rec_exclude = config.get("recover_exclude", "")
        self.word_manager.set_recover_config(rec_target, rec_exclude)

        word = self.word_manager.get_word(
            prompt_text,
            lang,
            min_len,
            max_len,
            strategy,
            priority_letters=priority_letters,
            exclude_letters=exclude_letters,
            starts_with_letters=starts_with_letters,
            finish_with_letters=finish_with_letters,
            priority_min_len=priority_min_len,
            priority_max_len=priority_max_len,
            priority_sublist=config.get("priority_sublist", ""),
        )
        if word:
            self.word_manager.mark_used(word)
            self.screen_reader.suggested_word = word
            if self.on_word_found_callback:
                self.on_word_found_callback(word)
            
            if not config.get("auto_type", True):
                self.autoplay_state.add_log(f"Match ready: '{word}'")
                return True

            self.autoplay_state.add_log(f"Typing: '{word}'")

            self.typer.type_word(
                word,
                wpm,
                error_rate,
                auto_tab=False,
                hesitation_prob=config["hesitation_prob"],
                retry_rate=config["retry_rate"],
                late_error_rate=config["late_error_rate"],
                max_typos=config["max_typos"],
                max_late_errors=config["max_late_errors"],
                delayed_type=config.get("delayed_type", False),
                add_period_prob=float(config.get("add_period_prob", 0.0)),
            )
            self.screen_reader.last_word_typed = word
            self.typer.done_event.wait(timeout=5)
            return True

        self.autoplay_state.add_log(f"No word found for '{prompt_text}'")
        if self.on_word_found_callback:
            self.on_word_found_callback("")
        return False

    def get_word_from_payload(self, data):
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

        auto_type = data.get("auto_type", False)
        wpm = to_int(data.get("wpm", 60), 60)
        error_rate = to_float(data.get("error_rate", 0), 0.0)

        rec_target = to_int(data.get("recover_target", 2), 2)
        rec_exclude = data.get("recover_exclude", "")
        self.word_manager.set_recover_config(rec_target, rec_exclude)

        self.word_manager.current_language = params.lang

        word = self.word_manager.get_word(
            params.prompt,
            params.lang,
            params.min_len,
            params.max_len,
            params.strategy,
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
            if auto_type:
                self.screen_reader.last_word_typed = word

                autoplay_cfg = self.autoplay_state.snapshot_config()
                h_prob = to_float(data.get("hesitation_prob", autoplay_cfg["hesitation_prob"]), autoplay_cfg["hesitation_prob"])
                r_rate = to_float(data.get("retry_rate", autoplay_cfg["retry_rate"]), autoplay_cfg["retry_rate"])
                l_rate = to_float(data.get("late_error_rate", autoplay_cfg["late_error_rate"]), autoplay_cfg["late_error_rate"])

                self.typer.type_word(
                    word,
                    wpm,
                    error_rate,
                    auto_tab=True,
                    hesitation_prob=h_prob,
                    retry_rate=r_rate,
                    late_error_rate=l_rate,
                    max_typos=to_int(data.get("max_typos", autoplay_cfg["max_typos"]), autoplay_cfg["max_typos"]),
                    max_late_errors=to_int(data.get("max_late_errors", autoplay_cfg["max_late_errors"]), autoplay_cfg["max_late_errors"]),
                    return_tab=True,
                    delayed_type=data.get("delayed_type", autoplay_cfg.get("delayed_type", False)),
                    add_period_prob=to_float(
                        data.get("add_period_prob", autoplay_cfg.get("add_period_prob", 0.0)),
                        autoplay_cfg.get("add_period_prob", 0.0),
                    ),
                )

        return word

    def reset_words(self):
        self.word_manager.reset_used()
        self.screen_reader.suggested_word = ""
        self.screen_reader.last_suggested_prompt = ""
        self.screen_reader.preview_prompt = ""
