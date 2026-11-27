"""Regras de negócio dos clientes e do fiado (RF07 a RF09, RF11, RN01 e RN03)."""
from __future__ import annotations

from datetime import datetime
from typing import Callable

from src.dinheiro import formatar_reais
from src.errors import (
    DadosInvalidosError,
    NaoEncontradoError,
    OperacaoNaoPermitidaError,
    RegistroDuplicadoError,
)
from src.repos.cliente_repo import Cliente, ClienteRepo
from src.textos import limpar_espacos

NOME_MAX = 60
CODIGO_MAXIMO = 999_999
VALOR_MAXIMO_CENTAVOS = 9_999_999  # R$ 99.999,99: barra erros de digitação


class ClienteService:
    def __init__(
        self, repo: ClienteRepo, agora: Callable[[], datetime] = datetime.now
    ) -> None:
        self._repo = repo
        self._agora = agora  # injetável para os testes controlarem a data

    # ---------------------------------------------------------------- consulta
    def listar(self, busca: str = "", somente_devedores: bool = False) -> list[Cliente]:
        return self._repo.listar(busca, somente_devedores)

    def obter(self, codigo: int) -> Cliente:
        cliente = self._repo.buscar(codigo)
        if cliente is None or not cliente.ativo:
            raise NaoEncontradoError("Esse cliente não existe mais.")
        return cliente

    def sugerir_codigo(self) -> int:
        return self._repo.proximo_codigo()

    # ---------------------------------------------------------------- cadastro
    def cadastrar(self, codigo: int, nome: str, limite_centavos: int | None = None) -> Cliente:
        if not (1 <= codigo <= CODIGO_MAXIMO):
            raise DadosInvalidosError(f"O código deve ser um número de 1 a {CODIGO_MAXIMO}.")
        nome = self._validar_nome(nome)
        self._validar_limite(limite_centavos)

        existente = self._repo.buscar(codigo)
        if existente is not None:
            if existente.ativo:
                raise RegistroDuplicadoError(f"Já existe um cliente com o código {codigo}.")
            raise RegistroDuplicadoError(
                f"O código {codigo} pertenceu a um cliente removido e não pode ser reutilizado."
            )

        with self._repo.transacao():
            self._repo.criar(codigo, nome, limite_centavos)
        return self.obter(codigo)

    def atualizar(self, codigo: int, nome: str, limite_centavos: int | None = None) -> Cliente:
        self.obter(codigo)
        nome = self._validar_nome(nome)
        self._validar_limite(limite_centavos)
        with self._repo.transacao():
            self._repo.atualizar(codigo, nome, limite_centavos)
        return self.obter(codigo)

    def remover(self, codigo: int) -> None:
        """Remoção lógica. Só é permitida sem dívida e sem crédito guardado."""
        cliente = self.obter(codigo)
        if cliente.divida_centavos > 0:
            raise OperacaoNaoPermitidaError(
                f"{cliente.nome} ainda deve {formatar_reais(cliente.divida_centavos)}. "
                "Registre o pagamento antes de remover."
            )
        if cliente.credito_centavos > 0:
            raise OperacaoNaoPermitidaError(
                f"{cliente.nome} tem {formatar_reais(cliente.credito_centavos)} de crédito "
                "na lanchonete e não pode ser removido."
            )
        with self._repo.transacao():
            self._repo.desativar(codigo)

    # ------------------------------------------------------------ dívida (RF11)
    def registrar_pagamento(self, codigo: int, valor_centavos: int) -> Cliente:
        """O cliente pagou parte (ou tudo) do que devia: abate da dívida e guarda no histórico."""
        cliente = self.obter(codigo)
        self._validar_valor(valor_centavos)
        if cliente.divida_centavos == 0:
            raise OperacaoNaoPermitidaError(f"{cliente.nome} não tem dívida.")
        if valor_centavos > cliente.divida_centavos:
            raise OperacaoNaoPermitidaError(
                f"O valor é maior que a dívida atual ({formatar_reais(cliente.divida_centavos)}). "
                'Para deixar o excedente como saldo, use "Adicionar crédito".'
            )
        data_hora = self._agora().isoformat(timespec="seconds")
        with self._repo.transacao():
            self._repo.somar_divida(codigo, -valor_centavos)
            self._repo.registrar_pagamento(codigo, data_hora, valor_centavos)
        return self.obter(codigo)

    # ------------------------------------------------------------ crédito (RN03)
    def adicionar_credito(self, codigo: int, valor_centavos: int) -> Cliente:
        """O cliente deixou dinheiro na lanchonete para abater em compras futuras."""
        self.obter(codigo)
        self._validar_valor(valor_centavos)
        with self._repo.transacao():
            self._repo.somar_credito(codigo, valor_centavos)
        return self.obter(codigo)

    # --------------------------------------------------------------- validações
    @staticmethod
    def _validar_nome(nome: str) -> str:
        nome = limpar_espacos(nome)
        if not nome:
            raise DadosInvalidosError("Informe o nome do cliente.")
        if len(nome) > NOME_MAX:
            raise DadosInvalidosError(f"O nome pode ter até {NOME_MAX} caracteres.")
        return nome

    @staticmethod
    def _validar_limite(limite_centavos: int | None) -> None:
        if limite_centavos is None:
            return
        if limite_centavos <= 0:
            raise DadosInvalidosError(
                "O limite deve ser maior que zero (deixe em branco para não ter limite)."
            )
        if limite_centavos > VALOR_MAXIMO_CENTAVOS:
            raise DadosInvalidosError("O limite máximo permitido é R$ 99.999,99.")

    @staticmethod
    def _validar_valor(valor_centavos: int) -> None:
        if valor_centavos <= 0:
            raise DadosInvalidosError("O valor deve ser maior que zero.")
        if valor_centavos > VALOR_MAXIMO_CENTAVOS:
            raise DadosInvalidosError("O valor máximo permitido é R$ 99.999,99.")
