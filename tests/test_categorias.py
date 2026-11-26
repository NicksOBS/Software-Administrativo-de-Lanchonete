import pytest

from src import database
from src.errors import (
    DadosInvalidosError,
    NaoEncontradoError,
    OperacaoNaoPermitidaError,
    RegistroDuplicadoError,
)
from src.repos.categoria_repo import CategoriaRepo
from src.repos.produto_repo import ProdutoRepo
from src.services.categoria_service import NOME_MAX, CategoriaService
from src.services.produto_service import ProdutoService


@pytest.fixture
def conn():
    c = database.conectar(":memory:")
    yield c
    c.close()


@pytest.fixture
def categorias(conn):
    return CategoriaService(CategoriaRepo(conn))


@pytest.fixture
def produtos(conn):
    return ProdutoService(ProdutoRepo(conn), CategoriaRepo(conn))


def test_criar_e_listar_em_ordem_alfabetica_sem_acento(categorias):
    for nome in ["Refrigerantes", "Doces", "Água", "Salgados"]:
        categorias.criar(nome)
    assert [c.nome for c in categorias.listar()] == ["Água", "Doces", "Refrigerantes", "Salgados"]


def test_nome_e_limpo(categorias):
    assert categorias.criar("   Café    da   manhã  ").nome == "Café da manhã"


def test_nome_vazio_e_recusado(categorias):
    with pytest.raises(DadosInvalidosError):
        categorias.criar("   ")


def test_nome_muito_longo_e_recusado(categorias):
    with pytest.raises(DadosInvalidosError):
        categorias.criar("x" * (NOME_MAX + 1))


@pytest.mark.parametrize("repetido", ["doces", "DOCES", "  Doces "])
def test_nome_repetido_e_recusado(categorias, repetido):
    categorias.criar("Doces")
    with pytest.raises(RegistroDuplicadoError):
        categorias.criar(repetido)


def test_nome_repetido_ignora_acentos_e_maiusculas(categorias):
    categorias.criar("Pão")
    with pytest.raises(RegistroDuplicadoError):
        categorias.criar("PAO")


def test_renomear(categorias):
    c = categorias.criar("Doce")
    categorias.renomear(c.id, "Doces")
    assert [x.nome for x in categorias.listar()] == ["Doces"]


def test_renomear_para_o_mesmo_nome_com_outra_caixa_e_permitido(categorias):
    c = categorias.criar("doces")
    categorias.renomear(c.id, "Doces")
    assert categorias.listar()[0].nome == "Doces"


def test_renomear_para_nome_de_outra_categoria_e_recusado(categorias):
    categorias.criar("Doces")
    outra = categorias.criar("Salgados")
    with pytest.raises(RegistroDuplicadoError):
        categorias.renomear(outra.id, "doces")


def test_renomear_categoria_inexistente(categorias):
    with pytest.raises(NaoEncontradoError):
        categorias.renomear(999, "X")


def test_remover_categoria_vazia(categorias):
    c = categorias.criar("Doces")
    categorias.remover(c.id)
    assert categorias.listar() == []


def test_remover_categoria_com_produtos_e_recusado(categorias, produtos):
    c = categorias.criar("Salgados")
    produtos.criar("Coxinha", c.id, 650)
    with pytest.raises(OperacaoNaoPermitidaError, match="1 produto cadastrado"):
        categorias.remover(c.id)
    assert len(categorias.listar()) == 1


def test_remover_categoria_com_varios_produtos_usa_plural(categorias, produtos):
    c = categorias.criar("Salgados")
    produtos.criar("Coxinha", c.id, 650)
    produtos.criar("Pastel", c.id, 700)
    with pytest.raises(OperacaoNaoPermitidaError, match="2 produtos cadastrados"):
        categorias.remover(c.id)


def test_remover_categoria_cujos_produtos_foram_removidos(categorias, produtos, conn):
    c = categorias.criar("Salgados")
    p = produtos.criar("Coxinha", c.id, 650)
    produtos.remover(p.id)
    categorias.remover(c.id)  # não deve falhar por causa da chave estrangeira
    assert categorias.listar() == []
    linha = conn.execute("SELECT categoria_id, ativo FROM produto WHERE id = ?", (p.id,)).fetchone()
    assert linha["categoria_id"] is None and linha["ativo"] == 0


def test_remover_categoria_inexistente(categorias):
    with pytest.raises(NaoEncontradoError):
        categorias.remover(999)
