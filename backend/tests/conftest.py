"""Configuração do pytest para o backend."""

import sys
import os

# Adiciona o diretório backend ao path para que os imports funcionem
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
