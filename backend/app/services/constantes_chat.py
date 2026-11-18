"""Constantes e erros de domínio do chat sobre o material.

Os limites configuráveis (tamanho da pergunta, histórico, orçamento de
contexto, prazo) ficam em ``settings.chat_*``; aqui só o que é fixo do
serviço. As mensagens dos erros nunca repetem o texto da pergunta, do
histórico ou do material.
"""

from __future__ import annotations

# Frase que o modelo deve devolver quando a resposta não está nos trechos.
FRASE_RECUSA = "Não encontrei isso no material."

# Excerto de cada citação devolvida ao cliente (cortado no fim de uma palavra).
TAMANHO_EXCERTO = 240

# Cada mensagem anterior do histórico é cortada neste tamanho pelo servidor.
MAX_CARACTERES_MENSAGEM_HISTORICO = 2_000

# Máximo de trechos que a busca devolve para a montagem do contexto.
K_MAXIMO_BUSCA = 50

# Pergunta com menos termos que isto é tratada como seguimento: a última
# pergunta do usuário no histórico entra na consulta da busca.
TERMOS_PERGUNTA_CURTA = 3

# Abaixo disto, o espaço que sobra no orçamento não recebe um trecho cortado.
MIN_CARACTERES_TRECHO_CORTADO = 120

# Marcação dos trechos no prompt; ocorrências dela dentro do material são neutralizadas.
TAG_FONTE = "fonte"

ORIGEM_DOCUMENTO = "documento"
ORIGEM_PACOTE = "pacote"
BASE_DOCUMENTO_E_PACOTE = "documento_e_pacote"
BASE_PACOTE = "pacote"


class ErroChat(Exception):
    """Erro de domínio do chat, com ``codigo`` estável para a rota mapear em HTTP.

    ``campo`` indica a entrada responsável (``None`` quando não é de entrada).
    """

    codigo = "CHAT_ERRO"
    campo: str | None = None

    def __init__(self, mensagem: str, *, codigo: str | None = None, campo: str | None = None):
        super().__init__(mensagem)
        self.mensagem = mensagem
        if codigo:
            self.codigo = codigo
        if campo:
            self.campo = campo


class PerguntaInvalida(ErroChat):
    """Pergunta vazia (``PERGUNTA_VAZIA``) ou longa demais (``PERGUNTA_LONGA``)."""

    codigo = "PERGUNTA_INVALIDA"
    campo = "pergunta"


class MaterialNaoEncontrado(ErroChat):
    """Não existe material com esse identificador."""

    codigo = "MATERIAL_NAO_ENCONTRADO"
    campo = "material_id"


class RespostaVazia(ErroChat):
    """O modelo respondeu, mas não sobrou texto depois de tirar o raciocínio."""

    codigo = "RESPOSTA_VAZIA"
