# SKILL — Automação de Digitação (humanização)

## Objetivo
Entender/ajustar `typer.py` (`Typer`): digitação que parece humana para evitar detecção.

## Quando usar
Ajustar realismo/velocidade, corrigir digitação na janela errada, adicionar comportamento.

## Conceitos
- **WPM → delay**: `(wpm*5)/60` chars/s. `wpm>=180` = **turbo** (pula pausas).
- **Drift/bursts**: modulação contínua de velocidade + rajadas de 2–5 chars.
- **Pausas contextuais**: letras difíceis `qwzxkyh`, antes de maiúscula/`'_`, clusters de consoantes.
- **Typos** (`error_rate`, `max_typos`): QWERTY adjacente; 70% fat-finger, 30% substituição.
- **Late errors** (`late_error_rate`, `max_late_errors`): erra, segue, limpa (Ctrl+A+Backspace), redigita.
- **Full retry** (`retry_rate`): palavra inteira errada → Enter → limpa → redigita.
- **Delayed type**: spam de ruído + Enter por ~1s, depois digita devagar.
- **Alt+Tab**: `auto_tab` (entra no jogo), `return_tab` (volta). Auto-play usa `auto_tab=False`.
- **Abort**: tecla **Insert** (hook) e `pyautogui.FAILSAFE`.
- **Concorrência**: `Lock` não-bloqueante (call duplicada ignorada) + `done_event`.

## Boas práticas
- Teste com `python debug_typer.py` (mocks de teclado/tempo) — NÃO mexe no teclado real.
- Para repetibilidade ao debugar, fixe `random.seed(...)` temporariamente.
- Mantenha checagens de `self._abort` nos loops longos.
- Cuidado: `keyboard.write` falha com certos caracteres especiais (por isso QWERTY_MAP foi reduzido).

## Anti-patterns
- ❌ Testar direto no jogo sem `debug_typer.py`.
- ❌ Remover checagem de `_abort` (perde o cancelamento por Insert).
- ❌ Bloquear na thread de digitação esperando `done_event` sem timeout.

## Checklist
- [ ] Rodou `debug_typer.py`? [ ] `_abort` respeitado? [ ] WPM/turbo coerentes?
- [ ] Alt+Tab correto para o modo (manual vs auto)? [ ] Atualizou BUSINESS_RULES se mudou comportamento?
