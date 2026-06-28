# SKILL — Análise de Requisitos

## Objetivo
Traduzir pedidos do usuário (dono do projeto) em mudanças coerentes com o domínio WordBomb.

## Contexto do domínio
- Usuário único, joga WordBomb (principalmente Português), quer achar+digitar palavras parecendo humano.
- Restrições implícitas: local-only, sem deps pesadas, anti-detecção importa, latência baixa (a "bomba" tem tempo).

## Como conduzir
1. Identifique o modo afetado: Manual, Auto-Play ou Config.
2. Mapeie para entidades existentes (Idioma, Estratégia, Config/Preset, Região) antes de criar coisas novas.
3. Verifique impacto em performance (loop de OCR / listas grandes) e em humanização.
4. Cheque KNOWN_ISSUES/TODO — talvez já esteja mapeado.
5. Prefira estender mecanismos existentes (nova estratégia, novo campo de config) a inventar subsistemas.

## Perguntas úteis ao usuário
- É para o modo manual, auto-play ou ambos? (config é compartilhada)
- Em qual idioma? (afeta OCR e listas)
- É comportamento de digitação (humanização) ou de seleção de palavra?
- Precisa persistir (preset/região) ou é só em memória?

## Anti-patterns
- ❌ Adicionar dependência/serviço sem necessidade clara.
- ❌ Ignorar a natureza local/single-user (não construa multiusuário/DB).
- ❌ Quebrar anti-detecção por conveniência.

## Checklist
- [ ] Modo e idioma claros. [ ] Mapeado a entidades existentes. [ ] Impacto perf/humanização avaliado.
- [ ] Documentado (BUSINESS_RULES/API conforme o caso).
