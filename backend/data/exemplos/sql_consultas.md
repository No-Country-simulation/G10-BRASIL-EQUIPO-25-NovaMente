# Consultas em bancos de dados relacionais com SQL

Texto simulado para testes do NovaMente.

## Tabelas e chaves

Um banco de dados relacional organiza as informações em tabelas, formadas por linhas e colunas. Cada linha representa um registro, como um cliente, e cada coluna representa um atributo, como o nome ou o e-mail. A chave primária é a coluna que identifica cada linha de forma única. A chave estrangeira é uma coluna que aponta para a chave primária de outra tabela e cria o relacionamento entre elas, por exemplo um pedido que guarda o id do cliente que o fez.

## SELECT, WHERE e ORDER BY

O comando SELECT lê dados. Depois dele vêm as colunas desejadas e, com FROM, a tabela de origem. A cláusula WHERE filtra as linhas com uma condição, como preço maior que 100. ORDER BY ordena o resultado, em ordem crescente com ASC ou decrescente com DESC, e LIMIT restringe a quantidade de linhas devolvidas.

## Junções

Quando a informação está espalhada em várias tabelas, usa-se JOIN. O INNER JOIN devolve apenas as linhas que têm correspondência nas duas tabelas. O LEFT JOIN devolve todas as linhas da tabela da esquerda e preenche com nulo as colunas da direita quando não há correspondência, o que ajuda a encontrar, por exemplo, clientes que nunca fizeram pedidos.

## Agregações

Funções de agregação resumem várias linhas em um valor: COUNT conta, SUM soma, AVG calcula a média, MIN e MAX encontram os extremos. Combinadas com GROUP BY, elas calculam o resultado por grupo, como o total vendido por mês. Para filtrar grupos depois da agregação usa-se HAVING, porque o WHERE atua antes do agrupamento.

## Índices

Um índice é uma estrutura auxiliar que acelera buscas em uma coluna, de forma parecida com o índice remissivo de um livro. Ele torna as consultas com WHERE e JOIN mais rápidas, mas ocupa espaço e deixa inserções e atualizações um pouco mais lentas, por isso deve ser criado nas colunas mais usadas em filtros.
