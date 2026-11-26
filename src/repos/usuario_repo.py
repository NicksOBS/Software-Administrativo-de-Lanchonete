"""Acesso ao banco para a tabela `usuario` (camada de persistência)."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from src.errors import LoginJaExisteError


@dataclass(frozen=True)
class Usuario:
    id: int
    login: str
    senha_hash: str


class UsuarioRepo:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def criar(self, login: str, senha_hash: str) -> Usuario:
        """Insere um usuário. Falha se o login já existir (sem diferenciar maiúsculas)."""
        try:
            with self._conn:
                cursor = self._conn.execute(
                    "INSERT INTO usuario (login, senha_hash) VALUES (?, ?)",
                    (login, senha_hash),
                )
        except sqlite3.IntegrityError:
            raise LoginJaExisteError("Já existe um usuário com esse login.") from None
        return Usuario(id=cursor.lastrowid, login=login, senha_hash=senha_hash)

    def buscar_por_login(self, login: str) -> Usuario | None:
        linha = self._conn.execute(
            "SELECT id, login, senha_hash FROM usuario WHERE login = ?", (login,)
        ).fetchone()
        if linha is None:
            return None
        return Usuario(id=linha["id"], login=linha["login"], senha_hash=linha["senha_hash"])

    def contar(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM usuario").fetchone()[0]
