# CLAUDE.md — WordBomb Helper

> Memória principal do projeto. Leia este arquivo antes de qualquer tarefa.
> Documentação detalhada vive em [`.claude/`](.claude/). Atualize ambos quando descobrir algo novo.

---

## 1. O que é o projeto

**WordBomb Helper** é uma ferramenta **local** (roda na máquina do usuário, não é hospedada) que
ajuda a jogar o jogo de navegador **WordBomb** (jklm.fun e similares). O jogo mostra uma sílaba
("prompt", ex: `nfl`) e o jogador precisa digitar, antes do tempo acabar, uma palavra que contenha
essa sílaba (ex: `i**nfl**amou`).

A ferramenta faz duas coisas:
1. **Encontra** uma palavra que contém a sílaba, a partir de listas de palavras por idioma.
2. **Digita** a palavra no jogo simulando digitação humana (velocidade variável, erros, hesitações)
   para parecer um jogador real.

Há dois modos:
- **Sugestão**: o helper detecta a sílaba e exibe a palavra sugerida — o usuário digita manualmente.
- **Auto-Play**: o helper detecta a sílaba e digita automaticamente (Alt+Tab + keyboard.write + Enter).

> ⚠️ **Natureza do projeto**: é uma ferramenta de automação/"cheat" de um jogo casual, de uso pessoal e
> local. Não há backend remoto, usuários múltiplos, banco de dados nem deploy. Não há mais humanizador —
> a digitação é instantânea via `keyboard.write(word, delay=0)`.

## 2. Stack

| Camada | Tecnologia |
|---|---|
| Linguagem | Python 3.8+ |
| Web server | Flask (servindo em `127.0.0.1:5000`) |
| Front-end | HTML + CSS + JavaScript vanilla (sem build, sem framework) — em `templates/` e `static/` |
| OCR | **`libtesseract` in-process via `ctypes`** (`ocr_engine.py`, ~7ms/leitura) com fallback para `pytesseract` (subprocess). tessdata `eng` em `tessdata/` |
| Captura de tela | `mss` |
| Visão computacional | `opencv-python` (cv2) + `numpy` — máscaras de cor HSV para detectar "SUA VEZ" |
| Automação de input | `pyautogui` + `keyboard` (digitação/teclas) e `pynput` (listener de mouse para calibração) |
| Imagem | `Pillow` (PIL) |
| Persistência | Arquivos JSON locais (`presets.json`, `calibration_region.json`). **Não há banco de dados.** |

Dependências em [`requirements.txt`](requirements.txt).

## 3. Como rodar

```bash
pip install -r requirements.txt          # instalar deps Python
# Tesseract OCR precisa estar instalado no SO (ver README.md)
python main.py                            # inicia o Flask em http://127.0.0.1:5000
```

- Tesseract no Windows é procurado em `C:\Program Files\Tesseract-OCR\tesseract.exe`; senão usa o PATH. Lógica em [`screen_reader.py`](screen_reader.py) (topo do arquivo).
- Variável de ambiente opcional `WORDBOMB_API_TOKEN`: se definida, exige header `X-API-Token` nas rotas que mutam estado. Vazia (padrão) = sem auth.
- Hotkeys globais de reroll: **Insert** = alternativa mais curta, **Ctrl+R** = anterior. A digitação em andamento (auto-type) é abortada por `pyautogui.FAILSAFE` (mouse no canto superior-esquerdo) — não há mais hotkey de abort.

## 4. Como testar

Existe uma suíte `unittest` para regras de palavras, ciclo de sugestão, Recover, dicionário pessoal, treino, perfis, diagnóstico OCR e contratos HTTP:

```bash
python -m unittest discover -s tests -v
```

A integração com a tela do jogo e o teclado continua exigindo verificação manual:
- [`debug_typer.py`](debug_typer.py): simula a digitação com mocks de teclado/tempo para inspecionar a lógica de erros/typos sem mexer no teclado real. Rode com `python debug_typer.py`.
- [`scratch/debug_tzc.py`](scratch/debug_tzc.py): debug de processamento.
- Verificação de OCR / turn-detection é manual (ver `.artifacts/.../implementation_plan.artifact.md`).

Para ampliar a suíte, ver [`.claude/SKILLS/testing.md`](.claude/SKILLS/testing.md), conferindo instruções antigas contra o código atual.

## 5. Arquitetura (resumo)

Arquitetura em camadas inspirada em DDD/hexagonal, montada por injeção de dependências em
[`application/app_factory.py`](application/app_factory.py) (`create_app()` retorna um `AppContext`).

```
main.py
  └─ application/app_factory.create_app()  → AppContext (DI container)
        ├─ api/routes.py            (Flask Blueprint — camada de apresentação HTTP)
        ├─ application/             (serviços/casos de uso)
        │     ├─ word_service       orquestra: prompt → busca palavra → digita
        │     ├─ word_manager       (re-export de word_manager.py raiz)
        │     ├─ autoplay_state_service   config + logs thread-safe do auto-play
        │     ├─ preset_service     CRUD de presets
        │     └─ region_store       região de calibração (persistida em JSON)
        ├─ domain/word_selection.py (WordSelectionParams — dataclass do domínio)
        ├─ infrastructure/          (adaptadores externos)
        │     ├─ ocr/screen_reader  (re-export de screen_reader.py raiz)
        │     ├─ input/typer        (re-export de typer.py raiz)
        │     └─ repositories/presets_repository  (re-export, persistência JSON)
        └─ shared/                  (parsing, security/auth)
```

> ⚠️ **Pegadinha importante de estrutura**: a lógica pesada vive em arquivos na **raiz**
> (`word_manager.py`, `screen_reader.py`, `typer.py`). Os módulos dentro de
> `application/`, `infrastructure/ocr/`, `infrastructure/input/` são **shims que só re-exportam**
> esses arquivos da raiz (ex: `application/word_manager.py` faz `from word_manager import WordManager`).
> Isso só funciona porque o processo roda a partir da raiz do projeto (CWD = raiz). Ao editar a lógica,
> edite os arquivos da **raiz**, não os shims. Ver [`.claude/ARCHITECTURE.md`](.claude/ARCHITECTURE.md) e
> [`.claude/KNOWN_ISSUES.md`](.claude/KNOWN_ISSUES.md).

Fluxo Auto-Play detalhado em [`.claude/ARCHITECTURE.md`](.claude/ARCHITECTURE.md). API em [`.claude/API.md`](.claude/API.md).

## 6. Convenções e estilo

- **Idioma**: código/comentários misturam português e inglês. Comentários explicativos frequentemente em PT-BR. Nomes de função/variável em inglês. Mantenha o padrão do arquivo que você está editando.
- **Logging**: `logging` da stdlib, `logger = logging.getLogger(__name__)` no topo de cada módulo. Não use `print` em código de produção (os scripts utilitários usam `print`, tudo bem).
- **Thread-safety**: `WordManager` usa `threading.RLock`; `AutoplayStateService` usa locks separados para config e logs; `Typer` usa um `Lock` não-bloqueante (chamada duplicada de digitação é ignorada). Respeite isso ao mexer em estado compartilhado — o `ScreenReader` roda em thread daemon própria.
- **Parsing defensivo**: entradas vindas do front-end passam por `shared/parsing.py` (`to_int`, `to_float`, `to_bool`, `normalize_capture_region`). Nunca confie em tipos do JSON cru.
- **Sem novas dependências** sem necessidade clara — o projeto é propositalmente enxuto.
- **Listas de palavras** (`wordlists/*.txt`): uma palavra por linha, minúsculas, sem acentos removidos (acentos são tratados na normalização em runtime). Arquivo `Idioma.txt` = lista principal; `Idioma_sub.txt` = sublista (ex: `Português_palindromos.txt`).

## 7. Como criar novas funcionalidades

1. **Nova rota HTTP** → adicione no Blueprint em [`api/routes.py`](api/routes.py), use `@optional_auth_required` se mutar estado, e `json_or_empty()` para ler o corpo.
2. **Nova lógica de negócio** → coloque num serviço em `application/` e injete via `app_factory`. Não acople lógica à rota.
3. **Nova estratégia de seleção de palavra** → adicione no `get_word()` de [`word_manager.py`](word_manager.py) (bloco `if strategy == ...`) e no `<select id="strategy-select">` em [`templates/index.html`](templates/index.html).
4. **Novo campo de config do auto-play** → adicione em `AutoplayStateService.config` (default), em `update_from_payload`, propague em `word_service`, e crie o controle no front-end + `currentConfig` em [`static/js/app.js`](static/js/app.js).
5. **Novo idioma** → adicione `wordlists/Idioma.txt` (uma palavra/linha, minúsculas). É descoberto automaticamente por `WordManager.get_languages()`.

Detalhes e checklists em [`.claude/DEVELOPMENT_GUIDE.md`](.claude/DEVELOPMENT_GUIDE.md).

## 8. Erros conhecidos / armadilhas

Lista completa em [`.claude/KNOWN_ISSUES.md`](.claude/KNOWN_ISSUES.md). Os principais:
- **CWD-dependente**: OCR (`tessdata`), `calibration_region.json` e os shims de import assumem que o processo roda a partir da raiz do projeto. Rodar de outro diretório quebra.
- **Shims duplicados de presets_repository**: existe em `infrastructure/presets_repository.py` E `infrastructure/repositories/presets_repository.py` (um re-exporta o outro). Não duplique lógica.
- **overlay_manager.py removido**: o overlay vermelho hoje é HTML (`#calibration-overlay`). Qualquer import de `overlay_manager` vai quebrar — não recriar.
- **OCR frágil**: depende de cores HSV específicas (texto branco em fundo escuro). Mudança de tema do jogo pode quebrar a detecção.
- **OCR latência (RESOLVIDO)**: a lentidão (`ocr=1569ms`) era o **spawn de subprocess** do `pytesseract`, não o engine. Agora `ocr_engine.py` mantém o `libtesseract` vivo na RAM via ctypes (~7ms/leitura, estável). Fallback automático para subprocess se a DLL não carregar. Ver KNOWN_ISSUES (gotchas do ctypes). NÃO setar `user_defined_dpi`.
- **Humanizador removido**: `typer.py` não tem mais humanizador. Toda a configuração de wpm/error_rate/hesitation foi removida do backend e frontend. Não reintroduzir.
- **turn_off_misses=1**: intencionalmente agressivo — 1 frame sem keyword encerra o turno para evitar ler turno do adversário. Risco: raro frame ruído durante turno legítimo.

## 9. Fluxo de trabalho com este repo

1. Antes de codar: leia este arquivo + o doc relevante em `.claude/`.
2. Edite a **lógica na raiz**, não os shims.
3. Rode `python debug_typer.py` se mexer no `Typer`; teste manualmente o OCR/auto-play se mexer no `ScreenReader`.
4. **Conhecimento vivo**: ao descobrir algo não óbvio, atualize `.claude/` (e este arquivo se for estrutural). Nunca deixe conhecimento só na conversa.
5. Commits: o repo está em `main`. Só faça commit/push se o usuário pedir.

## 10. Mapa de documentação (`.claude/`)

| Arquivo | Conteúdo |
|---|---|
| [PROJECT_CONTEXT.md](.claude/PROJECT_CONTEXT.md) | Domínio, problema, usuário, glossário do jogo |
| [ARCHITECTURE.md](.claude/ARCHITECTURE.md) | Camadas, DI, fluxos (dados, auto-play, calibração) |
| [MODULES.md](.claude/MODULES.md) | Responsabilidade de cada módulo |
| [API.md](.claude/API.md) | Todas as rotas HTTP, payloads e respostas |
| [BUSINESS_RULES.md](.claude/BUSINESS_RULES.md) | Regras de seleção de palavra, estratégias, humanização |
| [DATABASE.md](.claude/DATABASE.md) | Estado/persistência (não há DB; JSON + memória) |
| [DEPENDENCIES.md](.claude/DEPENDENCIES.md) | Cada dependência e por quê |
| [FILE_INDEX.md](.claude/FILE_INDEX.md) | Índice de todos os arquivos + dívida técnica |
| [GLOSSARY.md](.claude/GLOSSARY.md) | Termos do projeto e do jogo |
| [DEVELOPMENT_GUIDE.md](.claude/DEVELOPMENT_GUIDE.md) | Como estender, checklists |
| [KNOWN_ISSUES.md](.claude/KNOWN_ISSUES.md) | Bugs, armadilhas, dívida técnica |
| [DECISIONS.md](.claude/DECISIONS.md) | Decisões de arquitetura (ADR-lite) |
| [TODO.md](.claude/TODO.md) | Próximos passos sugeridos |
| [CHANGELOG_AI.md](.claude/CHANGELOG_AI.md) | Log de mudanças feitas por IA |
| [SKILLS/](.claude/SKILLS/) | Guias por domínio (backend, frontend, ocr, ...) |
| [`tools/`](tools/) | Scripts Python auxiliares (OCR, stats, deps) |
