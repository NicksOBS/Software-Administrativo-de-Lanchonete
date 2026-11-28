"""Calculadora integrada (RNF04): nos campos de valor, "=" seguido da expressão.

Exemplo: `=(3*4,50)` dá 13,50. Aceita + - * / , parênteses e números com vírgula
decimal (4,50), ponto decimal (4.5) e ponto de milhar (1.234,56). Não usa `eval`:
a expressão é lida por um analisador próprio, então só contas são aceitas.
"""
from __future__ import annotations

import re
from decimal import ROUND_HALF_UP, Decimal, DivisionByZero, InvalidOperation

from src.errors import DadosInvalidosError

TAMANHO_MAXIMO = 200
PROFUNDIDADE_MAXIMA = 30

_TOKEN = re.compile(
    r"\s*(?:(?P<num>[0-9]{1,3}(?:\.[0-9]{3})+(?:,[0-9]+)?|[0-9]+(?:[.,][0-9]+)?)|(?P<op>[-+*/()]))"
)

MENSAGEM_INVALIDA = "Expressão inválida. Use algo como =(3*4,50)."


def eh_expressao(texto: str | None) -> bool:
    return (texto or "").lstrip().startswith("=")


def calcular(texto: str) -> Decimal:
    """Avalia `=expressão` e devolve o resultado exato (sem arredondar)."""
    corpo = texto.strip()
    if not corpo.startswith("="):
        raise DadosInvalidosError(MENSAGEM_INVALIDA)
    corpo = corpo[1:].upper().replace("R$", "")
    if not corpo.strip() or len(corpo) > TAMANHO_MAXIMO:
        raise DadosInvalidosError(MENSAGEM_INVALIDA)
    return _Analisador(corpo).resultado()


def calcular_em_reais(texto: str) -> Decimal:
    """Resultado arredondado para centavos (metade para cima)."""
    return calcular(texto).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class _Analisador:
    """gramática:  soma = termo (('+'|'-') termo)* ;  termo = fator (('*'|'/') fator)* ;
    fator = ('+'|'-') fator | número | '(' soma ')'"""

    def __init__(self, texto: str) -> None:
        self._tokens = self._separar(texto)
        self._pos = 0
        self._nivel = 0

    @staticmethod
    def _separar(texto: str) -> list[tuple[str, str]]:
        tokens, pos = [], 0
        while pos < len(texto):
            if texto[pos:].strip() == "":
                break
            achado = _TOKEN.match(texto, pos)
            if achado is None:
                raise DadosInvalidosError(MENSAGEM_INVALIDA)
            if achado.group("num") is not None:
                tokens.append(("num", achado.group("num")))
            else:
                tokens.append(("op", achado.group("op")))
            pos = achado.end()
        return tokens

    def resultado(self) -> Decimal:
        try:
            valor = self._soma()
            if self._pos != len(self._tokens):
                raise DadosInvalidosError(MENSAGEM_INVALIDA)
            return valor
        except DivisionByZero:
            raise DadosInvalidosError("Divisão por zero.") from None
        except InvalidOperation:
            raise DadosInvalidosError(MENSAGEM_INVALIDA) from None

    def _espiar(self) -> str | None:
        if self._pos < len(self._tokens) and self._tokens[self._pos][0] == "op":
            return self._tokens[self._pos][1]
        return None

    def _soma(self) -> Decimal:
        valor = self._termo()
        while self._espiar() in ("+", "-"):
            operador = self._tokens[self._pos][1]
            self._pos += 1
            direito = self._termo()
            valor = valor + direito if operador == "+" else valor - direito
        return valor

    def _termo(self) -> Decimal:
        valor = self._fator()
        while self._espiar() in ("*", "/"):
            operador = self._tokens[self._pos][1]
            self._pos += 1
            direito = self._fator()
            if operador == "/" and direito == 0:
                raise DadosInvalidosError("Divisão por zero.")
            valor = valor * direito if operador == "*" else valor / direito
        return valor

    def _fator(self) -> Decimal:
        self._nivel += 1
        try:
            if self._nivel > PROFUNDIDADE_MAXIMA:
                raise DadosInvalidosError(MENSAGEM_INVALIDA)
            if self._pos >= len(self._tokens):
                raise DadosInvalidosError(MENSAGEM_INVALIDA)
            tipo, texto = self._tokens[self._pos]
            if tipo == "num":
                self._pos += 1
                return Decimal(texto.replace(".", "").replace(",", ".") if "," in texto or
                               re.fullmatch(r"[0-9]{1,3}(\.[0-9]{3})+", texto) else texto)
            if texto in ("+", "-"):
                self._pos += 1
                valor = self._fator()
                return -valor if texto == "-" else valor
            if texto == "(":
                self._pos += 1
                valor = self._soma()
                if self._espiar() != ")":
                    raise DadosInvalidosError(MENSAGEM_INVALIDA)
                self._pos += 1
                return valor
            raise DadosInvalidosError(MENSAGEM_INVALIDA)
        finally:
            self._nivel -= 1
