"""Janela para cadastrar ou editar um produto (RF05)."""
from __future__ import annotations

from tkinter import TclError

import customtkinter as ctk

from src.dinheiro import formatar_numero, parse_reais
from src.errors import ErroDeNegocio
from src.repos.produto_repo import Produto
from src.services.categoria_service import CategoriaService
from src.services.produto_service import ProdutoService
from src.ui import tema


class ProdutoDialog(ctk.CTkToplevel):
    """Depois de `wait_window()`, consulte `salvo` para saber se algo foi gravado."""

    def __init__(
        self,
        master,
        produtos: ProdutoService,
        categorias: CategoriaService,
        produto: Produto | None = None,
    ) -> None:
        super().__init__(master)
        self.salvo = False
        self._produtos = produtos
        self._produto = produto
        self._ids = {c.nome: c.id for c in categorias.listar()}

        self.title("Editar produto" if produto else "Novo produto")
        self.geometry("460x520")
        self.resizable(False, False)
        self.transient(master)
        self.protocol("WM_DELETE_WINDOW", self.destroy)

        self._montar()
        self.after(150, self._tornar_modal)

    def _montar(self) -> None:
        corpo = ctk.CTkFrame(self, fg_color="transparent")
        corpo.pack(fill="both", expand=True, padx=32, pady=24)

        ctk.CTkLabel(
            corpo, text=self.title(), font=tema.FONTE_TITULO, text_color=tema.COR_PRIMARIA,
        ).pack(anchor="w", pady=(0, 16))

        ctk.CTkLabel(corpo, text="Nome", font=tema.FONTE_NORMAL, anchor="w").pack(fill="x")
        self._entrada_nome = ctk.CTkEntry(corpo, height=tema.ALTURA_CAMPO, font=tema.FONTE_NORMAL)
        self._entrada_nome.pack(fill="x", pady=(2, 12))

        ctk.CTkLabel(corpo, text="Categoria", font=tema.FONTE_NORMAL, anchor="w").pack(fill="x")
        nomes = list(self._ids)
        self._menu_categoria = ctk.CTkOptionMenu(
            corpo, values=nomes, height=tema.ALTURA_CAMPO, font=tema.FONTE_NORMAL,
            dropdown_font=tema.FONTE_NORMAL,
            fg_color=tema.COR_PRIMARIA, button_color=tema.COR_PRIMARIA_HOVER,
            button_hover_color=tema.COR_PRIMARIA_HOVER,
        )
        self._menu_categoria.pack(fill="x", pady=(2, 12))

        ctk.CTkLabel(corpo, text="Preço (R$)", font=tema.FONTE_NORMAL, anchor="w").pack(fill="x")
        self._entrada_preco = ctk.CTkEntry(
            corpo, height=tema.ALTURA_CAMPO, font=tema.FONTE_NORMAL, placeholder_text="0,00",
        )
        self._entrada_preco.pack(fill="x", pady=(2, 8))

        self._rotulo_erro = ctk.CTkLabel(
            corpo, text="", font=tema.FONTE_NORMAL, text_color=tema.COR_ERRO,
            wraplength=380, justify="left",
        )
        self._rotulo_erro.pack(fill="x", pady=(0, 8))

        botoes = ctk.CTkFrame(corpo, fg_color="transparent")
        botoes.pack(fill="x", side="bottom")
        botoes.grid_columnconfigure((0, 1), weight=1, uniform="botao")
        ctk.CTkButton(
            botoes, text="Cancelar", height=tema.ALTURA_BOTAO, font=tema.FONTE_BOTAO,
            fg_color=tema.COR_SECUNDARIA, hover_color=tema.COR_SECUNDARIA_HOVER,
            text_color=tema.COR_PRIMARIA, command=self.destroy,
        ).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ctk.CTkButton(
            botoes, text="Salvar", height=tema.ALTURA_BOTAO, font=tema.FONTE_BOTAO,
            fg_color=tema.COR_PRIMARIA, hover_color=tema.COR_PRIMARIA_HOVER,
            text_color="white", command=self._salvar,
        ).grid(row=0, column=1, sticky="ew", padx=(6, 0))

        if self._produto is not None:
            self._entrada_nome.insert(0, self._produto.nome)
            self._entrada_preco.insert(0, formatar_numero(self._produto.preco_centavos))
            if self._produto.categoria_nome in self._ids:
                self._menu_categoria.set(self._produto.categoria_nome)

        for campo in (self._entrada_nome, self._entrada_preco):
            campo.bind("<Return>", self._salvar)

    def _tornar_modal(self) -> None:
        """Trava a janela de trás enquanto esta estiver aberta."""
        try:
            self.lift()
            self.grab_set()
            self._entrada_nome.focus()
        except TclError:
            pass  # a janela já foi fechada

    def _salvar(self, _evento=None) -> None:
        try:
            preco = parse_reais(self._entrada_preco.get())
            categoria_id = self._ids.get(self._menu_categoria.get())
            nome = self._entrada_nome.get()
            if self._produto is not None:
                self._produtos.atualizar(self._produto.id, nome, categoria_id, preco)
            else:
                self._produtos.criar(nome, categoria_id, preco)
        except ErroDeNegocio as erro:
            self._rotulo_erro.configure(text=str(erro))
            return
        self.salvo = True
        self.destroy()
