# DECISIONS — Decisões de Arquitetura (ADR-lite)

Decisões inferidas do código (não documentadas formalmente antes). Formato: contexto → decisão → consequência.

## ADR-001 — Ferramenta local, sem backend remoto/DB
- **Contexto**: uso pessoal, single-user, automação de um jogo.
- **Decisão**: Flask local em `127.0.0.1:5000`, persistência só em JSON/TXT.
- **Consequência**: simplicidade máxima; nada de auth real, deploy ou DB. Auth é "opcional" via token de ambiente.

## ADR-002 — Camadas DDD/hexagonal com DI manual
- **Contexto**: dar estrutura clara mesmo num app pequeno.
- **Decisão**: `create_app()` como composition root devolvendo `AppContext`; serviços em `application/`, adaptadores em `infrastructure/`.
- **Consequência**: testável e desacoplado em tese; mas a lógica real ficou na raiz e os pacotes viraram shims (ADR-003).

## ADR-003 — Lógica pesada na raiz + shims de re-export
- **Contexto**: arquivos históricos (`word_manager.py`, `screen_reader.py`, `typer.py`) já na raiz; quis-se uma fachada arquitetural.
- **Decisão**: manter a lógica na raiz e criar shims que re-exportam dentro dos pacotes.
- **Consequência**: imports "bonitos" (`from infrastructure.ocr.screen_reader import ...`) mas acoplamento ao CWD e confusão sobre "onde editar". (Dívida — ver KNOWN_ISSUES.)

## ADR-004 — Visão computacional (cor HSV) + OCR para detectar turno
- **Contexto**: o jogo não expõe API; precisa "ver" a tela.
- **Decisão**: máscaras HSV das cores do botão "SUA VEZ" como sinal primário e OCR (Tesseract) como confirmação/extração de sílaba; streaks de confirmação + frame-hash cache p/ performance.
- **Consequência**: rápido e razoavelmente robusto, mas frágil a mudanças de tema do jogo.

## ADR-005 — Humanização agressiva da digitação
- **Contexto**: evitar detecção de bot pelo jogo.
- **Decisão**: simular WPM variável, drift/bursts, typos QWERTY, hesitações, late errors, full retry, delayed type.
- **Consequência**: digitação convincente; código do `Typer` complexo. Verificação por `debug_typer.py` (mocks).

## ADR-006 — Config compartilhada entre Manual e Auto-Play
- **Contexto**: evitar dois conjuntos de parâmetros.
- **Decisão**: `AutoplayStateService.config` é a fonte única; o front sincroniza via `/api/autoplay/config` (debounced).
- **Consequência**: simplicidade; mas o nome "autoplay" engana (também governa o manual).

## ADR-007 — Overlay de calibração em HTML (Tk removido)
- **Contexto**: Tkinter dava `TclError`/instabilidade de thread.
- **Decisão**: trocar a janela Tk por overlay HTML (`#calibration-overlay`) + cliques via `/api/calibration/click` e/ou listener pynput.
- **Consequência**: estável; `overlay_manager.py` virou shim vazio; README ficou desatualizado.

## ADR-008 — Sem versões fixas em `requirements.txt`
- **Contexto**: projeto enxuto, ambiente único.
- **Decisão**: listar só nomes de pacotes.
- **Consequência**: instalação simples; risco de breaking changes em upgrades (dívida).
