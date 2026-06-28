# SKILL — Refatoração

## Objetivo
Melhorar o código sem mudar comportamento, respeitando as armadilhas do projeto.

## Alvos prioritários (ver KNOWN_ISSUES / TODO)
- `WordManager.get_word` (>170 linhas): extrair pipeline de filtros + objeto por estratégia.
- Caminhos dependentes de CWD em `screen_reader.py`/`region_store.py` → relativos a `__file__`.
- Consolidar duplicação de `presets_repository`.
- Mover utilitários da raiz p/ `tools/`.

## Regras de segurança
- **Não mova** a lógica da raiz para os pacotes sem ajustar todos os shims/imports e testar o CWD.
- Preserve assinaturas públicas usadas por `word_service.py` e `routes.py`.
- Refatore em passos pequenos; verifique com `debug_typer.py` / REPL / testes manuais a cada passo.
- Mantenha thread-safety (locks) intacta.

## Boas práticas
- Extraia funções puras p/ `shared/` quando possível (testáveis).
- Introduza testes ANTES de refatorar algo arriscado (caracterização).
- Documente a decisão em `DECISIONS.md` e registre em `CHANGELOG_AI.md`.

## Anti-patterns
- ❌ "Big bang" refactor sem rede de testes.
- ❌ Renomear arquivos da raiz quebrando os shims.
- ❌ Mudar comportamento "de brinde" durante refatoração.

## Checklist
- [ ] Comportamento idêntico verificado. [ ] Shims/imports coerentes. [ ] CWD testado.
- [ ] Locks preservados. [ ] Docs atualizadas.
