# WordBomb Helper

Aplicação local que observa uma partida de WordBomb, reconhece o prompt por OCR e mostra uma palavra válida para você digitar. Também acompanha palavras usadas, mantém um dicionário pessoal, oferece treino offline e ferramentas para revisar o OCR.

O helper roda somente no seu computador. Não exige conta, banco de dados, serviço remoto nem instalação do frontend.

## Sumário

- [Instalação](#instalação)
- [Iniciar e encerrar](#iniciar-e-encerrar)
- [Primeira configuração](#primeira-configuração)
- [Como jogar](#como-jogar)
- [Atalhos](#atalhos)
- [Estratégias e filtros](#estratégias-e-filtros)
- [Recover](#recover)
- [Dicionário pessoal](#dicionário-pessoal)
- [Painel SOLVE](#painel-solve)
- [Diagnóstico OCR](#diagnóstico-ocr)
- [Perfis de calibração](#perfis-de-calibração)
- [Treino offline](#treino-offline)
- [Resumo e reset](#resumo-e-reset)
- [Tela compacta e janela flutuante](#tela-compacta-e-janela-flutuante)
- [Arquivos locais](#arquivos-locais)
- [Testes](#testes)
- [Problemas comuns](#problemas-comuns)
- [Desinstalação](#desinstalação)

## Como funciona

O fluxo principal é:

1. Capturar uma região da tela escolhida por você.
2. Procurar o indicador `SUA VEZ` e o prompt.
3. Pesquisar palavras que contêm o prompt nas listas do idioma.
4. Mostrar uma sugestão com as letras pedidas destacadas.
5. Confirmar a palavra como usada quando o turno termina.

Por padrão, a interface apenas **sugere** palavras. Ela usa `auto_type: false`, então não digita automaticamente no jogo. O backend ainda aceita digitação automática para clientes diretos da API, mas esse não é o fluxo normal da tela.

Existem duas leituras independentes:

- **Prompt e turno:** região que contém o prompt e `SUA VEZ`.
- **Painel SOLVE:** região opcional da extensão Room Inspector, usada para reconhecer palavras válidas em verde.

## Instalação

### Windows

1. Instale uma versão recente do Python 3. A versão verificada atualmente é Python 3.13.
2. Instale o Tesseract OCR em `C:\Program Files\Tesseract-OCR\` ou disponibilize-o no `PATH`.
3. Abra o PowerShell na pasta do projeto.
4. Crie o ambiente virtual e instale as dependências:

```powershell
cd "C:\Users\vitu\Downloads\voltando a velha epoca\wordbombHelper"
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Os modelos `por` e `eng` estão em `tessdata/`. Se quiser ativar o ambiente no terminal, use `.\.venv\Scripts\Activate.ps1`. Isso é opcional porque os exemplos chamam diretamente o Python da `.venv`.

### Linux

Em Debian ou Ubuntu:

```bash
sudo apt install python3 python3-venv tesseract-ocr tesseract-ocr-por tesseract-ocr-eng
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Captura de tela e atalhos globais podem variar entre X11 e Wayland.

## Iniciar e encerrar

Na raiz do projeto:

```powershell
.\.venv\Scripts\python.exe main.py
```

Abra [http://127.0.0.1:5000](http://127.0.0.1:5000). Mantenha o terminal aberto. Para encerrar, volte ao terminal e pressione `Ctrl+C`.

## Primeira configuração

### Idioma e sublista

Selecione o idioma da partida. Os idiomas são descobertos pelos arquivos em `wordlists/`. Se houver uma sublista para o idioma, o seletor **Sublista** aparecerá.

Uma sublista prioritária com resultados usa sua própria seleção. Nesse caso, filtros adicionais não são aplicados da mesma forma que na lista principal.

### Calibrar prompt e turno

1. Deixe o jogo visível.
2. Clique em **Calibrar**.
3. Clique no canto superior esquerdo da região que contém o prompt e `SUA VEZ`.
4. Clique no canto inferior direito da mesma região.

Escolha uma região pequena que contenha completamente esses elementos. Evite chat, placar e outros textos variáveis.

### Calibrar painel SOLVE

Esta etapa é opcional e depende do painel SOLVE da extensão Room Inspector.

1. Clique em **Calibrar painel SOLVE**.
2. Marque os cantos superior esquerdo e inferior direito do painel.

Sem essa região, a sugestão principal continua funcionando normalmente.

## Como jogar

1. Selecione idioma, estratégia e filtros.
2. Clique em **Iniciar**.
3. Quando o programa reconhecer seu turno, digite no jogo a palavra sugerida.
4. Quando o prompt desaparecer, a palavra que estava exibida será confirmada como usada.

Durante o turno:

- **Próxima** avança pelas alternativas;
- a seta para a esquerda volta uma alternativa;
- **Mais curta** escolhe a menor alternativa disponível;
- **Esta palavra não serve** rejeita a palavra durante a partida;
- o campo de correção substitui uma sílaba lida incorretamente.

Uma palavra apenas exibida ainda não é consumida. Isso evita perder palavras quando o OCR lê o prompt errado.

## Atalhos

| Tecla | Ação |
| --- | --- |
| `Insert` | Escolhe a alternativa mais curta da sessão atual. |
| `Ctrl+R` | Volta para a sugestão anterior. |
| `Delete` | Remove permanentemente a palavra atual do dicionário. |
| `Esc` | Fecha o aviso de calibração quando a página está em foco. |
| `Ctrl+C` | Encerra o servidor quando usado no terminal. |

Em teclados 75%, `Insert` pode exigir `Fn`. O botão **Mais curta** executa a mesma ação. Os atalhos ainda não são configuráveis pela interface.

## Estratégias e filtros

| Estratégia | Comportamento |
| --- | --- |
| Aleatória | Escolhe entre os candidatos disponíveis. |
| Mais curta | Prioriza palavras menores. |
| Mais longa | Prioriza palavras maiores. |
| Alfabética | Usa ordem alfabética. |
| Recover | Prioriza letras necessárias para recuperar vida. |

Filtros disponíveis:

- **contém:** prefere palavras que contenham o texto;
- **começa com:** prefere palavras iniciadas pelo texto;
- **termina com:** prefere palavras terminadas pelo texto;
- **exclui:** prefere palavras sem os caracteres;
- **tamanho:** define mínimo e máximo.

Alguns filtros de letras são preferenciais. Se eliminariam todos os candidatos, o programa mantém o conjunto anterior para não deixar você sem sugestão.

## Recover

Recover acompanha quantas vezes cada letra ainda precisa aparecer nas suas palavras confirmadas. `K`, `W` e `Y` são ignoradas automaticamente.

### Casual

- primeiro ciclo: 1 ocorrência por letra;
- ciclos seguintes: 2 ocorrências por letra, permanentemente.

### Ranked

- primeiro ciclo: 3 ocorrências;
- segundo ciclo: 4;
- terceiro ciclo e seguintes: 5.

O campo de exclusão permite ignorar outras letras. A tela mostra modo, ciclo, alvo e letras restantes.

Somente palavras que você efetivamente jogou avançam o Recover. Palavras dos adversários vistas no SOLVE ficam indisponíveis, mas não contam como progresso pessoal.

## Dicionário pessoal

Abra **Manutenção do dicionário**. As palavras pessoais ficam em arquivos separados das listas originais, mas participam juntas das buscas.

### Adicionar, editar e apagar

- Digite uma palavra ou cole várias separadas por espaços e clique em **Adicionar**.
- Use os controles de cada palavra para editar ou apagar.
- Essas operações não alteram `wordlists/`.

### Importar e desfazer

1. Cole palavras separadas por espaços ou quebras de linha.
2. Clique em **Pré-visualizar**.
3. Confira novas, duplicadas e inválidas.
4. Clique em **Aplicar importação**.

**Desfazer última alteração** restaura o estado anterior ao último lote ou edição. O undo mais recente continua disponível depois de reiniciar.

## Painel SOLVE

Com o painel calibrado, o scanner:

1. isola textos verdes, que representam respostas válidas;
2. tenta casar a leitura com os dicionários;
3. marca palavras conhecidas como indisponíveis;
4. adiciona palavras desconhecidas estáveis no topo da lista pessoal para revisão manual.

O badge mostra quantas palavras foram aprendidas. Leituras ambíguas não são marcadas e aparecem no log **OCR ambíguo** para revisão e exportação.

## Diagnóstico OCR

Abra **Diagnóstico OCR e calibração**.

- **Atualizar imagem:** mostra a captura processada mais recente.
- **Reprocessar leitura:** guarda imagem e metadados do caso para diagnóstico.
- **Corrigir sílaba lida:** substitui manualmente o prompt incerto sem consumir a sugestão errada.

Os casos ficam em `debug_screenshots/` e o histórico é limitado.

Para diagnóstico avançado, antes de iniciar:

```powershell
$env:WORDBOMB_LOG_LEVEL = "DEBUG"
$env:WORDBOMB_OCR_DEBUG = "1"
$env:WORDBOMB_PROMPT_TRACE = "1"
.\.venv\Scripts\python.exe main.py
```

Depois, remova as variáveis:

```powershell
Remove-Item Env:WORDBOMB_LOG_LEVEL -ErrorAction SilentlyContinue
Remove-Item Env:WORDBOMB_OCR_DEBUG -ErrorAction SilentlyContinue
Remove-Item Env:WORDBOMB_PROMPT_TRACE -ErrorAction SilentlyContinue
```

## Perfis de calibração

Depois de calibrar as regiões:

1. Abra **Diagnóstico OCR e calibração**.
2. Informe um nome, como `Monitor principal`.
3. Clique em **Salvar**.

O perfil guarda as regiões de prompt e SOLVE. Ele pode ser ativado ou excluído, e o perfil ativo é restaurado na inicialização seguinte.

## Treino offline

Abra **Treino offline**. O treino não altera palavras usadas, rejeições ou Recover da partida.

1. Escolha **Normal** ou **Com dicas**.
2. Clique em **Nova rodada**.
3. Informe uma palavra que contenha o prompt.
4. Clique em **Conferir**.

As dicas mostram progressivamente tamanho, primeira letra e resposta. Erros e respostas corretas muito lentas aumentam o peso desses prompts nas rodadas futuras.

## Resumo e reset

Abra **Resumo da partida** para ver palavras jogadas, aprendidas, rejeitadas e prompts sem resposta. Sugestões apenas exibidas não entram como jogadas.

Use **Reset** ao começar outra partida. Ele:

- libera novamente as palavras usadas; rejeições já foram removidas permanentemente;
- encerra a sessão atual;
- reinicia Recover;
- limpa o aprendizado da partida;
- preserva registros de manutenção;
- mantém o resumo da partida anterior na interface.

O reset automático ainda não está ativo. A ausência de `SUA VEZ` também acontece durante turnos dos adversários, então é necessário um sinal confiável de fim de partida.

## Tela compacta e janela flutuante

- **Tela compacta:** reduz a página aos elementos necessários durante o jogo e guarda a preferência no navegador.
- **Janela flutuante:** abre uma janela pequena e redimensionável com a visão compacta.

Posicione a janela fora da área calibrada. Caso o navegador bloqueie a abertura, permita popups para `127.0.0.1`.

## Logs e manutenção

Na parte inferior da página:

- o log principal mostra eventos recentes;
- **Palavras aprendidas** mostra palavras observadas dos adversários;
- **Prompts sem palavra** permite exportar e limpar sílabas sem candidato;
- **OCR ambíguo** permite exportar leituras não resolvidas.

Diagnósticos completos ficam em `logs/wordbomb.log`.

## Arquivos locais

| Caminho | Conteúdo | Consequência ao apagar |
| --- | --- | --- |
| `calibration_region.json` | Região principal. | Será necessário calibrar novamente. |
| `solve_region.json` | Região SOLVE. | Será necessário calibrar novamente. |
| `calibration_profiles.json` | Perfis salvos. | Os perfis serão perdidos. |
| `presets.json` | Presets da API. | Os presets serão perdidos. |
| `personal_wordlists/` | Palavras pessoais e undo. | As palavras pessoais serão perdidas. |
| `missing_prompts.json` | Prompts sem resposta. | O histórico será perdido. |
| `ambiguous_ocr.json` | Leituras ambíguas. | O histórico será perdido. |
| `debug_screenshots/` | Casos de OCR. | Somente diagnósticos serão perdidos. |
| `logs/` | Logs. | Somente logs serão perdidos. |

Faça backup de `personal_wordlists/` e `calibration_profiles.json` antes de reinstalar se quiser manter seus dados.

## Token opcional da API

Para proteger rotas mutáveis de integrações próprias:

```powershell
$env:WORDBOMB_API_TOKEN = "seu-token-local"
.\.venv\Scripts\python.exe main.py
```

Clientes diretos devem enviar `X-API-Token`. A interface não possui campo para esse token; ativá-lo impedirá os controles mutáveis da página, portanto use apenas em integrações próprias.

## Testes

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m compileall -q .
node --check static\js\app.js
```

O comando do Node é opcional para uso comum. Testes automatizados não reproduzem resolução, escala, tema e cores reais do jogo.

## Problemas comuns

| Problema | Ação |
| --- | --- |
| Página não abre | Confirme que `main.py` está rodando e use `http://127.0.0.1:5000`. |
| Porta 5000 ocupada | Encerre a outra execução antes de iniciar novamente. |
| Tesseract não encontrado | Instale no caminho padrão ou adicione ao `PATH`. |
| Não detecta `SUA VEZ` | Recalibre uma região menor contendo prompt e indicador. |
| Prompt errado | Corrija manualmente e salve o caso em **Reprocessar leitura**. |
| Idioma errado | Selecione o idioma antes de iniciar. |
| Palavra volta a aparecer | Confira se o turno terminou e se o SOLVE está calibrado. |
| Palavra válida ausente | Adicione ao dicionário pessoal. |
| Janela flutuante bloqueada | Permita popups locais no navegador. |
| `Insert` não funciona | Tente `Fn+Insert` ou use **Mais curta**. |
| Atalho interfere em outro programa | Encerre o helper com `Ctrl+C`. |
| OCR lento | Reduza a região e confira `logs/wordbomb.log`. |
| Página parece antiga | Atualize com `Ctrl+F5`. |

## Desinstalação

### Remover somente as dependências locais

Encerre o servidor e apague `.venv`:

```powershell
Remove-Item -LiteralPath ".venv" -Recurse -Force
```

Isso preserva Python, Tesseract, dicionários e configurações.

### Remover configurações e dados pessoais

Faça backup de `personal_wordlists/` se necessário. Com o programa fechado:

```powershell
Remove-Item -LiteralPath "personal_wordlists" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath "debug_screenshots" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath "logs" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath "calibration_region.json", "solve_region.json", "calibration_profiles.json", "presets.json", "missing_prompts.json", "ambiguous_ocr.json" -Force -ErrorAction SilentlyContinue
```

### Remover tudo

1. Encerre com `Ctrl+C`.
2. Feche as janelas do helper.
3. Faça backup dos dados desejados.
4. Apague a pasta `wordbombHelper` pelo Explorador de Arquivos.
5. Desinstale Python e Tesseract em **Aplicativos instalados** somente se nenhum outro projeto depender deles.

## Limitações atuais

- O reset entre partidas é manual até existir um sinal confiável de término.
- A estratégia adaptativa por velocidade da bomba está isolada e testada, mas não é aplicada sem uma medida confiável de pressão.
- O OCR pode precisar de nova calibração após mudar resolução, escala, monitor ou tema.
- O aprendizado SOLVE depende da extensão Room Inspector, de texto verde legível e de leituras repetidas.
