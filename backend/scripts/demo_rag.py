"""Demonstração do RAG com o Gemini real.

Indexa um texto de `data/exemplos/`, faz algumas perguntas e imprime os
trechos recuperados com a relevância. O Chroma fica numa pasta temporária
apagada ao final; nada é gravado no repositório nem em CHROMA_DIR.

Uso (no container, a partir de /app):
    python backend/scripts/demo_rag.py                     # exemplo HTTP
    python backend/scripts/demo_rag.py sql_consultas.md    # outro exemplo

Lê GOOGLE_API_KEY do ambiente e nunca a imprime.
"""

import os
import sys
import tempfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

import chromadb  # noqa: E402

from app.rag import armazenamento, indexar_documento, recuperar  # noqa: E402

EXEMPLOS = BACKEND / "data" / "exemplos"
PERGUNTAS = {
    "http_apis_rest.md": [
        "O que significa o erro 404?",
        "Qual a diferença entre PUT e PATCH?",
        "Como versionar uma API?",
    ],
    "sql_consultas.md": [
        "Como encontrar clientes que nunca fizeram pedidos?",
        "Quando usar HAVING em vez de WHERE?",
        "Índices deixam o banco mais lento?",
    ],
    "git_versionamento.md": [
        "O que acontece quando duas pessoas mudam a mesma linha?",
        "Para que serve um pull request?",
        "Qual a diferença entre merge e rebase?",
    ],
}


def main() -> None:
    if not os.getenv("GOOGLE_API_KEY"):
        sys.exit("GOOGLE_API_KEY não definida no ambiente.")
    nome = sys.argv[1] if len(sys.argv) > 1 else "http_apis_rest.md"
    if nome not in PERGUNTAS:
        sys.exit(f"Exemplo desconhecido. Opções: {', '.join(PERGUNTAS)}")
    texto = (EXEMPLOS / nome).read_text(encoding="utf-8")

    with tempfile.TemporaryDirectory(prefix="demo_rag_") as pasta:
        armazenamento.definir_cliente(chromadb.PersistentClient(path=pasta))
        try:
            resultado = indexar_documento(
                nome, nome, texto, on_etapa=lambda e: print(f"[etapa] {e}")
            )
            print(
                f"[indexado] {resultado.documento_id}: {resultado.total_trechos} trechos, "
                f"{resultado.caracteres} caracteres\n"
            )
            for pergunta in PERGUNTAS[nome]:
                print(f"Pergunta: {pergunta}")
                for t in recuperar(nome, pergunta, k=2):
                    resumo = " ".join(t.texto.split())[:220]
                    print(f"  [{t.relevancia:.3f}] trecho {t.indice}: {resumo}...")
                print()
        finally:
            armazenamento.definir_cliente(None)


if __name__ == "__main__":
    main()
