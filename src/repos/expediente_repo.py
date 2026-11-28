"""Acesso ao banco para a tabela `expediente` (RF12)."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True)
class Expediente:
    id: int
    inicio: str          # ISO: 2026-11-27T08:00:00
    fim: str | None      # None = ainda aberto
    arquivo: str | None  # planilha gerada ao encerrar

    @property
    def aberto(self) -> bool:
        return self.fim is None


class ExpedienteRepo:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def aberto(self) -> Expediente | None:
        linha = self._conn.execute(
            "SELECT id, inicio, fim, arquivo FROM expediente WHERE fim IS NULL "
            "ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return self._montar(linha)

    def buscar(self, expediente_id: int) -> Expediente | None:
        linha = self._conn.execute(
            "SELECT id, inicio, fim, arquivo FROM expediente WHERE id = ?", (expediente_id,)
        ).fetchone()
        return self._montar(linha)

    def iniciar(self, inicio: str) -> int:
        with self._conn:
            return self._conn.execute(
                "INSERT INTO expediente (inicio) VALUES (?)", (inicio,)
            ).lastrowid

    def encerrar(self, expediente_id: int, fim: str, arquivo: str) -> None:
        with self._conn:
            self._conn.execute(
                "UPDATE expediente SET fim = ?, arquivo = ? WHERE id = ?",
                (fim, arquivo, expediente_id),
            )

    @staticmethod
    def _montar(linha) -> Expediente | None:
        if linha is None:
            return None
        return Expediente(linha["id"], linha["inicio"], linha["fim"], linha["arquivo"])
