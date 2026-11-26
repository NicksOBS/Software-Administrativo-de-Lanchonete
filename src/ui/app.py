"""Janela principal: troca entre a tela de login e o menu."""
from __future__ import annotations

import sqlite3

import customtkinter as ctk

from src import database
from src.config import NOME_APP
from src.repos.usuario_repo import Usuario, UsuarioRepo
from src.services.auth_service import AuthService
from src.ui.login_frame import LoginFrame
from src.ui.menu_frame import MenuFrame


class App(ctk.CTk):
    def __init__(self, conn: sqlite3.Connection | None = None) -> None:
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")
        super().__init__()

        self.title(NOME_APP)
        self.geometry("960x680")
        self.minsize(760, 600)

        self._conn = conn if conn is not None else database.conectar()
        self._auth = AuthService(UsuarioRepo(self._conn))
        self._tela_atual: ctk.CTkFrame | None = None

        self.protocol("WM_DELETE_WINDOW", self._fechar)
        self.mostrar_login()

    def _trocar_tela(self, tela: ctk.CTkFrame) -> None:
        if self._tela_atual is not None:
            self._tela_atual.destroy()
        self._tela_atual = tela
        tela.pack(fill="both", expand=True)

    def mostrar_login(self) -> None:
        self._trocar_tela(LoginFrame(self, self._auth, ao_entrar=self.mostrar_menu))

    def mostrar_menu(self, usuario: Usuario) -> None:
        self._trocar_tela(MenuFrame(self, usuario, ao_sair=self.mostrar_login))

    def _fechar(self) -> None:
        # Mais adiante (RNF02) este é o lugar de avisar sobre expediente aberto.
        self._conn.close()
        self.destroy()


def executar() -> None:
    App().mainloop()
