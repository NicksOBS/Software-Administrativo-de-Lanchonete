"""Estilo compartilhado das tabelas (ttk.Treeview) para combinar com o resto da interface."""
from __future__ import annotations

from tkinter import ttk

from src.ui import tema

ESTILO = "Lanchonete.Treeview"


def estilizar(master) -> str:
    """Configura o estilo das tabelas e devolve o nome para usar em `style=`."""
    estilo = ttk.Style(master)
    estilo.theme_use("clam")
    estilo.configure(
        ESTILO,
        font=("Arial", 14), rowheight=38,
        background="white", fieldbackground="white", foreground=tema.COR_TEXTO,
        borderwidth=0,
    )
    estilo.configure(
        f"{ESTILO}.Heading",
        font=("Arial", 14, "bold"), background=tema.COR_PRIMARIA, foreground="white",
        padding=8, relief="flat",
    )
    estilo.map(
        ESTILO,
        background=[("selected", tema.COR_PRIMARIA)],
        foreground=[("selected", "white")],
    )
    estilo.map(f"{ESTILO}.Heading", background=[("active", tema.COR_PRIMARIA_HOVER)])
    return ESTILO
