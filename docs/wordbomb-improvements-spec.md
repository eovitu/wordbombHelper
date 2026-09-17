# Melhorias aprovadas para o WordBomb Helper

Esta especificação reúne as escolhas feitas na conversa de 2026-09-16. O código atual é a referência para nomes e contratos; o comportamento de produto abaixo prevalece quando difere do código.

## Comportamento central

- A tela principal continua voltada a sugestões. Exibir o prompt dentro da palavra com destaque, contador distinto de candidatos e posição da sugestão, aviso visual para OCR incerto e layout compacto opcional.
- Insert e o botão equivalente procuram a próxima alternativa curta; Ctrl+R continua voltando. A interface apresenta o mapa completo dos atalhos e permite configurá-los quando houver um mecanismo seguro de persistência.
- A primeira sugestão exibida não deve ser perdida por uma leitura errada do prompt. Uma correção manual descarta a sugestão incorreta e recalcula. O desaparecimento de `SUA VEZ` não confirma acerto: uma palavra verde nova do SOLVE associada ao prompt confirma a palavra efetivamente jogada. Sem essa confirmação, a sugestão e o Recover são preservados. O usuário pode marcar uma palavra como rejeitada, impedindo seu retorno na partida.
- O Recover exclui K, W e Y. No casual, o alvo por letra é 1 no primeiro ciclo e 2 nos seguintes. No ranqueado é 3, depois 4 e depois 5 permanentemente. Somente palavras efetivamente jogadas ou confirmadas pelo painel SOLVE avançam as metas.
- A estratégia adaptativa pode alternar respostas mais desafiadoras e rápidas, mas só deve usar um sinal de tempo/pressão validado; em leitura incerta preserva a escolha atual.
- Reset manual permanece. Reset automático exige sinal confiável de fim de partida ou inatividade suficientemente distinguível de turnos dos oponentes.

## Dicionário e OCR

- Uma lista pessoal separada participa das buscas junto à principal. A interface permite adicionar, editar, apagar, pré-visualizar importações e desfazer lotes. A edição não deve alterar arquivos de terceiros sem intenção explícita.
- Palavras conhecidas lidas no painel SOLVE são marcadas automaticamente. A pedido do usuário, leituras desconhecidas estáveis entram no topo da lista pessoal para facilitar revisão e remoção manual.
- A tela deve permitir ver a área de OCR, sugerir um recorte e guardar um exemplo de erro quando o usuário o indicar. Correções confirmadas podem orientar leituras futuras sem substituir indiscriminadamente resultados do OCR.
- Perfis de calibração incluem as regiões do prompt e do painel SOLVE.

## Treino e ergonomia

- Resumo da partida usa dados confirmados, sem apresentar sugestão como palavra jogada.
- Treino offline vive fora da tela principal, com modo de dicas progressivas e seleção de prompts baseada nas dificuldades observadas.
- Vista compacta e janela flutuante devem permitir uso durante o jogo sem entrar na região capturada. Avisos são visuais e discretos.

## Escopo adiado e restrições

- A estratégia `Fácil de digitar` ordena por esforço estimado, penalizando pontuação, acentos, letras incomuns e grupos consonantais além do tamanho. Ao lado do prompt, a interface mostra quantas respostas filtradas e ainda disponíveis existem; até cinco respostas, destaca a cobertura rara.
- A busca reversa (ideia 36) fica para outra fase, conforme a escolha do usuário.
- Permanecem fora do escopo as ideias rejeitadas: três sugestões simultâneas, favoritos, lista de bloqueio pessoal, explicação de estratégia, sons, estatísticas técnicas de latência e outras rejeições explícitas.
- Preservar alterações locais em andamento; não fazer commits sem solicitação. Quando houver commit solicitado, omitir `Co-authored-by`. Conferir `requirements.txt` antes e depois de cada recurso que use dependências e testar a instalação final.
- Escrever testes após implementar cada recurso, como solicitado pelo usuário. Verificar API, seleção, persistência e interface separadamente e executar a suíte completa ao integrar.
