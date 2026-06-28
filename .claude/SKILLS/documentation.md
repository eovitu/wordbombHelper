# SKILL — Documentação (conhecimento vivo)

## Objetivo
Manter `.claude/` e `CLAUDE.md` sempre verdadeiros — a memória permanente do projeto.

## Quando atualizar
- Descobriu algo não óbvio → registre no doc relevante.
- Mudou comportamento/arquitetura → atualize `CLAUDE.md` + doc específico + `CHANGELOG_AI.md`.
- Tomou decisão de design → `DECISIONS.md`.
- Achou bug/armadilha → `KNOWN_ISSUES.md`.

## Onde vai cada coisa
| Conteúdo | Arquivo |
|---|---|
| Visão geral, stack, como rodar | `CLAUDE.md` |
| Domínio/negócio | `PROJECT_CONTEXT.md`, `BUSINESS_RULES.md` |
| Camadas/fluxos | `ARCHITECTURE.md` |
| Rotas | `API.md` |
| Estado/persistência | `DATABASE.md` |
| Responsabilidade por arquivo | `MODULES.md`, `FILE_INDEX.md` |
| Termos | `GLOSSARY.md` |
| Como estender | `DEVELOPMENT_GUIDE.md` |
| Bugs/dívida | `KNOWN_ISSUES.md`, `TODO.md` |
| Decisões | `DECISIONS.md` |
| Log de IA | `CHANGELOG_AI.md` |

## Boas práticas
- Baseie-se em **evidência do código** (cite arquivo/função). Não invente.
- Texto enxuto, tabelas/listas. Links relativos clicáveis.
- PT-BR (idioma do projeto).
- Ao terminar uma tarefa de código, faça um passo final de "atualizei a doc?".

## Anti-patterns
- ❌ Deixar conhecimento só na conversa.
- ❌ Doc que contradiz o código (verifique antes de citar).
- ❌ Duplicar a mesma info em 5 arquivos — referencie.

## Checklist
- [ ] Doc reflete o código atual. [ ] CHANGELOG_AI atualizado. [ ] Links válidos.
