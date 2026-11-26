"""Tela de Produtos: lista, pesquisa com lupa (RF06) e cadastro (RF05)."""
from __future__ import annotations

from tkinter import messagebox, ttk
from typing import Callable

import customtkinter as ctk

from src.dinheiro import formatar_reais
from src.errors import ErroDeNegocio
from src.services.categoria_service import CategoriaService
from src.services.produto_service import ProdutoService
from src.ui import tabela, tema
from src.ui.categorias_dialog import CategoriasDialog
from src.ui.produto_dialog import ProdutoDialog

TODAS = "Todas as categorias"


class ProdutosFrame(ctk.CTkFrame):
    def __init__(
        self,
        master,
        produtos: ProdutoService,
        categorias: CategoriaService,
        ao_voltar: Callable[[], None],
    ) -> None:
        super().__init__(master, fg_color="transparent")
        self._produtos = produtos
        self._categorias = categorias
        self._ids_categoria: dict[str, int] = {}

        self._montar(ao_voltar)
        self._recarregar_categorias()
        self._recarregar()

    # ------------------------------------------------------------------ layout
    def _montar(self, ao_voltar: Callable[[], None]) -> None:
        topo = ctk.CTkFrame(self, fg_color="transparent")
        topo.pack(fill="x", padx=30, pady=(24, 0))
        ctk.CTkButton(
            topo, text="← Voltar", width=120, height=tema.ALTURA_BOTAO, font=tema.FONTE_BOTAO,
            fg_color=tema.COR_SECUNDARIA, hover_color=tema.COR_SECUNDARIA_HOVER,
            text_color=tema.COR_PRIMARIA, command=ao_voltar,
        ).pack(side="left")
        ctk.CTkLabel(
            topo, text="Produtos", font=tema.FONTE_TITULO, text_color=tema.COR_PRIMARIA,
        ).pack(side="left", padx=20)
        ctk.CTkButton(
            topo, text="Categorias", width=150, height=tema.ALTURA_BOTAO, font=tema.FONTE_BOTAO,
            fg_color=tema.COR_PRIMARIA, hover_color=tema.COR_PRIMARIA_HOVER,
            text_color="white", command=self._abrir_categorias,
        ).pack(side="right")

        busca = ctk.CTkFrame(self, fg_color="transparent")
        busca.pack(fill="x", padx=30, pady=(18, 0))
        self._entrada_busca = ctk.CTkEntry(
            busca, height=tema.ALTURA_CAMPO, font=tema.FONTE_NORMAL,
            placeholder_text="Pesquisar por nome ou categoria",
        )
        self._entrada_busca.pack(side="left", fill="x", expand=True)
        self._entrada_busca.bind("<KeyRelease>", lambda _e: self._recarregar())
        ctk.CTkButton(
            busca, text="🔍", width=56, height=tema.ALTURA_CAMPO, font=("Arial", 20),
            fg_color=tema.COR_PRIMARIA, hover_color=tema.COR_PRIMARIA_HOVER,
            text_color="white", command=self._recarregar,
        ).pack(side="left", padx=(8, 12))
        self._menu_categoria = ctk.CTkOptionMenu(
            busca, values=[TODAS], width=240, height=tema.ALTURA_CAMPO,
            font=tema.FONTE_NORMAL, dropdown_font=tema.FONTE_NORMAL,
            fg_color=tema.COR_PRIMARIA, button_color=tema.COR_PRIMARIA_HOVER,
            button_hover_color=tema.COR_PRIMARIA_HOVER,
            command=lambda _valor: self._recarregar(),
        )
        self._menu_categoria.pack(side="left")

        rodape = ctk.CTkFrame(self, fg_color="transparent")
        rodape.pack(fill="x", side="bottom", padx=30, pady=(12, 24))
        self._rotulo_total = ctk.CTkLabel(
            rodape, text="", font=tema.FONTE_NORMAL, text_color=tema.COR_TEXTO_SUAVE,
        )
        self._rotulo_total.pack(side="left")
        ctk.CTkButton(
            rodape, text="Remover", width=140, height=tema.ALTURA_BOTAO, font=tema.FONTE_BOTAO,
            fg_color=tema.COR_ERRO, hover_color="#8A0019", text_color="white",
            command=self._remover,
        ).pack(side="right")
        ctk.CTkButton(
            rodape, text="Editar", width=140, height=tema.ALTURA_BOTAO, font=tema.FONTE_BOTAO,
            fg_color=tema.COR_PRIMARIA, hover_color=tema.COR_PRIMARIA_HOVER,
            text_color="white", command=self._editar,
        ).pack(side="right", padx=10)
        ctk.CTkButton(
            rodape, text="Novo produto", width=180, height=tema.ALTURA_BOTAO,
            font=tema.FONTE_BOTAO, fg_color=tema.COR_PRIMARIA,
            hover_color=tema.COR_PRIMARIA_HOVER, text_color="white", command=self._novo,
        ).pack(side="right")

        area = ctk.CTkFrame(self, fg_color="transparent")
        area.pack(fill="both", expand=True, padx=30, pady=(16, 0))
        self._tabela = ttk.Treeview(
            area, columns=("nome", "categoria", "preco"), show="headings",
            selectmode="browse", style=tabela.estilizar(self),
        )
        self._tabela.heading("nome", text="Produto", anchor="w")
        self._tabela.heading("categoria", text="Categoria", anchor="w")
        self._tabela.heading("preco", text="Preço", anchor="e")
        self._tabela.column("nome", width=360, anchor="w")
        self._tabela.column("categoria", width=200, anchor="w")
        self._tabela.column("preco", width=120, anchor="e")
        barra = ctk.CTkScrollbar(area, command=self._tabela.yview)
        self._tabela.configure(yscrollcommand=barra.set)
        barra.pack(side="right", fill="y")
        self._tabela.pack(side="left", fill="both", expand=True)
        self._tabela.bind("<Double-1>", lambda _e: self._editar())

    # ------------------------------------------------------------------- dados
    def _categoria_selecionada(self) -> int | None:
        return self._ids_categoria.get(self._menu_categoria.get())  # None = todas

    def _selecionado(self) -> int | None:
        selecao = self._tabela.selection()
        return int(selecao[0]) if selecao else None

    def _recarregar_categorias(self) -> None:
        categorias = self._categorias.listar()
        self._ids_categoria = {c.nome: c.id for c in categorias}
        valores = [TODAS] + list(self._ids_categoria)
        self._menu_categoria.configure(values=valores)
        if self._menu_categoria.get() not in valores:
            self._menu_categoria.set(TODAS)

    def _recarregar(self) -> None:
        produtos = self._produtos.listar(
            self._entrada_busca.get(), self._categoria_selecionada()
        )
        self._tabela.delete(*self._tabela.get_children())
        for p in produtos:
            self._tabela.insert(
                "", "end", iid=str(p.id),
                values=(p.nome, p.categoria_nome or "(sem categoria)", formatar_reais(p.preco_centavos)),
            )
        plural = "produto" if len(produtos) == 1 else "produtos"
        self._rotulo_total.configure(text=f"{len(produtos)} {plural}")

    # ------------------------------------------------------------------ ações
    def _abrir_categorias(self) -> None:
        dialogo = CategoriasDialog(self.winfo_toplevel(), self._categorias)
        dialogo.wait_window()
        self._recarregar_categorias()
        self._recarregar()

    def _novo(self) -> None:
        if not self._categorias.listar():
            messagebox.showinfo(
                "Crie uma categoria primeiro",
                "Antes de cadastrar produtos, crie ao menos uma categoria "
                "(por exemplo: Salgados, Bebidas).",
            )
            self._abrir_categorias()
            return
        dialogo = ProdutoDialog(self.winfo_toplevel(), self._produtos, self._categorias)
        dialogo.wait_window()
        if dialogo.salvo:
            self._recarregar()

    def _editar(self) -> None:
        produto_id = self._selecionado()
        if produto_id is None:
            messagebox.showinfo("Editar produto", "Clique num produto da lista para editá-lo.")
            return
        try:
            produto = self._produtos.obter(produto_id)
        except ErroDeNegocio as erro:
            messagebox.showerror("Editar produto", str(erro))
            self._recarregar()
            return
        dialogo = ProdutoDialog(
            self.winfo_toplevel(), self._produtos, self._categorias, produto
        )
        dialogo.wait_window()
        if dialogo.salvo:
            self._recarregar()

    def _remover(self) -> None:
        produto_id = self._selecionado()
        if produto_id is None:
            messagebox.showinfo("Remover produto", "Clique num produto da lista para removê-lo.")
            return
        nome = self._tabela.item(str(produto_id), "values")[0]
        if not messagebox.askyesno(
            "Remover produto",
            f'Remover "{nome}"?\n\nEle deixa de aparecer na lista, mas as vendas '
            "já registradas continuam como estavam.",
        ):
            return
        try:
            self._produtos.remover(produto_id)
        except ErroDeNegocio as erro:
            messagebox.showerror("Remover produto", str(erro))
        self._recarregar()
