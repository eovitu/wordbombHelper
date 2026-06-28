# BUSINESS_RULES — Regras de Negócio

Fonte: `word_manager.py` (`get_word`, `mark_used`), `typer.py`, `screen_reader.py`, `word_service.py`.

## 1. Seleção de palavra (`WordManager.get_word`)
Objetivo: dado um `prompt` (sílaba) ou `prefix`/`suffix`, devolver uma palavra do idioma que satisfaça
os critérios e não tenha sido usada.

Ordem de processamento:
1. **Resolve idioma** (`_resolve_language_name`): match exato → normalizado (sem acentos/case) → alias (`portuguese`→`portugues`). Carrega lista do disco se necessário (lazy).
2. **Sublista prioritária** (`priority_sublist`): se houver match na sublista, escolhe lá direto (ignora os demais filtros) — `random.choice`.
3. **Candidatos base**:
   - Se `prefix`/`suffix`: palavras que começam/terminam com eles.
   - Senão: palavras que **contêm** o `prompt`.
   - Filtro de comprimento (`min_len`/`max_len`) usa um índice por tamanho (`len_map`) para performance.
   - Sempre exclui `used_words`.
4. **Filtros adicionais** (cada um só aplica se não esvaziar a lista — "soft filter"):
   - `exclude_letters`: remove palavras que **começam** com letra excluída.
   - `starts_with_letters`: mantém só as que começam com letra permitida.
   - `finish_with_letters`: mantém só as que terminam com letra permitida.
   - `priority_min_len`/`priority_max_len`: faixa de comprimento "preferida".
   - `priority_letters`: pontua palavras pela quantidade dessas letras contidas; mantém só as de maior score.
5. **Estratégia** (escolha final):
   | Estratégia | Comportamento |
   |---|---|
   | `random` (default) | `random.choice` entre candidatos. |
   | `shortest` | menor comprimento. |
   | `longest` | maior comprimento. |
   | `hyphen` | prefere palavras com `-`; senão random. |
   | `alpha` | percorre o alfabeto: escolhe palavra começando com `current_alpha_char` e avança a→…→z→a. Se `starts_with_letters` ativo, não avança (retoma depois). Pula letras excluídas. |
   | `recover` | escolhe palavra que cobre as letras mais "necessitadas" (ver regra de cobertura abaixo). |

## 2. Palavras usadas e cobertura de letras
- `mark_used(word)`: adiciona ao set `used_words` (minúsculo). Toda palavra escolhida é marcada usada → não repete na partida.
- **Recover/cobertura**: mantém `letter_targets` (a–z, valor inicial = `recover_target`, default 2). Ao marcar palavra usada, decrementa a meta de cada letra única (sem acento) presente. Quando todas zeram, reseta o ciclo. A estratégia `recover` prioriza palavras cuja soma de metas remanescentes é maior — útil para jogar modo "use cada letra do alfabeto N vezes". `recover_exclude` tira letras do alvo (ex: `k,w,y`).
- `reset_used()`: limpa `used_words`, **recarrega listas do disco**, reseta ciclo alpha e cobertura. (Botão "Reset Used Words" / nova partida.)

## 3. Idiomas e listas
- Idioma descoberto por arquivo `wordlists/Idioma.txt` (sem `_`). Sublista = `Idioma_sub.txt`.
- Listas: 1 palavra por linha, minúsculas. Acentos preservados no arquivo; normalização (NFD) só em runtime para casar com metas a–z e nomes de idioma.
- Idiomas presentes: Alemão, Dinamarquês, Espanhol, Holandês, Inglês, Italiano, Norueguês, Polonês, Português (~248k palavras, principal), Russo, Sueco, Turco, jklm. Sublista: `Português_palindromos`.

## 4. Humanização da digitação (`Typer`) — anti-detecção
- **WPM** → delay base por caractere (`(wpm*5)/60` chars/s). `wpm >= 180` ativa **turbo** (pula pausas humanas).
- **Drift & bursts**: velocidade oscila; rajadas rápidas de 2–5 chars; pausas em letras difíceis (`qwzxkyh`), antes de maiúsculas/`'_`, e em clusters de consoantes.
- **Hesitação** (`hesitation_prob`): pausa no meio da palavra, mais provável no começo.
- **Typos** (`error_rate`, até `max_typos`): erro por proximidade QWERTY; 70% "fat finger" (digita certo+errado, apaga errado), 30% substituição (digita errado, apaga, digita certo).
- **Late errors** (`late_error_rate`, até `max_late_errors`): erra, digita mais 2–5 chars, "percebe", limpa o campo (Ctrl+A+Backspace) e redigita.
- **Full retry** (`retry_rate`): digita versão errada da palavra inteira, dá Enter, "percebe", limpa e redigita mais rápido/cuidadoso.
- **Delayed type** (`delayed_type`): spamma ruído + Enter por ~0,5–1s, depois digita a palavra mais devagar (engana timing).
- **add_period_prob**: chance de adicionar `.` ao fim.
- **Pré-Enter**: pausa proporcional ao comprimento da palavra.
- **Alt+Tab**: `auto_tab` (vai pro jogo antes), `return_tab` (volta ao browser depois). No auto-play o foco já está no jogo, então `auto_tab=False`.
- **Abort**: tecla **Insert** (hook global) ou `pyautogui.FAILSAFE` (mouse no canto).

## 5. Detecção de turno e sílaba (`ScreenReader`)
- **É minha vez (`is_my_turn`)**: muita cor de botão (amarelo/azul/vermelho > 8000 px) OU cor moderada (>2000) + keyword OCR (`VEZ/TURN/YOUR/SUA/VE2/UEZ`). Confirmado por streak ≥ 1.
- **Sílaba válida**: candidato OCR de 2–4 letras, confiança ≥55 (ou ≥35 com cor, ou cor+keyword), **não** sufixo da última palavra digitada (ghost protection). Precisa de streak ≥ 2 frames iguais.
- **Anti-flicker**: se a sílaba é igual à última sugerida, não recalcula.
- **Auto-type loop**: após digitar, recaptura; "SUA VEZ" sumiu = aceita; prompt mudou = aceita (solo); mesmo prompt = rejeitada → tenta outra (até `max_retries=5`).
- **auto_type OFF** (default): apenas sugere a palavra (preview no front), não digita.

## 6. Auth
- Sem `WORDBOMB_API_TOKEN`: todas as rotas abertas (uso local). Com token: rotas que mutam exigem `X-API-Token` igual.
