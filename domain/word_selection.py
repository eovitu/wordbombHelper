from dataclasses import dataclass


@dataclass(frozen=True)
class WordSelectionParams:
    prompt: str
    lang: str
    min_len: int
    max_len: int
    strategy: str
    priority_letters: str
    exclude_letters: str
    starts_with_letters: str
    finish_with_letters: str
    priority_min_len: int
    priority_max_len: int
    priority_sublist: str
    prefix: str
    suffix: str
