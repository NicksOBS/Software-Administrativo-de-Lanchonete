"""Acesso ao banco para a tabela `produto`."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from src.textos import normalizar


@dataclass(frozen=True)
class Produto:
    id: int
    nome: str
    categoria_id: int | None
    categoria_nome: str | None
    preco_centavos: int
    ativo: bool = True


_SELECT = """
    SELECT p.id, p.nome, p.categoria_id, c.nome AS categoria_nome,
           p.preco_centavos, p.ativo
      FROM produto p
      LEFT JOIN categoria c ON c.id = p.categoria_id
"""


def _para_produto(linha: sqlite3.Row) -> Produto:
    return Produto(
        id=linha["id"],
        nome=linha["nome"],
        categoria_id=linha["categoria_id"],
        categoria_nome=linha["categoria_nome"],
        preco_centavos=linha["preco_centavos"],
        ativo=bool(linha["ativo"]),
    )


def _escapar_like(termo: str) -> str:
    return termo.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class ProdutoRepo:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def criar(self, nome: str, categoria_id: int | None, preco_centavos: int) -> Produto:
        with self._conn:
            cursor = self._conn.execute(
                "INSERT INTO produto (nome, categoria_id, preco_centavos) VALUES (?, ?, ?)",
                (nome, categoria_id, preco_centavos),
            )
        return self.buscar_por_id(cursor.lastrowid)

    def buscar_por_id(self, produto_id: int) -> Produto | None:
        linha = self._conn.execute(_SELECT + " WHERE p.id = ?", (produto_id,)).fetchone()
        return _para_produto(linha) if linha else None

    def atualizar(
        self, produto_id: int, nome: str, categoria_id: int | None, preco_centavos: int
    ) -> None:
        with self._conn:
            self._conn.execute(
                "UPDATE produto SET nome = ?, categoria_id = ?, preco_centavos = ? WHERE id = ?",
                (nome, categoria_id, preco_centavos, produto_id),
            )

    def desativar(self, produto_id: int) -> None:
        """Remoção lógica: o produto some das listas, mas as vendas antigas o mantêm."""
        with self._conn:
            self._conn.execute("UPDATE produto SET ativo = 0 WHERE id = ?", (produto_id,))

    def existe_nome_ativo(self, nome: str, ignorar_id: int | None = None) -> bool:
        linha = self._conn.execute(
            "SELECT 1 FROM produto "
            "WHERE ativo = 1 AND sem_acento(nome) = sem_acento(?) AND id IS NOT ?",
            (nome, ignorar_id),
        ).fetchone()
        return linha is not None

    def listar(self, busca: str = "", categoria_id: int | None = None) -> list[Produto]:
        """Produtos ativos, em ordem alfabética.

        `busca` procura pelo nome do produto ou da categoria, sem diferenciar
        acentos nem maiúsculas (RF06).
        """
        condicoes = ["p.ativo = 1"]
        parametros: list = []

        termo = normalizar((busca or "").strip())
        if termo:
            padrao = f"%{_escapar_like(termo)}%"
            condicoes.append(
                "(sem_acento(p.nome) LIKE ? ESCAPE '\\' OR sem_acento(c.nome) LIKE ? ESCAPE '\\')"
            )
            parametros += [padrao, padrao]
        if categoria_id is not None:
            condicoes.append("p.categoria_id = ?")
            parametros.append(categoria_id)

        sql = _SELECT + " WHERE " + " AND ".join(condicoes) + " ORDER BY sem_acento(p.nome)"
        return [_para_produto(l) for l in self._conn.execute(sql, parametros).fetchall()]
