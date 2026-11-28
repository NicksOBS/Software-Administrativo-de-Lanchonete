"""Tela de Expediente: iniciar/encerrar (RF12), pasta das planilhas (RF14) e
quantidade vendida por produto (RF15)."""
from __future__ import annotations

from datetime import datetime
from tkinter import messagebox, ttk
from typing import Callable

import customtkinter as ctk

from src.dinheiro import formatar_reais
from src.errors import ErroDeNegocio
from src.services.expediente_service import ExpedienteService
from src.ui import tabela, tema

PERIODOS = [("hoje", "Hoje"), ("mes_atual", "Este mês"), ("mes_anterior", "Mês anterior")]


def escolher_pasta_no_windows(inicial: str) -> str:
    """Abre a janela de escolher pasta. Devolve "" se a pessoa cancelar."""
    from tkinter import filedialog

    return filedialog.askdirectory(initialdir=inicial, title="Pasta das planilhas", mustexist=True) or ""


class ExpedienteFrame(ctk.CTkFrame):
    def __init__(
        self,
        master,
        expedientes: ExpedienteService,
        ao_voltar: Callable[[], None],
        escolher_pasta: Callable[[str], str] = escolher_pasta_no_windows,
    ) -> None:
        super().__init__(master, fg_color="transparent")
        self._expedientes = expedientes
        self._escolher_pasta = escolher_pasta
        self._periodo = "hoje"
        self._botoes_periodo: dict[str, ctk.CTkButton] = {}
        self._montar(ao_voltar)
        self._atualizar()

    # ------------------------------------------------------------------ layout
    def _montar(self, ao_voltar: Callable[[], None]) -> None:
        topo = ctk.CTkFrame(self, fg_color="transparent")
        topo.pack(fill="x", padx=30, pady=(20, 0))
        ctk.CTkButton(
            topo, text="← Voltar", width=120, height=tema.ALTURA_BOTAO, font=tema.FONTE_BOTAO,
            fg_color=tema.COR_SECUNDARIA, hover_color=tema.COR_SECUNDARIA_HOVER,
            text_color=tema.COR_PRIMARIA, command=ao_voltar,
        ).pack(side="left")
        ctk.CTkLabel(
            topo, text="Expediente", font=tema.FONTE_TITULO, text_color=tema.COR_PRIMARIA,
        ).pack(side="left", padx=20)

        corpo = ctk.CTkFrame(self, fg_color="transparent")
        corpo.pack(fill="both", expand=True, padx=30, pady=(14, 20))
        corpo.grid_columnconfigure(0, weight=5, uniform="col")
        corpo.grid_columnconfigure(1, weight=6, uniform="col")
        corpo.grid_rowconfigure(0, weight=1)

        # ---- esquerda: situação e pasta
        esq = ctk.CTkFrame(corpo, fg_color="transparent")
        esq.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        cartao = ctk.CTkFrame(esq, fg_color=tema.COR_SECUNDARIA, corner_radius=12)
        cartao.pack(fill="x")
        self._rotulo_situacao = ctk.CTkLabel(
            cartao, text="", font=tema.FONTE_MENU, text_color=tema.COR_PRIMARIA,
            wraplength=420, justify="left", anchor="w",
        )
        self._rotulo_situacao.pack(fill="x", padx=18, pady=(16, 4))
        self._rotulo_resumo = ctk.CTkLabel(
            cartao, text="", font=tema.FONTE_NORMAL, text_color=tema.COR_TEXTO_SUAVE,
            wraplength=420, justify="left", anchor="w",
        )
        self._rotulo_resumo.pack(fill="x", padx=18, pady=(0, 16))

        self._botao_principal = ctk.CTkButton(
            esq, text="", height=72, font=tema.FONTE_MENU, text_color="white",
            command=self._alternar,
        )
        self._botao_principal.pack(fill="x", pady=(14, 0))

        ctk.CTkLabel(
            esq, text="Pasta das planilhas", font=tema.FONTE_BOTAO, text_color=tema.COR_PRIMARIA,
            anchor="w",
        ).pack(fill="x", pady=(24, 4))
        self._rotulo_pasta = ctk.CTkLabel(
            esq, text="", font=tema.FONTE_NORMAL, text_color=tema.COR_TEXTO,
            wraplength=420, justify="left", anchor="w",
        )
        self._rotulo_pasta.pack(fill="x")
        ctk.CTkButton(
            esq, text="Escolher pasta", height=tema.ALTURA_BOTAO, font=tema.FONTE_BOTAO,
            fg_color=tema.COR_PRIMARIA, hover_color=tema.COR_PRIMARIA_HOVER,
            text_color="white", command=self._trocar_pasta,
        ).pack(fill="x", pady=(10, 0))

        # ---- direita: quantidade vendida
        dir_ = ctk.CTkFrame(corpo, fg_color="transparent")
        dir_.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        ctk.CTkLabel(
            dir_, text="Quantidade vendida", font=tema.FONTE_BOTAO, text_color=tema.COR_PRIMARIA,
            anchor="w",
        ).pack(fill="x")

        periodos = ctk.CTkFrame(dir_, fg_color="transparent")
        periodos.pack(fill="x", pady=(8, 0))
        periodos.grid_columnconfigure((0, 1, 2), weight=1, uniform="periodo")
        for coluna, (chave, texto) in enumerate(PERIODOS):
            botao = ctk.CTkButton(
                periodos, text=texto, height=tema.ALTURA_BOTAO, font=tema.FONTE_NORMAL,
                command=lambda c=chave: self._escolher_periodo(c),
            )
            botao.grid(row=0, column=coluna, sticky="ew", padx=2)
            self._botoes_periodo[chave] = botao

        self._rotulo_vazio = ctk.CTkLabel(
            dir_, text="", font=tema.FONTE_NORMAL, text_color=tema.COR_TEXTO_SUAVE, anchor="w",
        )
        self._rotulo_vazio.pack(fill="x", side="bottom", pady=(8, 0))

        area = ctk.CTkFrame(dir_, fg_color="transparent")
        area.pack(fill="both", expand=True, pady=(10, 0))
        self._tabela = ttk.Treeview(
            area, columns=("produto", "categoria", "quantidade"), show="headings",
            selectmode="browse", style=tabela.estilizar(self),
        )
        for coluna, texto, largura, alinhamento in [
            ("produto", "Produto", 200, "w"), ("categoria", "Categoria", 130, "w"),
            ("quantidade", "Quantidade", 100, "e"),
        ]:
            self._tabela.heading(coluna, text=texto, anchor=alinhamento)
            self._tabela.column(coluna, width=largura, anchor=alinhamento)
        barra = ctk.CTkScrollbar(area, command=self._tabela.yview)
        self._tabela.configure(yscrollcommand=barra.set)
        barra.pack(side="right", fill="y")
        self._tabela.pack(side="left", fill="both", expand=True)

    # ------------------------------------------------------------------- dados
    def _atualizar(self) -> None:
        aberto = self._expedientes.aberto()
        if aberto is None:
            self._rotulo_situacao.configure(text="Expediente fechado")
            self._rotulo_resumo.configure(text="Inicie o expediente para registrar vendas.")
            self._botao_principal.configure(
                text="Iniciar expediente", fg_color=tema.COR_SUCESSO, hover_color="#144618",
            )
        else:
            desde = datetime.fromisoformat(aberto.inicio).strftime("%d/%m/%Y às %H:%M")
            totais = self._expedientes.totais_atuais()
            plural = "venda" if totais.quantidade_vendas == 1 else "vendas"
            self._rotulo_situacao.configure(text=f"Aberto desde {desde}")
            self._rotulo_resumo.configure(
                text=f"{totais.quantidade_vendas} {plural} · Total vendido: "
                     f"{formatar_reais(totais.total_centavos)}\n"
                     "A planilha é gerada ao encerrar."
            )
            self._botao_principal.configure(
                text="Encerrar expediente", fg_color=tema.COR_ERRO, hover_color="#8A0019",
            )
        self._rotulo_pasta.configure(text=str(self._expedientes.pasta_planilhas()))
        self._pintar_periodos()
        self._carregar_quantidades()

    def _carregar_quantidades(self) -> None:
        quantidades = self._expedientes.quantidades(self._periodo)
        self._tabela.delete(*self._tabela.get_children())
        for indice, q in enumerate(quantidades):
            self._tabela.insert("", "end", iid=str(indice), values=(q.produto, q.categoria, q.quantidade))
        total = sum(q.quantidade for q in quantidades)
        self._rotulo_vazio.configure(
            text=f"{total} unidade(s) vendida(s) no período." if quantidades
            else "Nenhuma venda nesse período."
        )

    def _escolher_periodo(self, chave: str) -> None:
        self._periodo = chave
        self._pintar_periodos()
        self._carregar_quantidades()

    def _pintar_periodos(self) -> None:
        for chave, botao in self._botoes_periodo.items():
            if chave == self._periodo:
                botao.configure(fg_color=tema.COR_PRIMARIA, hover_color=tema.COR_PRIMARIA_HOVER,
                                text_color="white")
            else:
                botao.configure(fg_color=tema.COR_SECUNDARIA, hover_color=tema.COR_SECUNDARIA_HOVER,
                                text_color=tema.COR_PRIMARIA)

    # ------------------------------------------------------------------ ações
    def _alternar(self) -> None:
        if self._expedientes.aberto() is None:
            self._iniciar()
        else:
            self._encerrar()

    def _iniciar(self) -> None:
        try:
            self._expedientes.iniciar()
        except ErroDeNegocio as erro:
            messagebox.showerror("Iniciar expediente", str(erro))
        self._atualizar()

    def _encerrar(self) -> None:
        pasta = self._expedientes.pasta_planilhas()
        if not messagebox.askyesno(
            "Encerrar expediente",
            f"Encerrar o expediente e gerar a planilha de vendas do dia?\n\nPasta: {pasta}",
        ):
            return
        try:
            resultado = self._expedientes.encerrar()
        except ErroDeNegocio as erro:
            messagebox.showerror("Encerrar expediente", str(erro))
            self._atualizar()
            return
        t = resultado.totais
        plural = "venda" if t.quantidade_vendas == 1 else "vendas"
        messagebox.showinfo(
            "Expediente encerrado",
            f"Planilha salva em:\n{resultado.caminho}\n\n"
            f"{t.quantidade_vendas} {plural} · Total vendido: {formatar_reais(t.total_centavos)}",
        )
        self._atualizar()

    def _trocar_pasta(self) -> None:
        escolhida = self._escolher_pasta(str(self._expedientes.pasta_planilhas()))
        if not escolhida:
            return
        try:
            self._expedientes.definir_pasta_planilhas(escolhida)
        except ErroDeNegocio as erro:
            messagebox.showerror("Pasta das planilhas", str(erro))
            return
        self._atualizar()
