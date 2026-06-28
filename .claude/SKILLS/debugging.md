# SKILL — Debugging

## Objetivo
Diagnosticar problemas comuns rapidamente.

## Logs
- stdlib `logging` (nível INFO em `main.py`; `werkzeug` em WARNING).
- Logs do auto-play também vão para o front (`AutoplayStateService.add_log` → `/api/autoplay/status`).
- Suba o nível p/ DEBUG temporariamente p/ ver OCR raw (`logger.debug("OCR RAW: ...")`).

## Sintomas → causas prováveis
| Sintoma | Verifique |
|---|---|
| "No word found" | idioma errado; filtros muito restritivos; `used_words` cheio (Reset). |
| Auto-play não detecta turno | região mal calibrada; cores HSV não batem; thresholds; ver SKILL ocr. |
| Lê sílaba errada | confiança baixa; ghost-prompt; sílaba fora de 2–4 chars; `tess_lang`. |
| Digita na janela errada | foco/ordem de Alt+Tab; no auto-play o jogo precisa estar em foco. |
| Digitação não cancela | hook da tecla Insert; `_abort`; FAILSAFE (mouse no canto). |
| Tesseract não encontrado | caminho em `screen_reader.py`; instalação no SO. |
| ImportError nos shims | rodou de fora da raiz (CWD); rode da raiz. |
| Presets não salvam | permissão de escrita em `presets.json`; caminho (CWD). |

## Ferramentas
- `python debug_typer.py` — lógica de digitação.
- `screen_reader.save_debug_screenshots = True` → `debug_screenshots/last_processed.png`.
- `tools/ocr_extract.py` — testar OCR em imagem.
- `tools/project_stats.py` / `tools/dependency_map.py` — visão do repo.

## Anti-patterns
- ❌ Debugar OCR direto no jogo sem screenshots.
- ❌ Mudar vários parâmetros de uma vez.
- ❌ Ignorar o CWD ao ver ImportError/arquivo-não-encontrado.
