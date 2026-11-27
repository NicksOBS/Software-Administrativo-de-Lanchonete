"""Tela de Clientes: lista com dívida, pesquisa (RF08, RF09), pagamento (RF11) e crédito."""
from __future__ import annotations

from tkinter import messagebox, ttk
from typing import Callable

import customtkinter as ctk

from src.dinheiro import formatar_reais
from src.errors import ErroDeNegocio
from src.repos.cliente_repo import Cliente
from src.services.cliente_service import ClienteService
from src.ui import tabela, tema
from src.ui.cliente_dialog import ClienteDialog
from src.ui.valor_dialog import ValorDialog

SITUACAO_BLOQUEADO = "Bloqueado (acima do limite)"


class ClientesFrame(ctk.CTkFrame):
    def __init__(
        self, master, clientes: ClienteService, ao_voltar: Callable[[], None]
    ) -> None:
        super().__init__(master, fg_color="transparent")
        self._clientes = clientes
        self._montar(ao_voltar)
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
            topo, text="Clientes", font=tema.FONTE_TITULO, text_color=tema.COR_PRIMARIA,
        ).pack(side="left", padx=20)

        busca = ctk.CTkFrame(self, fg_color="transparent")
        busca.pack(fill="x", padx=30, pady=(18, 0))
        self._entrada_busca = ctk.CTkEntry(
            busca, height=tema.ALTURA_CAMPO, font=tema.FONTE_NORMAL,
            placeholder_text="Pesquisar por código ou nome",
        )
        self._entrada_busca.pack(side="left", fill="x", expand=True)
        self._entrada_busca.bind("<KeyRelease>", lambda _e: self._recarregar())
        ctk.CTkButton(
            busca, text="🔍", width=56, height=tema.ALTURA_CAMPO, font=("Arial", 20),
            fg_color=tema.COR_PRIMARIA, hover_color=tema.COR_PRIMARIA_HOVER,
            text_color="white", command=self._recarregar,
        ).pack(side="left", padx=(8, 16))
        self._so_devedores = ctk.CTkCheckBox(
            busca, text="Só quem deve", font=tema.FONTE_NORMAL, text_color=tema.COR_TEXTO,
            fg_color=tema.COR_PRIMARIA, hover_color=tema.COR_PRIMARIA_HOVER,
            command=self._recarregar,
        )
        self._so_devedores.pack(side="left")

        botoes = ctk.CTkFrame(self, fg_color="transparent")
        botoes.pack(fill="x", side="bottom", padx=30, pady=(8, 24))
        botoes.grid_columnconfigure((0, 1, 2, 3, 4), weight=1, uniform="botao")
        acoes = [
            ("Novo cliente", self._novo, tema.COR_PRIMARIA, tema.COR_PRIMARIA_HOVER),
            ("Editar", self._editar, tema.COR_PRIMARIA, tema.COR_PRIMARIA_HOVER),
            ("Pagou", self._pagou, tema.COR_PRIMARIA, tema.COR_PRIMARIA_HOVER),
            ("+ Crédito", self._adicionar_credito, tema.COR_PRIMARIA, tema.COR_PRIMARIA_HOVER),
            ("Remover", self._remover, tema.COR_ERRO, "#8A0019"),
        ]
        for coluna, (texto, comando, cor, cor_hover) in enumerate(acoes):
            ctk.CTkButton(
                botoes, text=texto, height=tema.ALTURA_BOTAO, font=tema.FONTE_BOTAO,
                fg_color=cor, hover_color=cor_hover, text_color="white", command=comando,
            ).grid(row=0, column=coluna, sticky="ew", padx=4)

        self._rotulo_total = ctk.CTkLabel(
            self, text="", font=tema.FONTE_NORMAL, text_color=tema.COR_TEXTO_SUAVE, anchor="w",
        )
        self._rotulo_total.pack(fill="x", side="bottom", padx=34, pady=(10, 0))

        area = ctk.CTkFrame(self, fg_color="transparent")
        area.pack(fill="both", expand=True, padx=30, pady=(16, 0))
        self._tabela = ttk.Treeview(
            area, columns=("codigo", "nome", "divida", "credito", "limite", "situacao"),
            show="headings", selectmode="browse", style=tabela.estilizar(self),
        )
        cabecalhos = [
            ("codigo", "Código", 80, "e"), ("nome", "Nome", 240, "w"),
            ("divida", "Deve", 110, "e"), ("credito", "Crédito", 110, "e"),
            ("limite", "Limite", 110, "e"), ("situacao", "Situação", 200, "w"),
        ]
        for coluna, texto, largura, alinhamento in cabecalhos:
            self._tabela.heading(coluna, text=texto, anchor=alinhamento)
            self._tabela.column(coluna, width=largura, anchor=alinhamento)
        barra = ctk.CTkScrollbar(area, command=self._tabela.yview)
        self._tabela.configure(yscrollcommand=barra.set)
        barra.pack(side="right", fill="y")
        self._tabela.pack(side="left", fill="both", expand=True)
        self._tabela.bind("<Double-1>", lambda _e: self._editar())

    # ------------------------------------------------------------------- dados
    def _selecionado(self) -> int | None:
        selecao = self._tabela.selection()
        return int(selecao[0]) if selecao else None

    def _recarregar(self, selecionar: int | None = None) -> None:
        clientes = self._clientes.listar(
            self._entrada_busca.get(), bool(self._so_devedores.get())
        )
        self._tabela.delete(*self._tabela.get_children())
        for c in clientes:
            self._tabela.insert(
                "", "end", iid=str(c.codigo),
                values=(
                    str(c.codigo), c.nome,
                    formatar_reais(c.divida_centavos),
                    formatar_reais(c.credito_centavos),
                    "Sem limite" if c.limite_centavos is None else formatar_reais(c.limite_centavos),
                    SITUACAO_BLOQUEADO if c.bloqueado else "",
                ),
            )
        if selecionar is not None and str(selecionar) in self._tabela.get_children():
            self._tabela.selection_set(str(selecionar))
            self._tabela.see(str(selecionar))

        total = sum(c.divida_centavos for c in clientes)
        plural = "cliente" if len(clientes) == 1 else "clientes"
        self._rotulo_total.configure(
            text=f"{len(clientes)} {plural}   ·   Total devendo: {formatar_reais(total)}"
        )

    def _cliente_selecionado(self, titulo: str) -> Cliente | None:
        codigo = self._selecionado()
        if codigo is None:
            messagebox.showinfo(titulo, "Clique num cliente da lista primeiro.")
            return None
        try:
            return self._clientes.obter(codigo)
        except ErroDeNegocio as erro:
            messagebox.showerror(titulo, str(erro))
            self._recarregar()
            return None

    # ------------------------------------------------------------------ ações
    def _novo(self) -> None:
        dialogo = ClienteDialog(self.winfo_toplevel(), self._clientes)
        dialogo.wait_window()
        if dialogo.salvo:
            self._recarregar()

    def _editar(self) -> None:
        cliente = self._cliente_selecionado("Editar cliente")
        if cliente is None:
            return
        dialogo = ClienteDialog(self.winfo_toplevel(), self._clientes, cliente)
        dialogo.wait_window()
        if dialogo.salvo:
            self._recarregar(selecionar=cliente.codigo)

    def _pagou(self) -> None:
        cliente = self._cliente_selecionado("Registrar pagamento")
        if cliente is None:
            return
        if cliente.divida_centavos == 0:
            messagebox.showinfo("Registrar pagamento", f"{cliente.nome} não tem dívida.")
            return
        dialogo = ValorDialog(
            self.winfo_toplevel(),
            titulo="Registrar pagamento",
            info=f"{cliente.nome} (código {cliente.codigo})\n"
                 f"Dívida atual: {formatar_reais(cliente.divida_centavos)}",
            texto_confirmar="Registrar",
            ao_confirmar=lambda valor: self._clientes.registrar_pagamento(cliente.codigo, valor),
            atalho=("Pagar tudo", cliente.divida_centavos),
        )
        dialogo.wait_window()
        if dialogo.salvo:
            self._recarregar(selecionar=cliente.codigo)

    def _adicionar_credito(self) -> None:
        cliente = self._cliente_selecionado("Adicionar crédito")
        if cliente is None:
            return
        dialogo = ValorDialog(
            self.winfo_toplevel(),
            titulo="Adicionar crédito",
            info=f"{cliente.nome} (código {cliente.codigo})\n"
                 f"Crédito atual: {formatar_reais(cliente.credito_centavos)}",
            texto_confirmar="Adicionar",
            ao_confirmar=lambda valor: self._clientes.adicionar_credito(cliente.codigo, valor),
        )
        dialogo.wait_window()
        if dialogo.salvo:
            self._recarregar(selecionar=cliente.codigo)

    def _remover(self) -> None:
        cliente = self._cliente_selecionado("Remover cliente")
        if cliente is None:
            return
        if not messagebox.askyesno(
            "Remover cliente",
            f'Remover "{cliente.nome}" (código {cliente.codigo})?\n\n'
            "O histórico de pagamentos e de vendas dele continua guardado.",
        ):
            return
        try:
            self._clientes.remover(cliente.codigo)
        except ErroDeNegocio as erro:
            messagebox.showerror("Remover cliente", str(erro))
        self._recarregar()
