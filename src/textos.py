"""Utilidades de texto."""
from __future__ import annotations

import unicodedata


def normalizar(texto: str | None) -> str | None:
    """Tira acentos e diferença de maiúsculas, para comparar e pesquisar.

    "Pão de Queijo" e "pao de queijo" viram o mesmo texto.
    """
    if texto is None:
        return None
    decomposto = unicodedata.normalize("NFD", str(texto))
    sem_acento = "".join(c for c in decomposto if not unicodedata.combining(c))
    return sem_acento.casefold()


def escapar_like(termo: str) -> str:
    """Faz % e _ valerem como texto comum num LIKE ... ESCAPE '\\'."""
    return termo.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def limpar_espacos(texto: str | None) -> str:
    """Remove espaços nas pontas e reduz espaços repetidos no meio."""
    return " ".join((texto or "").split())
