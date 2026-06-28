# SKILL — Backend (Flask + serviços)

## Objetivo
Trabalhar na camada Python: rotas, serviços de aplicação, DI, persistência JSON.

## Quando usar
Ao adicionar/alterar rotas, lógica de negócio, estado compartilhado ou persistência.

## Mapa
- Entry: `main.py` → `application/app_factory.create_app()` → `AppContext`.
- Rotas: `api/routes.py` (Blueprint, recebe `deps` por DI).
- Serviços: `application/*` (`WordService`, `AutoplayStateService`, `PresetService`, `RegionStore`).
- Lógica core: raiz (`word_manager.py`).
- Shared: `shared/parsing.py`, `shared/security.py`.

## Boas práticas
- Toda dependência entra via `create_app()` e é passada no dict `deps` do Blueprint.
- Saneie input com `to_int/to_float/to_bool` + `json_or_empty()`.
- Use `@optional_auth_required` em rotas que mutam estado.
- Respeite locks ao tocar estado compartilhado; prefira `snapshot_config()` a ler `config` direto.
- `logger = logging.getLogger(__name__)`.

## Anti-patterns
- ❌ Lógica de negócio dentro da função de rota.
- ❌ Editar shims em `application/`/`infrastructure/` achando que é a lógica.
- ❌ Ler `request.json` sem `silent=True`/checagem (use `json_or_empty`).
- ❌ Acessar `autoplay_state.config` sem lock em thread do watcher.

## Fluxo típico (nova rota)
1. Defina `@bp.route` em `routes.py`. 2. Leia/saneie corpo. 3. Chame serviço. 4. `jsonify` + status.
5. Atualize `API.md`.

## Checklist
- [ ] Rota fina, lógica no serviço.
- [ ] Input saneado.
- [ ] Auth onde muta estado.
- [ ] Thread-safety preservada.
- [ ] Documentado em `.claude/API.md`.
