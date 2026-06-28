# SKILL — Segurança

## Objetivo
Manter o app local seguro o suficiente sem complicar (uso pessoal, sem dados sensíveis).

## Superfície de ataque (pequena)
- Servidor só em `127.0.0.1:5000` (localhost). Não expor à rede.
- Auth opcional via `WORDBOMB_API_TOKEN` (header `X-API-Token`) nas rotas que mutam estado.
- Persistência em arquivos locais (presets/região). Sem dados de terceiros.

## Boas práticas
- Não fazer bind em `0.0.0.0` nem expor a porta sem necessidade.
- Se compartilhar a máquina, defina `WORDBOMB_API_TOKEN`.
- Saneie input do front (já feito via `shared/parsing.py`) — evita type confusion.
- `calibration/click` valida coordenadas e retorna 400 em entrada inválida — mantenha esse padrão.
- Cuidado com `keyboard`/`pyautogui`: têm poder total sobre teclado/mouse; um bug pode digitar em qualquer lugar. Mantenha o abort (Insert/FAILSAFE) funcionando.

## Anti-patterns
- ❌ Expor o Flask na rede local/internet.
- ❌ Logar o token ou conteúdo sensível.
- ❌ Executar input do usuário como comando/código.
- ❌ Rodar com `debug=True` em produção (já está `False`).

## Checklist
- [ ] Bind em localhost. [ ] Token quando necessário. [ ] Input saneado. [ ] Abort de digitação OK.
