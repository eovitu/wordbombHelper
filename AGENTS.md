# WordBomb Helper — contexto do projeto

Este documento orienta quem trabalha neste repositório. Descreve o estado observado no código atual. Para detalhes históricos, consulte `CLAUDE.md` e `.claude/`, conferindo cada afirmação com a implementação antes de usá-la.

## Produto e uso

WordBomb Helper é uma aplicação local de uma pessoa para acompanhar uma partida de WordBomb no navegador. O jogo apresenta um **prompt** (sequência de letras que deve aparecer numa palavra) durante o turno. O helper captura a área calibrada da tela, reconhece `SUA VEZ` e o prompt, procura uma palavra nas listas por idioma e mostra uma sugestão para o jogador digitar. A interface atual tem uma única tela de observação e configuração; não há contas, banco de dados, serviço remoto nem processo de build do frontend.

O backend ainda oferece `/api/word` e digitação automática por `Typer`, mas a interface atual envia `auto_type: false` e foi desenhada para **sugerir** palavras. A digitação automática é um caminho disponível pela API/configuração, não o fluxo padrão da tela. `typer.py` usa `keyboard.write(..., delay=0)` e Enter; as descrições antigas de WPM, typos e hesitações não representam o código atual.

Há dois caminhos de leitura de tela:

1. **Prompt e turno (Pipeline A):** a região principal contém o prompt e o indicador de turno. O resultado alimenta a sugestão.
2. **Palavras já jogadas (Pipeline B):** uma região separada cobre o painel SOLVE da extensão Room Inspector. Um scanner opcional lê palavras válidas exibidas em verde e as marca como usadas, evitando sugeri-las novamente. Sem essa região ou sem OCR disponível, o scanner fica ocioso e a sugestão principal continua funcionando.

## Stack e execução

| Parte | Implementação e finalidade |
| --- | --- |
| Servidor local | Python + Flask em `main.py`; `application/app_factory.py` monta as dependências e registra a API. |
| Interface | Template HTML em `templates/index.html`, CSS em `static/css/style.css` e JavaScript puro em `static/js/app.js`. |
| Captura e imagem | `mss` captura regiões da tela; OpenCV e NumPy preparam as imagens. |
| OCR | `ocr_engine.py` usa `libtesseract` no processo via `ctypes`; `screen_reader.py` tem fallback para `pytesseract`. Os modelos `por` e `eng` ficam em `tessdata/`. |
| Entrada no sistema | `pynput` escuta cliques de calibração; `keyboard` registra atalhos e escreve palavras; `pyautogui` faz Alt+Tab no caminho manual de digitação. |
| Dados | `wordlists/*.txt` são dicionários; configurações de região, presets e registros de manutenção usam arquivos JSON locais. |
| Testes | `unittest` da biblioteca padrão em `tests/`, cobrindo montagem de prompt e casamento conservador de palavras lidas por OCR. |

As dependências Python estão em `requirements.txt`; Tesseract OCR também precisa estar instalado no sistema. Para executar a partir da raiz do repositório:

```powershell
python -m pip install -r requirements.txt
python main.py
```

Abra `http://127.0.0.1:5000`. `main.py` desliga debug/reloader e usa Flask com requisições em threads. A execução pressupõe desktop com acesso à tela e ao teclado; um ambiente sem interface gráfica não valida OCR e automação. Algumas rotinas usam o diretório de trabalho para localizar arquivos JSON, então execute da raiz. `WORDBOMB_API_TOKEN` é opcional: quando definido, as rotas mutáveis exigem o header `X-API-Token`; sem ele, a API local fica aberta. `WORDBOMB_LOG_LEVEL`, `WORDBOMB_OCR_DEBUG` e `WORDBOMB_PROMPT_TRACE` controlam diagnóstico.

## Fluxo atual da aplicação

1. `main.py` configura logging e chama `create_app()`. A factory instancia `WordManager`, `ScreenReader`, `WordService`, `AutoplayStateService`, `Typer`, os stores e o scanner do painel SOLVE. Liga callbacks e registra o Blueprint de `api/routes.py`.
2. O usuário abre a página, escolhe idioma, sublista, estratégia e filtros, calibra a região do prompt e inicia a observação. Opcionalmente calibra o painel SOLVE. A configuração da tela é enviada para `/api/autoplay/config` com debounce.
3. `ScreenReader` captura a região principal numa thread. Ele prepara texto branco, faz OCR, detecta o turno pela leitura de `SUA VEZ`/equivalentes e confirma o prompt. Cache de frame e uma trava temporal evitam leituras repetidas ou mudanças por ruído.
4. Ao confirmar um prompt, `WordService.on_prompt_found()` pede candidatos ao `WordManager` e cria uma `SuggestionSession` provisória. A palavra exibida só é marcada como usada quando o turno termina. Insert escolhe a alternativa mais curta; Ctrl+R volta; Delete rejeita a palavra atual. Correção manual ignora a leitura errada anterior e libera o próximo prompt após confirmação estável.
5. A UI recebe palavra, prompt e status por `/api/stream` (SSE). `/api/autoplay/status` é consultado a cada segundo para logs, calibração, contagens e como fallback se a conexão SSE falhar.
6. O scanner opcional do painel SOLVE roda em thread e OCR próprios. Ele só considera texto verde e consulta `WordManager.resolve_played_ocr()`; resultados ambíguos não são marcados. No início de um turno, o fluxo principal pode pedir uma varredura imediata com espera limitada a 180 ms.

`WordManager` carrega listas por idioma, filtra por prompt/comprimento e por preferências de letras, depois escolhe por `random`, `shortest`, `longest`, `hyphen`, `alpha` ou `recover`. Alguns filtros são **preferenciais**: se eliminariam todos os candidatos, o conjunto anterior é mantido. Uma sublista prioritária com resultados usa sua própria seleção e ignora os filtros adicionais. Confira essa regra antes de prometer que um filtro é obrigatório.

## Mapa do código

| Caminho | Responsabilidade |
| --- | --- |
| `api/routes.py` | Rotas HTTP de idiomas, palavra, reset, calibração, observação, SSE, reroll, exportações e presets. |
| `application/word_service.py` | Orquestra busca, sessão provisória, confirmação ao fim do turno e digitação opcional. |
| `application/personal_dictionary.py` | Mantém listas pessoais por idioma, importação e undo com escrita atômica. |
| `application/practice_service.py`, `application/match_summary.py` | Treino offline e resumo de eventos confirmados da partida. |
| `application/calibration_profiles.py` | Persiste perfis com as regiões de prompt e painel SOLVE. |
| `application/autoplay_state_service.py` | Configuração e logs compartilhados com locks. |
| `word_manager.py` | Leitura das listas, índices, filtros, estratégias, palavras usadas e casamento das leituras do painel SOLVE. |
| `screen_reader.py` | Captura, OCR do prompt/turno, estado temporal, loop de observação e calibração. |
| `ocr_engine.py` | Acesso ao Tesseract pela biblioteca nativa. |
| `used_word_scanner.py` | OCR e aprendizagem opcional das palavras válidas do painel SOLVE. |
| `typer.py` | Digitação instantânea opcional; executa numa thread e impede chamadas simultâneas. |
| `application/region_store.py`, `application/missing_prompts_store.py` | Persistência local de regiões e registros de manutenção. |
| `infrastructure/presets_repository.py` | Leitura e escrita dos presets JSON. |
| `shared/` | Parsing de entradas, autenticação opcional e logging. |

Os módulos `application/word_manager.py`, `infrastructure/ocr/screen_reader.py`, `infrastructure/input/typer.py` e `infrastructure/repositories/presets_repository.py` apenas reexportam implementações. Edite a implementação real indicada na tabela. A interface não expõe todos os endpoints do backend: `/api/word` e presets continuam disponíveis para clientes diretos.

## Estado, persistência e manutenção

- `wordlists/Idioma.txt` é a lista principal, `wordlists/Idioma_sub.txt` é uma sublista e `personal_wordlists/Idioma.txt` guarda palavras pessoais; há uma palavra por linha. As listas principal e pessoal participam juntas da busca.
- O painel SOLVE marca palavras conhecidas e adiciona leituras desconhecidas estáveis no topo da lista pessoal para revisão. `Delete` remove permanentemente a sugestão dos arquivos do idioma ativo.
- `used_words`, sessão de reroll, configuração ativa e logs vivem em memória. `/api/reset` limpa palavras usadas, recarrega listas e limpa o estado aprendido do scanner. O registro de prompts sem palavra é preservado para manutenção.
- `calibration_region.json` guarda a região principal; `solve_region.json`, a do painel SOLVE; `presets.json`, os presets; `missing_prompts.json` e `ambiguous_ocr.json`, registros para revisão. Esses arquivos são estado local gerado em execução e estão no `.gitignore`.
- `logs/wordbomb.log` registra diagnósticos. Evite testar o OCR ou a digitação contra o teclado real durante uma simples revisão de código.

## Verificação e fontes de verdade

Para a lógica coberta sem tela nem teclado, rode `python -m unittest discover -s tests -v`. Mudanças em OCR ou foco de janela exigem validação manual com o jogo e com a região calibrada; os testes atuais não provam esse fluxo completo. Ao documentar comportamento, priorize código e testes atuais. `CLAUDE.md`, `README.md` e vários arquivos de `.claude/` ainda contêm descrições de versões anteriores, como três abas, overlay Tk, OCR por botões coloridos, digitação humanizada e ausência de testes. O plano em `.artifacts/` também é histórico.

## Divisão de trabalho entre agentes

Em tarefas com frentes independentes, divida a investigação ou implementação entre subagentes para reduzir tempo e custo. Prefira modelos menores em subtarefas limitadas, como inventariar rotas, revisar documentação ou validar um módulo isolado. Dê a cada agente um objetivo verificável, os arquivos de interesse e um limite de escopo; consolide as conclusões contra o código antes de aplicá-las. Como os agentes compartilham o mesmo diretório, atribua arquivos distintos para edição simultânea e preserve todas as alterações locais. Para uma tarefa curta ou sequencial, trabalhe diretamente: a coordenação também tem custo.

Antes de editar, confira `git status` e preserve alterações locais. Para mudanças de API, leia `api/routes.py` e os consumidores em `static/js/app.js`; para seleção de palavras, leia `word_manager.py` e os testes; para OCR, leia `screen_reader.py`, `ocr_engine.py` e `used_word_scanner.py`. Atualize o documento de domínio pertinente quando uma mudança tornar a documentação incorreta. Faça commits somente quando solicitados e sempre sem trailer `Co-authored-by`.
