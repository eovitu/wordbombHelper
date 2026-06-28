# SKILL — Performance

## Objetivo
Manter o auto-play responsivo e a busca de palavra rápida mesmo com listas grandes.

## Pontos quentes
- **Listas grandes** (Português 248k): `get_word` usa `len_map` (índice por comprimento) e listas
  pré-lowercase. Evite varrer a lista inteira sem filtro de comprimento.
- **OCR loop** (`_watch_loop`): roda continuamente. Otimizações já presentes:
  - **Frame hash cache**: pula pipeline se a tela é byte-idêntica.
  - **Early-exit por cor**: se quase não há cor de botão, retorna cedo (sem OCR).
  - Máscara HSV na imagem pequena ANTES do upscale.
  - `INTER_NEAREST` no resize quando a largura já é decente.
  - Sleeps curtos (0.1s) quando não é a vez; maiores quando estável.
- **reset_used()** recarrega listas do disco — custoso; só no Reset/nova partida.

## Boas práticas
- Não faça OCR fora do necessário (respeite os early-exits e o cache).
- Em filtros de palavra, prefira operar sobre índices/`lower` já calculados.
- Evite alocar arrays grandes por frame; reuse o `mss` (já é mantido aberto no loop).

## Anti-patterns
- ❌ Remover o frame cache ou os early-exits "para simplificar".
- ❌ Recarregar wordlists a cada request.
- ❌ Polling do front mais agressivo que 250ms sem necessidade.

## Checklist
- [ ] Filtro de comprimento usa `len_map`? [ ] OCR mantém cache/early-exit?
- [ ] Sem recarregar listas por request? [ ] Sleeps coerentes no loop?
