# Controle de versão com Git

Texto simulado para testes do NovaMente.

## Por que versionar

O controle de versão registra o histórico de alterações de um projeto. Com ele é possível saber quem mudou o quê e quando, voltar a uma versão anterior quando algo quebra e permitir que várias pessoas trabalhem no mesmo código sem sobrescrever o trabalho umas das outras. O Git é um sistema distribuído: cada pessoa tem uma cópia completa do histórico no próprio computador.

## Commits

Um commit é uma fotografia do projeto em um momento. Antes de registrar, as alterações passam pela área de preparação com git add, o que permite escolher exatamente o que entra. A mensagem do commit deve explicar de forma curta o que mudou e por quê. Commits pequenos e focados facilitam a revisão e tornam mais simples desfazer uma mudança específica.

## Branches

Uma branch é uma linha de desenvolvimento independente. A prática comum é criar uma branch para cada funcionalidade ou correção, trabalhar nela e, quando estiver pronta, integrá-la à branch principal. Assim o código estável não é afetado por trabalho incompleto.

## Merge e rebase

O merge junta o histórico de duas branches e pode criar um commit de junção. O rebase reaplica os commits de uma branch sobre a ponta de outra, deixando o histórico linear. Quando duas pessoas alteram as mesmas linhas, surge um conflito: o Git marca os trechos no arquivo e alguém precisa escolher a versão correta antes de concluir a operação.

## Repositórios remotos e pull requests

O repositório remoto, hospedado em serviços como GitHub ou GitLab, é o ponto de encontro da equipe. O git push envia commits locais para o remoto e o git pull traz as novidades. Em vez de enviar direto para a branch principal, as equipes costumam abrir um pull request, onde outra pessoa revisa o código, comenta e aprova antes da integração.
