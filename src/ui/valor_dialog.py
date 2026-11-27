"""Janela genérica para pedir um valor em reais (pagamento de dívida, crédito...)."""
from __future__ import annotations

from tkinter import TclError
from typing import Callable

import customtkinter as ctk

from src.dinheiro import formatar_numero, formatar_reais, parse_reais
from src.errors import ErroDeNegocio
from src.ui import tema


class ValorDialog(ctk.CTkToplevel):
    """Pede um valor e entrega em centavos para `ao_confirmar`.

    `ao_confirmar` faz a operação de verdade e pode levantar um erro de negócio:
    a mensagem aparece na janela, que continua aberta. Depois de `wait_window()`,
    consulte `salvo` para saber se a operação foi feita.

    `atalho` é opcional: (rótulo, centavos) cria um botão que preenche o campo,
    como "Pagar tudo".
    """

    def __init__(
        self,
        master,
        titulo: str,
        info: str,
        texto_confirmar: str,
        ao_confirmar: Callable[[int], None],
        atalho: tuple[str, int] | None = None,
    ) -> None:
        super().__init__(master)
        self.salvo = False
        self._ao_confirmar = ao_confirmar

        self.title(titulo)
        self.geometry("480x470")
        self.resizable(False, False)
        self.transient(master)
        self.protocol("WM_DELETE_WINDOW", self.destroy)

        self._montar(titulo, info, texto_confirmar, atalho)
        self.after(150, self._tornar_modal)

    def _montar(self, titulo, info, texto_confirmar, atalho) -> None:
        corpo = ctk.CTkFrame(self, fg_color="transparent")
        corpo.pack(fill="both", expand=True, padx=32, pady=24)

        ctk.CTkLabel(
            corpo, text=titulo, font=tema.FONTE_TITULO, text_color=tema.COR_PRIMARIA,
        ).pack(anchor="w", pady=(0, 10))
        ctk.CTkLabel(
            corpo, text=info, font=tema.FONTE_NORMAL, text_color=tema.COR_TEXTO_SUAVE,
            wraplength=400, justify="left", anchor="w",
        ).pack(fill="x", pady=(0, 14))

        ctk.CTkLabel(corpo, text="Valor (R$)", font=tema.FONTE_NORMAL, anchor="w").pack(fill="x")
        self._entrada_valor = ctk.CTkEntry(
            corpo, height=tema.ALTURA_CAMPO, font=tema.FONTE_NORMAL, placeholder_text="0,00",
        )
        self._entrada_valor.pack(fill="x", pady=(2, 8))
        self._entrada_valor.bind("<Return>", self._confirmar)

        self._botao_atalho = None
        if atalho is not None:
            rotulo, centavos = atalho
            self._botao_atalho = ctk.CTkButton(
                corpo, text=f"{rotulo} ({formatar_reais(centavos)})",
                height=tema.ALTURA_BOTAO, font=tema.FONTE_NORMAL,
                fg_color=tema.COR_SECUNDARIA, hover_color=tema.COR_SECUNDARIA_HOVER,
                text_color=tema.COR_PRIMARIA,
                command=lambda: self._preencher(centavos),
            )
            self._botao_atalho.pack(fill="x", pady=(0, 8))

        self._rotulo_erro = ctk.CTkLabel(
            corpo, text="", font=tema.FONTE_NORMAL, text_color=tema.COR_ERRO,
            wraplength=400, justify="left", anchor="w",
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
            botoes, text=texto_confirmar, height=tema.ALTURA_BOTAO, font=tema.FONTE_BOTAO,
            fg_color=tema.COR_PRIMARIA, hover_color=tema.COR_PRIMARIA_HOVER,
            text_color="white", command=self._confirmar,
        ).grid(row=0, column=1, sticky="ew", padx=(6, 0))

    def _tornar_modal(self) -> None:
        try:
            self.lift()
            self.grab_set()
            self._entrada_valor.focus()
        except TclError:
            pass

    def _preencher(self, centavos: int) -> None:
        self._entrada_valor.delete(0, "end")
        self._entrada_valor.insert(0, formatar_numero(centavos))

    def _confirmar(self, _evento=None) -> None:
        try:
            valor = parse_reais(self._entrada_valor.get(), campo="valor")
            self._ao_confirmar(valor)
        except ErroDeNegocio as erro:
            self._rotulo_erro.configure(text=str(erro))
            return
        self.salvo = True
        self.destroy()
