# FILE_INDEX — Índice de Arquivos + Dívida Técnica

## Núcleo da aplicação
| Arquivo | Papel | Crítico? |
|---|---|---|
| `main.py` | Entry point Flask. | ⭐ |
| `application/app_factory.py` | DI / composition root. | ⭐ |
| `api/routes.py` | Rotas HTTP. | ⭐ |
| `word_manager.py` (raiz) | Seleção de palavra (lógica real). | ⭐⭐ |
| `screen_reader.py` (raiz) | OCR + visão + auto-play loop (lógica real). | ⭐⭐ |
| `typer.py` (raiz) | Digitação humanizada (lógica real). | ⭐⭐ |
| `application/word_service.py` | Orquestração prompt→palavra→digitação. | ⭐ |
| `application/autoplay_state_service.py` | Config + logs thread-safe. | ⭐ |
| `application/preset_service.py` | CRUD presets. | |
| `application/region_store.py` | Região calibrada + persistência. | |
| `domain/word_selection.py` | `WordSelectionParams`. | |
| `infrastructure/presets_repository.py` | Persistência JSON de presets (real). | |
| `shared/parsing.py` | Parsing defensivo. | ⭐ |
| `shared/security.py` | Auth opcional. | |

## Front-end
| `templates/index.html` | UI (3 abas + overlay). |
| `static/js/app.js` | Lógica do front (548 linhas). |
| `static/css/style.css` | Estilos. |

## Shims (re-export — NÃO colocar lógica)
- `application/word_manager.py` → `word_manager.WordManager`
- `infrastructure/ocr/screen_reader.py` → `screen_reader.ScreenReader`
- `infrastructure/input/typer.py` → `typer.Typer`
- `infrastructure/repositories/presets_repository.py` → `infrastructure.presets_repository.FilePresetRepository`

## Dados / config
- `wordlists/*.txt` — dicionários (Português ~248k é o maior; ver tamanhos abaixo).
- `tessdata/{por,eng}.traineddata` — modelos OCR (binários versionados).
- `presets.json` — presets salvos.
- `calibration_region.json` — região calibrada.
- `.gitignore`, `.idea/` (config JetBrains).
- `.artifacts/.../implementation_plan.artifact.md` — plano antigo de melhorias de OCR/UI.

## Scripts utilitários (raiz) — manutenção de wordlists (modo `print`, one-off)
| Script | Função |
|---|---|
| `download_wordlists.py` | Baixa/processa listas (FrequencyWords) p/ idiomas faltantes. |
| `clean_wordlists.py` | Remove palavras com chars inválidos (`, . - = ' "`). |
| `lowercase_wordlists.py` | Converte listas p/ minúsculas. |
| `normalize_wordlists.py` | Lowercase + remove acentos (NFKD→ASCII). |
| `process_words.py` | Strip + lowercase de um arquivo (CLI por arg). |
| `organize_lists.py` | Organiza/filtra listas (remove acentos, gentílicos). |
| `filter_gentiles.py` | Filtra gentílicos. |
| `check_words.py` | Heurística p/ detectar palavras provavelmente erradas em Português.txt. |
| `debug_typer.py` | Simulação do `Typer` com mocks (verificação manual). |

## scratch/ (rascunhos / one-off — candidatos a remoção)
`append_words.py`, `append_words_batch2..4.py`, `append_large_batch.py`, `clean_wordlist.py`,
`debug_tzc.py`, `three_letter_words.txt`. Scripts de append em lote já consumidos.

## Arquivos mortos / legado
| Arquivo | Situação |
|---|---|
| `overlay_manager.py` | Shim vazio (Tk removido). Manter só se algum import órfão existir; senão pode sumir. |
| `_check_line_out.txt`, `_np_names.txt` | Saídas/scratch de scripts (dados temporários versionados por engano). |
| `scratch/append_words_batch*.py` | Provavelmente já aplicados; sem uso recorrente. |

## Dívida técnica (resumo — ver KNOWN_ISSUES.md)
1. **Shims + lógica na raiz** acoplados ao CWD.
2. **Duplicação** de `presets_repository` (2 caminhos).
3. **OCR frágil** dependente de cores HSV fixas.
4. **Sem testes automatizados**.
5. **Scripts utilitários espalhados na raiz** (deveriam estar em `tools/`).
6. **Arquivos temporários versionados** (`_check_line_out.txt`, `_np_names.txt`).
7. **README desatualizado** (fala de janela vermelha Tk).
8. `get_word` é um método grande (>170 linhas) — candidato a refatoração por estratégia.

## Tamanhos das wordlists (linhas)
Português 247.918 · Polonês 49.405 · Dinamarquês 48.982 · Norueguês 48.956 · Russo 48.828 ·
jklm 31.036 · Inglês 11.351 · Espanhol 3.282 · Sueco 2.499 · Holandês 1.994 · Italiano 903 ·
Alemão 726 · Turco 468 · Português_palindromos 126.
