from decimal import Decimal

import pytest

from src.calculadora import PROFUNDIDADE_MAXIMA, calcular, calcular_em_reais, eh_expressao
from src.dinheiro import parse_reais
from src.errors import DadosInvalidosError


@pytest.mark.parametrize(
    "texto, esperado",
    [
        ("=(3*4,50)", "13.50"),          # exemplo do documento (CT11)
        ("=3*4,5", "13.50"),
        ("=3*4.5", "13.50"),
        ("=2+3*4", "14.00"),             # precedência
        ("=(2+3)*4", "20.00"),
        ("=10-2-3", "5.00"),             # associa à esquerda
        ("=100/4/5", "5.00"),
        ("=10/4", "2.50"),
        ("=-5+8", "3.00"),
        ("=--5", "5.00"),
        ("=2*-3", "-6.00"),
        ("=+7", "7.00"),
        ("=1.234,56+1", "1235.56"),      # milhar com ponto
        ("=R$ 5 + R$ 2,50", "7.50"),
        ("  = ( 1 + 1 ) ", "2.00"),
        ("=((((1))))", "1.00"),
        ("=0,1+0,2", "0.30"),            # sem erro de ponto flutuante
    ],
)
def test_contas_corretas(texto, esperado):
    assert str(calcular_em_reais(texto)) == esperado


def test_arredonda_para_centavos_metade_para_cima():
    assert str(calcular_em_reais("=1/3")) == "0.33"
    assert str(calcular_em_reais("=2/3")) == "0.67"
    assert str(calcular_em_reais("=0,005")) == "0.01"
    assert calcular("=1/4") == Decimal("0.25")


@pytest.mark.parametrize(
    "texto",
    ["=", "=   ", "=(3", "=3)", "=()", "=3+", "=*3", "=3 4", "=1,2,3", "=abc", "=3**2",
     "=2^3", "=3;4", "=__import__('os')", "=open('x')", "=1e3", "=0x10", "3*4"],
)
def test_expressoes_invalidas_dao_mensagem_sem_travar(texto):
    with pytest.raises(DadosInvalidosError, match="Expressão inválida"):
        calcular(texto)


@pytest.mark.parametrize("texto", ["=10/0", "=1/(2-2)", "=5/(0,0)"])
def test_divisao_por_zero(texto):
    with pytest.raises(DadosInvalidosError, match="Divisão por zero"):
        calcular(texto)


def test_aninhamento_exagerado_nao_estoura_a_pilha():
    n = PROFUNDIDADE_MAXIMA + 5
    with pytest.raises(DadosInvalidosError, match="inválida"):
        calcular("=" + "(" * n + "1" + ")" * n)


def test_expressao_gigante_e_recusada():
    with pytest.raises(DadosInvalidosError):
        calcular("=" + "1+" * 300 + "1")


def test_eh_expressao():
    assert eh_expressao("=(1+1)") and eh_expressao("  =1")
    assert not eh_expressao("1+1") and not eh_expressao("") and not eh_expressao(None)


# ---------------------------------------------------- integração com os campos
def test_parse_reais_aceita_conta():
    assert parse_reais("=(3*4,50)") == 1350
    assert parse_reais("=(3*4,50)", campo="valor") == 1350
    assert parse_reais("=0,333*3") == 100


def test_parse_reais_continua_igual_sem_igual():
    assert parse_reais("6,50") == 650 and parse_reais("R$ 1.234,56") == 123456


def test_resultado_negativo_e_recusado_no_campo():
    with pytest.raises(DadosInvalidosError, match="negativo"):
        parse_reais("=2-5", campo="valor")


def test_conta_invalida_no_campo():
    with pytest.raises(DadosInvalidosError, match="Expressão inválida"):
        parse_reais("=(3*", campo="valor")
