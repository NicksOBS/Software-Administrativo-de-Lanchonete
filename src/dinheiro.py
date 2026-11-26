"""Conversão de valores em reais para centavos (e de volta).

Todo dinheiro dentro do sistema é um número inteiro de centavos. Estas funções
fazem a ponte com o que o usuário digita e vê na tela.
"""
from __future__ import annotations

import re
from decimal import Decimal

from src.errors import DadosInvalidosError

_DIGITOS = re.compile(r"[0-9]+")
_MILHAR = re.compile(r"[0-9]{1,3}(\.[0-9]{3})+")          # 1.234 ou 1.234.567
_INTEIRA = re.compile(r"[0-9]+|[0-9]{1,3}(\.[0-9]{3})+")   # parte antes da vírgula
_NUMERO = re.compile(r"[0-9]+(\.[0-9]+)?")


def parse_reais(texto: str | None) -> int:
    """Converte o texto digitado em centavos.

    Aceita "6", "6,5", "6,50", "6.50", "R$ 6,50" e "1.234,56".
    A vírgula é o separador decimal; o ponto só vale como decimal quando tem
    de 1 a 2 dígitos depois dele ("6.5"). "1.234" é lido como mil duzentos e
    trinta e quatro reais.
    """
    bruto = (texto or "").upper().replace("R$", "").replace(" ", "")
    if not bruto:
        raise DadosInvalidosError("Informe o preço.")
    if bruto.startswith("-"):
        raise DadosInvalidosError("O preço não pode ser negativo.")

    invalido = DadosInvalidosError("Preço inválido. Use um formato como 6,50.")
    if "," in bruto:
        inteira, _, decimal = bruto.partition(",")
        if not (_INTEIRA.fullmatch(inteira) and _DIGITOS.fullmatch(decimal)):
            raise invalido
        bruto = f"{inteira.replace('.', '')}.{decimal}"
    elif _MILHAR.fullmatch(bruto):
        bruto = bruto.replace(".", "")

    if not _NUMERO.fullmatch(bruto):
        raise invalido

    valor = Decimal(bruto)
    if valor.as_tuple().exponent < -2:
        raise DadosInvalidosError("Use no máximo 2 casas decimais no preço.")
    return int(valor * 100)


def formatar_numero(centavos: int) -> str:
    """6050 -> '60,50' (sem o símbolo, bom para preencher um campo)."""
    reais, cent = divmod(abs(centavos), 100)
    return f"{reais},{cent:02d}"


def formatar_reais(centavos: int) -> str:
    """6050 -> 'R$ 60,50'; 123456 -> 'R$ 1.234,56'."""
    sinal = "-" if centavos < 0 else ""
    reais, cent = divmod(abs(centavos), 100)
    parte_inteira = f"{reais:,}".replace(",", ".")
    return f"{sinal}R$ {parte_inteira},{cent:02d}"
