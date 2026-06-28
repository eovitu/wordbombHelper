# SKILL — Testes

## Objetivo
Verificar mudanças num projeto **sem suíte automatizada**.

## Estado atual
- Sem `pytest`/CI. Verificação = `debug_typer.py` + testes manuais (OCR/auto-play) + bom senso.

## Como verificar hoje
- **Typer**: `python debug_typer.py` (mocks de teclado/tempo). Fixe `random.seed` p/ repetibilidade.
- **WordManager**: rode um REPL: `from word_manager import WordManager; wm=WordManager(); wm.get_word('nfl','Português')`.
- **Parsing**: funções puras em `shared/parsing.py` — fáceis de testar isoladamente.
- **OCR**: manual com a tela do jogo + `tools/ocr_extract.py` em imagens; `save_debug_screenshots`.
- **API**: `curl`/navegador contra `127.0.0.1:5000`.

## Se for introduzir testes (recomendado)
- Adicione `pytest` (dev-only). Estrutura sugerida: `tests/test_parsing.py`, `tests/test_word_manager.py`,
  `tests/test_preset_service.py`, `tests/test_autoplay_state.py`.
- Use uma wordlist fixture pequena (`tests/fixtures/Teste.txt`) e `WordManager(wordlist_dir=...)`.
- Mocke `keyboard`/`pyautogui` para testar `Typer` sem efeitos reais (como `debug_typer.py` faz).
- Não dependa de Tesseract/tela em testes unitários (isole o pipeline puro se possível).

## Anti-patterns
- ❌ Testes que movem mouse/teclado de verdade.
- ❌ Testes que exigem o jogo aberto.
- ❌ Depender de `random` sem seed.

## Checklist
- [ ] Mudança em `Typer`? rodou `debug_typer.py`.
- [ ] Mudança em seleção? testou `get_word` com casos.
- [ ] Mudança em parsing? cobriu defaults/erros.
- [ ] Mudança em OCR? verificou manualmente + screenshot.
