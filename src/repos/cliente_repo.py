"""Acesso ao banco para as tabelas `cliente` e `pagamento_divida`.

Atenção: diferente dos outros repositórios, os métodos que gravam aqui NÃO
confirmam (commit) sozinhos. Quem chama agrupa as gravações com

    with repo.transacao():
        ...

assim, uma operação que mexe em mais de uma tabela (por exemplo uma venda no
fiado: venda + dívida do cliente) vira tudo-ou-nada (RNF07).
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from src.errors import RegistroDuplicadoError
from src.textos import escapar_like, normalizar

_COLUNAS = "codigo, nome, divida_centavos, credito_centavos, limite_centavos, ativo"
_ORDEM = " ORDER BY sem_acento(nome), codigo"


@dataclass(frozen=True)
class Cliente:
    codigo: int
    nome: str
    divida_centavos: int
    credito_centavos: int
    limite_centavos: int | None  # None = sem limite
    ativo: bool = True

    @property
    def bloqueado(self) -> bool:
        """RN01: com a dívida acima do limite, o cliente não compra mais no fiado."""
        return self.limite_centavos is not None and self.divida_centavos > self.limite_centavos


def _para_cliente(linha: sqlite3.Row) -> Cliente:
    return Cliente(
        codigo=linha["codigo"],
        nome=linha["nome"],
        divida_centavos=linha["divida_centavos"],
        credito_centavos=linha["credito_centavos"],
        limite_centavos=linha["limite_centavos"],
        ativo=bool(linha["ativo"]),
    )


class ClienteRepo:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def transacao(self):
        """Use como `with repo.transacao():` (confirma no fim, desfaz se der erro)."""
        return self._conn

    # ---------------------------------------------------------------- leitura
    def buscar(self, codigo: int) -> Cliente | None:
        """Devolve o cliente (ativo ou não) ou None se o código nunca existiu."""
        linha = self._conn.execute(
            f"SELECT {_COLUNAS} FROM cliente WHERE codigo = ?", (codigo,)
        ).fetchone()
        return _para_cliente(linha) if linha else None

    def proximo_codigo(self) -> int:
        """Maior código já usado + 1 (inclui clientes removidos, que não liberam o código)."""
        return self._conn.execute("SELECT COALESCE(MAX(codigo), 0) + 1 FROM cliente").fetchone()[0]

    def listar(self, busca: str = "", somente_devedores: bool = False) -> list[Cliente]:
        """Clientes ativos em ordem alfabética (RF08 e RF09).

        Um texto só de números procura primeiro pelo CÓDIGO exato; se não houver
        esse código, procura o número dentro dos nomes. Qualquer outro texto
        procura dentro do nome, sem diferenciar acentos nem maiúsculas.
        """
        termo = (busca or "").strip()
        base = f"SELECT {_COLUNAS} FROM cliente WHERE ativo = 1"
        if somente_devedores:
            base += " AND divida_centavos > 0"

        if termo.isascii() and termo.isdigit() and len(termo) <= 9:
            linhas = self._conn.execute(
                base + " AND codigo = ?" + _ORDEM, (int(termo),)
            ).fetchall()
            if linhas:
                return [_para_cliente(l) for l in linhas]

        if termo:
            padrao = f"%{escapar_like(normalizar(termo))}%"
            linhas = self._conn.execute(
                base + " AND sem_acento(nome) LIKE ? ESCAPE '\\'" + _ORDEM, (padrao,)
            ).fetchall()
        else:
            linhas = self._conn.execute(base + _ORDEM).fetchall()
        return [_para_cliente(l) for l in linhas]

    # --------------------------------------------------------------- gravação
    def criar(self, codigo: int, nome: str, limite_centavos: int | None) -> None:
        try:
            self._conn.execute(
                "INSERT INTO cliente (codigo, nome, limite_centavos) VALUES (?, ?, ?)",
                (codigo, nome, limite_centavos),
            )
        except sqlite3.IntegrityError:
            raise RegistroDuplicadoError(f"Já existe um cliente com o código {codigo}.") from None

    def atualizar(self, codigo: int, nome: str, limite_centavos: int | None) -> None:
        self._conn.execute(
            "UPDATE cliente SET nome = ?, limite_centavos = ? WHERE codigo = ?",
            (nome, limite_centavos, codigo),
        )

    def desativar(self, codigo: int) -> None:
        self._conn.execute("UPDATE cliente SET ativo = 0 WHERE codigo = ?", (codigo,))

    def somar_divida(self, codigo: int, centavos: int) -> None:
        """Soma (ou subtrai, se negativo) da dívida. O banco recusa dívida negativa."""
        self._conn.execute(
            "UPDATE cliente SET divida_centavos = divida_centavos + ? WHERE codigo = ?",
            (centavos, codigo),
        )

    def somar_credito(self, codigo: int, centavos: int) -> None:
        self._conn.execute(
            "UPDATE cliente SET credito_centavos = credito_centavos + ? WHERE codigo = ?",
            (centavos, codigo),
        )

    def registrar_pagamento(self, codigo: int, data_hora: str, valor_centavos: int) -> None:
        self._conn.execute(
            "INSERT INTO pagamento_divida (cliente_codigo, data_hora, valor_centavos) "
            "VALUES (?, ?, ?)",
            (codigo, data_hora, valor_centavos),
        )
