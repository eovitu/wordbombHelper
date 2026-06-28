# GLOSSARY — Termos do projeto e do jogo

| Termo | Significado |
|---|---|
| **WordBomb** | Jogo de navegador (jklm.fun). Recebe-se uma sílaba e há tempo limitado para digitar uma palavra que a contenha antes da "bomba" explodir. |
| **Prompt / Sílaba** | A string curta exigida (ex: `nfl`, `est`). A palavra resposta deve contê-la. |
| **"SUA VEZ" / "YOUR TURN"** | Indicador na tela de que é a vez do jogador. Detectado por cor (botão amarelo/azul/vermelho) + OCR. |
| **Helper** | Esta ferramenta (WordBomb Helper). |
| **Manual mode** | Usuário digita a sílaba no helper; recebe palavra (e digita no jogo se ativado). |
| **Auto-Play** | Helper lê a tela e joga sozinho via OCR + digitação. |
| **Calibração** | Definir o retângulo da tela a capturar (cobre prompt + "SUA VEZ"), por 2 cliques. |
| **Região (Region)** | Retângulo `{x1,y1,width,height}` capturado pelo `mss`. Persistido em `calibration_region.json`. |
| **Turn region / Prompt region** | Hoje são a mesma região unificada (calibração de 1 retângulo). |
| **Overlay** | Moldura visual de calibração. Hoje é HTML (`#calibration-overlay`); a versão Tk foi removida. |
| **Estratégia (Strategy)** | Como escolher entre palavras candidatas: `random/shortest/longest/hyphen/alpha/recover`. |
| **Sublista (Sublist)** | Lista secundária de um idioma, arquivo `Idioma_sub.txt` (ex: `Português_palindromos`). Prioritária se selecionada. |
| **Recover / cobertura** | Estratégia que prioriza palavras cobrindo letras "ainda necessárias" (metas a–z, `recover_target`). |
| **used_words** | Conjunto de palavras já usadas na partida (não repetir). Limpo por "Reset". |
| **WPM** | Words per minute — velocidade-alvo de digitação. ≥180 ativa "turbo". |
| **Typo / fat finger** | Erro de digitação simulado por proximidade no teclado QWERTY. |
| **Late error** | Erro percebido tarde: digita errado, segue alguns chars, limpa tudo e redigita. |
| **Full retry** | Digita a palavra inteira errada, dá Enter, "percebe", limpa e redigita. |
| **Delayed type** | Spamma ruído + Enter por ~1s e só então digita a palavra (engana timing). |
| **Hesitação / travadinha** | Pausa simulada no meio da palavra. |
| **Ghost prompt** | Falsa sílaba que é só sufixo da última palavra digitada; é descartada. |
| **Frame hash cache** | Pula o pipeline de OCR se a captura é byte-idêntica à anterior. |
| **Confirm streak** | Nº de frames consecutivos confirmando turno/sílaba antes de agir (anti-ruído). |
| **Turbo mode** | WPM≥180: pula pausas humanas para priorizar velocidade. |
| **Shim** | Módulo que só re-exporta outro (ex: `infrastructure/ocr/screen_reader.py`). |
| **AppContext** | Dataclass devolvida por `create_app()` com todas as dependências montadas (DI container). |
| **optional_auth_required** | Decorator de auth que só exige token se `WORDBOMB_API_TOKEN` estiver setado. |
