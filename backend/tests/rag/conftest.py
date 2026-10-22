import sys
from pathlib import Path

# Permite importar `app.rag` rodando o pytest a partir da raiz do repositório.
BACKEND = Path(__file__).resolve().parents[2]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
