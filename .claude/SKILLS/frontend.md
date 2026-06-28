# SKILL — Frontend (HTML/CSS/JS vanilla)

## Objetivo
Trabalhar na UI servida pelo Flask: `templates/index.html`, `static/js/app.js`, `static/css/style.css`.

## Quando usar
Ao adicionar controles de config, melhorar feedback do auto-play, ajustar abas/atalhos.

## Mapa
- 3 abas: Manual / Auto-Play / Config (`switchTab`, atalhos Alt+1/2/3 e 1/2/3).
- Estado do front: objeto `currentConfig` em `app.js` (espelha a config do backend).
- Sincronização: `syncConfigToBackend()` faz POST debounced em `/api/autoplay/config`.
- Polling: `pollAutoStatus()` a cada 250ms lê `/api/autoplay/status` e atualiza display/logs/botões.
- Presets: `fetchPresets/loadPreset/saveNewPreset/deletePreset`.
- Calibração: overlay HTML `#calibration-overlay` (`showOverlay/updateOverlay/hideOverlay`).

## Boas práticas
- Sem framework, sem build: JS puro, funções globais. Mantenha esse padrão.
- Para um novo controle: crie o elemento em `index.html`, faça o binding em `setupEventListeners`,
  adicione o campo em `currentConfig`, reflita em `updateUIFromConfig`, e chame `scheduleSyncConfig()`.
- Use os helpers `bindSlider/bindNumber` existentes.
- IDs seguem convenção: `<algo>-slider`, `<algo>-value`, `<algo>-toggle`, `<algo>-select`.

## Anti-patterns
- ❌ Introduzir framework/bundler.
- ❌ Sincronizar config sem debounce (gera flood de POST).
- ❌ Ler estado direto do DOM em vez de `currentConfig`.

## Checklist (novo controle de config)
- [ ] Elemento no HTML com ID padronizado.
- [ ] Binding em `setupEventListeners`.
- [ ] Campo em `currentConfig` + `updateUIFromConfig`.
- [ ] `scheduleSyncConfig()` no handler.
- [ ] Campo aceito no backend (ver SKILL backend / DEVELOPMENT_GUIDE).
