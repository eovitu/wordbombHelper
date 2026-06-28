# SKILL — API HTTP

## Objetivo
Projetar/alterar endpoints Flask de forma consistente.

## Quando usar
Nova rota, mudança de payload/resposta, auth.

## Convenções
- Prefixo `/api/...`. JSON in/out. Corpo via `json_or_empty()`.
- Mutações: POST + `@optional_auth_required`. Leituras: GET, geralmente sem auth.
- Respostas de erro: `{"status":"error","message":...}` + status HTTP adequado (400/401/404/500).
- Sucesso simples: `{"status":"success"}` ou `{"status":"ok", ...}`.

## Endpoints existentes
Ver `.claude/API.md` (tabela completa). Grupos: languages/sublists, word/reset, calibration,
autoplay (toggle/status/config), presets (get/save/delete).

## Boas práticas
- Valide coords/números explicitamente onde o valor é crítico (ex: `/api/calibration/click` retorna 400).
- Não exponha exceções cruas; logue e devolva mensagem amigável.
- Mantps `/api/autoplay/status` barato (é chamado a cada 250ms).

## Anti-patterns
- ❌ Endpoints que retornam HTML em vez de JSON (exceto `/`).
- ❌ Efeitos colaterais pesados num GET de polling.
- ❌ Esquecer de documentar em `API.md`.

## Checklist
- [ ] Método/rota corretos. [ ] Auth onde muta. [ ] Input saneado. [ ] Erros tratados.
- [ ] `API.md` atualizado.
