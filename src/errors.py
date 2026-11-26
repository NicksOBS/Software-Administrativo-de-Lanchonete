"""Erros de negócio.

Todo erro que herda de ErroDeNegocio tem uma mensagem pensada para ser
mostrada ao usuário na tela. Erros inesperados (bugs) continuam sendo
exceções comuns do Python.
"""


class ErroDeNegocio(Exception):
    """Base para erros que podem ser exibidos ao usuário."""


class DadosInvalidosError(ErroDeNegocio):
    """Algum dado informado não passou na validação."""


class LoginJaExisteError(ErroDeNegocio):
    """Já existe um usuário com o login informado."""


class CredenciaisInvalidasError(ErroDeNegocio):
    """Login ou senha incorretos."""
