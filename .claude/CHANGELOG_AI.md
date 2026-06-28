# CHANGELOG_AI — Log de mudanças feitas por IA

Formato: data (YYYY-MM-DD) — autor (modelo) — resumo. Mais recente no topo.

## 2026-06-27 — Claude (Opus 4.8) — Bootstrap da base de conhecimento
- Engenharia reversa completa do projeto (estrutura, stack, arquitetura, domínio).
- Criado `CLAUDE.md` (memória principal) na raiz.
- Criada a base `.claude/`: README, PROJECT_CONTEXT, ARCHITECTURE, MODULES, API, BUSINESS_RULES,
  DATABASE, DEPENDENCIES, FILE_INDEX, GLOSSARY, KNOWN_ISSUES, DECISIONS, DEVELOPMENT_GUIDE, TODO,
  CHANGELOG_AI, PROMPTS.
- Criada `.claude/SKILLS/`: backend, frontend, api, ocr, wordlists, typing-automation, testing,
  debugging, refactoring, security, performance, documentation, requirements.
- Criada `tools/` com scripts Python (`ocr_extract.py`, `project_stats.py`, `dependency_map.py`) + README.
- **Nenhuma mudança em código de negócio** — apenas documentação/ferramentas.
- Constatado: não há imagens/PDFs/docs binárias no repo (Etapa OCR de docs não aplicável; `ocr_extract.py`
  fica pronto para uso futuro contra screenshots do jogo).

## 2026-06-27 — Claude (Opus 4.8) — Passo 1: Logging estruturado
- Novo módulo `shared/logging_config.py` (`setup_logging`): console (nível via env `WORDBOMB_LOG_LEVEL`,
  default INFO) + arquivo rotativo `logs/wordbomb.log` sempre em DEBUG (idempotente; path relativo a
  `__file__`, robusto a CWD). `logs/` adicionado ao `.gitignore`.
- `main.py` agora usa `setup_logging()` em vez de `basicConfig`.
- `screen_reader.py`: `_log` subido para INFO (eventos significativos vão ao console + front); log de
  **transição de turno** (não por-frame) no `_watch_loop`; log DEBUG de **diagnóstico de decisão de OCR**
  (contagens de cor, keyword, streak, candidato, confiança) em `_capture_and_ocr`; flag de screenshots de
  debug via env `WORDBOMB_OCR_DEBUG=1`.
- **Descoberta importante** registrada em KNOWN_ISSUES: o usuário joga **wordbomb.io** (tema escuro, prompt
  branco, "SUA VEZ" em texto, seta, bomba com anel branco), não jklm.fun — a detecção HSV de botões
  coloridos não se aplica. É o foco do próximo passo (OCR).

## 2026-06-27 — Claude (Opus 4.8) — Bugfix: tessdata + caminho com espaços
- Os logs revelaram a causa do OCR "não funcionar": `screen_reader.py` montava `--tessdata-dir <path>`
  na string de config do pytesseract, que **quebra a string nos espaços**. O caminho do projeto tem
  espaços ("voltando a velha epoca"), então virava `--tessdata-dir C:/Users/vitu/Downloads/voltando` →
  Tesseract não carregava `por`/`eng` ("Could not initialize tesseract") em loop.
- Correção: definir `os.environ['TESSDATA_PREFIX']` para o tessdata empacotado (path relativo a
  `__file__`, robusto a CWD) e remover `--tessdata-dir` do config.
- Confirmado via `debug_screenshots/last_processed.png`: o pré-processamento gera "AGU"/"SUA VEZ" em
  preto nítido — o OCR deve ler bem. **Pendente (passo 2):** a detecção de turno ainda é gated por cor
  (amarelo/azul/vermelho) que não existe no tema escuro; precisa passar a usar a keyword "SUA VEZ".

## 2026-06-27 — Claude (Opus 4.8) — Passo 2: detecção de turno por texto (wordbomb.io)
- Reescrita do `screen_reader._capture_and_ocr`: detecção de turno deixou de depender de **cor de botão**
  (jklm) e passou a se basear no **texto "SUA VEZ"/"YOUR TURN"** lido por OCR numa zona inferior dedicada.
- Pipeline novo, theme-agnóstico p/ tema escuro: máscara de **texto branco** → medianBlur → inverte → Otsu,
  aplicada em duas zonas (`prompt_zone` topo, `turn_zone` base) via helper `_prep_zone`.
- **Early-exit por branco** (`min_white_pixels`) no lugar do early-exit por cor.
- Extração do prompt só roda **quando é a vez** (economia de OCR). Validação por confiança
  (`prompt_conf_threshold`) OU keyword presente. Ghost-protection mantida (agora usa keyword como reforço).
- Parâmetros de tuning expostos no `__init__`: `turn_keywords`, `min_white_pixels`, `min/max_prompt_len`,
  `prompt_conf_threshold`. Salva também `debug_screenshots/last_turn_zone.png` quando `WORDBOMB_OCR_DEBUG=1`.
- Removidas as máscaras HSV amarelo/azul/vermelho e o OCR da imagem inteira.

## 2026-06-27 — Claude (Opus 4.8) — Passo 2.1: corrige pisca-pisca + leitura da sílaba
- Causa do "detecta/encerra" e do `candidate=''`: OCR em `psm 7` (linha única) numa imagem com 2 linhas
  ("SÍLABA" + "SUA VEZ") ora lia uma, ora outra. Trocado por **`psm 11` (texto esparso)** numa **única
  leitura** da região inteira (`_read_prompt_and_turn`): pega todas as palavras, detecta a vez se
  "SUA/VEZ/TURN" aparece e escolhe a sílaba = melhor palavra que não é indicador de turno.
- **Debounce de turno** (`turn_off_misses=2`): só encerra a vez após 2 frames seguidos sem keyword —
  elimina o flicker por frame ruim isolado.
- Removida a divisão em zonas (prompt/turn) e a 2ª chamada de OCR.
- Bugfix: calibração via **listener de mouse (pynput)** não persistia em `calibration_region.json`
  (só o caminho HTTP salvava). Adicionado `ScreenReader.on_region_calibrated`, ligado ao
  `RegionStore.set_region` no `app_factory` → agora qualquer calibração persiste.

## 2026-06-27 — Claude (Opus 4.8) — Passo 2.2: sílaba pelo MAIOR texto + log de tokens
- Pisca-pisca confirmado resolvido (em solo, `miss=0` e turno estável). Resta o "novo" fantasma:
  aparece ~2 frames na transição entre prompts (conf 96), enquanto prompts reais duram ~6s.
- `_read_prompt_and_turn` agora seleciona a sílaba pela **altura da fonte** (maior texto = prompt),
  com confiança como desempate — descarta rótulos de UI menores. Adicionado log DEBUG de todos os
  tokens (texto, conf, altura) para diagnosticar a origem do "novo".

## 2026-06-27 — Claude (Opus 4.8) — Passo 2.3: origem do "novo" identificada
- O "novo" fantasma é o **balão de "palavra nova descoberta"** do wordbomb.io (sobe na tela; comum em
  conta nova e sempre que se digita palavra inédita). Adicionado "NOVO"/"NOVA" ao `_UI_KEYWORDS`
  (ignorados como sílaba). Relevante também p/ auto_type: evita ler o próprio balão pós-digitação.

## 2026-06-27 — Claude (Opus 4.8) — Passo 3: latência do OCR
- Causa principal: a imagem era **ampliada 2x sempre** antes do OCR → em região grande o OCR ficava lento.
  Agora normaliza para `ocr_target_width` (640px): reduz regiões grandes (OCR bem mais rápido) e amplia
  pequenas. Reduzidas as esperas no caminho crítico (0.1→0.05s). Adicionado no log o tamanho da imagem e o
  **tempo de OCR por frame** (`ocr=NNms`) para medir o ganho.

## 2026-06-27 — Claude (Opus 4.8) — Passo 3.1: reverte downscale (quebrou "SUA VEZ")
- Benchmark com o tesseract real: OCR ~220ms/chamada "a quente" e **quase independente do tamanho**
  (214ms numa imagem 50x30 vs 222ms em 640x260). O custo é o **spawn do tesseract.exe** por chamada;
  os 1700ms vistos foram pico de sistema/antivírus, não o tamanho.
- Logo, reduzir a imagem (passo 3) não acelerou e **encolheu o "SUA VEZ" p/ ~8px → ilegível →
  detecção de turno quebrou**. Revertido: agora amplia ~2x (legibilidade) com teto `ocr_max_width=1600`
  e NUNCA reduz abaixo do nativo. Mantido o log de `ocr=NNms` para medir em jogo.
- Latência real virá de: reduzir frames-de-confirmação e/ou eliminar o spawn por chamada
  (ex.: exclusão do antivírus p/ tesseract.exe, ou lib in-process) — a investigar com dados de jogo.

## 2026-06-27 — Claude (Opus 4.8) — Passo 3.2: latência (AV + aceite no 1º frame)
- Exclusão do tesseract.exe no antivírus ajudou: OCR mediana **242ms** (cauda longa só em telas cheias de
  texto, que são keyword=False e não afetam o turno).
- `instant_accept_conf=88`: aceita a sílaba já no 1º frame quando a confiança é alta (a maioria é 90-96),
  cortando ~uma leitura de OCR; mantém 2 frames quando a confiança é baixa (anti-fragmento).
- Front-end: polling de status 250ms → 120ms (sugestão aparece mais rápido na tela).

## 2026-06-27 — Claude (Opus 4.8) — Passo 4: redesign do front-end (auto-only, minimalista)
- Front-end reescrito do zero (index.html, app.js, style.css) — tema preto minimalista, fontes do sistema
  (removida a dependência do Google Fonts → carrega mais leve).
- **Removido**: aba Manual, aba Config, presets, todos os controles de humanização/digitação (WPM, typos,
  hesitação, retry, late error, delayed type, period, auto-type toggle) e atalhos de aba.
- **Mantido (uma tela só, modo Auto)**: calibrar, iniciar/parar, reset; exibição da palavra sugerida +
  sílaba; idioma, sublista, estratégia (random/shortest/longest/alpha/recover), filtros (contém/começa/
  termina/exclui/tamanho) e recover (target/exclude, visível só na estratégia recover); log compacto.
- `auto_type` fixo em `false` (nunca digita — o usuário digita). Polling de status a 150ms.
- Nota: os endpoints de manual/presets continuam no backend (inofensivos); docs de UI em MODULES/ARCH
  ficaram desatualizadas — refletem o layout antigo (anotado no TODO).

<!-- Próximas entradas acima desta linha -->
