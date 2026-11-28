"""Janela para escolher o cliente de uma venda (pesquisa por código ou nome)."""
from __future__ import annotations

from tkinter import TclError, ttk

import customtkinter as ctk

from src.dinheiro import formatar_reais
from src.repos.cliente_repo import Cliente
from src.services.cliente_service import ClienteService
from src.ui import tabela, tema


class ClienteEscolhaDialog(ctk.CTkToplevel):
    """Depois de `wait_window()`: `escolhido` tem o Cliente selecionado;
    `limpou` é True se a pessoa clicou em "Sem cliente"."""

    def __init__(self, master, clientes: ClienteService) -> None:
        super().__init__(master)
        self._clientes = clientes
        self.escolhido: Cliente | None = None
        self.limpou = False

        self.title("Escolher cliente")
        self.geometry("640x560")
        self.minsize(560, 480)
        self.transient(master)
        self.protocol("WM_DELETE_WINDOW", self.destroy)

        self._montar()
        self._recarregar()
        self.after(150, self._tornar_modal)

    def _montar(self) -> None:
        corpo = ctk.CTkFrame(self, fg_color="transparent")
        corpo.pack(fill="both", expand=True, padx=24, pady=20)

        ctk.CTkLabel(
            corpo, text="Escolher cliente", font=tema.FONTE_TITULO, text_color=tema.COR_PRIMARIA,
        ).pack(anchor="w", pady=(0, 10))

        self._entrada_busca = ctk.CTkEntry(
            corpo, height=tema.ALTURA_CAMPO, font=tema.FONTE_NORMAL,
            placeholder_text="Pesquisar por código ou nome",
        )
        self._entrada_busca.pack(fill="x")
        self._entrada_busca.bind("<KeyRelease>", lambda _e: self._recarregar())

        botoes = ctk.CTkFrame(corpo, fg_color="transparent")
        botoes.pack(fill="x", side="bottom", pady=(12, 0))
        botoes.grid_columnconfigure((0, 1, 2), weight=1, uniform="botao")
        ctk.CTkButton(
            botoes, text="Cancelar", height=tema.ALTURA_BOTAO, font=tema.FONTE_BOTAO,
            fg_color=tema.COR_SECUNDARIA, hover_color=tema.COR_SECUNDARIA_HOVER,
            text_color=tema.COR_PRIMARIA, command=self.destroy,
        ).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ctk.CTkButton(
            botoes, text="Sem cliente", height=tema.ALTURA_BOTAO, font=tema.FONTE_BOTAO,
            fg_color=tema.COR_SECUNDARIA, hover_color=tema.COR_SECUNDARIA_HOVER,
            text_color=tema.COR_PRIMARIA, command=self._sem_cliente,
        ).grid(row=0, column=1, sticky="ew", padx=4)
        ctk.CTkButton(
            botoes, text="Selecionar", height=tema.ALTURA_BOTAO, font=tema.FONTE_BOTAO,
            fg_color=tema.COR_PRIMARIA, hover_color=tema.COR_PRIMARIA_HOVER,
            text_color="white", command=self._selecionar,
        ).grid(row=0, column=2, sticky="ew", padx=(4, 0))

        area = ctk.CTkFrame(corpo, fg_color="transparent")
        area.pack(fill="both", expand=True, pady=(12, 0))
        self._tabela = ttk.Treeview(
            area, columns=("codigo", "nome", "divida", "credito"),
            show="headings", selectmode="browse", style=tabela.estilizar(self),
        )
        for coluna, texto, largura, alinhamento in [
            ("codigo", "Código", 70, "e"), ("nome", "Nome", 220, "w"),
            ("divida", "Deve", 100, "e"), ("credito", "Crédito", 100, "e"),
        ]:
            self._tabela.heading(coluna, text=texto, anchor=alinhamento)
            self._tabela.column(coluna, width=largura, anchor=alinhamento)
        barra = ctk.CTkScrollbar(area, command=self._tabela.yview)
        self._tabela.configure(yscrollcommand=barra.set)
        barra.pack(side="right", fill="y")
        self._tabela.pack(side="left", fill="both", expand=True)
        self._tabela.bind("<Double-1>", lambda _e: self._selecionar())

    def _tornar_modal(self) -> None:
        try:
            self.lift()
            self.grab_set()
            self._entrada_busca.focus()
        except TclError:
            pass

    def _recarregar(self) -> None:
        self._lista = {c.codigo: c for c in self._clientes.listar(self._entrada_busca.get())}
        self._tabela.delete(*self._tabela.get_children())
        for c in self._lista.values():
            self._tabela.insert(
                "", "end", iid=str(c.codigo),
                values=(c.codigo, c.nome, formatar_reais(c.divida_centavos),
                        formatar_reais(c.credito_centavos)),
            )

    def _selecionar(self) -> None:
        selecao = self._tabela.selection()
        if not selecao:
            return
        self.escolhido = self._lista.get(int(selecao[0]))
        self.destroy()

    def _sem_cliente(self) -> None:
        self.limpou = True
        self.destroy()
