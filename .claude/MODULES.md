# MODULES — Responsabilidade de cada módulo

## Entrada
| Arquivo | Responsabilidade |
|---|---|
| [`main.py`](../main.py) | Entry point. Configura logging, chama `create_app()`, expõe `app`/serviços a nível de módulo, roda Flask em `127.0.0.1:5000`. |

## Aplicação (`application/`)
| Arquivo | Responsabilidade |
|---|---|
| [`app_factory.py`](../application/app_factory.py) | Composition root / DI. `create_app()` monta tudo e devolve `AppContext`. |
| [`word_service.py`](../application/word_service.py) | Orquestra o caso de uso central: dado um prompt/payload → escolhe palavra (`WordManager`) → marca usada → digita (`Typer`). `on_prompt_found` (auto-play) e `get_word_from_payload` (manual). |
| [`autoplay_state_service.py`](../application/autoplay_state_service.py) | Estado do auto-play: dicionário `config` (defaults), `logs` (máx 50), thread-safe. `update_from_payload`, `snapshot_config`, `add_log`, `last_logs`. |
| [`preset_service.py`](../application/preset_service.py) | CRUD de presets (get_all/save/delete) sobre o repositório. Validação mínima. |
| [`region_store.py`](../application/region_store.py) | Guarda a região calibrada em memória + persiste em `calibration_region.json`. |
| `word_manager.py` (shim) | Re-export de `WordManager` da raiz. |

## Domínio (`domain/`)
| Arquivo | Responsabilidade |
|---|---|
| [`word_selection.py`](../domain/word_selection.py) | `WordSelectionParams` — dataclass frozen com todos os parâmetros de busca de palavra. |

## Lógica core (raiz — onde editar de verdade)
| Arquivo | Responsabilidade |
|---|---|
| [`word_manager.py`](../word_manager.py) | `WordManager`: carrega `wordlists/`, índice por comprimento, resolução de nome de idioma (acentos/aliases), `get_word()` com todos os filtros e estratégias, `mark_used`/`reset_used`, sublistas, "recover" (cobertura de letras). |
| [`screen_reader.py`](../screen_reader.py) | `ScreenReader`: captura (mss) + visão (cv2 HSV) + OCR (Tesseract), detecção de turno, extração de sílaba, loop do auto-play, calibração via pynput, configuração do caminho do Tesseract por SO. |
| [`typer.py`](../typer.py) | `Typer`: digitação humanizada (WPM, drift, bursts, typos QWERTY, hesitações, late errors, full retry, delayed type), Alt+Tab, abort via tecla Insert, `drag_path` (modo "cobrinha"/Letter Link). |

## Infraestrutura (`infrastructure/`)
| Arquivo | Responsabilidade |
|---|---|
| `ocr/screen_reader.py` (shim) | Re-export de `ScreenReader`. |
| `input/typer.py` (shim) | Re-export de `Typer`. |
| [`presets_repository.py`](../infrastructure/presets_repository.py) | `FilePresetRepository`: load/save de `presets.json` (implementação real). |
| `repositories/presets_repository.py` (shim) | Re-export do `FilePresetRepository`. **Duplicação** — ver KNOWN_ISSUES. |

## Apresentação
| Arquivo | Responsabilidade |
|---|---|
| [`api/routes.py`](../api/routes.py) | Blueprint Flask `/api/*`. Liga HTTP aos serviços; auth opcional; parsing. |
| [`templates/index.html`](../templates/index.html) | UI: abas Manual / Auto-Play / Config, overlay de calibração, controles. |
| [`static/js/app.js`](../static/js/app.js) | Estado do front (`currentConfig`), eventos, polling de status (250ms), presets, calibração, atalhos (Alt+1/2/3). |
| [`static/css/style.css`](../static/css/style.css) | Estilos. |

## Shared
| Arquivo | Responsabilidade |
|---|---|
| [`shared/parsing.py`](../shared/parsing.py) | `to_int/to_float/to_bool`, `normalize_capture_region`, `json_or_empty`. |
| [`shared/security.py`](../shared/security.py) | `make_optional_auth_required(token)` — decorator de auth opcional por header. |

## Legado / vazio
| Arquivo | Estado |
|---|---|
| [`overlay_manager.py`](../overlay_manager.py) | Shim vazio. Tk overlay removido; overlay hoje é HTML. |

## Scripts utilitários e dados
Ver [FILE_INDEX.md](FILE_INDEX.md) (scripts de manutenção de wordlist, `scratch/`, `tessdata/`, `wordlists/`).
