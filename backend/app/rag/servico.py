"""Funções públicas do módulo RAG: indexar um documento e recuperar trechos.

Não dependem de FastAPI nem de fila de jobs. O que fica para quem integra
o endpoint:

- Extração de texto: o endpoint recebe o PDF/MD, executa a etapa
  "extraindo" e entrega aqui o `texto` já extraído. Este módulo não lê
  arquivos.
- Progresso: `on_etapa` é chamado com "chunking" e depois "embeddings";
  o endpoint mapeia para as faixas de progresso (20-35 e 35-55).
- Erros: `ValueError` (texto ou parâmetro inválido) vira HTTP 422;
  `LookupError` (documento não indexado) vira HTTP 404.
- `ancoragem_fonte_score`: o cálculo final NÃO é feito aqui. `recuperar`
  devolve trechos com `relevancia` (1 - distância cosseno, de 0 a 1); quem
  gera o conteúdo combina esse valor com o LLM-as-a-judge sobre o texto
  gerado e pede reescrita quando o score ficar abaixo de 0,85.
"""

from collections.abc import Callable

from app.rag import armazenamento, chunking, config, embeddings
from app.rag.modelos import ResultadoIndexacao, Trecho

ETAPA_CHUNKING = "chunking"
ETAPA_EMBEDDINGS = "embeddings"


def indexar_documento(
    documento_id: str,
    titulo: str,
    texto: str,
    on_etapa: Callable[[str], None] | None = None,
) -> ResultadoIndexacao:
    """Divide o texto, gera embeddings e grava no Chroma.

    Reindexar o mesmo `documento_id` substitui os trechos anteriores.
    Levanta ValueError se o texto tiver menos de 200 ou mais de 50.000
    caracteres, ou se o `documento_id` for vazio.
    """
    armazenamento.nome_collection(documento_id)  # valida o id antes de gastar API
    limpo = chunking.validar_texto(texto)
    avisar = on_etapa or (lambda _etapa: None)

    avisar(ETAPA_CHUNKING)
    trechos = chunking.dividir_texto(limpo)

    avisar(ETAPA_EMBEDDINGS)
    vetores = embeddings.vetorizar_trechos(trechos)
    total = armazenamento.salvar_trechos(documento_id, titulo, trechos, vetores)

    return ResultadoIndexacao(
        documento_id=documento_id, total_trechos=total, caracteres=len(limpo)
    )


def recuperar(documento_id: str, consulta: str, k: int = config.K_PADRAO) -> list[Trecho]:
    """Devolve os `k` trechos do documento mais relevantes para a consulta.

    A lista vem ordenada da maior para a menor `relevancia`. Levanta
    LookupError se o documento não foi indexado e ValueError se a consulta
    for vazia ou `k` < 1.
    """
    if not consulta or not consulta.strip():
        raise ValueError("A consulta não pode ser vazia.")
    if k < 1:
        raise ValueError("k precisa ser pelo menos 1.")
    if not armazenamento.existe_documento(documento_id):
        raise LookupError(f"Documento não indexado: {documento_id}")
    vetor = embeddings.vetorizar_consulta(consulta.strip())
    return armazenamento.buscar(documento_id, vetor, k)
