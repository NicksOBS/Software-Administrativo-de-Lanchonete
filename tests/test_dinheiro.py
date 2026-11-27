import pytest

from src.dinheiro import formatar_numero, formatar_reais, parse_reais
from src.errors import DadosInvalidosError


@pytest.mark.parametrize(
    "texto, esperado",
    [
        ("6", 600),
        ("6,5", 650),
        ("6,50", 650),
        ("6.50", 650),
        ("6.5", 650),
        ("R$ 6,50", 650),
        ("r$6,50", 650),
        ("  12,00  ", 1200),
        ("0,05", 5),
        ("1.234,56", 123456),
        ("1.234", 123400),
        ("1.234.567,89", 123456789),
        ("0,10", 10),
    ],
)
def test_parse_reais_aceita_formatos_comuns(texto, esperado):
    assert parse_reais(texto) == esperado


@pytest.mark.parametrize(
    "texto",
    ["", "   ", "abc", "6,5,0", "6,50x", "1e5", "R$", ",", "--5", "6,5.5", "6,", "12.34,5",
     "6.5.5", "1.23,45", "1..234", "٣"],
)
def test_parse_reais_recusa_texto_invalido(texto):
    with pytest.raises(DadosInvalidosError):
        parse_reais(texto)


def test_parse_reais_recusa_negativo():
    with pytest.raises(DadosInvalidosError, match="negativo"):
        parse_reais("-5,00")


def test_parse_reais_recusa_mais_de_duas_casas():
    with pytest.raises(DadosInvalidosError, match="casas"):
        parse_reais("6,555")


def test_mensagens_usam_o_nome_do_campo():
    with pytest.raises(DadosInvalidosError, match="Informe o limite"):
        parse_reais("", campo="limite")
    with pytest.raises(DadosInvalidosError, match="Valor inválido"):
        parse_reais("abc", campo="valor")
    with pytest.raises(DadosInvalidosError, match="O valor não pode ser negativo"):
        parse_reais("-1", campo="valor")
    with pytest.raises(DadosInvalidosError, match="casas decimais no limite"):
        parse_reais("1,555", campo="limite")


def test_parse_reais_none():
    with pytest.raises(DadosInvalidosError):
        parse_reais(None)


def test_nao_ha_erro_de_arredondamento():
    assert parse_reais("0,1") + parse_reais("0,2") == parse_reais("0,3")


@pytest.mark.parametrize(
    "centavos, esperado",
    [(0, "R$ 0,00"), (5, "R$ 0,05"), (650, "R$ 6,50"), (123456, "R$ 1.234,56"),
     (123456789, "R$ 1.234.567,89"), (-250, "-R$ 2,50")],
)
def test_formatar_reais(centavos, esperado):
    assert formatar_reais(centavos) == esperado


def test_formatar_numero():
    assert formatar_numero(650) == "6,50"
    assert formatar_numero(5) == "0,05"


def test_ida_e_volta():
    for centavos in (1, 99, 100, 650, 99999):
        assert parse_reais(formatar_numero(centavos)) == centavos
