"""Exceções de domínio mapeadas para códigos de erro da spec do frontend."""

from typing import Literal

CodigoErro = Literal[
    "VALIDACAO",
    "ARQUIVO_INVALIDO",
    "DOCUMENTO_ILEGIVEL",
    "LIMITE_EXCEDIDO",
    "ADAPTACAO_NAO_ENCONTRADA",
    "JOB_NAO_ENCONTRADO",
    "JOB_FINALIZADO",
    "FORMATO_INCOMPATIVEL",
    "FORMATO_DESCONHECIDO",
    "OCI_INDISPONIVEL",
    "INTERNO",
]


class NovaMenteError(Exception):
    """Erro de domínio com mapeamento para HTTP e código de erro da spec."""

    def __init__(
        self,
        codigo: CodigoErro,
        mensagem: str,
        status_http: int = 400,
        campos: dict[str, str] | None = None,
        request_id: str | None = None,
    ) -> None:
        super().__init__(mensagem)
        self.codigo = codigo
        self.mensagem = mensagem
        self.status_http = status_http
        self.campos = campos
        self.request_id = request_id
