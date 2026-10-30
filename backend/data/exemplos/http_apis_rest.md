# Introdução a APIs REST com HTTP

Texto simulado para testes do NovaMente.

## O que é HTTP

O HTTP é o protocolo usado pela web para trocar mensagens entre um cliente, como o navegador ou um aplicativo, e um servidor. Cada troca tem uma requisição, enviada pelo cliente, e uma resposta, devolvida pelo servidor. O protocolo não guarda estado entre requisições: cada mensagem precisa carregar tudo o que o servidor precisa para entendê-la, como cabeçalhos de autenticação.

## Métodos

Os métodos dizem ao servidor qual ação o cliente quer realizar. GET busca um recurso sem alterá-lo. POST cria um recurso novo e normalmente leva os dados no corpo da requisição. PUT substitui um recurso inteiro, enquanto PATCH altera apenas alguns campos. DELETE remove o recurso. Um método é chamado de idempotente quando repetir a mesma requisição várias vezes produz o mesmo resultado que fazê-la uma vez; GET, PUT e DELETE são idempotentes, POST não é.

## Códigos de status

Toda resposta traz um código de três dígitos. A família 2xx indica sucesso: 200 significa que deu certo e 201 que um recurso foi criado. A família 3xx indica redirecionamento. A família 4xx aponta erro do cliente: 400 para requisição malformada, 401 quando falta autenticação, 403 quando o usuário não tem permissão e 404 quando o recurso não foi encontrado. Já a família 5xx indica falha no servidor, como o 500, erro interno, e o 503, serviço indisponível.

## Boas práticas de REST

Em uma API REST, as URLs representam recursos com substantivos no plural, como /usuarios ou /pedidos/42, e a ação fica por conta do método HTTP. As respostas costumam usar JSON. É recomendável versionar a API, por exemplo com /v1 no caminho, para não quebrar clientes antigos quando o contrato mudar. Listagens grandes devem ser paginadas com parâmetros como pagina e limite. Por fim, mensagens de erro precisam ser claras e acompanhadas do código de status correto, para que o cliente saiba se deve corrigir a requisição ou tentar novamente mais tarde.
