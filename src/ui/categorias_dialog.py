"""Janela para gerenciar as categorias de produtos (RF04)."""
from __future__ import annotations

from tkinter import TclError, messagebox, ttk

import customtkinter as ctk

from src.errors import ErroDeNegocio
from src.services.categoria_service import CategoriaService
from src.ui import tabela, tema


class CategoriasDialog(ctk.CTkToplevel):
    def __init__(self, master, categorias: CategoriaService) -> None:
        super().__init__(master)
        self._categorias = categorias

        self.title("Categorias")
        self.geometry("520x640")
        self.minsize(480, 560)
        self.transient(master)
        self.protocol("WM_DELETE_WINDOW", self.destroy)

        self._montar()
        self._recarregar()
        self.after(150, self._tornar_modal)

    def _montar(self) -> None:
        corpo = ctk.CTkFrame(self, fg_color="transparent")
        corpo.pack(fill="both", expand=True, padx=28, pady=24)

        ctk.CTkLabel(
            corpo, text="Categorias", font=tema.FONTE_TITULO, text_color=tema.COR_PRIMARIA,
        ).pack(anchor="w", pady=(0, 12))

        self._entrada_nome = ctk.CTkEntry(
            corpo, height=tema.ALTURA_CAMPO, font=tema.FONTE_NORMAL,
            placeholder_text="Nome da categoria",
        )
        self._entrada_nome.pack(fill="x", pady=(0, 8))
        self._entrada_nome.bind("<Return>", lambda _e: self._adicionar())

        linha = ctk.CTkFrame(corpo, fg_color="transparent")
        linha.pack(fill="x", pady=(0, 8))
        linha.grid_columnconfigure((0, 1), weight=1, uniform="botao")
        ctk.CTkButton(
            linha, text="Adicionar", height=tema.ALTURA_BOTAO, font=tema.FONTE_BOTAO,
            fg_color=tema.COR_PRIMARIA, hover_color=tema.COR_PRIMARIA_HOVER,
            text_color="white", command=self._adicionar,
        ).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ctk.CTkButton(
            linha, text="Renomear", height=tema.ALTURA_BOTAO, font=tema.FONTE_BOTAO,
            fg_color=tema.COR_PRIMARIA, hover_color=tema.COR_PRIMARIA_HOVER,
            text_color="white", command=self._renomear,
        ).grid(row=0, column=1, sticky="ew", padx=(6, 0))

        self._rotulo_erro = ctk.CTkLabel(
            corpo, text="", font=tema.FONTE_NORMAL, text_color=tema.COR_ERRO,
            wraplength=440, justify="left", anchor="w",
        )
        self._rotulo_erro.pack(fill="x", pady=(0, 8))

        rodape = ctk.CTkFrame(corpo, fg_color="transparent")
        rodape.pack(fill="x", side="bottom", pady=(12, 0))
        rodape.grid_columnconfigure((0, 1), weight=1, uniform="botao")
        ctk.CTkButton(
            rodape, text="Remover selecionada", height=tema.ALTURA_BOTAO, font=tema.FONTE_BOTAO,
            fg_color=tema.COR_ERRO, hover_color="#8A0019", text_color="white",
            command=self._remover,
        ).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ctk.CTkButton(
            rodape, text="Fechar", height=tema.ALTURA_BOTAO, font=tema.FONTE_BOTAO,
            fg_color=tema.COR_SECUNDARIA, hover_color=tema.COR_SECUNDARIA_HOVER,
            text_color=tema.COR_PRIMARIA, command=self.destroy,
        ).grid(row=0, column=1, sticky="ew", padx=(6, 0))

        area = ctk.CTkFrame(corpo, fg_color="transparent")
        area.pack(fill="both", expand=True)
        self._tabela = ttk.Treeview(
            area, columns=("nome",), show="headings", selectmode="browse",
            style=tabela.estilizar(self),
        )
        self._tabela.heading("nome", text="Nome", anchor="w")
        self._tabela.column("nome", anchor="w")
        barra = ctk.CTkScrollbar(area, command=self._tabela.yview)
        self._tabela.configure(yscrollcommand=barra.set)
        barra.pack(side="right", fill="y")
        self._tabela.pack(side="left", fill="both", expand=True)
        self._tabela.bind("<<TreeviewSelect>>", self._ao_selecionar)

    def _tornar_modal(self) -> None:
        try:
            self.lift()
            self.grab_set()
            self._entrada_nome.focus()
        except TclError:
            pass

    # ------------------------------------------------------------------ dados
    def _recarregar(self) -> None:
        self._tabela.delete(*self._tabela.get_children())
        for categoria in self._categorias.listar():
            self._tabela.insert("", "end", iid=str(categoria.id), values=(categoria.nome,))

    def _selecionada(self) -> int | None:
        selecao = self._tabela.selection()
        return int(selecao[0]) if selecao else None

    def _ao_selecionar(self, _evento=None) -> None:
        """Ao clicar numa categoria, o nome dela vai para o campo (para renomear)."""
        categoria_id = self._selecionada()
        if categoria_id is None:
            return
        nome = self._tabela.item(str(categoria_id), "values")[0]
        self._entrada_nome.delete(0, "end")
        self._entrada_nome.insert(0, nome)
        self._mostrar_erro("")

    def _mostrar_erro(self, mensagem: str) -> None:
        self._rotulo_erro.configure(text=mensagem)

    # ------------------------------------------------------------------ ações
    def _adicionar(self) -> None:
        try:
            self._categorias.criar(self._entrada_nome.get())
        except ErroDeNegocio as erro:
            self._mostrar_erro(str(erro))
            return
        self._entrada_nome.delete(0, "end")
        self._mostrar_erro("")
        self._recarregar()

    def _renomear(self) -> None:
        categoria_id = self._selecionada()
        if categoria_id is None:
            self._mostrar_erro("Clique numa categoria da lista para renomeá-la.")
            return
        try:
            self._categorias.renomear(categoria_id, self._entrada_nome.get())
        except ErroDeNegocio as erro:
            self._mostrar_erro(str(erro))
            return
        self._mostrar_erro("")
        self._recarregar()

    def _remover(self) -> None:
        categoria_id = self._selecionada()
        if categoria_id is None:
            self._mostrar_erro("Clique numa categoria da lista para removê-la.")
            return
        nome = self._tabela.item(str(categoria_id), "values")[0]
        if not messagebox.askyesno(
            "Remover categoria", f'Remover a categoria "{nome}"?', parent=self
        ):
            return
        try:
            self._categorias.remover(categoria_id)
        except ErroDeNegocio as erro:
            self._mostrar_erro(str(erro))
            return
        self._entrada_nome.delete(0, "end")
        self._mostrar_erro("")
        self._recarregar()
