"""Regras de negócio das vendas (RF02, RF03, RF10, RN01, RN02 e RN03).

Ordem do cálculo de uma venda:

    subtotal  = soma de (quantidade x preço atual de cada produto)
    desconto  = 15% do subtotal, se o subtotal for MAIOR que o valor mínimo
                definido pelo proprietário (RN02)
    total     = subtotal - desconto
    crédito   = quanto do crédito do cliente é abatido, no máximo o total (RN03)
    a pagar   = total - crédito  ->  é o que entra pela forma de pagamento escolhida
                                      (ou vira dívida, se a forma for "fiado")

Os preços vêm sempre do banco, nunca da tela, e ficam gravados em cada item
da venda: mudar o preço de um produto depois não altera vendas antigas.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Iterable

from src.dinheiro import formatar_reais
from src.errors import DadosInvalidosError, NaoEncontradoError, OperacaoNaoPermitidaError
from src.repos.cliente_repo import Cliente, ClienteRepo
from src.repos.produto_repo import ProdutoRepo
from src.repos.venda_repo import VendaRepo
from src.services.configuracao_service import ConfiguracaoService
from src.services.expediente_service import ExpedienteService

FORMAS_PAGAMENTO = ("dinheiro", "pix", "debito", "credito", "fiado")
PERCENTUAL_DESCONTO = 15
QUANTIDADE_MAXIMA = 999


@dataclass(frozen=True)
class ItemPedido:
    produto_id: int
    quantidade: int


@dataclass(frozen=True)
class ItemCalculado:
    produto_id: int
    nome: str
    quantidade: int
    preco_unitario_centavos: int

    @property
    def subtotal_centavos(self) -> int:
        return self.quantidade * self.preco_unitario_centavos


@dataclass(frozen=True)
class Resumo:
    itens: tuple[ItemCalculado, ...]
    subtotal_centavos: int
    desconto_centavos: int
    total_centavos: int
    credito_usado_centavos: int

    @property
    def a_pagar_centavos(self) -> int:
        return self.total_centavos - self.credito_usado_centavos


@dataclass(frozen=True)
class VendaRegistrada:
    id: int
    data_hora: str
    forma_pagamento: str
    cliente_codigo: int | None
    resumo: Resumo


class VendaService:
    def __init__(
        self,
        vendas: VendaRepo,
        produtos: ProdutoRepo,
        clientes: ClienteRepo,
        configuracao: ConfiguracaoService,
        agora: Callable[[], datetime] = datetime.now,
        expedientes: ExpedienteService | None = None,
    ) -> None:
        self._vendas = vendas
        self._produtos = produtos
        self._clientes = clientes
        self._configuracao = configuracao
        self._agora = agora  # injetável para os testes controlarem a data
        self._expedientes = expedientes  # se informado, só vende com o expediente aberto

    # ----------------------------------------------------------------- cálculo
    def calcular(
        self,
        itens: Iterable[ItemPedido],
        cliente_codigo: int | None = None,
        usar_credito: bool = False,
    ) -> Resumo:
        """Calcula os valores sem gravar nada (a tela usa para mostrar o resumo).

        Uma lista vazia dá um resumo zerado.
        """
        calculados = self._calcular_itens(itens)
        subtotal = sum(i.subtotal_centavos for i in calculados)
        desconto = self._desconto(subtotal)
        total = subtotal - desconto

        credito_usado = 0
        if usar_credito:
            if cliente_codigo is None:
                raise DadosInvalidosError("Escolha um cliente para usar o crédito.")
            cliente = self._obter_cliente(cliente_codigo)
            credito_usado = min(cliente.credito_centavos, total)

        return Resumo(
            itens=tuple(calculados),
            subtotal_centavos=subtotal,
            desconto_centavos=desconto,
            total_centavos=total,
            credito_usado_centavos=credito_usado,
        )

    def _calcular_itens(self, itens: Iterable[ItemPedido]) -> list[ItemCalculado]:
        juntos: dict[int, int] = {}  # o mesmo produto repetido soma as quantidades
        for item in itens:
            if item.quantidade <= 0:
                raise DadosInvalidosError("A quantidade deve ser maior que zero.")
            juntos[item.produto_id] = juntos.get(item.produto_id, 0) + item.quantidade

        calculados = []
        for produto_id, quantidade in juntos.items():
            if quantidade > QUANTIDADE_MAXIMA:
                raise DadosInvalidosError(
                    f"A quantidade máxima por produto é {QUANTIDADE_MAXIMA}."
                )
            produto = self._produtos.buscar_por_id(produto_id)
            if produto is None or not produto.ativo:
                raise NaoEncontradoError(
                    "Um dos produtos não existe mais. Atualize a lista e tente de novo."
                )
            calculados.append(
                ItemCalculado(produto.id, produto.nome, quantidade, produto.preco_centavos)
            )
        return calculados

    def _desconto(self, subtotal_centavos: int) -> int:
        minimo = self._configuracao.valor_minimo_desconto()
        if minimo is None or subtotal_centavos <= minimo:
            return 0
        # 15% arredondado para o centavo mais próximo (metade para cima), só com inteiros.
        return (subtotal_centavos * PERCENTUAL_DESCONTO + 50) // 100

    # ---------------------------------------------------------------- registro
    def registrar(
        self,
        itens: Iterable[ItemPedido],
        forma_pagamento: str,
        cliente_codigo: int | None = None,
        usar_credito: bool = False,
    ) -> VendaRegistrada:
        itens = list(itens)
        if not itens:  # RF03
            raise DadosInvalidosError("Adicione ao menos um produto à venda.")
        if forma_pagamento not in FORMAS_PAGAMENTO:
            raise DadosInvalidosError("Escolha a forma de pagamento.")
        if self._expedientes is not None:
            self._expedientes.exigir_aberto()

        resumo = self.calcular(itens, cliente_codigo, usar_credito)
        cliente = self._obter_cliente(cliente_codigo) if cliente_codigo is not None else None

        if forma_pagamento == "fiado":
            if cliente is None:
                raise DadosInvalidosError("Escolha o cliente para vender no fiado.")
            if resumo.a_pagar_centavos > 0 and cliente.bloqueado:  # RN01
                raise OperacaoNaoPermitidaError(
                    f"{cliente.nome} está acima do limite de dívida "
                    f"({formatar_reais(cliente.divida_centavos)} de "
                    f"{formatar_reais(cliente.limite_centavos)}) e não pode comprar no fiado "
                    "até pagar parte do que deve."
                )

        data_hora = self._agora().isoformat(timespec="seconds")
        with self._vendas.transacao():  # RNF07: tudo ou nada
            venda_id = self._vendas.inserir(
                data_hora, cliente_codigo, forma_pagamento,
                resumo.desconto_centavos, resumo.total_centavos, resumo.credito_usado_centavos,
            )
            self._vendas.inserir_itens(
                venda_id,
                [(i.produto_id, i.quantidade, i.preco_unitario_centavos) for i in resumo.itens],
            )
            if resumo.credito_usado_centavos > 0:
                self._clientes.somar_credito(cliente.codigo, -resumo.credito_usado_centavos)
            if forma_pagamento == "fiado" and resumo.a_pagar_centavos > 0:  # RF10
                self._clientes.somar_divida(cliente.codigo, resumo.a_pagar_centavos)

        return VendaRegistrada(venda_id, data_hora, forma_pagamento, cliente_codigo, resumo)

    # ----------------------------------------------------------------- apoio
    def _obter_cliente(self, codigo: int) -> Cliente:
        cliente = self._clientes.buscar(codigo)
        if cliente is None or not cliente.ativo:
            raise NaoEncontradoError("Esse cliente não existe mais.")
        return cliente
