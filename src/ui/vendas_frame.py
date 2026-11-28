"""Tela de Vendas: monta o pedido, mostra o resumo e registra a venda (RF02, RF03, RF10)."""
from __future__ import annotations

from tkinter import messagebox, ttk
from typing import Callable

import customtkinter as ctk

from src.dinheiro import formatar_reais
from src.errors import ErroDeNegocio
from src.repos.cliente_repo import Cliente
from src.repos.produto_repo import Produto
from src.services.cliente_service import ClienteService
from src.services.configuracao_service import ConfiguracaoService
from src.services.expediente_service import ExpedienteService
from src.services.produto_service import ProdutoService
from src.services.venda_service import (
    FORMAS_PAGAMENTO, PERCENTUAL_DESCONTO, ItemPedido, Resumo, VendaService,
)
from src.ui import tabela, tema
from src.ui.cliente_escolha_dialog import ClienteEscolhaDialog
from src.ui.valor_dialog import ValorDialog

ROTULOS_FORMA = {
    "dinheiro": "Dinheiro", "pix": "PIX", "debito": "Débito", "credito": "Crédito", "fiado": "Fiado",
}


class VendasFrame(ctk.CTkFrame):
    def __init__(
        self,
        master,
        vendas: VendaService,
        produtos: ProdutoService,
        clientes: ClienteService,
        configuracao: ConfiguracaoService,
        ao_voltar: Callable[[], None],
        expedientes: ExpedienteService | None = None,
    ) -> None:
        super().__init__(master, fg_color="transparent")
        self._vendas = vendas
        self._produtos = produtos
        self._clientes = clientes
        self._configuracao = configuracao
        self._ao_voltar = ao_voltar

        self._carrinho: dict[int, int] = {}      # produto_id -> quantidade
        self._produto_por_id: dict[int, Produto] = {}
        self._cliente: Cliente | None = None
        self._forma: str | None = None
        self._botoes_forma: dict[str, ctk.CTkButton] = {}

        self._montar()
        self._recarregar_produtos()
        self._atualizar_resumo()
        if expedientes is not None and expedientes.aberto() is None:
            self._aviso("O expediente está fechado. Inicie o expediente para registrar vendas.")

    def tem_pendencia(self) -> bool:
        """Há itens no pedido ainda não finalizados (usado no aviso ao fechar, RNF02)."""
        return bool(self._carrinho)

    # ------------------------------------------------------------------ layout
    def _montar(self) -> None:
        topo = ctk.CTkFrame(self, fg_color="transparent")
        topo.pack(fill="x", padx=30, pady=(20, 0))
        ctk.CTkButton(
            topo, text="← Voltar", width=120, height=tema.ALTURA_BOTAO, font=tema.FONTE_BOTAO,
            fg_color=tema.COR_SECUNDARIA, hover_color=tema.COR_SECUNDARIA_HOVER,
            text_color=tema.COR_PRIMARIA, command=self._voltar,
        ).pack(side="left")
        ctk.CTkLabel(
            topo, text="Nova venda", font=tema.FONTE_TITULO, text_color=tema.COR_PRIMARIA,
        ).pack(side="left", padx=20)
        ctk.CTkButton(
            topo, text="Desconto", width=140, height=tema.ALTURA_BOTAO, font=tema.FONTE_BOTAO,
            fg_color=tema.COR_SECUNDARIA, hover_color=tema.COR_SECUNDARIA_HOVER,
            text_color=tema.COR_PRIMARIA, command=self._configurar_desconto,
        ).pack(side="right")

        corpo = ctk.CTkFrame(self, fg_color="transparent")
        corpo.pack(fill="both", expand=True, padx=30, pady=(14, 20))
        corpo.grid_columnconfigure(0, weight=5, uniform="col")
        corpo.grid_columnconfigure(1, weight=6, uniform="col")
        corpo.grid_rowconfigure(0, weight=1)

        self._montar_produtos(corpo)
        self._montar_pedido(corpo)

    def _montar_produtos(self, corpo) -> None:
        esq = ctk.CTkFrame(corpo, fg_color="transparent")
        esq.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        self._busca = ctk.CTkEntry(
            esq, height=tema.ALTURA_CAMPO, font=tema.FONTE_NORMAL,
            placeholder_text="Pesquisar produto",
        )
        self._busca.pack(fill="x")
        self._busca.bind("<KeyRelease>", lambda _e: self._recarregar_produtos())

        adicionar = ctk.CTkFrame(esq, fg_color="transparent")
        adicionar.pack(fill="x", side="bottom", pady=(10, 0))
        ctk.CTkLabel(adicionar, text="Qtd.", font=tema.FONTE_NORMAL).pack(side="left")
        self._qtd = ctk.CTkEntry(
            adicionar, width=70, height=tema.ALTURA_BOTAO, font=tema.FONTE_NORMAL, justify="center",
        )
        self._qtd.insert(0, "1")
        self._qtd.pack(side="left", padx=8)
        self._qtd.bind("<Return>", lambda _e: self._adicionar())
        ctk.CTkButton(
            adicionar, text="Adicionar ao pedido", height=tema.ALTURA_BOTAO, font=tema.FONTE_BOTAO,
            fg_color=tema.COR_PRIMARIA, hover_color=tema.COR_PRIMARIA_HOVER,
            text_color="white", command=self._adicionar,
        ).pack(side="left", fill="x", expand=True)

        area = ctk.CTkFrame(esq, fg_color="transparent")
        area.pack(fill="both", expand=True, pady=(10, 0))
        self._tab_produtos = ttk.Treeview(
            area, columns=("nome", "preco"), show="headings", selectmode="browse",
            style=tabela.estilizar(self),
        )
        self._tab_produtos.heading("nome", text="Produto", anchor="w")
        self._tab_produtos.heading("preco", text="Preço", anchor="e")
        self._tab_produtos.column("nome", width=200, anchor="w")
        self._tab_produtos.column("preco", width=90, anchor="e")
        barra = ctk.CTkScrollbar(area, command=self._tab_produtos.yview)
        self._tab_produtos.configure(yscrollcommand=barra.set)
        barra.pack(side="right", fill="y")
        self._tab_produtos.pack(side="left", fill="both", expand=True)
        self._tab_produtos.bind("<Double-1>", lambda _e: self._adicionar())

    def _montar_pedido(self, corpo) -> None:
        dir_ = ctk.CTkFrame(corpo, fg_color="transparent")
        dir_.grid(row=0, column=1, sticky="nsew", padx=(10, 0))

        # Parte de baixo primeiro (empacotada de baixo para cima).
        self._rotulo_status = ctk.CTkLabel(
            dir_, text="", font=tema.FONTE_NORMAL, text_color=tema.COR_ERRO,
            wraplength=480, justify="left", anchor="w",
        )
        self._rotulo_status.pack(fill="x", side="bottom", pady=(6, 0))
        ctk.CTkButton(
            dir_, text="Finalizar venda", height=56, font=tema.FONTE_BOTAO,
            fg_color=tema.COR_SUCESSO, hover_color="#144618", text_color="white",
            command=self._finalizar,
        ).pack(fill="x", side="bottom", pady=(10, 0))

        formas = ctk.CTkFrame(dir_, fg_color="transparent")
        formas.pack(fill="x", side="bottom", pady=(8, 0))
        formas.grid_columnconfigure(tuple(range(len(FORMAS_PAGAMENTO))), weight=1, uniform="forma")
        for coluna, forma in enumerate(FORMAS_PAGAMENTO):
            botao = ctk.CTkButton(
                formas, text=ROTULOS_FORMA[forma], height=tema.ALTURA_BOTAO, font=tema.FONTE_NORMAL,
                command=lambda f=forma: self._escolher_forma(f),
            )
            botao.grid(row=0, column=coluna, sticky="ew", padx=2)
            self._botoes_forma[forma] = botao
        self._pintar_formas()

        ctk.CTkLabel(
            dir_, text="Forma de pagamento", font=tema.FONTE_NORMAL, anchor="w",
        ).pack(fill="x", side="bottom", pady=(10, 0))

        resumo = ctk.CTkFrame(dir_, fg_color=tema.COR_SECUNDARIA, corner_radius=10)
        resumo.pack(fill="x", side="bottom", pady=(8, 0))
        resumo.grid_columnconfigure(1, weight=1)
        self._val = {}
        for linha, (chave, texto) in enumerate(
            [("subtotal", "Subtotal"), ("desconto", "Desconto"), ("credito", "Crédito do cliente")]
        ):
            ctk.CTkLabel(resumo, text=texto, font=tema.FONTE_NORMAL, anchor="w").grid(
                row=linha, column=0, sticky="w", padx=14, pady=(6 if linha == 0 else 0, 0))
            self._val[chave] = ctk.CTkLabel(resumo, text="", font=tema.FONTE_NORMAL, anchor="e")
            self._val[chave].grid(row=linha, column=1, sticky="e", padx=14,
                                  pady=(6 if linha == 0 else 0, 0))
        ctk.CTkLabel(
            resumo, text="Total a pagar", font=tema.FONTE_BOTAO, text_color=tema.COR_PRIMARIA, anchor="w",
        ).grid(row=3, column=0, sticky="w", padx=14, pady=(4, 8))
        self._val["total"] = ctk.CTkLabel(
            resumo, text="", font=tema.FONTE_TOTAL, text_color=tema.COR_PRIMARIA, anchor="e",
        )
        self._val["total"].grid(row=3, column=1, sticky="e", padx=14, pady=(4, 8))

        cliente = ctk.CTkFrame(dir_, fg_color="transparent")
        cliente.pack(fill="x", side="bottom", pady=(8, 0))
        ctk.CTkButton(
            cliente, text="Cliente", width=110, height=tema.ALTURA_BOTAO, font=tema.FONTE_BOTAO,
            fg_color=tema.COR_PRIMARIA, hover_color=tema.COR_PRIMARIA_HOVER,
            text_color="white", command=self._escolher_cliente,
        ).pack(side="left")
        self._rotulo_cliente = ctk.CTkLabel(
            cliente, text="", font=tema.FONTE_NORMAL, anchor="w", justify="left", wraplength=220,
        )
        self._rotulo_cliente.pack(side="left", padx=10, fill="x", expand=True)
        self._usar_credito = ctk.CTkCheckBox(
            cliente, text="Usar crédito", font=tema.FONTE_NORMAL, text_color=tema.COR_TEXTO,
            fg_color=tema.COR_PRIMARIA, hover_color=tema.COR_PRIMARIA_HOVER,
            command=self._atualizar_resumo,
        )
        self._usar_credito.pack(side="right")

        acoes = ctk.CTkFrame(dir_, fg_color="transparent")
        acoes.pack(fill="x", side="bottom", pady=(8, 0))
        acoes.grid_columnconfigure((0, 1, 2, 3), weight=1, uniform="acao")
        for coluna, (texto, comando) in enumerate(
            [("− 1", lambda: self._mudar_qtd(-1)), ("+ 1", lambda: self._mudar_qtd(1)),
             ("Remover", self._remover_item), ("Limpar", self._limpar)]
        ):
            ctk.CTkButton(
                acoes, text=texto, height=tema.ALTURA_BOTAO, font=tema.FONTE_BOTAO,
                fg_color=tema.COR_SECUNDARIA, hover_color=tema.COR_SECUNDARIA_HOVER,
                text_color=tema.COR_PRIMARIA, command=comando,
            ).grid(row=0, column=coluna, sticky="ew", padx=2)

        area = ctk.CTkFrame(dir_, fg_color="transparent")
        area.pack(fill="both", expand=True)
        self._tab_carrinho = ttk.Treeview(
            area, columns=("nome", "qtd", "preco", "subtotal"), show="headings",
            selectmode="browse", style=tabela.estilizar(self),
        )
        for coluna, texto, largura, alinhamento in [
            ("nome", "Item", 170, "w"), ("qtd", "Qtd.", 50, "e"),
            ("preco", "Preço", 80, "e"), ("subtotal", "Subtotal", 90, "e"),
        ]:
            self._tab_carrinho.heading(coluna, text=texto, anchor=alinhamento)
            self._tab_carrinho.column(coluna, width=largura, anchor=alinhamento)
        barra = ctk.CTkScrollbar(area, command=self._tab_carrinho.yview)
        self._tab_carrinho.configure(yscrollcommand=barra.set)
        barra.pack(side="right", fill="y")
        self._tab_carrinho.pack(side="left", fill="both", expand=True)

    # ---------------------------------------------------------------- produtos
    def _recarregar_produtos(self) -> None:
        produtos = self._produtos.listar(self._busca.get())
        self._produto_por_id = {p.id: p for p in produtos}
        self._tab_produtos.delete(*self._tab_produtos.get_children())
        for p in produtos:
            self._tab_produtos.insert(
                "", "end", iid=str(p.id), values=(p.nome, formatar_reais(p.preco_centavos)),
            )

    def _adicionar(self) -> None:
        selecao = self._tab_produtos.selection()
        if not selecao:
            self._aviso("Clique num produto da lista primeiro.")
            return
        texto = self._qtd.get().strip()
        if not texto.isdigit() or int(texto) <= 0:
            self._aviso("A quantidade deve ser um número inteiro maior que zero.")
            return
        produto_id = int(selecao[0])
        self._carrinho[produto_id] = self._carrinho.get(produto_id, 0) + int(texto)
        self._qtd.delete(0, "end")
        self._qtd.insert(0, "1")
        self._atualizar_resumo(selecionar=produto_id)

    # ----------------------------------------------------------------- carrinho
    def _item_selecionado(self) -> int | None:
        selecao = self._tab_carrinho.selection()
        return int(selecao[0]) if selecao else None

    def _mudar_qtd(self, delta: int) -> None:
        produto_id = self._item_selecionado()
        if produto_id is None:
            self._aviso("Clique num item do pedido primeiro.")
            return
        nova = self._carrinho[produto_id] + delta
        if nova <= 0:
            del self._carrinho[produto_id]
            produto_id = None
        else:
            self._carrinho[produto_id] = nova
        self._atualizar_resumo(selecionar=produto_id)

    def _remover_item(self) -> None:
        produto_id = self._item_selecionado()
        if produto_id is None:
            self._aviso("Clique num item do pedido primeiro.")
            return
        del self._carrinho[produto_id]
        self._atualizar_resumo()

    def _limpar(self) -> None:
        if self._carrinho and not messagebox.askyesno("Limpar pedido", "Tirar todos os itens do pedido?"):
            return
        self._carrinho.clear()
        self._atualizar_resumo()

    def _pedido(self) -> list[ItemPedido]:
        return [ItemPedido(pid, q) for pid, q in self._carrinho.items()]

    # ------------------------------------------------------------------ cliente
    def _escolher_cliente(self) -> None:
        dialogo = ClienteEscolhaDialog(self.winfo_toplevel(), self._clientes)
        dialogo.wait_window()
        if dialogo.escolhido is not None:
            self._cliente = dialogo.escolhido
        elif dialogo.limpou:
            self._cliente = None
            self._usar_credito.deselect()
        else:
            return
        self._atualizar_resumo()

    # ---------------------------------------------------------------- pagamento
    def _escolher_forma(self, forma: str) -> None:
        self._forma = forma
        self._pintar_formas()
        self._aviso("")

    def _pintar_formas(self) -> None:
        for forma, botao in self._botoes_forma.items():
            if forma == self._forma:
                botao.configure(fg_color=tema.COR_PRIMARIA, hover_color=tema.COR_PRIMARIA_HOVER,
                                text_color="white")
            else:
                botao.configure(fg_color=tema.COR_SECUNDARIA, hover_color=tema.COR_SECUNDARIA_HOVER,
                                text_color=tema.COR_PRIMARIA)

    # ------------------------------------------------------------------- resumo
    def _calcular(self) -> Resumo | None:
        usar = bool(self._usar_credito.get()) and self._cliente is not None
        try:
            return self._vendas.calcular(
                self._pedido(), self._cliente.codigo if self._cliente else None, usar
            )
        except ErroDeNegocio as erro:
            self._aviso(str(erro))
            return None

    def _atualizar_resumo(self, selecionar: int | None = None) -> None:
        resumo = self._calcular()

        self._tab_carrinho.delete(*self._tab_carrinho.get_children())
        if resumo is not None:
            for item in resumo.itens:
                self._tab_carrinho.insert(
                    "", "end", iid=str(item.produto_id),
                    values=(item.nome, item.quantidade, formatar_reais(item.preco_unitario_centavos),
                            formatar_reais(item.subtotal_centavos)),
                )
            if selecionar is not None and str(selecionar) in self._tab_carrinho.get_children():
                self._tab_carrinho.selection_set(str(selecionar))
        else:
            resumo = Resumo((), 0, 0, 0, 0)

        minimo = self._configuracao.valor_minimo_desconto()
        if resumo.desconto_centavos:
            texto_desc = f"− {formatar_reais(resumo.desconto_centavos)} ({PERCENTUAL_DESCONTO}%)"
        elif minimo is None:
            texto_desc = "—"
        else:
            texto_desc = f"acima de {formatar_reais(minimo)}"
        self._val["subtotal"].configure(text=formatar_reais(resumo.subtotal_centavos))
        self._val["desconto"].configure(text=texto_desc)
        self._val["credito"].configure(
            text="− " + formatar_reais(resumo.credito_usado_centavos)
            if resumo.credito_usado_centavos else "—"
        )
        self._val["total"].configure(text=formatar_reais(resumo.a_pagar_centavos))

        if self._cliente is None:
            self._rotulo_cliente.configure(text="Nenhum cliente (opcional)")
        else:
            c = self._cliente
            self._rotulo_cliente.configure(
                text=f"{c.nome} · cód. {c.codigo}\nDeve {formatar_reais(c.divida_centavos)} · "
                     f"Crédito {formatar_reais(c.credito_centavos)}"
            )

    def _configurar_desconto(self) -> None:
        minimo = self._configuracao.valor_minimo_desconto()
        atual = "sem desconto" if minimo is None else f"acima de {formatar_reais(minimo)}"
        dialogo = ValorDialog(
            self.winfo_toplevel(),
            titulo="Desconto de 15%",
            info=f"Vendas acima deste valor ganham {PERCENTUAL_DESCONTO}% de desconto.\n"
                 f"Hoje: {atual}.\nDeixe em branco para não dar desconto.",
            texto_confirmar="Salvar",
            ao_confirmar=self._configuracao.definir_valor_minimo_desconto,
            permitir_vazio=True,
            valor_inicial=minimo,
            placeholder="Sem desconto",
        )
        dialogo.wait_window()
        if dialogo.salvo:
            self._atualizar_resumo()

    # ----------------------------------------------------------------- finalizar
    def _finalizar(self) -> None:
        if not self._carrinho:  # RF03
            messagebox.showwarning("Nova venda", "Adicione ao menos um produto à venda.")
            return
        if self._forma is None:
            self._aviso("Escolha a forma de pagamento.")
            return
        usar = bool(self._usar_credito.get()) and self._cliente is not None
        try:
            venda = self._vendas.registrar(
                self._pedido(), self._forma,
                self._cliente.codigo if self._cliente else None, usar,
            )
        except ErroDeNegocio as erro:
            messagebox.showerror("Nova venda", str(erro))
            return

        r = venda.resumo
        linhas = [f"Total: {formatar_reais(r.total_centavos)}"]
        if r.credito_usado_centavos:
            linhas.append(f"Pago com crédito: {formatar_reais(r.credito_usado_centavos)}")
        if venda.forma_pagamento == "fiado":
            linhas.append(f"Anotado no fiado: {formatar_reais(r.a_pagar_centavos)}")
        elif r.a_pagar_centavos:
            linhas.append(f"{ROTULOS_FORMA[venda.forma_pagamento]}: {formatar_reais(r.a_pagar_centavos)}")
        messagebox.showinfo("Venda registrada", "\n".join(linhas))
        self._nova_venda()

    def _nova_venda(self) -> None:
        self._carrinho.clear()
        self._cliente = None
        self._forma = None
        self._usar_credito.deselect()
        self._pintar_formas()
        self._aviso("")
        self._atualizar_resumo()

    # ------------------------------------------------------------------- apoio
    def _aviso(self, texto: str) -> None:
        self._rotulo_status.configure(text=texto)

    def _voltar(self) -> None:
        if self._carrinho and not messagebox.askyesno(
            "Sair da venda", "Há itens no pedido que ainda não foram finalizados.\nSair mesmo assim?"
        ):
            return
        self._ao_voltar()
