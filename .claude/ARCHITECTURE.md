# ARCHITECTURE

## Padrão geral
Arquitetura em **camadas** com sabor de DDD/hexagonal, montada por **injeção de dependências**.
O composition root é [`application/app_factory.py`](../application/app_factory.py): `create_app()`
instancia tudo e devolve um `AppContext` (dataclass) que `main.py` desempacota.

```
┌─────────────────────────────────────────────────────────┐
│ Apresentação                                             │
│   templates/index.html + static/js/app.js  (browser UI)  │
│   api/routes.py  (Flask Blueprint /api/*)                │
├─────────────────────────────────────────────────────────┤
│ Aplicação (casos de uso / serviços)                      │
│   WordService · AutoplayStateService · PresetService     │
│   RegionStore                                            │
├─────────────────────────────────────────────────────────┤
│ Domínio                                                  │
│   domain/word_selection.py (WordSelectionParams)         │
│   regras em WordManager (raiz)                           │
├─────────────────────────────────────────────────────────┤
│ Infraestrutura (adaptadores)                             │
│   ScreenReader (OCR/visão) · Typer (input) ·             │
│   FilePresetRepository (JSON) · RegionStore (JSON)       │
├─────────────────────────────────────────────────────────┤
│ Shared: parsing.py, security.py                          │
└─────────────────────────────────────────────────────────┘
```

## ⚠️ Estrutura física vs. lógica (armadilha central)
A lógica pesada está em arquivos da **raiz**: `word_manager.py`, `screen_reader.py`, `typer.py`.
Os pacotes `application/`, `infrastructure/ocr/`, `infrastructure/input/` contêm **shims** que apenas
re-exportam (ex: `infrastructure/ocr/screen_reader.py` → `from screen_reader import ScreenReader`).
Isso depende de o processo rodar com CWD = raiz do projeto (a raiz está no `sys.path`).

**Regra**: edite a lógica nos arquivos da raiz. Os shims existem para dar uma fachada "arquitetural"
limpa aos imports (`from infrastructure.ocr.screen_reader import ScreenReader`).

Também há **dois** `presets_repository` shimando o mesmo `FilePresetRepository`:
`infrastructure/presets_repository.py` (implementação real) e
`infrastructure/repositories/presets_repository.py` (re-export).

## Composition root — o que `create_app()` faz
1. Cria o `Flask` apontando `templates/` e `static/` por caminho absoluto.
2. Instancia `WordManager`, `Typer`, `RegionStore`, `AutoplayStateService`.
3. Lê `WORDBOMB_API_TOKEN` do ambiente → cria o decorator `optional_auth_required`.
4. Instancia `ScreenReader(autoplay_state, callback=None)`; carrega a região persistida (se houver) em `turn_region`/`prompt_region`.
5. Instancia `WordService(word_manager, typer, screen_reader, autoplay_state)`.
6. Liga callbacks: `screen_reader.set_callback(word_service.on_prompt_found)` e `set_log_callback(autoplay_state.add_log)`.
7. Instancia `FilePresetRepository(presets.json)` + `PresetService`.
8. Registra o Blueprint da API e a rota `/` (renderiza `index.html`).

## Fluxo de dados — Modo Manual
```
Browser (Enter na sílaba)
  → POST /api/word  {prompt, lang, strategy, filtros, auto_type, wpm, ...}
  → WordService.get_word_from_payload()
      → WordManager.get_word(...)  → escolhe palavra
      → WordManager.mark_used(word)
      → se auto_type: Typer.type_word(... auto_tab=True, return_tab=True)  (Alt+Tab → digita → Alt+Tab)
  → resposta {word}
  → app.js mostra a palavra em #current-word
```

## Fluxo Auto-Play (visão computacional)
Thread daemon `ScreenReader._watch_loop` (iniciada por `start_watching`/`toggle_watching`):
```
loop (enquanto is_watching):
  _capture_and_ocr(sct):
    grab da região calibrada (mss)
    cache de frame (hash dos bytes) → pula pipeline se tela idêntica
    máscara HSV p/ cores do botão (amarelo/azul/vermelho) → early-exit se sem cor
    upscale 2x, separa Top Zone (prompt 0–65%) e Bottom Zone (turn 55–100%)
    OCR (Tesseract por+eng, psm 7, whitelist A-Za-z) → texto + candidato de sílaba
    decide is_my_turn (cor forte OU cor+keyword "SUA/VEZ/TURN") com streak de confirmação
  se !is_my_turn → limpa sugestão, continua
  se prompt instável (streak<2) → continua
  se prompt == último sugerido → não recalcula (anti-flicker)
  callback_found_word(prompt) == WordService.on_prompt_found:
      busca palavra; se auto_type ON → Typer digita; senão só sugere (preview no front)
  TYPE+RETRY LOOP (só se auto_type): digita, espera, recaptura; se "SUA VEZ" sumiu → aceitou;
      se prompt mudou → aceitou (solo); se mesmo prompt → rejeitada, tenta outra (até max_retries=5)
```
Proteções: **frame hash cache**, **ghost prompt protection** (ignora sílaba que é só sufixo da última
palavra digitada), **confirm streaks** de turno e de prompt, **border crop** de 12px (não detectar a
própria moldura do overlay).

## Fluxo de Calibração
```
POST /api/calibration/start → ScreenReader.start_calibration()
    status=Calibrating, inicia pynput mouse.Listener
usuário clica canto sup-esq → step turn_start
usuário clica canto inf-dir → step turn_end → region normalizada
  (front-end também pode enviar POST /api/calibration/click {x,y})
done → RegionStore.set_region(region) (persiste calibration_region.json)
       screen_reader.turn_region = prompt_region = region
```
O overlay de calibração é **HTML** (`#calibration-overlay` em `index.html`), não Tkinter — o antigo
`overlay_manager.py` Tk foi removido e virou shim vazio.

## Concorrência / threads
- **Thread principal**: Flask (single-threaded por padrão; `app.run`).
- **Thread do watcher**: `ScreenReader._watch_loop` (daemon).
- **Thread de digitação**: `Typer._type_thread` (uma por palavra; `Lock` não-bloqueante evita concorrência; `done_event` sincroniza).
- **Listener de mouse**: `pynput` durante calibração.
- Estado compartilhado protegido por locks: `WordManager._lock` (RLock), `AutoplayStateService.config_lock`/`logs_lock`, `RegionStore._lock`.

## Eventos / callbacks (em vez de DI rígida)
- `screen_reader.callback_found_word` → `word_service.on_prompt_found(prompt)` (retorna bool "digitou/achou").
- `screen_reader.log_callback` → `autoplay_state.add_log(msg)` (logs exibidos no front via polling).
- `word_service.on_word_found_callback` → opcional (não setado por padrão; gancho para UI futura).
