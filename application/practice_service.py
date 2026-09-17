"""Prática offline baseada nas palavras já ativas no ``WordManager``.

O serviço não usa ``get_word`` porque esse método considera palavras usadas e pode
alterar a estratégia do jogo. Ele lê a lista ativa para montar rodadas independentes.
"""

from __future__ import annotations

from dataclasses import dataclass
import random
import threading
import unicodedata


class PracticeError(Exception):
    """Erro de contrato do modo de prática."""


class NoPracticeWordsError(PracticeError):
    """O idioma não tem palavras válidas para gerar uma rodada."""


@dataclass(frozen=True)
class PracticeRound:
    language: str
    prompt: str
    answer: str


@dataclass(frozen=True)
class PracticeHint:
    """Uma dica independente: ``length``, ``first_letter`` ou ``answer``."""

    mode: str
    value: str | int


@dataclass(frozen=True)
class PracticeEvaluation:
    correct: bool
    reason: str
    word: str | None
    elapsed_seconds: float | None


@dataclass(frozen=True)
class PromptStats:
    attempts: int
    errors: int
    slow_responses: int


class PracticeService:
    """Gera rodadas, valida respostas e prioriza prompts que exigiram mais prática.

    ``word_manager`` é deliberadamente uma dependência de leitura. O serviço nunca
    chama ``mark_used``, ``reject_word`` ou ``resolve_played_ocr``.
    """

    HINT_LENGTH = "length"
    HINT_FIRST_LETTER = "first_letter"
    HINT_ANSWER = "answer"
    _HINTS = {HINT_LENGTH, HINT_FIRST_LETTER, HINT_ANSWER}

    def __init__(
        self,
        word_manager,
        *,
        random_source: random.Random | None = None,
        slow_response_seconds: float = 5.0,
    ) -> None:
        if slow_response_seconds <= 0:
            raise ValueError("slow_response_seconds must be positive")
        self._word_manager = word_manager
        self._random = random_source or random.Random()
        self._slow_response_seconds = float(slow_response_seconds)
        self._lock = threading.RLock()
        self._history: dict[tuple[str, str], PromptStats] = {}
        self._prompt_cache: dict[str, tuple[int, int, tuple[str, ...]]] = {}

    def generate_round(
        self,
        language: str,
        *,
        min_prompt_length: int = 2,
        max_prompt_length: int = 3,
    ) -> PracticeRound:
        """Cria uma rodada cujo prompt aparece na resposta e na lista ativa.

        O serviço escolhe entre prompts de dois ou três caracteres por padrão. O
        histórico aumenta o peso de prompts com erros e respostas lentas, mas todos os
        prompts válidos continuam elegíveis.
        """
        if not isinstance(min_prompt_length, int) or not isinstance(max_prompt_length, int):
            raise PracticeError("Os tamanhos do prompt devem ser inteiros.")
        if min_prompt_length < 1 or max_prompt_length < min_prompt_length:
            raise PracticeError("O intervalo de tamanho do prompt é inválido.")
        resolved_language, words, fingerprint = self._active_words(language)
        prompts = self._prompts_for(resolved_language, words, fingerprint, min_prompt_length, max_prompt_length)
        if not prompts:
            raise NoPracticeWordsError("Não há palavras suficientes para gerar prompts nesse idioma.")
        with self._lock:
            weights = [self._weight_for(resolved_language, prompt) for prompt in prompts]
            prompt = self._random.choices(prompts, weights=weights, k=1)[0]
        candidates = [word for word in words if prompt in self._canonical(word)]
        if not candidates:  # a lista mudou após a criação do cache; tenta novamente de forma segura.
            cache_key = f"{resolved_language}\0{min_prompt_length}\0{max_prompt_length}"
            with self._lock:
                self._prompt_cache.pop(cache_key, None)
            return self.generate_round(
                resolved_language,
                min_prompt_length=min_prompt_length,
                max_prompt_length=max_prompt_length,
            )
        return PracticeRound(resolved_language, prompt, self._random.choice(candidates))

    def evaluate(
        self,
        round_: PracticeRound,
        typed_answer: str,
        *,
        elapsed_seconds: float | None = None,
    ) -> PracticeEvaluation:
        """Valida uma resposta sem tocar no estado de jogo do ``WordManager``.

        Uma resposta correta pode ser qualquer palavra ativa que contenha o prompt;
        ela não precisa coincidir com a resposta sorteada para a dica. ``elapsed_seconds``
        é opcional e, se informado, alimenta a adaptação de dificuldade.
        """
        self._validate_round(round_)
        elapsed = self._validate_elapsed(elapsed_seconds)
        language, words, _ = self._active_words(round_.language)
        prompt = self._canonical(round_.prompt)
        typed = self._canonical(typed_answer)
        canonical_words = {self._canonical(word): word for word in words}

        if not typed:
            result = PracticeEvaluation(False, "empty_answer", None, elapsed)
        elif prompt not in typed:
            result = PracticeEvaluation(False, "missing_prompt", None, elapsed)
        elif typed not in canonical_words:
            result = PracticeEvaluation(False, "not_in_dictionary", None, elapsed)
        else:
            result = PracticeEvaluation(True, "correct", canonical_words[typed], elapsed)
        self._record_result(language, prompt, result)
        return result

    def hint(self, round_: PracticeRound, mode: str) -> PracticeHint:
        """Fornece uma dica pontual: tamanho, primeira letra ou resposta completa."""
        self._validate_round(round_)
        if mode not in self._HINTS:
            raise PracticeError("Modo de dica inválido.")
        if mode == self.HINT_LENGTH:
            return PracticeHint(mode, len(round_.answer))
        if mode == self.HINT_FIRST_LETTER:
            return PracticeHint(mode, round_.answer[0])
        return PracticeHint(mode, round_.answer)

    def get_prompt_stats(self, language: str, prompt: str) -> PromptStats:
        """Expõe o histórico em memória para a UI, sem persistência."""
        language, _, _ = self._active_words(language)
        key = (language, self._canonical(prompt))
        with self._lock:
            return self._history.get(key, PromptStats(0, 0, 0))

    def _active_words(self, language: str) -> tuple[str, tuple[str, ...], tuple[int, int]]:
        if not isinstance(language, str) or not language.strip():
            raise PracticeError("Informe um idioma.")
        manager = self._word_manager
        # WordManager protege tanto o carregamento lazy quanto os mapas em memória com
        # RLock. Não alteramos used_words, rejected_words ou índices de OCR.
        with manager._lock:
            resolved = manager._resolve_language_name(language)
            if resolved not in manager.wordlists:
                manager._load_language_unsafe(resolved)
            data = manager.wordlists.get(resolved)
            if not data:
                raise NoPracticeWordsError("Idioma sem wordlist ativa.")
            raw_words = data.get("full", ())
            words = tuple(raw_words)
            fingerprint = (id(raw_words), len(raw_words))
        valid_words = tuple(word for word in words if isinstance(word, str) and self._canonical(word))
        if not valid_words:
            raise NoPracticeWordsError("Idioma sem palavras válidas para prática.")
        return resolved, valid_words, fingerprint

    def _prompts_for(
        self, language: str, words: tuple[str, ...], fingerprint: tuple[int, int], min_length: int, max_length: int
    ) -> tuple[str, ...]:
        # A wordlist é mantida como lista pelo WordManager; seu id e tamanho permitem
        # invalidar o índice caso a futura integração substitua ou acrescente palavras.
        cache_key = f"{language}\0{min_length}\0{max_length}"
        with self._lock:
            cached = self._prompt_cache.get(cache_key)
            if cached and cached[:2] == fingerprint:
                return cached[2]
        prompts: set[str] = set()
        for word in words:
            canonical = self._canonical(word)
            for length in range(min_length, max_length + 1):
                for start in range(0, len(canonical) - length + 1):
                    prompts.add(canonical[start : start + length])
        result = tuple(sorted(prompts))
        with self._lock:
            self._prompt_cache[cache_key] = (fingerprint[0], fingerprint[1], result)
        return result

    def _weight_for(self, language: str, prompt: str) -> int:
        stats = self._history.get((language, prompt), PromptStats(0, 0, 0))
        return 1 + stats.errors * 3 + stats.slow_responses

    def _record_result(self, language: str, prompt: str, result: PracticeEvaluation) -> None:
        key = (language, prompt)
        with self._lock:
            current = self._history.get(key, PromptStats(0, 0, 0))
            self._history[key] = PromptStats(
                attempts=current.attempts + 1,
                errors=current.errors + (0 if result.correct else 1),
                slow_responses=current.slow_responses
                + (1 if result.correct and result.elapsed_seconds is not None
                   and result.elapsed_seconds >= self._slow_response_seconds else 0),
            )

    @staticmethod
    def _canonical(value: str | None) -> str:
        if not isinstance(value, str):
            return ""
        return unicodedata.normalize("NFC", value).strip().casefold()

    @staticmethod
    def _validate_round(round_: PracticeRound) -> None:
        if not isinstance(round_, PracticeRound) or not round_.language or not round_.prompt or not round_.answer:
            raise PracticeError("Rodada de prática inválida.")

    @staticmethod
    def _validate_elapsed(elapsed_seconds: float | None) -> float | None:
        if elapsed_seconds is None:
            return None
        if not isinstance(elapsed_seconds, (int, float)) or isinstance(elapsed_seconds, bool) or elapsed_seconds < 0:
            raise PracticeError("O tempo de resposta deve ser um número não negativo.")
        return float(elapsed_seconds)
