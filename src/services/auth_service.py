"""Regras de cadastro e login de usuários (RF01)."""
from __future__ import annotations

import re

from src.errors import CredenciaisInvalidasError, DadosInvalidosError
from src.repos.usuario_repo import Usuario, UsuarioRepo
from src.services.security import gerar_hash, verificar_senha

LOGIN_MIN = 3
LOGIN_MAX = 30
SENHA_MIN = 4
_LOGIN_VALIDO = re.compile(r"^[A-Za-z0-9._-]+$")


class AuthService:
    def __init__(self, repo: UsuarioRepo) -> None:
        self._repo = repo

    def existe_usuario(self) -> bool:
        """Usado para saber se é o primeiro acesso (nenhum usuário cadastrado)."""
        return self._repo.contar() > 0

    def cadastrar(self, login: str, senha: str, confirmacao: str | None = None) -> Usuario:
        login = (login or "").strip()
        self._validar_login(login)
        self._validar_senha(senha)
        if confirmacao is not None and senha != confirmacao:
            raise DadosInvalidosError("A confirmação da senha não confere.")
        return self._repo.criar(login, gerar_hash(senha))

    def autenticar(self, login: str, senha: str) -> Usuario:
        login = (login or "").strip()
        if not login or not senha:
            raise CredenciaisInvalidasError("Informe o login e a senha.")

        usuario = self._repo.buscar_por_login(login)
        # Mesma mensagem para "usuário não existe" e "senha errada", para não
        # revelar quais logins estão cadastrados.
        if usuario is None or not verificar_senha(senha, usuario.senha_hash):
            raise CredenciaisInvalidasError("Login ou senha incorretos.")
        return usuario

    @staticmethod
    def _validar_login(login: str) -> None:
        if not (LOGIN_MIN <= len(login) <= LOGIN_MAX):
            raise DadosInvalidosError(
                f"O login deve ter entre {LOGIN_MIN} e {LOGIN_MAX} caracteres."
            )
        if not _LOGIN_VALIDO.match(login):
            raise DadosInvalidosError(
                "O login só pode ter letras sem acento, números, ponto, hífen e sublinhado."
            )

    @staticmethod
    def _validar_senha(senha: str) -> None:
        if len(senha or "") < SENHA_MIN:
            raise DadosInvalidosError(f"A senha deve ter pelo menos {SENHA_MIN} caracteres.")
