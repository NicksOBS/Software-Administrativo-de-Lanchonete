"""Tela principal: quatro opções grandes (RU06)."""
from __future__ import annotations

from tkinter import messagebox
from typing import Callable

import customtkinter as ctk

from src.repos.usuario_repo import Usuario
from src.ui import tema

OPCOES = [
    "Clientes",
    "Vendas",
    "Iniciar/Encerrar\nExpediente",
    "Produtos",
]


class MenuFrame(ctk.CTkFrame):
    def __init__(
        self,
        master,
        usuario: Usuario,
        ao_sair: Callable[[], None],
        ao_abrir_produtos: Callable[[], None],
        ao_abrir_clientes: Callable[[], None],
        ao_abrir_vendas: Callable[[], None],
        ao_abrir_expediente: Callable[[], None],
    ) -> None:
        super().__init__(master, fg_color="transparent")
        self._usuario = usuario
        acoes = {
            "Produtos": ao_abrir_produtos,
            "Clientes": ao_abrir_clientes,
            "Vendas": ao_abrir_vendas,
            "Iniciar/Encerrar\nExpediente": ao_abrir_expediente,
        }

        topo = ctk.CTkFrame(self, fg_color="transparent")
        topo.pack(fill="x", padx=30, pady=(24, 0))
        ctk.CTkLabel(
            topo, text=f"Olá, {usuario.login}", font=tema.FONTE_TITULO,
            text_color=tema.COR_PRIMARIA,
        ).pack(side="left")
        ctk.CTkButton(
            topo, text="Sair", width=110, height=tema.ALTURA_BOTAO, font=tema.FONTE_BOTAO,
            fg_color=tema.COR_SECUNDARIA, hover_color=tema.COR_SECUNDARIA_HOVER,
            text_color=tema.COR_PRIMARIA, command=ao_sair,
        ).pack(side="right")

        grade = ctk.CTkFrame(self, fg_color="transparent")
        grade.pack(fill="both", expand=True, padx=30, pady=30)
        grade.grid_columnconfigure((0, 1), weight=1, uniform="coluna")
        grade.grid_rowconfigure((0, 1), weight=1, uniform="linha")

        for indice, texto in enumerate(OPCOES):
            ctk.CTkButton(
                grade, text=texto, font=tema.FONTE_MENU, height=tema.ALTURA_BOTAO_MENU,
                fg_color=tema.COR_PRIMARIA, hover_color=tema.COR_PRIMARIA_HOVER,
                text_color="white", corner_radius=14,
                command=acoes.get(texto, lambda t=texto: self._em_construcao(t)),
            ).grid(row=indice // 2, column=indice % 2, sticky="nsew", padx=12, pady=12)

    @staticmethod
    def _em_construcao(texto: str) -> None:
        nome = texto.replace("\n", " ")
        messagebox.showinfo(
            "Em construção", f"A tela \"{nome}\" será implementada nas próximas etapas."
        )
