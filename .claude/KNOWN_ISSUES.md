# KNOWN_ISSUES — Bugs, Armadilhas e Dívida Técnica

## Armadilhas estruturais
1. **Dependência de CWD (raiz do projeto)**
   - Os shims (`from word_manager import ...`) só resolvem porque a raiz está no `sys.path` (processo iniciado da raiz).
   - `screen_reader.py` usa `os.path.abspath('tessdata')` e `os.getcwd()` (debug_screenshots); `region_store.py` usa `os.getcwd()/calibration_region.json`.
   - **Efeito**: rodar de outro diretório quebra OCR, persistência e imports. `WordManager` é a exceção (usa caminho relativo ao próprio arquivo).
   - **Mitigação ao mexer**: prefira caminhos relativos a `__file__` (como faz `WordManager`).

2. **Duplicação de `presets_repository`**
   - `infrastructure/presets_repository.py` (real) e `infrastructure/repositories/presets_repository.py` (shim). Não duplicar lógica; editar o real.

3. **Lógica na raiz + shims**
   - Editar `word_manager.py`/`screen_reader.py`/`typer.py` da **raiz**, não os pacotes. Ver ARCHITECTURE.

## Pipeline B — aprendizado de palavras já jogadas (jun/2026)
Pipeline SEPARADO e OPCIONAL que lê o painel SOLVE (extensão Room Inspector) e marca as
palavras válidas como usadas, para o solver não sugerir palavra já jogada por ninguém.
**Totalmente isolado do Pipeline A (prompt)** — nunca afeta a latência do OCR do prompt.
- Arquivos: [`used_word_scanner.py`](../used_word_scanner.py) (`UsedWordScanner` + fonte
  modular `OcrSolvePanelSource`); `WordManager.mark_used_ocr` (casa OCR sem acento ↔ wordlist).
- **Isolamento**: thread própria (`UsedWordScanner`), **WarmTesseract próprio** (2º engine,
  ~30-50MB), **mss próprio**, polling 750ms. Só varre durante a partida (`is_active=is_watching`).
- **Só marca verde**: máscara HSV de verde isola palavras VÁLIDAS antes do OCR — vermelhas
  (inválidas) nem chegam ao Tesseract. Faixa em `OcrSolvePanelSource.green_lower/upper`.
- **Autodesativa** se o engine não carrega ou a região SOLVE não foi calibrada — o resto do
  app segue normal. Decisão de arquitetura: a extensão é *enhancement opcional*, nunca core.
- **Por que OCR e não DOM/WS**: investigado ao vivo — o jogo renderiza tudo num único
  `ok-canvas` (WebGL), então o prompt NÃO está no DOM (OCR é obrigatório). O WebSocket existe
  (raw) e a extensão o consome, mas ler DOM/WS exigiria injetar script no navegador (processo
  separado do Flask) — rejeitado para manter o app self-contained. Ver DECISIONS.
- **Região SOLVE**: calibração própria (`solve_region.json`), 2 cliques, via
  `start_calibration(target="solve")`. Botão "Calibrar painel SOLVE" no front.
- **Limitação**: OCR pode errar palavra composta longa → não marca aquela (dano baixo, =hoje).
  Depende do painel da extensão estar visível e na posição calibrada.

## Estabilidade do prompt — lock/hysteresis (jun/2026)
**Sintoma corrigido**: durante o turno, um prompt estável era trocado por leituras
transitórias (`'ar → cs → ri → 'ar`) vindas da animação da bomba / texto digitado entrando
na ROI grande, e voltava 1s depois. Causa: a lógica antiga **sobrescrevia o prompt a cada
frame**; com `instant_accept_conf=70`, um único frame garbage de conf alta roubava o lock.
**Solução** (em `_watch_loop` + `_commit_prompt`/`_clear_prompt_lock` em `screen_reader.py`):
máquina de estados com **lock**. Uma vez comprometido um prompt, ele fica travado e:
- leitura IGUAL → reafirma (poupa CPU com sleep 0.04s);
- leitura DIFERENTE → vira "challenger"; só rouba o lock após `switch_confirm_frames` (3)
  frames seguidos iguais — transitório de 1-2 frames é ignorado;
- SEM prompt (oclusão) → mantém o lock; só solta após `unlock_absent_frames` (25) ou fim do turno.
- **NÃO "consertar" removendo o lock** nem voltar a sobrescrever por frame: isso reintroduz o
  flicker. Aquisição inicial e troca legítima continuam rápidas (sem sleep nesses caminhos).
- **ROI grande agrava** (calibração 767×393 capta bomba/avatares/texto digitado). O lock
  neutraliza, mas calibrar mais justo no prompt ajudaria ainda mais.

## Performance do OCR — RESOLVIDO com engine in-process (medido, jun/2026)
**O Tesseract NÃO era lento — o problema era o subprocess.** Diagnóstico:
- Benchmark `pytesseract.image_to_data` em loop ocioso: `median=130ms`, mas em jogo
  esticava para 1–2s (`ocr=1569ms` nas logs). Causa: cada chamada faz **spawn de
  `tesseract.exe` + leitura do `tessdata` do disco**. Quando o jogo (WebGL) + gravador de
  tela competem por CPU/disco, o spawn/init estica aleatoriamente. **Não é o engine nem o psm.**
- `--oem 0` (legacy) nunca funcionou: tessdata empacotado é `tessdata_fast` só-LSTM.

**SOLUÇÃO IMPLEMENTADA** — [`ocr_engine.py`](../ocr_engine.py) `WarmTesseract`:
carrega `libtesseract-5.dll` (que vem na instalação do Tesseract) via **ctypes** (stdlib,
sem dep nova) e mantém o engine **vivo na RAM**. Init UMA vez; cada leitura usa SetImage +
Recognize + ResultIterator. **Medido: ~7ms median, ~10ms max, estável** (vs 130ms–2s do
subprocess) = ~18–200x mais rápido. `screen_reader._get_ocr_tokens()` usa ele e **cai para
pytesseract (subprocess) automaticamente** se a DLL não carregar (`OcrEngineUnavailable`).
- **Gotchas do ctypes** (não mexer sem reler `ocr_engine.py`): (a) NÃO setar
  `user_defined_dpi` — quebra leitura multi-token (dropa o prompt); silenciar o spam
  "Estimating resolution" via `debug_file=NUL`. (b) Manter referência viva ao buffer numpy
  entre SetImage e Recognize (senão GC corrompe). (c) Definir `argtypes`/`restype` de TODAS
  as funções, senão ponteiros de 64 bits truncam (`OverflowError`). (d) `read_tokens` é
  serializado por lock — libtesseract não é reentrante.
- **psm 11 in-process custa ~5–8ms** (a "lentidão do psm 11" era spawn/contenção, não layout).
- **Regras de latência**: NUNCA exigir 2 frames globais de confirmação (dobra latência);
  usar `instant_accept_conf` (1º frame se conf alta, 2 frames só p/ conf baixa). Prompts de
  2 letras só são lidos em tamanho real (sparse mode dropa texto minúsculo — não é bug).

## OCR / visão (frágil por natureza)
4. **⚠️ Detecção feita pro jogo ERRADO (jklm.fun), mas o usuário joga `wordbomb.io`**. No wordbomb.io o tema é escuro: o prompt é **texto branco maiúsculo** (ex: `ABO`) numa caixa escura no topo, "**SUA VEZ**" aparece em texto abaixo do prompt quando é a vez, a **seta** aponta para o jogador da vez, e a **bomba tem um anel branco** que encolhe (~6s, acelerando) até explodir (perde 1 vida ❤️; jogando sozinho é sempre a vez). **NÃO existem os botões coloridos amarelo/azul/vermelho** que o `screen_reader.py` procura via HSV — por isso a detecção de turno não funciona. Reescrever a detecção é o próximo grande passo (detectar texto "SUA VEZ" + ler prompt branco; opcionalmente seta/anel). Atualizar também README/CLAUDE que dizem "jklm.fun".
5. **Cores HSV fixas**: detecção de "SUA VEZ" depende de ranges de amarelo/azul/vermelho. Tema/skin diferente do jogo → falha. Thresholds de pixels (1000/2000/8000) calibrados para um tamanho de região específico.
5. **Sílaba 2–4 letras**: candidatos fora dessa faixa são ignorados. Sílabas de 1 ou 5+ chars não são lidas.
6. **Idiomas OCR fixos**: `por+eng`. Jogar em outro idioma reduz acerto da leitura da sílaba (a busca de palavra suporta vários idiomas, mas o OCR não).
7. **Ghost prompt protection** pode descartar sílaba legítima que coincide com sufixo da última palavra (raro).

## Automação de input
8. **Foco da janela**: no auto-play o jogo precisa estar em foco; no manual o `auto_tab`/`return_tab` faz Alt+Tab — se a ordem de janelas mudar, digita na janela errada.
9. **`keyboard`/`pyautogui` exigem permissões** (Windows: ok; Linux: X11/root; Wayland não suportado). Abort só por Insert ou FAILSAFE.
10. **Chamada dupla de digitação é silenciosamente ignorada** (`Lock` não-bloqueante) — comportamento intencional, mas pode confundir ao debugar.

## Higiene de repo
11. **Sem testes automatizados** — só `debug_typer.py` e verificação manual.
12. **Scripts utilitários na raiz** (deveriam migrar p/ `tools/` — ver `tools/` novos).
13. **Arquivos temporários versionados**: `_check_line_out.txt`, `_np_names.txt`, `scratch/`.
14. **README desatualizado**: descreve "janela vermelha" Tkinter; hoje overlay é HTML.
15. **`requirements.txt` sem versões** — risco de quebra em upgrade de libs (ex: mudanças de API do opencv/pyautogui).

## Comportamentos sutis (não são bugs, mas surpreendem)
16. `reset_used()` **recarrega listas do disco** (limpa cache) — custo alto em listas grandes (Português 248k).
17. Filtros em `get_word` são "soft": só aplicam se não esvaziarem a lista; combinação de filtros pode não ser estritamente respeitada.
18. Sublista prioritária **ignora todos os outros filtros** quando há match.
19. `priority_min_len`/`priority_max_len` default a 46 (≈ maior palavra plausível) — valor mágico repetido no código.
