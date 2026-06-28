# DEVELOPMENT_GUIDE — Como estender com segurança

## Setup
```bash
pip install -r requirements.txt
# Instale o Tesseract OCR no SO (Windows: C:\Program Files\Tesseract-OCR\)
python main.py            # http://127.0.0.1:5000  (RODE A PARTIR DA RAIZ)
```
> Sempre rode da raiz do projeto (CWD = raiz) — ver KNOWN_ISSUES sobre dependência de CWD.

## Regras de ouro
1. Edite a **lógica na raiz** (`word_manager.py`, `screen_reader.py`, `typer.py`), nunca os shims.
2. Não acople lógica às rotas — coloque em serviços `application/` e injete via `app_factory`.
3. Saneie toda entrada do front com `shared/parsing.py`.
4. Respeite os locks (RLock do WordManager; locks de config/logs; Lock do Typer).
5. Sem novas dependências sem necessidade clara.
6. Atualize a doc em `.claude/` ao descobrir/alterar algo (conhecimento vivo) + `CHANGELOG_AI.md`.

## Receitas (checklists)

### Adicionar uma rota HTTP
- [ ] Adicione no Blueprint em `api/routes.py`.
- [ ] `@optional_auth_required` se mutar estado.
- [ ] Leia o corpo com `json_or_empty()`; saneie campos.
- [ ] Delegue a um serviço (não ponha lógica na rota).
- [ ] Documente em `.claude/API.md`.

### Adicionar uma estratégia de seleção de palavra
- [ ] Em `word_manager.py::get_word`, adicione `elif strategy == 'novo':`.
- [ ] Retorne uma palavra dos `candidates` (já filtrados).
- [ ] Adicione a opção no `<select id="strategy-select">` de `templates/index.html`.
- [ ] Documente em `.claude/BUSINESS_RULES.md` (tabela de estratégias).

### Adicionar um campo de config (auto-play/manual)
- [ ] Default em `AutoplayStateService.__init__.config`.
- [ ] Handler em `AutoplayStateService.update_from_payload` (use `to_int/to_float/to_bool`).
- [ ] Propague em `WordService.on_prompt_found` e/ou `get_word_from_payload`.
- [ ] Se afeta digitação, passe a `Typer.type_word`.
- [ ] No front: controle em `index.html`, binding em `app.js` (`setupEventListeners`), campo em `currentConfig`, refletir em `updateUIFromConfig`.
- [ ] Documente em `API.md` + `DATABASE.md` (schema da config).

### Adicionar um idioma
- [ ] Crie `wordlists/Idioma.txt` (1 palavra/linha, minúsculas; rode `tools/`/scripts de limpeza).
- [ ] É descoberto automaticamente por `WordManager.get_languages()`.
- [ ] Sublista: `Idioma_sub.txt`.
- [ ] (Opcional) ajuste OCR `tess_lang` se for jogar nesse idioma no auto-play.

### Mexer no `Typer` (digitação)
- [ ] Rode `python debug_typer.py` para inspecionar com mocks (sem mexer no teclado real).
- [ ] Cuidado com `_abort` (Insert) e `done_event`.
- [ ] Teste manualmente num campo de texto inofensivo antes do jogo.

### Mexer no `ScreenReader` (OCR)
- [ ] Ative `save_debug_screenshots = True` para inspecionar `debug_screenshots/last_processed.png`.
- [ ] Verifique manualmente com a tela do jogo (não há teste automatizado).
- [ ] Use `tools/ocr_extract.py` para testar Tesseract numa imagem isolada.

## Estilo
- PT-BR em comentários explicativos, inglês em nomes de identificadores. Siga o arquivo que edita.
- `logger = logging.getLogger(__name__)`; nada de `print` em código de produção.
- Funções pequenas e puras quando possível (especialmente em `shared/`).
