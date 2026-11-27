"""Janela para cadastrar ou editar um cliente (RF07)."""
from __future__ import annotations

from tkinter import TclError

import customtkinter as ctk

from src.dinheiro import formatar_numero, parse_reais
from src.errors import DadosInvalidosError, ErroDeNegocio
from src.repos.cliente_repo import Cliente
from src.services.cliente_service import ClienteService
from src.ui import tema


class ClienteDialog(ctk.CTkToplevel):
    """Depois de `wait_window()`, consulte `salvo` para saber se algo foi gravado."""

    def __init__(
        self, master, clientes: ClienteService, cliente: Cliente | None = None
    ) -> None:
        super().__init__(master)
        self.salvo = False
        self._clientes = clientes
        self._cliente = cliente

        self.title("Editar cliente" if cliente else "Novo cliente")
        self.geometry("460x560")
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

        ctk.CTkLabel(corpo, text="Código", font=tema.FONTE_NORMAL, anchor="w").pack(fill="x")
        self._entrada_codigo = ctk.CTkEntry(corpo, height=tema.ALTURA_CAMPO, font=tema.FONTE_NORMAL)
        self._entrada_codigo.pack(fill="x", pady=(2, 12))

        ctk.CTkLabel(corpo, text="Nome", font=tema.FONTE_NORMAL, anchor="w").pack(fill="x")
        self._entrada_nome = ctk.CTkEntry(corpo, height=tema.ALTURA_CAMPO, font=tema.FONTE_NORMAL)
        self._entrada_nome.pack(fill="x", pady=(2, 12))

        ctk.CTkLabel(
            corpo, text="Limite de dívida (R$)", font=tema.FONTE_NORMAL, anchor="w"
        ).pack(fill="x")
        self._entrada_limite = ctk.CTkEntry(
            corpo, height=tema.ALTURA_CAMPO, font=tema.FONTE_NORMAL,
            placeholder_text="Sem limite",
        )
        self._entrada_limite.pack(fill="x", pady=(2, 8))

        self._rotulo_erro = ctk.CTkLabel(
            corpo, text="", font=tema.FONTE_NORMAL, text_color=tema.COR_ERRO,
            wraplength=380, justify="left", anchor="w",
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

        if self._cliente is None:
            self._entrada_codigo.insert(0, str(self._clientes.sugerir_codigo()))
        else:
            self._entrada_codigo.insert(0, str(self._cliente.codigo))
            self._entrada_codigo.configure(state="disabled")  # o código não muda depois
            self._entrada_nome.insert(0, self._cliente.nome)
            if self._cliente.limite_centavos is not None:
                self._entrada_limite.insert(0, formatar_numero(self._cliente.limite_centavos))

        for campo in (self._entrada_codigo, self._entrada_nome, self._entrada_limite):
            campo.bind("<Return>", self._salvar)

    def _tornar_modal(self) -> None:
        try:
            self.lift()
            self.grab_set()
            self._entrada_nome.focus()
        except TclError:
            pass

    def _ler_codigo(self) -> int:
        texto = self._entrada_codigo.get().strip()
        if not (texto.isascii() and texto.isdigit()):
            raise DadosInvalidosError("O código deve ser um número inteiro, como 12.")
        return int(texto)

    def _ler_limite(self) -> int | None:
        texto = self._entrada_limite.get().strip()
        if not texto:
            return None
        return parse_reais(texto, campo="limite")

    def _salvar(self, _evento=None) -> None:
        try:
            nome = self._entrada_nome.get()
            limite = self._ler_limite()
            if self._cliente is None:
                self._clientes.cadastrar(self._ler_codigo(), nome, limite)
            else:
                self._clientes.atualizar(self._cliente.codigo, nome, limite)
        except ErroDeNegocio as erro:
            self._rotulo_erro.configure(text=str(erro))
            return
        self.salvo = True
        self.destroy()
