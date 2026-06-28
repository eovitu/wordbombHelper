# PROJECT_CONTEXT — Domínio do Negócio

## O que o projeto faz
Assistente local para o jogo **WordBomb** (jogo de navegador, ex: jklm.fun). No WordBomb, cada
jogador recebe uma **sílaba/prompt** (ex: `nfl`, `est`, `ção`) e precisa digitar, dentro de um tempo
limite (a "bomba" explode), uma palavra válida do idioma que **contenha** essa sílaba. Quem não
consegue perde uma vida.

O helper:
1. Mantém **listas de palavras** por idioma (`wordlists/`).
2. Dada uma sílaba, **encontra** uma palavra que a contém, respeitando filtros e estratégias.
3. Opcionalmente **digita** a palavra no jogo simulando um humano (anti-detecção).
4. No modo **Auto-Play**, lê a tela via OCR, detecta a vez do jogador ("SUA VEZ") e faz tudo sozinho.

## Quem usa
Um único usuário, na própria máquina (uso pessoal). Não há multiusuário, contas nem servidor remoto.
O dono do repo (git user `eovitu`) usa para jogar WordBomb, principalmente em **Português**.

## Qual problema resolve
"Achar rápido uma palavra com a sílaba dada e digitá-la antes do tempo, parecendo um jogador humano."
O diferencial em relação a um simples dicionário é a **humanização da digitação** (WPM variável, typos
realistas, hesitações, retries) e o **modo automático por visão computacional**.

## Principais módulos (visão de domínio)
- **Seleção de palavra** — `word_manager.py` (`WordManager`): carrega listas, filtra, aplica estratégia.
- **Humanização de digitação** — `typer.py` (`Typer`): simula digitação humana.
- **Percepção (OCR/visão)** — `screen_reader.py` (`ScreenReader`): lê a tela, detecta "SUA VEZ" e a sílaba.
- **Orquestração** — `application/word_service.py` (`WordService`): liga sílaba → palavra → digitação.
- **Estado do auto-play** — `application/autoplay_state_service.py`: config + logs.
- **Apresentação** — Flask (`api/routes.py`) + front-end (`templates/`, `static/`).

## Entidades e relações
- **Idioma (Language)** → tem 1 lista principal e N **Sublistas** (ex: palíndromos).
- **Palavra (Word)** → pertence a um idioma; pode estar "usada" (`used_words`) na partida atual.
- **Prompt/Sílaba** → string curta lida do jogo ou digitada; usada para filtrar palavras.
- **Config (AutoplayState)** → parâmetros de busca + humanização; compartilhada entre Manual e Auto-Play.
- **Preset** → uma Config nomeada, salva em `presets.json`.
- **Região de calibração (Region)** → retângulo da tela a capturar; salvo em `calibration_region.json`.

## Fluxo da aplicação (alto nível)
1. Usuário roda `python main.py` → Flask em `127.0.0.1:5000`.
2. Abre o navegador no helper → 3 abas: **Manual**, **Auto-Play**, **Config**.
3. **Config**: escolhe idioma, estratégia, WPM, taxas de erro, filtros; pode salvar/carregar presets.
4. **Manual**: digita a sílaba + Enter → recebe palavra (e digita no jogo se `auto_type`/`Simulate Typing` ligado).
5. **Auto-Play**: calibra a região (cliques marcando o retângulo do prompt + "SUA VEZ"), ativa o watcher; o
   `ScreenReader` lê a tela em loop e dispara a busca+digitação quando é a vez do jogador.

Ver regras detalhadas em [BUSINESS_RULES.md](BUSINESS_RULES.md) e fluxos em [ARCHITECTURE.md](ARCHITECTURE.md).
