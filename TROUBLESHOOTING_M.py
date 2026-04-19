#!/usr/bin/env python
"""
Diagnostics for Letter Link OCR issues, especially M detection
"""

print("""
╔════════════════════════════════════════════════════════════════╗
║          LETTER LINK OCR - TROUBLESHOOTING GUIDE              ║
╚════════════════════════════════════════════════════════════════╝

🔴 PROBLEMA: M está sendo lido errado (como W, N, H, etc.)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1️⃣  VERIFICAR CALIBRAÇÃO DO OVERLAY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

❌ ERRADO (overlay muito pequeno/grande):
   ┌────────────────┐
   │ D  S  I  P  U  │ ← Cobre parcialmente
   │ E  E  T  E  E  │
   └────────────────┘

✅ CORRETO (overlay alinhado perfeitamente):
   ┌──────────────────────┐
   │ D  S  I  P  U        │
   │ E  E  T  E  E        │ ← Incluir espaços em branco
   │ R  N  O  R  F        │
   │ E  V  V  L  R        │
   │ T  N  I  E  V        │
   └──────────────────────┘

CHECKLIST:
□ Overlay cobre TODO o grid (topo, fundo, esquerda, direita)
□ Não há células "cortadas" na borda
□ Cells têm tamanho consistente (~80-120px cada)
□ Espaço branco ao redor é incluído

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
2️⃣  POSSÍVEIS CULPADOS POR M NÃO SER LIDO
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Problema              │ Sintoma                  │ Solução
─────────────────────┼─────────────────────────┼──────────────────
Grid muito pequeno    │ M vira ".":confundido    │ Aumentar overlay
Célula desalinhada    │ M parcialmente cortado   │ Recalibrar overlay
Brightness baixa      │ M fica muito escuro      │ Verificar tela do jogo
Antialiasing jogo     │ M tem pixels fracos      │ Nada (limitação jogo)
Fonte fina do jogo    │ M naturalmente fina      │ Confiar no solver

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
3️⃣  COMO VERIFICAR O QUE TESSERACT RECEBEU
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Após executar "SOLVE GRID":
1. Vá para: debug_screenshots/
2. Procure por: cell_*_M.png (células que foram lidas como M)
3. Procure por: cell_*_UNCERTAIN.png (células que geraram dúvida)

Se vir cell_1_1_W.png mas deveria ser M:
→ OCR achou W, não M
→ Verifique a calibração do overlay

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
4️⃣  MELHORIAS IMPLEMENTADAS PARA M
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ Extra dilation para letras finas (M, W, P)
✅ CLAHE contrast enhancement
✅ Múltiplas tentativas OCR (PSM 6 → PSM 10)
✅ Morphological closing para preencher buracos
✅ Dilation vertical (1px height) para preservar estrutura fina

Se mesmo com isso ainda não ler M:
→ Problema é calibração do overlay
→ OU limitação da imagem do jogo

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
5️⃣  PRÓXIMOS PASSOS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. Reinicie Flask (com melhorias novas)
2. Recalibre o overlay CUIDADOSAMENTE
3. Execute SOLVE GRID (Alt+S)
4. Verifique logs e debug_screenshots/
5. Se M ainda não for lido:
   → Tire screenshot da célula M
   → Verifique se célula está clara/legível
   → Ajuste overlay se necessário

╔════════════════════════════════════════════════════════════════╗
║  Se problema persistir, pode ser limitação do Tesseract OCR   ║
║  Mas com calibração correta, deve ler 95%+ das letras!        ║
╚════════════════════════════════════════════════════════════════╝
""")
