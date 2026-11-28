"""Consultas de leitura sobre as vendas, para a planilha (RF13) e as quantidades (RF15).

Os períodos são textos ISO (`2026-11-27T08:00:00`), que se comparam como texto.
Itens de produtos removidos continuam aparecendo: o histórico não some.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass

SEM_CATEGORIA = "Sem categoria"


@dataclass(frozen=True)
class LinhaProduto:
    produto: str
    categoria: str
    quantidade: int
    preco_unitario_centavos: int

    @property
    def subtotal_centavos(self) -> int:
        return self.quantidade * self.preco_unitario_centavos


@dataclass(frozen=True)
class QuantidadeProduto:
    produto: str
    categoria: str
    quantidade: int


@dataclass(frozen=True)
class TotaisVendas:
    quantidade_vendas: int
    descontos_centavos: int
    total_centavos: int                      # já com desconto
    credito_usado_centavos: int              # pago com saldo de crédito do cliente
    por_forma_centavos: dict[str, int]       # só a parte paga na forma (total - crédito usado)


class RelatorioRepo:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def linhas_produtos(self, inicio: str, fim: str) -> list[LinhaProduto]:
        """Vendas com inicio <= data_hora <= fim, agrupadas por produto e preço unitário."""
        linhas = self._conn.execute(
            "SELECT p.nome AS produto, COALESCE(c.nome, ?) AS categoria, "
            "SUM(i.quantidade) AS quantidade, i.preco_unitario_centavos AS preco "
            "FROM venda v JOIN item_venda i ON i.venda_id = v.id "
            "JOIN produto p ON p.id = i.produto_id "
            "LEFT JOIN categoria c ON c.id = p.categoria_id "
            "WHERE v.data_hora >= ? AND v.data_hora <= ? "
            "GROUP BY i.produto_id, i.preco_unitario_centavos "
            "ORDER BY categoria COLLATE NOCASE, produto COLLATE NOCASE, preco",
            (SEM_CATEGORIA, inicio, fim),
        ).fetchall()
        return [LinhaProduto(l["produto"], l["categoria"], l["quantidade"], l["preco"]) for l in linhas]

    def totais(self, inicio: str, fim: str) -> TotaisVendas:
        resumo = self._conn.execute(
            "SELECT COUNT(*) AS n, COALESCE(SUM(desconto_centavos), 0) AS d, "
            "COALESCE(SUM(total_centavos), 0) AS t, COALESCE(SUM(credito_usado_centavos), 0) AS c "
            "FROM venda WHERE data_hora >= ? AND data_hora <= ?",
            (inicio, fim),
        ).fetchone()
        por_forma = {
            l["forma_pagamento"]: l["valor"]
            for l in self._conn.execute(
                "SELECT forma_pagamento, SUM(total_centavos - credito_usado_centavos) AS valor "
                "FROM venda WHERE data_hora >= ? AND data_hora <= ? GROUP BY forma_pagamento",
                (inicio, fim),
            )
        }
        return TotaisVendas(resumo["n"], resumo["d"], resumo["t"], resumo["c"], por_forma)

    def quantidades(self, inicio: str, fim_exclusivo: str) -> list[QuantidadeProduto]:
        """Quantidade vendida de cada produto com inicio <= data_hora < fim_exclusivo."""
        linhas = self._conn.execute(
            "SELECT p.nome AS produto, COALESCE(c.nome, ?) AS categoria, "
            "SUM(i.quantidade) AS quantidade "
            "FROM venda v JOIN item_venda i ON i.venda_id = v.id "
            "JOIN produto p ON p.id = i.produto_id "
            "LEFT JOIN categoria c ON c.id = p.categoria_id "
            "WHERE v.data_hora >= ? AND v.data_hora < ? "
            "GROUP BY i.produto_id "
            "ORDER BY quantidade DESC, produto COLLATE NOCASE",
            (SEM_CATEGORIA, inicio, fim_exclusivo),
        ).fetchall()
        return [QuantidadeProduto(l["produto"], l["categoria"], l["quantidade"]) for l in linhas]
