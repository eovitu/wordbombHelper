# API — Rotas HTTP

Blueprint em [`api/routes.py`](../api/routes.py). Base: `http://127.0.0.1:5000`.
Rotas marcadas 🔒 usam `@optional_auth_required`: exigem header `X-API-Token` **somente** se a env
`WORDBOMB_API_TOKEN` estiver definida (caso contrário, abertas). Corpos JSON lidos via `json_or_empty()`.

## Páginas
| Método | Rota | Descrição |
|---|---|---|
| GET | `/` | Renderiza `index.html` (a UI). |

## Idiomas / listas
| Método | Rota | Resposta |
|---|---|---|
| GET | `/api/languages` | `["Alemão", "Português", ...]` — idiomas descobertos em `wordlists/`. |
| GET | `/api/sublists` | `{ "Português": ["palindromos"], ... }` — mapa lang→sublistas. |
| GET | `/api/sublists/<lang>` | `["palindromos", ...]` — sublistas do idioma. |

## Palavra
| Método | Rota | Corpo | Resposta |
|---|---|---|---|
| POST 🔒 | `/api/word` | `{prompt, lang, min_len, max_len, strategy, priority_letters, exclude_letters, starts_with_letters, finish_with_letters, priority_min_len, priority_max_len, priority_sublist, prefix, suffix, auto_type, wpm, error_rate, recover_target, recover_exclude, ...}` | `{"word": "inflamou"}` ou `{"word": null}`. Se `auto_type` true, digita no jogo (Alt+Tab). |
| POST 🔒 | `/api/reset` | — | `{"status":"success"}`. Limpa `used_words` e recarrega listas do disco. |

## Calibração
| Método | Rota | Corpo | Resposta |
|---|---|---|---|
| POST 🔒 | `/api/calibration/start` | — | `{"status":"started","step":"turn_start","message":...}`. Inicia listener de mouse. |
| POST 🔒 | `/api/calibration/click` | `{x, y}` | Estado da calibração. No `done`, persiste a região e a aplica ao `ScreenReader`. 400 se x/y ausentes/inválidos. |

## Auto-Play
| Método | Rota | Corpo | Resposta |
|---|---|---|---|
| POST 🔒 | `/api/autoplay/toggle` | — | `{"status":"active"|"inactive"}`. Liga/desliga o watcher. 500 em erro. |
| GET | `/api/autoplay/status` | — | `{status, is_watching, calibration_step, regions_set, suggested_word, preview_prompt, turn_region, prompt_region, logs:[{id,msg}], autoplay_lang, autoplay_strategy}`. Polled a cada 250ms pelo front. |
| POST 🔒 | `/api/autoplay/config` | (qualquer subconjunto de campos da config) | `{"status":"ok","config":{...}}`. Atualiza config compartilhada; sincroniza `wm.current_language`. |

## Presets
| Método | Rota | Corpo | Resposta |
|---|---|---|---|
| GET | `/api/presets` | — | `{ "<nome>": {config...}, ... }` (de `presets.json`). |
| POST 🔒 | `/api/presets/save` | `{name, config}` | `{"status":"success"}` / 400 se faltar name/config / 500 se falhar gravar. |
| POST 🔒 | `/api/presets/delete` | `{name}` | `{"status":"success"}` / 404 se não existir. |

## Notas
- Campos numéricos são saneados com `to_int`/`to_float`/`to_bool` (default em caso de erro).
- `strategy` ∈ `random | shortest | longest | hyphen | alpha | recover` (ver BUSINESS_RULES).
- A config do auto-play e a do modo manual **compartilham** o mesmo conjunto de campos; o front mantém `currentConfig` e faz POST debounced em `/api/autoplay/config`.
