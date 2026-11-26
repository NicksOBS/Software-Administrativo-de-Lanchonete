"""Tela de login e de cadastro de usuário (RF01)."""
from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from src.errors import ErroDeNegocio
from src.repos.usuario_repo import Usuario
from src.services.auth_service import AuthService
from src.ui import tema

MODO_LOGIN = "login"
MODO_CADASTRO = "cadastro"


class LoginFrame(ctk.CTkFrame):
    def __init__(
        self,
        master,
        auth: AuthService,
        ao_entrar: Callable[[Usuario], None],
    ) -> None:
        super().__init__(master, fg_color="transparent")
        self._auth = auth
        self._ao_entrar = ao_entrar

        # No primeiro acesso ainda não existe nenhum usuário: vai direto para o cadastro.
        self._primeiro_acesso = not auth.existe_usuario()
        self._modo = MODO_CADASTRO if self._primeiro_acesso else MODO_LOGIN

        self._montar()
        self._aplicar_modo()
        self._entrada_login.focus()

    # ------------------------------------------------------------------ layout
    def _montar(self) -> None:
        cartao = ctk.CTkFrame(self, corner_radius=16, fg_color=tema.COR_SECUNDARIA)
        cartao.place(relx=0.5, rely=0.5, anchor="center")
        cartao.grid_columnconfigure(0, weight=1)

        margem = {"padx": 48, "sticky": "ew"}

        ctk.CTkLabel(
            cartao, text="Lanchonete", font=tema.FONTE_TITULO, text_color=tema.COR_PRIMARIA
        ).grid(row=0, column=0, pady=(36, 4), padx=48)

        self._rotulo_subtitulo = ctk.CTkLabel(
            cartao, text="", font=tema.FONTE_SUBTITULO,
            text_color=tema.COR_TEXTO_SUAVE, wraplength=340,
        )
        self._rotulo_subtitulo.grid(row=1, column=0, pady=(0, 18), padx=48)

        ctk.CTkLabel(
            cartao, text="Login", font=tema.FONTE_NORMAL,
            text_color=tema.COR_TEXTO, anchor="w",
        ).grid(row=2, column=0, pady=(0, 2), **margem)
        self._entrada_login = ctk.CTkEntry(
            cartao, width=340, height=tema.ALTURA_CAMPO, font=tema.FONTE_NORMAL,
        )
        self._entrada_login.grid(row=3, column=0, pady=(0, 12), **margem)

        ctk.CTkLabel(
            cartao, text="Senha", font=tema.FONTE_NORMAL,
            text_color=tema.COR_TEXTO, anchor="w",
        ).grid(row=4, column=0, pady=(0, 2), **margem)
        self._entrada_senha = ctk.CTkEntry(
            cartao, width=340, height=tema.ALTURA_CAMPO, font=tema.FONTE_NORMAL, show="•",
        )
        self._entrada_senha.grid(row=5, column=0, pady=(0, 12), **margem)

        self._rotulo_confirma = ctk.CTkLabel(
            cartao, text="Confirmar senha", font=tema.FONTE_NORMAL,
            text_color=tema.COR_TEXTO, anchor="w",
        )
        self._rotulo_confirma.grid(row=6, column=0, pady=(0, 2), **margem)
        self._entrada_confirma = ctk.CTkEntry(
            cartao, width=340, height=tema.ALTURA_CAMPO, font=tema.FONTE_NORMAL, show="•",
        )
        self._entrada_confirma.grid(row=7, column=0, pady=(0, 12), **margem)

        self._rotulo_erro = ctk.CTkLabel(
            cartao, text="", font=tema.FONTE_NORMAL,
            text_color=tema.COR_ERRO, wraplength=340,
        )
        self._rotulo_erro.grid(row=8, column=0, pady=(0, 6), padx=48)

        self._botao_principal = ctk.CTkButton(
            cartao, text="", height=tema.ALTURA_BOTAO, font=tema.FONTE_BOTAO,
            fg_color=tema.COR_PRIMARIA, hover_color=tema.COR_PRIMARIA_HOVER,
            text_color="white", command=self._enviar,
        )
        self._botao_principal.grid(row=9, column=0, pady=(0, 10), **margem)

        self._botao_alternar = ctk.CTkButton(
            cartao, text="", height=tema.ALTURA_BOTAO, font=tema.FONTE_NORMAL,
            fg_color="transparent", hover_color=tema.COR_SECUNDARIA_HOVER,
            text_color=tema.COR_PRIMARIA, command=self._alternar_modo,
        )
        self._botao_alternar.grid(row=10, column=0, pady=(0, 30), **margem)

        # Enter envia o formulário em qualquer um dos campos.
        for campo in (self._entrada_login, self._entrada_senha, self._entrada_confirma):
            campo.bind("<Return>", self._enviar)

    # ------------------------------------------------------------------- modos
    def _aplicar_modo(self) -> None:
        self._mostrar_erro("")
        if self._modo == MODO_CADASTRO:
            if self._primeiro_acesso:
                self._rotulo_subtitulo.configure(
                    text="Primeiro acesso: crie o usuário do proprietário."
                )
            else:
                self._rotulo_subtitulo.configure(text="Cadastrar novo usuário")
            self._rotulo_confirma.grid()
            self._entrada_confirma.grid()
            self._botao_principal.configure(text="Criar usuário")
            # No primeiro acesso não há para onde voltar: ainda não existe login.
            if self._primeiro_acesso:
                self._botao_alternar.grid_remove()
            else:
                self._botao_alternar.grid()
                self._botao_alternar.configure(text="Já tenho usuário: entrar")
        else:
            self._rotulo_subtitulo.configure(text="Entre para abrir o caixa")
            self._rotulo_confirma.grid_remove()
            self._entrada_confirma.grid_remove()
            self._botao_principal.configure(text="Entrar")
            self._botao_alternar.grid()
            self._botao_alternar.configure(text="Cadastrar novo usuário")

    def _alternar_modo(self) -> None:
        self._modo = MODO_LOGIN if self._modo == MODO_CADASTRO else MODO_CADASTRO
        self._entrada_senha.delete(0, "end")
        self._entrada_confirma.delete(0, "end")
        self._aplicar_modo()
        self._entrada_login.focus()

    # ------------------------------------------------------------------- ações
    def _enviar(self, _evento=None) -> None:
        login = self._entrada_login.get()
        senha = self._entrada_senha.get()
        try:
            if self._modo == MODO_CADASTRO:
                usuario = self._auth.cadastrar(login, senha, self._entrada_confirma.get())
            else:
                usuario = self._auth.autenticar(login, senha)
        except ErroDeNegocio as erro:
            self._mostrar_erro(str(erro))
            self._entrada_senha.delete(0, "end")
            self._entrada_confirma.delete(0, "end")
            return
        self._ao_entrar(usuario)

    def _mostrar_erro(self, mensagem: str) -> None:
        self._rotulo_erro.configure(text=mensagem)
