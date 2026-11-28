import pytest

from src import database
from src.errors import DadosInvalidosError
from src.repos.configuracao_repo import ConfiguracaoRepo
from src.services.configuracao_service import VALOR_MAXIMO_CENTAVOS, ConfiguracaoService


@pytest.fixture
def conn():
    c = database.conectar(":memory:")
    yield c
    c.close()


@pytest.fixture
def config(conn):
    return ConfiguracaoService(ConfiguracaoRepo(conn))


def test_repo_obter_e_definir(conn):
    repo = ConfiguracaoRepo(conn)
    assert repo.obter("x") is None
    repo.definir("x", "1")
    assert repo.obter("x") == "1"
    repo.definir("x", "2")  # sobrescreve
    assert repo.obter("x") == "2"
    repo.definir("x", None)  # apaga
    assert repo.obter("x") is None


def test_desconto_comeca_desligado(config):
    assert config.valor_minimo_desconto() is None


def test_definir_e_ler_valor_minimo(config):
    config.definir_valor_minimo_desconto(8000)
    assert config.valor_minimo_desconto() == 8000


def test_desligar_o_desconto(config):
    config.definir_valor_minimo_desconto(8000)
    config.definir_valor_minimo_desconto(None)
    assert config.valor_minimo_desconto() is None


@pytest.mark.parametrize("valor", [0, -1])
def test_valor_minimo_precisa_ser_positivo(config, valor):
    with pytest.raises(DadosInvalidosError, match="maior que zero"):
        config.definir_valor_minimo_desconto(valor)


def test_valor_minimo_maximo(config):
    with pytest.raises(DadosInvalidosError, match="máximo"):
        config.definir_valor_minimo_desconto(VALOR_MAXIMO_CENTAVOS + 1)


def test_valor_invalido_guardado_nao_quebra(conn, config):
    ConfiguracaoRepo(conn).definir("desconto_valor_minimo_centavos", "lixo")
    assert config.valor_minimo_desconto() is None


def test_valor_persiste_entre_conexoes(tmp_path):
    caminho = tmp_path / "x.db"
    c1 = database.conectar(caminho)
    ConfiguracaoService(ConfiguracaoRepo(c1)).definir_valor_minimo_desconto(5000)
    c1.close()
    c2 = database.conectar(caminho)
    assert ConfiguracaoService(ConfiguracaoRepo(c2)).valor_minimo_desconto() == 5000
    c2.close()
