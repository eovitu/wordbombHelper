"""Resumo em memória de eventos confirmados durante uma partida.

Sugestões não entram neste serviço. A camada que sabe que uma palavra foi aceita,
rejeitada ou aprendida precisa registrar explicitamente o respectivo evento.
"""

from __future__ import annotations

import threading
import time
from typing import Callable


class MatchSummaryError(ValueError):
    """Dados inválidos para um evento confirmado da partida."""


class MatchSummary:
    """Acumula contagens e uma janela limitada dos eventos recentes.

    As contagens abrangem a partida inteira. Apenas ``events`` é limitado por
    ``max_events`` para impedir crescimento contínuo de memória em partidas longas.
    """

    def __init__(self, *, max_events: int = 200, clock: Callable[[], float] = time.time) -> None:
        if not isinstance(max_events, int) or isinstance(max_events, bool) or max_events <= 0:
            raise MatchSummaryError("max_events deve ser um inteiro positivo.")
        self._max_events = max_events
        self._clock = clock
        self._lock = threading.RLock()
        self._counts = {
            "confirmed_words": 0,
            "missing_prompts": 0,
            "rejections": 0,
            "learned_words": 0,
        }
        self._events: list[dict[str, object]] = []
        self._next_event_id = 1

    def record_confirmed_word(self, prompt: str, word: str, source: str) -> dict[str, object]:
        """Registra uma palavra efetivamente confirmada como jogada."""
        return self._record("confirmed_word", prompt=prompt, word=word, source=source)

    def record_missing_prompt(self, prompt: str) -> dict[str, object]:
        """Registra um prompt confirmado para o qual não houve palavra encontrada."""
        return self._record("missing_prompt", prompt=prompt)

    def record_rejection(self, prompt: str, word: str) -> dict[str, object]:
        """Registra uma rejeição explícita; isso não conta como palavra jogada."""
        return self._record("rejection", prompt=prompt, word=word)

    def record_learned_word(self, word: str, source: str) -> dict[str, object]:
        """Registra uma palavra aprendida de uma fonte confirmada, como o painel SOLVE."""
        return self._record("learned_word", word=word, source=source)

    def snapshot(self) -> dict[str, object]:
        """Retorna um snapshot independente e serializável por ``json.dumps``."""
        with self._lock:
            return {
                **self._counts,
                "event_count": sum(self._counts.values()),
                "retained_event_count": len(self._events),
                "events": [dict(event) for event in self._events],
            }

    def reset(self) -> dict[str, object]:
        """Limpa a partida e devolve o snapshot completo que existia antes do reset."""
        with self._lock:
            previous = self.snapshot()
            for key in self._counts:
                self._counts[key] = 0
            self._events.clear()
            self._next_event_id = 1
            return previous

    def _record(self, event_type: str, **fields: str) -> dict[str, object]:
        validated = {key: self._normalize(value, key) for key, value in fields.items()}
        with self._lock:
            event = {
                "id": self._next_event_id,
                "type": event_type,
                "timestamp": float(self._clock()),
                **validated,
            }
            self._next_event_id += 1
            self._events.append(event)
            if len(self._events) > self._max_events:
                del self._events[: len(self._events) - self._max_events]
            self._counts[self._count_key_for(event_type)] += 1
            return dict(event)

    @staticmethod
    def _count_key_for(event_type: str) -> str:
        return {
            "confirmed_word": "confirmed_words",
            "missing_prompt": "missing_prompts",
            "rejection": "rejections",
            "learned_word": "learned_words",
        }[event_type]

    @staticmethod
    def _normalize(value: str, field: str) -> str:
        if not isinstance(value, str):
            raise MatchSummaryError(f"{field} deve ser texto.")
        result = value.strip().casefold()
        if not result:
            raise MatchSummaryError(f"{field} não pode estar vazio.")
        if any(char.isspace() for char in result) or any(ord(char) < 32 for char in result):
            raise MatchSummaryError(f"{field} deve conter um único token sem espaços.")
        return result
