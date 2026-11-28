"""Acesso ao banco para a tabela `configuracao` (valores definidos pelo proprietário)."""
from __future__ import annotations

import sqlite3


class ConfiguracaoRepo:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def obter(self, chave: str) -> str | None:
        linha = self._conn.execute(
            "SELECT valor FROM configuracao WHERE chave = ?", (chave,)
        ).fetchone()
        return linha["valor"] if linha else None

    def definir(self, chave: str, valor: str | None) -> None:
        """Grava o valor. Com `None`, apaga a configuração."""
        with self._conn:
            if valor is None:
                self._conn.execute("DELETE FROM configuracao WHERE chave = ?", (chave,))
            else:
                self._conn.execute(
                    "INSERT INTO configuracao (chave, valor) VALUES (?, ?) "
                    "ON CONFLICT(chave) DO UPDATE SET valor = excluded.valor",
                    (chave, valor),
                )
