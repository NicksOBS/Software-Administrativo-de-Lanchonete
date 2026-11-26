import pytest

from src import database
from src.errors import DadosInvalidosError, NaoEncontradoError, RegistroDuplicadoError
from src.repos.categoria_repo import CategoriaRepo
from src.repos.produto_repo import ProdutoRepo
from src.services.categoria_service import CategoriaService
from src.services.produto_service import NOME_MAX, PRECO_MAXIMO_CENTAVOS, ProdutoService


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


@pytest.fixture
def salgados(categorias):
    return categorias.criar("Salgados")


@pytest.fixture
def bebidas(categorias):
    return categorias.criar("Bebidas")


# ----------------------------------------------------------------- cadastro
def test_criar_produto(produtos, salgados):
    p = produtos.criar("Coxinha", salgados.id, 650)
    assert p.id > 0
    assert (p.nome, p.categoria_nome, p.preco_centavos, p.ativo) == ("Coxinha", "Salgados", 650, True)


def test_nome_e_limpo(produtos, salgados):
    assert produtos.criar("  Pão   de   queijo ", salgados.id, 500).nome == "Pão de queijo"


def test_nome_vazio_e_recusado(produtos, salgados):
    with pytest.raises(DadosInvalidosError):
        produtos.criar("  ", salgados.id, 650)


def test_nome_muito_longo_e_recusado(produtos, salgados):
    with pytest.raises(DadosInvalidosError):
        produtos.criar("x" * (NOME_MAX + 1), salgados.id, 650)


def test_categoria_e_obrigatoria(produtos):
    with pytest.raises(DadosInvalidosError, match="categoria"):
        produtos.criar("Coxinha", None, 650)


def test_categoria_inexistente_e_recusada(produtos):
    with pytest.raises(DadosInvalidosError, match="categoria"):
        produtos.criar("Coxinha", 999, 650)


@pytest.mark.parametrize("preco", [0, -1, -650])
def test_preco_precisa_ser_positivo(produtos, salgados, preco):
    with pytest.raises(DadosInvalidosError, match="maior que zero"):
        produtos.criar("Coxinha", salgados.id, preco)


def test_preco_maximo(produtos, salgados):
    produtos.criar("Caro", salgados.id, PRECO_MAXIMO_CENTAVOS)
    with pytest.raises(DadosInvalidosError, match="máximo"):
        produtos.criar("Caro demais", salgados.id, PRECO_MAXIMO_CENTAVOS + 1)


@pytest.mark.parametrize("repetido", ["coxinha", "COXINHA", " Coxinha "])
def test_nome_repetido_e_recusado(produtos, salgados, repetido):
    produtos.criar("Coxinha", salgados.id, 650)
    with pytest.raises(RegistroDuplicadoError):
        produtos.criar(repetido, salgados.id, 700)


def test_nome_repetido_em_outra_categoria_tambem_e_recusado(produtos, salgados, bebidas):
    produtos.criar("Café", salgados.id, 400)
    with pytest.raises(RegistroDuplicadoError):
        produtos.criar("CAFE", bebidas.id, 400)


def test_nome_de_produto_removido_pode_ser_reutilizado(produtos, salgados):
    antigo = produtos.criar("Coxinha", salgados.id, 650)
    produtos.remover(antigo.id)
    novo = produtos.criar("Coxinha", salgados.id, 700)
    assert novo.id != antigo.id


# ------------------------------------------------------------------ edição
def test_atualizar_produto(produtos, salgados, bebidas):
    p = produtos.criar("Coxinha", salgados.id, 650)
    atualizado = produtos.atualizar(p.id, "Coxinha de frango", bebidas.id, 700)
    assert (atualizado.nome, atualizado.categoria_nome, atualizado.preco_centavos) == (
        "Coxinha de frango", "Bebidas", 700)


def test_atualizar_mantendo_o_proprio_nome(produtos, salgados):
    """Editar só o preço não pode acusar 'nome repetido' contra si mesmo."""
    p = produtos.criar("Coxinha", salgados.id, 650)
    assert produtos.atualizar(p.id, "Coxinha", salgados.id, 700).preco_centavos == 700


def test_atualizar_para_nome_de_outro_produto_e_recusado(produtos, salgados):
    produtos.criar("Coxinha", salgados.id, 650)
    outro = produtos.criar("Pastel", salgados.id, 700)
    with pytest.raises(RegistroDuplicadoError):
        produtos.atualizar(outro.id, "coxinha", salgados.id, 700)


def test_atualizar_produto_inexistente(produtos, salgados):
    with pytest.raises(NaoEncontradoError):
        produtos.atualizar(999, "X", salgados.id, 100)


def test_novo_preco_nao_altera_vendas_antigas(produtos, salgados, conn):
    """Vendas guardam o preço da época em item_venda."""
    p = produtos.criar("Coxinha", salgados.id, 650)
    with conn:
        conn.execute(
            "INSERT INTO venda (data_hora, forma_pagamento, total_centavos) "
            "VALUES ('2026-11-26T10:00:00', 'pix', 650)"
        )
        conn.execute("INSERT INTO item_venda VALUES (1, ?, 1, 650)", (p.id,))
    produtos.atualizar(p.id, "Coxinha", salgados.id, 800)
    preco_na_venda = conn.execute("SELECT preco_unitario_centavos FROM item_venda").fetchone()[0]
    assert preco_na_venda == 650


# ------------------------------------------------------------------ remoção
def test_remover_some_da_lista(produtos, salgados):
    p = produtos.criar("Coxinha", salgados.id, 650)
    produtos.remover(p.id)
    assert produtos.listar() == []
    with pytest.raises(NaoEncontradoError):
        produtos.obter(p.id)


def test_remover_mantem_historico_de_vendas(produtos, salgados, conn):
    p = produtos.criar("Coxinha", salgados.id, 650)
    with conn:
        conn.execute(
            "INSERT INTO venda (data_hora, forma_pagamento, total_centavos) "
            "VALUES ('2026-11-26T10:00:00', 'pix', 650)"
        )
        conn.execute("INSERT INTO item_venda VALUES (1, ?, 1, 650)", (p.id,))
    produtos.remover(p.id)  # não pode falhar por chave estrangeira
    assert conn.execute("SELECT COUNT(*) FROM item_venda").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM produto").fetchone()[0] == 1


def test_remover_duas_vezes(produtos, salgados):
    p = produtos.criar("Coxinha", salgados.id, 650)
    produtos.remover(p.id)
    with pytest.raises(NaoEncontradoError):
        produtos.remover(p.id)


# ----------------------------------------------------------------- pesquisa
@pytest.fixture
def cardapio(produtos, salgados, bebidas):
    produtos.criar("Coxinha", salgados.id, 650)
    produtos.criar("Pão de queijo", salgados.id, 500)
    produtos.criar("Café", bebidas.id, 400)
    produtos.criar("Coca-Cola 350ml", bebidas.id, 600)
    produtos.criar("Suco 100% natural", bebidas.id, 800)
    return produtos


def nomes(lista):
    return [p.nome for p in lista]


def test_listar_tudo_em_ordem_alfabetica(cardapio):
    assert nomes(cardapio.listar()) == [
        "Café", "Coca-Cola 350ml", "Coxinha", "Pão de queijo", "Suco 100% natural"]


def test_pesquisa_por_parte_do_nome(cardapio):
    assert nomes(cardapio.listar("cox")) == ["Coxinha"]


def test_pesquisa_ignora_acentos_e_maiusculas(cardapio):
    assert nomes(cardapio.listar("PAO")) == ["Pão de queijo"]
    assert nomes(cardapio.listar("cafe")) == ["Café"]
    assert nomes(cardapio.listar("café")) == ["Café"]


def test_pesquisa_pelo_nome_da_categoria(cardapio):
    assert nomes(cardapio.listar("bebida")) == ["Café", "Coca-Cola 350ml", "Suco 100% natural"]


def test_filtro_por_categoria(cardapio, salgados):
    assert nomes(cardapio.listar(categoria_id=salgados.id)) == ["Coxinha", "Pão de queijo"]


def test_pesquisa_combinada_com_filtro(cardapio, bebidas):
    assert nomes(cardapio.listar("coca", bebidas.id)) == ["Coca-Cola 350ml"]
    assert nomes(cardapio.listar("cox", bebidas.id)) == []  # Coxinha é de outra categoria


def test_pesquisa_sem_resultado(cardapio):
    assert cardapio.listar("pizza") == []


def test_pesquisa_vazia_ou_so_espacos_lista_tudo(cardapio):
    assert len(cardapio.listar("   ")) == 5


@pytest.mark.parametrize("termo", ["%", "_", "100%", "\\"])
def test_caracteres_especiais_da_pesquisa_sao_literais(cardapio, termo):
    """% e _ são curingas no LIKE do SQL; aqui valem como texto comum."""
    esperado = ["Suco 100% natural"] if "%" in termo else []
    assert nomes(cardapio.listar(termo)) == esperado


def test_produto_sem_categoria_aparece_na_listagem(produtos, categorias, salgados, conn):
    p = produtos.criar("Coxinha", salgados.id, 650)
    with conn:
        conn.execute("UPDATE produto SET categoria_id = NULL WHERE id = ?", (p.id,))
    resultado = produtos.listar()
    assert nomes(resultado) == ["Coxinha"] and resultado[0].categoria_nome is None
