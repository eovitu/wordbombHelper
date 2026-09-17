# WordBomb Helper Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Entregar as melhorias aprovadas para partida, OCR, dicionário, treino e ergonomia mantendo o helper local.

**Architecture:** Preservar a factory Flask e os serviços atuais. Separar persistência do dicionário pessoal e treino em módulos pequenos, expor operações por rotas HTTP, e manter OCR e UI como adaptadores do estado da partida.

**Tech Stack:** Python, Flask, unittest, Tesseract, OpenCV, HTML/CSS/JavaScript puro.

**Spec:** [Melhorias aprovadas](../../wordbomb-improvements-spec.md)

## Global Constraints

- Preservar alterações locais existentes e não criar commits automaticamente.
- Usar o dicionário principal e o pessoal juntos nas buscas; persistir adições pessoais separadamente.
- Contar Recover apenas com uso confirmado; casual 1/2/2... e ranqueado 3/4/5/5..., excluindo K/W/Y.
- Manter a tela principal simples; treino e manutenção em áreas separadas.
- Escrever testes depois da implementação, conforme o pedido do usuário.
- Revisar `requirements.txt` antes e depois de adicionar bibliotecas.

---

### Task 1: Persistência do dicionário pessoal

**Files:** Create `application/personal_dictionary.py`, `tests/test_personal_dictionary.py`; integrate later in `application/app_factory.py` and `word_manager.py`.

**Interfaces:** `PersonalDictionary(store_dir).list_words(lang)`, `.add(lang, word)`, `.edit(lang, old, new)`, `.delete(lang, word)`, `.preview_import(lang, text)`, `.apply_import(lang, text)`, `.undo(lang)`.

- [ ] Implementar validação UTF-8, persistência atômica e operações idempotentes. O formato aceito para importação é uma palavra por linha.
- [ ] Escrever testes depois do módulo, cobrindo duplicatas, entrada inválida, importação e undo.
- [ ] Rodar `python -m unittest tests.test_personal_dictionary -v` e conferir o resultado completo.
- [ ] Integrar a leitura das palavras pessoais ao índice de `WordManager`, invalidando caches ao editar.

### Task 2: Ciclo da sugestão e Recover

**Files:** Modify `application/word_service.py`, `word_manager.py`, `application/autoplay_state_service.py`, `application/app_factory.py`; create `tests/test_suggestion_lifecycle.py`, `tests/test_recover_cycles.py`.

**Interfaces:** `WordService.correct_prompt(prompt)`, `.reject_current()`, `.reroll_short()`, `.finish_turn()`, `WordManager.recover_progress()`.

- [ ] Fazer a sugestão inicial provisória; ao terminar o turno, confirmar apenas a palavra exibida. Uma correção do prompt descarta a sugestão antiga.
- [ ] Inserir rejeições no conjunto de palavras indisponíveis da partida e escolher a próxima alternativa.
- [ ] Ordenar a navegação curta por comprimento sem refazer a busca do prompt.
- [ ] Implementar alvos de Recover por modo e ciclo, excluindo K/W/Y, com progresso legível pela UI.
- [ ] Escrever testes para correção, confirmação, rejeição, reroll curto e transições 1→2/3→4→5; executar os testes focados.

### Task 3: OCR e calibração observáveis

**Files:** Modify `screen_reader.py`; create `tests/test_ocr_diagnostics.py`; integrate routes in `api/routes.py`.

**Interfaces:** `ScreenReader.get_preview_png() -> bytes | None`, `.capture_ocr_replay() -> dict | None`, `get_state()['ocr_uncertain']`.

- [ ] Manter uma prévia limitada da captura processada e expor incerteza com base no estado de confirmação existente.
- [ ] Guardar um caso diagnóstico somente por ação explícita do usuário, com imagem e metadados suficientes para reprodução.
- [ ] Escrever testes depois da implementação para limite de memória, ausência de captura e metadados; rodar os testes focados.
- [ ] Expor prévia e gravação por HTTP sem alterar o algoritmo principal de detecção.

### Task 4: API e interface da partida

**Files:** Modify `api/routes.py`, `templates/index.html`, `static/js/app.js`, `static/css/style.css`; create `tests/test_game_api.py`.

**Interfaces:** `POST /api/reroll/short`, `POST /api/prompt/correct`, `POST /api/word/reject`, `GET /api/autoplay/status` com `recover_progress` e `ocr_uncertain`.

- [ ] Integrar operações de serviço com validação de entrada e auth opcional, preservando rotas existentes.
- [ ] Destacar a sílaba sem usar HTML derivado de OCR, mostrar estado incerto, correção, rejeição, progresso Recover, contador e atalhos.
- [ ] Criar o modo compacto mantendo comandos e estados acessíveis.
- [ ] Escrever testes de contrato HTTP depois da implementação e validar JavaScript, tela desktop/mobile e console.

### Task 5: Manutenção de palavras e aprendizado do painel SOLVE

**Files:** Modify `used_word_scanner.py`, `api/routes.py`, `application/app_factory.py`, `templates/index.html`, `static/js/app.js`; create `tests/test_dictionary_api.py`, `tests/test_opponent_learning.py`.

**Interfaces:** Rotas `/api/dictionary/*` para consulta/edição/importação/undo; scanner acrescenta palavra desconhecida apenas após leituras verdes estáveis e rastreáveis.

- [ ] Integrar o dicionário pessoal à API e à UI de manutenção.
- [ ] Exigir evidência repetida antes de adicionar leitura desconhecida do painel SOLVE; registrar origem e permitir undo.
- [ ] Escrever testes de persistência, deduplicação entre listas e rejeição de OCR ambíguo após implementar.
- [ ] Rodar testes de dicionário e scanner com fonte falsa, sem movimentar teclado ou exigir jogo aberto.

### Task 6: Treino, resumos, ergonomia e integração

**Files:** Create `application/practice_service.py`, `tests/test_practice_service.py`; modify UI/API, documentação e `requirements.txt` somente conforme necessidade verificada.

**Interfaces:** Treino em tela separada, dicas progressivas, resumo da partida e perfis de calibração; a janela flutuante usa os mesmos dados da tela compacta.

- [ ] Implementar geração de prompts válidos e avaliação com dicionários locais; separar desempenho do treino dos dados da partida.
- [ ] Mostrar resumo baseado em eventos confirmados e selecionar treinos a partir das dificuldades registradas.
- [ ] Persistir perfis de calibração com regiões de prompt e SOLVE, mantendo o perfil ativo restaurável.
- [ ] Disponibilizar janela compacta independente e mapa de atalhos com conflitos detectáveis.
- [ ] Escrever testes após cada parte; executar a suíte completa, verificar importações em ambiente com dependências instaladas, renderizar a UI, testar console/rede e revisar `git diff --check`.
