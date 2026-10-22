"""Constantes do módulo RAG.

Valores iniciais; ajuste aqui em vez de espalhar números pelo código.
"""

import os

# Chunking
CHUNK_TAMANHO = 1000
CHUNK_OVERLAP = 150
# Ordem de preferência para quebrar o texto: parágrafo, linha, frase, palavra.
SEPARADORES = ["\n\n", "\n", ". ", "? ", "! ", "; ", " ", ""]

# Limites do texto recebido (o endpoint traduz o ValueError para HTTP 422)
TEXTO_MIN_CARACTERES = 200
TEXTO_MAX_CARACTERES = 50_000

# Embeddings (a chave vem de GOOGLE_API_KEY, nunca deste arquivo)
MODELO_EMBEDDING = "models/gemini-embedding-001"
TASK_TYPE_DOCUMENTO = "RETRIEVAL_DOCUMENT"
TASK_TYPE_CONSULTA = "RETRIEVAL_QUERY"
# Limites do plano gratuito não verificados: lotes pequenos e retentativa em 429.
EMBEDDING_LOTE = 50
EMBEDDING_TENTATIVAS = 3
EMBEDDING_ESPERA_INICIAL = 2.0  # segundos, dobra a cada tentativa

# Vector store
METRICA = "cosine"
PREFIXO_COLLECTION = "doc_"

# Recuperação
K_PADRAO = 4

# Vector store fica fora do repositório
CHROMA_DIR = os.getenv("CHROMA_DIR", "/data/chroma")
