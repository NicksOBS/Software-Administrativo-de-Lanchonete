"""Acesso ao banco para a tabela `categoria`."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from src.errors import RegistroDuplicadoError


@dataclass(frozen=True)
class Categoria:
    id: int
    nome: str


class CategoriaRepo:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def criar(self, nome: str) -> Categoria:
        try:
            with self._conn:
                cursor = self._conn.execute("INSERT INTO categoria (nome) VALUES (?)", (nome,))
        except sqlite3.IntegrityError:
            raise RegistroDuplicadoError("Já existe uma categoria com esse nome.") from None
        return Categoria(id=cursor.lastrowid, nome=nome)

    def listar(self) -> list[Categoria]:
        linhas = self._conn.execute(
            "SELECT id, nome FROM categoria ORDER BY sem_acento(nome)"
        ).fetchall()
        return [Categoria(id=l["id"], nome=l["nome"]) for l in linhas]

    def buscar_por_id(self, categoria_id: int) -> Categoria | None:
        linha = self._conn.execute(
            "SELECT id, nome FROM categoria WHERE id = ?", (categoria_id,)
        ).fetchone()
        return Categoria(id=linha["id"], nome=linha["nome"]) if linha else None

    def existe_nome(self, nome: str, ignorar_id: int | None = None) -> bool:
        """Compara sem diferenciar acentos e maiúsculas ("Pão" = "PAO")."""
        linha = self._conn.execute(
            "SELECT 1 FROM categoria WHERE sem_acento(nome) = sem_acento(?) AND id IS NOT ?",
            (nome, ignorar_id),
        ).fetchone()
        return linha is not None

    def renomear(self, categoria_id: int, nome: str) -> None:
        try:
            with self._conn:
                self._conn.execute(
                    "UPDATE categoria SET nome = ? WHERE id = ?", (nome, categoria_id)
                )
        except sqlite3.IntegrityError:
            raise RegistroDuplicadoError("Já existe uma categoria com esse nome.") from None

    def contar_produtos_ativos(self, categoria_id: int) -> int:
        return self._conn.execute(
            "SELECT COUNT(*) FROM produto WHERE categoria_id = ? AND ativo = 1",
            (categoria_id,),
        ).fetchone()[0]

    def remover(self, categoria_id: int) -> None:
        """Apaga a categoria. Produtos inativos que a usavam ficam sem categoria."""
        with self._conn:
            self._conn.execute(
                "UPDATE produto SET categoria_id = NULL WHERE categoria_id = ?", (categoria_id,)
            )
            self._conn.execute("DELETE FROM categoria WHERE id = ?", (categoria_id,))
