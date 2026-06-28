# PROMPTS — Prompts reutilizáveis para trabalhar neste repo

Cole estes prompts ao iniciar uma tarefa para carregar contexto rápido.

## Onboarding rápido
> Leia `CLAUDE.md` e o doc relevante em `.claude/`. Lembre: a lógica real está em `word_manager.py`,
> `screen_reader.py`, `typer.py` na RAIZ; os pacotes `application/`/`infrastructure/` são shims.
> Rode sempre da raiz (CWD-dependente). Não há DB nem testes automatizados.

## Adicionar estratégia de palavra
> Adicione a estratégia `<nome>` em `word_manager.py::get_word` e no `<select id="strategy-select">`
> de `index.html`. Documente em `.claude/BUSINESS_RULES.md`. Veja o checklist em DEVELOPMENT_GUIDE.

## Adicionar campo de config
> Adicione o campo `<campo>` seguindo o checklist de "campo de config" em
> `.claude/DEVELOPMENT_GUIDE.md` (default no AutoplayStateService → update_from_payload → word_service
> → Typer → front-end). Atualize API.md e DATABASE.md.

## Debug de digitação
> Quero ajustar o comportamento do `Typer`. Rode `python debug_typer.py` (mocks) e mostre o efeito.
> Não toque no teclado real. Veja `.claude/SKILLS/typing-automation.md`.

## Debug de OCR / auto-play
> O auto-play não detecta "SUA VEZ" / lê a sílaba errada. Veja `.claude/SKILLS/ocr.md`,
> ative `save_debug_screenshots`, e use `tools/ocr_extract.py` para testar.

## Manutenção de wordlists
> Quero limpar/normalizar a lista `<idioma>`. Veja `.claude/SKILLS/wordlists.md` e os scripts de
> limpeza. Mantenha 1 palavra/linha, minúsculas.

## Revisão / dívida técnica
> Faça uma revisão à luz de `.claude/KNOWN_ISSUES.md` e `.claude/TODO.md`. Não introduza dependências
> novas sem justificar.
