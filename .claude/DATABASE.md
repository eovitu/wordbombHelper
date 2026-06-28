# DATABASE — Estado e Persistência

**Não há banco de dados.** O estado é em memória (durante a execução) + alguns arquivos JSON/TXT.

## Estado em memória (perde ao fechar)
| Onde | O quê |
|---|---|
| `WordManager.wordlists` / `.sublists` | Listas carregadas (lazy) com índice por comprimento. |
| `WordManager.used_words` (set) | Palavras já usadas na partida atual. |
| `WordManager.letter_targets` | Metas de cobertura de letras (estratégia `recover`). |
| `WordManager.current_language` / `current_alpha_char` | Idioma atual / posição no ciclo `alpha`. |
| `AutoplayStateService.config` (dict) | Config compartilhada (idioma, estratégia, WPM, filtros, taxas, auto_type...). |
| `AutoplayStateService.logs` (lista, máx 50) | Logs do auto-play exibidos no front. |
| `ScreenReader.*` | turn/prompt region, status, streaks, cache de frame, sílaba/preview, última palavra digitada. |

## Persistência em disco
| Arquivo | Conteúdo | Escrito por |
|---|---|---|
| [`presets.json`](../presets.json) | Mapa `nome → config`. Presets nomeados (ver exemplos no arquivo). | `FilePresetRepository.save` via `PresetService`. |
| [`calibration_region.json`](../calibration_region.json) | Região calibrada `{x1,y1,width,height}`. | `RegionStore.set_region`. Carregado no boot. |
| [`wordlists/*.txt`](../wordlists/) | Dicionários por idioma (1 palavra/linha, minúsculas). | Mantidos por scripts utilitários (ver FILE_INDEX). |
| `debug_screenshots/` (gitignored) | Imagens de OCR processado, se `ScreenReader.save_debug_screenshots=True`. | `ScreenReader`. |

## Schema da config (campos)
`lang, min_len, max_len, strategy, wpm, error_rate, hesitation_prob, retry_rate, late_error_rate,
max_typos, max_late_errors, priority_min_len, priority_max_len, priority_letters, exclude_letters,
starts_with_letters, finish_with_letters, recover_target, recover_exclude, priority_sublist,
delayed_type, add_period_prob, auto_type`. Defaults em `AutoplayStateService.__init__`.

## Schema da região
`{ "x1": int, "y1": int, "width": int, "height": int }` (pode conter `x2`/`y2` opcionais).
Normalizada por `shared.parsing.normalize_capture_region`.
