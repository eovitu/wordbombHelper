# WordBomb Helper 💣

Ferramenta para ajudar no jogo WordBomb. Encontra palavras que contêm a sílaba do prompt automaticamente.

## Instalação

### Pré-requisitos

1. **Python 3.8+** instalado
2. **Tesseract OCR** instalado no sistema
   - **Windows**: Instale em `C:\Program Files\Tesseract-OCR\` (Baixe em: https://github.com/UB-Mannheim/tesseract/wiki)
   - **Linux**: `sudo apt install tesseract-ocr tesseract-ocr-por`
   - Certifique-se de que o idioma **Português** está instalado para maior precisão.

### Instalando dependências

```bash
pip install -r requirements.txt
```

### Rodando o app

```bash
python main.py
```

Acesse **http://localhost:5000** no navegador.

---

## Como Usar

### Modo Manual (aba "Manual")

1. O jogo mostra um prompt (ex: `nfl`)
2. Você digita o prompt no campo de texto do helper
3. Aperta **Enter**
4. O helper mostra uma palavra que contém essa sílaba (ex: `inflamou`)
5. Se "Simulate Typing" estiver ligado na aba Config, ele digita automaticamente no jogo

### Aba Config

| Configuração | Descrição |
|---|---|
| **Language** | Idioma da lista de palavras (ex: Portuguese) |
| **Strategy** | Como escolher a palavra: Random, Shortest, Longest, Hyphens, Alphabetical |
| **Simulate Typing** | Se ligado, o helper digita a palavra no jogo via Alt+Tab (modo Manual) |
| **Speed (WPM)** | Velocidade de digitação em palavras por minuto |
| **Error Rate** | Porcentagem de erros simulados (para parecer mais humano) |
| **Min/Max Length** | Filtro de tamanho da palavra |

> [!IMPORTANT]
> As configurações da aba Config **também são usadas pelo Auto-Play**! Configure tudo antes de ativar.

---

## 🎮 Como Usar o Auto-Play (Passo a Passo)

O Auto-Play faz tudo sozinho: lê a tela do jogo, detecta quando é sua vez, encontra uma palavra e digita automaticamente.

### Passo 1: Configure

1. Abra a aba **Config**
2. Selecione o **idioma** correto (ex: Portuguese)
3. Ajuste a **velocidade (WPM)** — recomendo 150-300 para auto-play
4. Ajuste **Error Rate** se quiser parecer mais humano (0% = sem erros)
5. Escolha a **Strategy** que preferir

### Passo 2: Posicione o Overlay Vermelho

Quando você roda `python main.py`, uma **janela vermelha transparente** aparece na tela. Essa janela é o "olho" do auto-play — ela define a área que o programa vai ler.

1. **Redimensione** a janela vermelha para que ela cubra **exatamente** a área do jogo que contém:
   - O **prompt** (a sílaba, ex: `NFL`)
   - O texto **"SUA VEZ"** (que aparece embaixo do prompt quando é sua vez)
2. A moldura vermelha deve englobar **ambos** — prompt e "SUA VEZ"
3. Não precisa ser perfeito, mas quanto melhor o enquadramento, melhor a leitura

```
┌──────────────────────┐
│   ┌──────────────┐   │
│   │     NFL      │   │  ← Prompt
│   │   SUA VEZ    │   │  ← Indicador de vez
│   └──────────────┘   │
│  ▲ Moldura vermelha  │
└──────────────────────┘
```

### Passo 3: Ative o Auto-Play

1. Abra a aba **Auto-Play** no helper
2. Clique em **"Start Auto-Play"**
3. O status vai mudar para **"Watching"**
4. **Deixe a janela do jogo em foco** (o helper digita diretamente na janela ativa)

### Passo 4: Jogue!

O auto-play agora funciona assim:

1. 👀 **Lê a tela** continuamente na área da moldura vermelha
2. 🔍 **Procura "SUA VEZ"** no texto lido por OCR
3. ❌ Se **NÃO** encontra "SUA VEZ" → ignora e continua monitorando
4. ✅ Se **encontra "SUA VEZ"** → extrai o prompt (sílaba) do texto
5. 📝 **Busca uma palavra** na lista que contém essa sílaba
6. ⌨️ **Digita a palavra** e aperta Enter automaticamente
7. 🔄 **Re-verifica**: se "SUA VEZ" ainda aparece (palavra rejeitada), tenta outra palavra
8. Repete até "SUA VEZ" sumir (máximo 5 tentativas por rodada)

### Passo 5: Parar

- Clique em **"Stop Auto-Play"** na aba Auto-Play
- Ou feche o programa

---

## Dicas

- **Dois monitores**: Se você tem dois monitores, coloque o helper em um e o jogo no outro. A moldura vermelha precisa estar sobre a área do jogo.
- **Mesmo monitor**: O helper fica em background. A moldura vermelha fica por cima do jogo (always on top). O jogo deve estar por trás da moldura.
- **Reset Words**: Use o botão "Reset Used Words" na aba Manual quando começar uma nova partida, para que palavras já usadas possam ser usadas novamente.
- **Logs**: A aba Auto-Play mostra logs em tempo real do que o auto-play está fazendo.
- **OCR impreciso?**: Tente aumentar o tamanho da moldura vermelha ou ajustar o brilho/contraste da tela do jogo.

---

## Solução de Problemas

| Problema | Solução |
|---|---|
| "No word found" | Verifique se o idioma está correto na Config |
| Auto-play não detecta "SUA VEZ" | Aumente a moldura vermelha, certifique-se que cobre o texto |
| Digita na janela errada | A janela do jogo (Opera) precisa estar em foco |
| Tesseract não encontrado | Instale o Tesseract OCR e verifique o caminho em `screen_reader.py` |
| Palavras repetidas | Clique em "Reset Used Words" |
