"""Janela principal: troca entre a tela de login e o menu."""
from __future__ import annotations

import sqlite3

import customtkinter as ctk

from tkinter import messagebox

from src import database
from src.config import NOME_APP, PASTA_DADOS
from src.repos.categoria_repo import CategoriaRepo
from src.repos.cliente_repo import ClienteRepo
from src.repos.configuracao_repo import ConfiguracaoRepo
from src.repos.expediente_repo import ExpedienteRepo
from src.repos.relatorio_repo import RelatorioRepo
from src.repos.produto_repo import ProdutoRepo
from src.repos.usuario_repo import Usuario, UsuarioRepo
from src.repos.venda_repo import VendaRepo
from src.services.auth_service import AuthService
from src.services.categoria_service import CategoriaService
from src.services.cliente_service import ClienteService
from src.services.configuracao_service import ConfiguracaoService
from src.services.expediente_service import ExpedienteService
from src.services.produto_service import ProdutoService
from src.services.venda_service import VendaService
from src.ui.clientes_frame import ClientesFrame
from src.ui.expediente_frame import ExpedienteFrame
from src.ui.login_frame import LoginFrame
from src.ui.menu_frame import MenuFrame
from src.ui.produtos_frame import ProdutosFrame
from src.ui.vendas_frame import VendasFrame


class App(ctk.CTk):
    def __init__(self, conn: sqlite3.Connection | None = None) -> None:
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")
        super().__init__()

        self.title(NOME_APP)
        self.geometry("1180x760")
        self.minsize(980, 680)

        self._conn = conn if conn is not None else database.conectar()
        self._auth = AuthService(UsuarioRepo(self._conn))
        categoria_repo = CategoriaRepo(self._conn)
        self._categorias = CategoriaService(categoria_repo)
        produto_repo = ProdutoRepo(self._conn)
        self._produtos = ProdutoService(produto_repo, categoria_repo)
        cliente_repo = ClienteRepo(self._conn)
        self._clientes = ClienteService(cliente_repo)
        self._configuracao = ConfiguracaoService(ConfiguracaoRepo(self._conn))
        self._expediente = ExpedienteService(
            ExpedienteRepo(self._conn), RelatorioRepo(self._conn), self._configuracao,
            pasta_padrao=PASTA_DADOS / "planilhas",
        )
        self._vendas = VendaService(
            VendaRepo(self._conn), produto_repo, cliente_repo, self._configuracao,
            expedientes=self._expediente,
        )
        self._usuario: Usuario | None = None
        self._tela_atual: ctk.CTkFrame | None = None
        self._fechando = False

        self.protocol("WM_DELETE_WINDOW", self._fechar)
        self.mostrar_login()
        self._agendar_autosave()

    def _trocar_tela(self, tela: ctk.CTkFrame) -> None:
        if self._tela_atual is not None:
            self._tela_atual.destroy()
        self._tela_atual = tela
        tela.pack(fill="both", expand=True)

    def mostrar_login(self) -> None:
        self._trocar_tela(LoginFrame(self, self._auth, ao_entrar=self.mostrar_menu))

    def mostrar_menu(self, usuario: Usuario | None = None) -> None:
        if usuario is not None:
            self._usuario = usuario
        self._trocar_tela(
            MenuFrame(
                self, self._usuario,
                ao_sair=self.mostrar_login,
                ao_abrir_produtos=self.mostrar_produtos,
                ao_abrir_clientes=self.mostrar_clientes,
                ao_abrir_vendas=self.mostrar_vendas,
                ao_abrir_expediente=self.mostrar_expediente,
            )
        )

    def mostrar_clientes(self) -> None:
        self._trocar_tela(ClientesFrame(self, self._clientes, ao_voltar=self.mostrar_menu))

    def mostrar_vendas(self) -> None:
        self._trocar_tela(
            VendasFrame(
                self, self._vendas, self._produtos, self._clientes, self._configuracao,
                ao_voltar=self.mostrar_menu, expedientes=self._expediente,
            )
        )

    def mostrar_expediente(self) -> None:
        self._trocar_tela(ExpedienteFrame(self, self._expediente, ao_voltar=self.mostrar_menu))

    def mostrar_produtos(self) -> None:
        self._trocar_tela(
            ProdutosFrame(self, self._produtos, self._categorias, ao_voltar=self.mostrar_menu)
        )

    # ------------------------------------------------------ autosave (RNF01)
    def _agendar_autosave(self) -> None:
        self.after(self._configuracao.autosave_segundos() * 1000, self._autosave)

    def _autosave(self) -> None:
        if self._fechando:
            return
        try:
            self._expediente.salvar_rascunho()
        except Exception:  # o salvamento automático nunca pode derrubar o programa
            pass
        self._agendar_autosave()

    # ---------------------------------------------------- aviso ao fechar (RNF02)
    def _fechar(self) -> None:
        pendencia = getattr(self._tela_atual, "tem_pendencia", lambda: False)()
        if self._expediente.aberto() is not None or pendencia:
            avisos = []
            if pendencia:
                avisos.append("Há itens no pedido que ainda não foram finalizados.")
            if self._expediente.aberto() is not None:
                avisos.append(
                    "O expediente ainda está aberto: a planilha do dia ainda não foi gerada."
                )
            if not messagebox.askyesno(
                "Fechar o programa",
                "\n".join(avisos) + "\n\nFechar mesmo assim?\n"
                "As vendas já registradas ficam guardadas, e o expediente continua aberto "
                "na próxima vez.",
            ):
                return
        self._fechando = True
        try:
            self._expediente.salvar_rascunho()
        except Exception:
            pass
        self._conn.close()
        self.destroy()


def executar() -> None:
    App().mainloop()
