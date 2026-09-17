"""Seleção adaptativa pura para uma futura medida confiável de pressão da bomba.

Contrato:
* ``select_adaptive_candidate(candidates, pressure, state)`` não altera a lista nem o
  estado recebido e devolve ``AdaptiveSelection``.
* Sem ``pressure`` a escolha original (primeiro candidato) é preservada e o estado não
  avança. Isso evita inferir urgência de sinais de OCR ou de tempo não validados.
* Com pressão baixa, a política alterna candidato longo (desafio) e curto (rápido).
  Com pressão média ou alta, usa o mais curto; comprimento é a única aproximação de
  facilidade disponível neste módulo.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class AdaptiveStrategyState:
    """Estado injetável que torna a alternância reproduzível entre chamadas."""

    measured_decisions: int = 0


@dataclass(frozen=True)
class AdaptiveSelection:
    """Decisão pura e o estado a passar para a próxima chamada."""

    candidate: str | None
    mode: str
    state: AdaptiveStrategyState


def _validate_pressure(pressure: float | None) -> float | None:
    if pressure is None:
        return None
    if isinstance(pressure, bool):
        raise ValueError("pressure deve ser um número entre 0 e 1.")
    try:
        value = float(pressure)
    except (TypeError, ValueError) as exc:
        raise ValueError("pressure deve ser um número entre 0 e 1.") from exc
    if not 0.0 <= value <= 1.0:
        raise ValueError("pressure deve estar entre 0 e 1.")
    return value


def _valid_candidates(candidates: Sequence[str]) -> list[str]:
    if isinstance(candidates, (str, bytes)):
        raise ValueError("candidates deve ser uma sequência de palavras.")
    try:
        values = list(candidates)
    except TypeError as exc:
        raise ValueError("candidates deve ser uma sequência de palavras.") from exc
    if any(not isinstance(candidate, str) or not candidate for candidate in values):
        raise ValueError("candidates deve conter apenas palavras não vazias.")
    return values


def _shortest(candidates: list[str]) -> str:
    return min(enumerate(candidates), key=lambda item: (len(item[1]), item[0]))[1]


def _longest(candidates: list[str]) -> str:
    return max(enumerate(candidates), key=lambda item: (len(item[1]), -item[0]))[1]


def select_adaptive_candidate(
    candidates: Sequence[str],
    pressure: float | None,
    state: AdaptiveStrategyState = AdaptiveStrategyState(),
) -> AdaptiveSelection:
    """Escolhe uma sugestão usando apenas pressão medida e estado injetado.

    ``pressure`` é normalizada em ``0..1`` pelo fornecedor futuro: abaixo de ``0.35``
    alterna desafio/rápida; a partir desse ponto escolhe curta, e em ``>= 0.75`` marca
    explicitamente a decisão como urgência alta. Empates mantêm a ordem de candidatos.
    """
    if not isinstance(state, AdaptiveStrategyState) or state.measured_decisions < 0:
        raise ValueError("state adaptativo inválido.")
    values = _valid_candidates(candidates)
    if not values:
        return AdaptiveSelection(None, "empty", state)

    measured_pressure = _validate_pressure(pressure)
    original = values[0]
    if measured_pressure is None:
        return AdaptiveSelection(original, "unmeasured", state)

    next_state = AdaptiveStrategyState(measured_decisions=state.measured_decisions + 1)
    if measured_pressure < 0.35:
        challenge_turn = state.measured_decisions % 2 == 0
        return AdaptiveSelection(
            _longest(values) if challenge_turn else _shortest(values),
            "challenge" if challenge_turn else "quick",
            next_state,
        )
    if measured_pressure >= 0.75:
        return AdaptiveSelection(_shortest(values), "high_pressure_quick", next_state)
    return AdaptiveSelection(_shortest(values), "quick", next_state)


class AdaptiveStrategy:
    """Adaptador de estado opcional para consumidores que não querem guardá-lo fora."""

    def __init__(self, state: AdaptiveStrategyState | None = None) -> None:
        self.state = state or AdaptiveStrategyState()

    def select(self, candidates: Sequence[str], pressure: float | None) -> AdaptiveSelection:
        selection = select_adaptive_candidate(candidates, pressure, self.state)
        self.state = selection.state
        return selection
