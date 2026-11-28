"""Acesso ao banco para as tabelas `venda` e `item_venda`.

Como no ClienteRepo, os métodos de gravação NÃO confirmam sozinhos: quem chama
abre a transação com `with repo.transacao():`, para que a venda, os itens e a
atualização do cliente sejam gravados juntos ou não sejam gravados (RNF07).
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True)
class Venda:
    id: int
    data_hora: str
    cliente_codigo: int | None
    forma_pagamento: str
    desconto_centavos: int
    total_centavos: int          # já com o desconto aplicado
    credito_usado_centavos: int  # parte paga com o crédito do cliente

    @property
    def pago_na_forma_centavos(self) -> int:
        """Quanto entrou pela forma de pagamento escolhida (total menos o crédito usado)."""
        return self.total_centavos - self.credito_usado_centavos


@dataclass(frozen=True)
class ItemVendido:
    produto_id: int
    nome: str
    quantidade: int
    preco_unitario_centavos: int


class VendaRepo:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def transacao(self):
        """Use como `with repo.transacao():` (confirma no fim, desfaz se der erro)."""
        return self._conn

    def inserir(
        self,
        data_hora: str,
        cliente_codigo: int | None,
        forma_pagamento: str,
        desconto_centavos: int,
        total_centavos: int,
        credito_usado_centavos: int,
    ) -> int:
        cursor = self._conn.execute(
            "INSERT INTO venda (data_hora, cliente_codigo, forma_pagamento, desconto_centavos, "
            "total_centavos, credito_usado_centavos) VALUES (?, ?, ?, ?, ?, ?)",
            (data_hora, cliente_codigo, forma_pagamento, desconto_centavos,
             total_centavos, credito_usado_centavos),
        )
        return cursor.lastrowid

    def inserir_itens(self, venda_id: int, itens: list[tuple[int, int, int]]) -> None:
        """`itens`: lista de (produto_id, quantidade, preço unitário em centavos)."""
        self._conn.executemany(
            "INSERT INTO item_venda (venda_id, produto_id, quantidade, preco_unitario_centavos) "
            "VALUES (?, ?, ?, ?)",
            [(venda_id, produto_id, quantidade, preco) for produto_id, quantidade, preco in itens],
        )

    def buscar(self, venda_id: int) -> Venda | None:
        linha = self._conn.execute(
            "SELECT id, data_hora, cliente_codigo, forma_pagamento, desconto_centavos, "
            "total_centavos, credito_usado_centavos FROM venda WHERE id = ?",
            (venda_id,),
        ).fetchone()
        if linha is None:
            return None
        return Venda(
            id=linha["id"], data_hora=linha["data_hora"], cliente_codigo=linha["cliente_codigo"],
            forma_pagamento=linha["forma_pagamento"], desconto_centavos=linha["desconto_centavos"],
            total_centavos=linha["total_centavos"],
            credito_usado_centavos=linha["credito_usado_centavos"],
        )

    def itens_da_venda(self, venda_id: int) -> list[ItemVendido]:
        linhas = self._conn.execute(
            "SELECT i.produto_id, p.nome, i.quantidade, i.preco_unitario_centavos "
            "FROM item_venda i JOIN produto p ON p.id = i.produto_id "
            "WHERE i.venda_id = ? ORDER BY i.rowid",
            (venda_id,),
        ).fetchall()
        return [
            ItemVendido(l["produto_id"], l["nome"], l["quantidade"], l["preco_unitario_centavos"])
            for l in linhas
        ]
