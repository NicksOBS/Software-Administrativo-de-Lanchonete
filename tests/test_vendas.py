from datetime import datetime

import pytest

from src import database
from src.errors import DadosInvalidosError, NaoEncontradoError, OperacaoNaoPermitidaError
from src.repos.categoria_repo import CategoriaRepo
from src.repos.cliente_repo import ClienteRepo
from src.repos.configuracao_repo import ConfiguracaoRepo
from src.repos.produto_repo import ProdutoRepo
from src.repos.venda_repo import VendaRepo
from src.services.categoria_service import CategoriaService
from src.services.cliente_service import ClienteService
from src.services.configuracao_service import ConfiguracaoService
from src.services.produto_service import ProdutoService
from src.services.venda_service import QUANTIDADE_MAXIMA, ItemPedido, VendaService


class Relogio:
    def __init__(self):
        self.agora = datetime(2026, 11, 27, 12, 0, 0)

    def __call__(self):
        return self.agora


@pytest.fixture
def conn():
    c = database.conectar(":memory:")
    yield c
    c.close()


@pytest.fixture
def relogio():
    return Relogio()


@pytest.fixture
def config(conn):
    return ConfiguracaoService(ConfiguracaoRepo(conn))


@pytest.fixture
def clientes(conn):
    return ClienteService(ClienteRepo(conn))


@pytest.fixture
def produtos(conn):
    return ProdutoService(ProdutoRepo(conn), CategoriaRepo(conn))


@pytest.fixture
def vendas(conn, config, relogio):
    return VendaService(VendaRepo(conn), ProdutoRepo(conn), ClienteRepo(conn), config, relogio)


@pytest.fixture
def cardapio(conn, produtos):
    """Coxinha R$ 6,50 / Refrigerante R$ 6,00 / Marmita R$ 25,00."""
    categoria = CategoriaService(CategoriaRepo(conn)).criar("Geral")
    return {
        "coxinha": produtos.criar("Coxinha", categoria.id, 650),
        "refri": produtos.criar("Refrigerante", categoria.id, 600),
        "marmita": produtos.criar("Marmita", categoria.id, 2500),
    }


def pedido(*pares):
    return [ItemPedido(p.id, q) for p, q in pares]


def contar(conn, tabela):
    return conn.execute(f"SELECT COUNT(*) FROM {tabela}").fetchone()[0]


def definir_divida(conn, codigo, centavos):
    with conn:
        conn.execute("UPDATE cliente SET divida_centavos = ? WHERE codigo = ?", (centavos, codigo))


# ================================================================== cálculo
def test_resumo_soma_os_itens(vendas, cardapio):
    r = vendas.calcular(pedido((cardapio["coxinha"], 2), (cardapio["refri"], 1)))
    assert r.subtotal_centavos == 1900
    assert r.desconto_centavos == 0
    assert r.total_centavos == 1900
    assert r.a_pagar_centavos == 1900
    assert [(i.nome, i.quantidade, i.subtotal_centavos) for i in r.itens] == [
        ("Coxinha", 2, 1300), ("Refrigerante", 1, 600)]


def test_carrinho_vazio_da_resumo_zerado(vendas):
    r = vendas.calcular([])
    assert (r.subtotal_centavos, r.total_centavos, r.a_pagar_centavos) == (0, 0, 0)


def test_produto_repetido_soma_as_quantidades(vendas, cardapio):
    r = vendas.calcular(pedido((cardapio["coxinha"], 2), (cardapio["coxinha"], 3)))
    assert len(r.itens) == 1 and r.itens[0].quantidade == 5 and r.subtotal_centavos == 3250


@pytest.mark.parametrize("quantidade", [0, -1])
def test_quantidade_precisa_ser_positiva(vendas, cardapio, quantidade):
    with pytest.raises(DadosInvalidosError, match="maior que zero"):
        vendas.calcular(pedido((cardapio["coxinha"], quantidade)))


def test_quantidade_maxima(vendas, cardapio):
    vendas.calcular(pedido((cardapio["coxinha"], QUANTIDADE_MAXIMA)))
    with pytest.raises(DadosInvalidosError, match="máxima"):
        vendas.calcular(pedido((cardapio["coxinha"], QUANTIDADE_MAXIMA + 1)))


def test_produto_inexistente(vendas):
    with pytest.raises(NaoEncontradoError):
        vendas.calcular([ItemPedido(999, 1)])


def test_produto_removido_nao_pode_ser_vendido(vendas, produtos, cardapio):
    produtos.remover(cardapio["coxinha"].id)
    with pytest.raises(NaoEncontradoError):
        vendas.calcular(pedido((cardapio["coxinha"], 1)))


# ============================================================ desconto (RN02)
def test_sem_valor_minimo_nao_ha_desconto(vendas, cardapio):
    assert vendas.calcular(pedido((cardapio["marmita"], 10))).desconto_centavos == 0


def test_venda_acima_do_minimo_recebe_15_por_cento(vendas, config, cardapio):
    """RN02: com limite de R$ 80,00, venda de R$ 100,00 resulta em total de R$ 85,00."""
    config.definir_valor_minimo_desconto(8000)
    r = vendas.calcular(pedido((cardapio["marmita"], 4)))
    assert (r.subtotal_centavos, r.desconto_centavos, r.total_centavos) == (10000, 1500, 8500)


def test_venda_abaixo_do_minimo_nao_tem_desconto(vendas, config, cardapio):
    """RN02: venda de R$ 70,00 (limite R$ 80,00) não tem desconto."""
    config.definir_valor_minimo_desconto(8000)
    r = vendas.calcular(pedido((cardapio["marmita"], 2), (cardapio["refri"], 3)))
    assert r.subtotal_centavos == 6800 and r.desconto_centavos == 0


def test_venda_exatamente_no_minimo_nao_tem_desconto(vendas, config, cardapio):
    """'Acima de' quer dizer estritamente maior."""
    config.definir_valor_minimo_desconto(5000)
    r = vendas.calcular(pedido((cardapio["marmita"], 2)))
    assert r.subtotal_centavos == 5000 and r.desconto_centavos == 0


def test_desconto_ligado_so_depois_vale_para_calculos_novos(vendas, config, cardapio):
    itens = pedido((cardapio["marmita"], 4))
    assert vendas.calcular(itens).desconto_centavos == 0
    config.definir_valor_minimo_desconto(8000)
    assert vendas.calcular(itens).desconto_centavos == 1500
    config.definir_valor_minimo_desconto(None)
    assert vendas.calcular(itens).desconto_centavos == 0


@pytest.mark.parametrize(
    "preco, desconto_esperado",
    [
        (1005, 151),   # 150,75 -> 151 (metade para cima)
        (1003, 150),   # 150,45 -> 150
        (1001, 150),   # 150,15 -> 150
        (1010, 152),   # 151,50 -> 152 (metade para cima)
    ],
)
def test_desconto_arredonda_para_o_centavo_mais_proximo(
    vendas, config, produtos, cardapio, preco, desconto_esperado
):
    categoria = CategoriaRepo(vendas._produtos._conn).listar()[0]
    produto = produtos.criar("Teste", categoria.id, preco)
    config.definir_valor_minimo_desconto(1000)
    r = vendas.calcular(pedido((produto, 1)))
    assert r.desconto_centavos == desconto_esperado
    assert r.total_centavos == preco - desconto_esperado


# =============================================================== registro
def test_registrar_venda_simples(vendas, conn, cardapio, relogio):
    """RF02: total igual à soma dos itens, com a forma de pagamento escolhida."""
    v = vendas.registrar(pedido((cardapio["coxinha"], 2), (cardapio["refri"], 1), (cardapio["marmita"], 1)), "pix")
    assert v.id > 0 and v.forma_pagamento == "pix" and v.cliente_codigo is None
    assert v.resumo.total_centavos == 650 * 2 + 600 + 2500
    assert v.data_hora == "2026-11-27T12:00:00"

    venda = VendaRepo(conn).buscar(v.id)
    assert (venda.forma_pagamento, venda.total_centavos, venda.desconto_centavos) == ("pix", 4400, 0)
    assert venda.pago_na_forma_centavos == 4400
    assert [(i.nome, i.quantidade, i.preco_unitario_centavos) for i in VendaRepo(conn).itens_da_venda(v.id)] == [
        ("Coxinha", 2, 650), ("Refrigerante", 1, 600), ("Marmita", 1, 2500)]


@pytest.mark.parametrize("forma", ["dinheiro", "pix", "debito", "credito"])
def test_todas_as_formas_a_vista(vendas, conn, cardapio, forma):
    v = vendas.registrar(pedido((cardapio["coxinha"], 1)), forma)
    assert VendaRepo(conn).buscar(v.id).forma_pagamento == forma


def test_venda_sem_produtos_e_recusada_e_nada_e_gravado(vendas, conn):
    """RF03."""
    with pytest.raises(DadosInvalidosError, match="ao menos um produto"):
        vendas.registrar([], "dinheiro")
    assert contar(conn, "venda") == 0 and contar(conn, "item_venda") == 0


@pytest.mark.parametrize("forma", ["", "cheque", "PIX", None])
def test_forma_de_pagamento_invalida(vendas, conn, cardapio, forma):
    with pytest.raises(DadosInvalidosError, match="forma de pagamento"):
        vendas.registrar(pedido((cardapio["coxinha"], 1)), forma)
    assert contar(conn, "venda") == 0


def test_mudar_o_preco_depois_nao_altera_a_venda_antiga(vendas, produtos, conn, cardapio):
    v = vendas.registrar(pedido((cardapio["coxinha"], 2)), "dinheiro")
    produtos.atualizar(cardapio["coxinha"].id, "Coxinha", cardapio["coxinha"].categoria_id, 900)
    assert VendaRepo(conn).itens_da_venda(v.id)[0].preco_unitario_centavos == 650
    assert vendas.calcular(pedido((cardapio["coxinha"], 2))).subtotal_centavos == 1800


def test_venda_com_desconto_grava_total_e_desconto(vendas, config, conn, cardapio):
    config.definir_valor_minimo_desconto(8000)
    v = vendas.registrar(pedido((cardapio["marmita"], 4)), "dinheiro")
    venda = VendaRepo(conn).buscar(v.id)
    assert (venda.desconto_centavos, venda.total_centavos) == (1500, 8500)


def test_venda_a_vista_pode_ter_cliente_associado(vendas, clientes, conn, cardapio):
    clientes.cadastrar(1, "Ana")
    v = vendas.registrar(pedido((cardapio["coxinha"], 1)), "pix", cliente_codigo=1)
    assert VendaRepo(conn).buscar(v.id).cliente_codigo == 1
    assert clientes.obter(1).divida_centavos == 0


def test_cliente_inexistente_ou_removido(vendas, clientes, conn, cardapio):
    with pytest.raises(NaoEncontradoError):
        vendas.registrar(pedido((cardapio["coxinha"], 1)), "pix", cliente_codigo=99)
    clientes.cadastrar(1, "Ana")
    clientes.remover(1)
    with pytest.raises(NaoEncontradoError):
        vendas.registrar(pedido((cardapio["coxinha"], 1)), "pix", cliente_codigo=1)
    assert contar(conn, "venda") == 0


# ================================================================ fiado (RF10)
def test_fiado_soma_a_venda_na_divida(vendas, clientes, conn, cardapio):
    """RF10: dívida de R$ 20,00 + compra de R$ 15,00 no fiado => R$ 35,00."""
    clientes.cadastrar(1, "Ana")
    definir_divida(conn, 1, 2000)
    produto = cardapio["coxinha"]  # 6,50
    vendas.registrar(pedido((produto, 1), (cardapio["refri"], 1), (produto, 0 + 1)), "fiado", cliente_codigo=1)
    # 2 x 6,50 + 6,00 = 19,00
    assert clientes.obter(1).divida_centavos == 2000 + 1900
    venda = VendaRepo(conn).buscar(1)
    assert venda.forma_pagamento == "fiado" and venda.cliente_codigo == 1


def test_fiado_exatamente_quinze_reais(vendas, clientes, conn, produtos, cardapio):
    clientes.cadastrar(1, "Ana")
    definir_divida(conn, 1, 2000)
    categoria = CategoriaRepo(conn).listar()[0]
    lanche = produtos.criar("Lanche", categoria.id, 1500)
    vendas.registrar(pedido((lanche, 1)), "fiado", cliente_codigo=1)
    assert clientes.obter(1).divida_centavos == 3500


def test_fiado_exige_cliente(vendas, conn, cardapio):
    with pytest.raises(DadosInvalidosError, match="cliente"):
        vendas.registrar(pedido((cardapio["coxinha"], 1)), "fiado")
    assert contar(conn, "venda") == 0


def test_fiado_com_desconto_anota_o_valor_com_desconto(vendas, config, clientes, cardapio):
    config.definir_valor_minimo_desconto(8000)
    clientes.cadastrar(1, "Ana")
    vendas.registrar(pedido((cardapio["marmita"], 4)), "fiado", cliente_codigo=1)
    assert clientes.obter(1).divida_centavos == 8500


# ============================================================== limite (RN01)
def test_cliente_acima_do_limite_nao_compra_no_fiado(vendas, clientes, conn, cardapio):
    """RN01: limite R$ 100,00 e dívida R$ 101,00 => venda no fiado recusada."""
    clientes.cadastrar(1, "Ana", 10000)
    definir_divida(conn, 1, 10100)
    with pytest.raises(OperacaoNaoPermitidaError, match="acima do limite"):
        vendas.registrar(pedido((cardapio["coxinha"], 1)), "fiado", cliente_codigo=1)
    assert contar(conn, "venda") == 0 and contar(conn, "item_venda") == 0
    assert clientes.obter(1).divida_centavos == 10100


def test_mensagem_de_bloqueio_traz_os_valores(vendas, clientes, conn, cardapio):
    clientes.cadastrar(1, "Ana", 10000)
    definir_divida(conn, 1, 10100)
    with pytest.raises(OperacaoNaoPermitidaError, match=r"R\$ 101,00 de R\$ 100,00"):
        vendas.registrar(pedido((cardapio["coxinha"], 1)), "fiado", cliente_codigo=1)


def test_depois_de_pagar_ate_o_limite_volta_a_comprar(vendas, clientes, conn, cardapio):
    """RN01: após pagamento que reduza a dívida ao limite ou abaixo, volta a ser aceito."""
    clientes.cadastrar(1, "Ana", 10000)
    definir_divida(conn, 1, 10100)
    clientes.registrar_pagamento(1, 100)
    vendas.registrar(pedido((cardapio["coxinha"], 1)), "fiado", cliente_codigo=1)
    assert clientes.obter(1).divida_centavos == 10000 + 650


def test_no_limite_exato_ainda_compra(vendas, clientes, conn, cardapio):
    clientes.cadastrar(1, "Ana", 10000)
    definir_divida(conn, 1, 10000)
    vendas.registrar(pedido((cardapio["coxinha"], 1)), "fiado", cliente_codigo=1)


def test_compra_pode_ultrapassar_o_limite_e_so_entao_bloqueia(vendas, clientes, conn, cardapio):
    """Como no documento: o bloqueio vale quando a dívida JÁ passou do limite."""
    clientes.cadastrar(1, "Ana", 10000)
    definir_divida(conn, 1, 9900)
    vendas.registrar(pedido((cardapio["marmita"], 1)), "fiado", cliente_codigo=1)  # 99 + 25 = 124
    assert clientes.obter(1).bloqueado
    with pytest.raises(OperacaoNaoPermitidaError):
        vendas.registrar(pedido((cardapio["coxinha"], 1)), "fiado", cliente_codigo=1)


def test_cliente_sem_limite_compra_sempre(vendas, clientes, conn, cardapio):
    clientes.cadastrar(1, "Ana")
    definir_divida(conn, 1, 5_000_000)
    vendas.registrar(pedido((cardapio["coxinha"], 1)), "fiado", cliente_codigo=1)


def test_bloqueado_pode_comprar_a_vista(vendas, clientes, conn, cardapio):
    clientes.cadastrar(1, "Ana", 10000)
    definir_divida(conn, 1, 10100)
    vendas.registrar(pedido((cardapio["coxinha"], 1)), "pix", cliente_codigo=1)
    assert clientes.obter(1).divida_centavos == 10100


# =============================================================== crédito (RN03)
def test_credito_abate_a_compra(vendas, clientes, conn, cardapio, produtos):
    """RN03: crédito de R$ 20,00 que compra R$ 15,00 fica com crédito de R$ 5,00."""
    clientes.cadastrar(1, "Ana")
    clientes.adicionar_credito(1, 2000)
    categoria = CategoriaRepo(conn).listar()[0]
    lanche = produtos.criar("Lanche", categoria.id, 1500)
    v = vendas.registrar(pedido((lanche, 1)), "dinheiro", cliente_codigo=1, usar_credito=True)
    assert clientes.obter(1).credito_centavos == 500
    assert (v.resumo.credito_usado_centavos, v.resumo.a_pagar_centavos) == (1500, 0)
    venda = VendaRepo(conn).buscar(v.id)
    assert (venda.total_centavos, venda.credito_usado_centavos, venda.pago_na_forma_centavos) == (1500, 1500, 0)


def test_credito_menor_que_a_compra_paga_so_uma_parte(vendas, clientes, conn, produtos, cardapio):
    clientes.cadastrar(1, "Ana")
    clientes.adicionar_credito(1, 1000)
    categoria = CategoriaRepo(conn).listar()[0]
    lanche = produtos.criar("Lanche", categoria.id, 1500)
    v = vendas.registrar(pedido((lanche, 1)), "pix", cliente_codigo=1, usar_credito=True)
    assert clientes.obter(1).credito_centavos == 0
    venda = VendaRepo(conn).buscar(v.id)
    assert (venda.credito_usado_centavos, venda.pago_na_forma_centavos) == (1000, 500)


def test_sem_marcar_usar_credito_o_saldo_fica_guardado(vendas, clientes, cardapio):
    clientes.cadastrar(1, "Ana")
    clientes.adicionar_credito(1, 2000)
    v = vendas.registrar(pedido((cardapio["coxinha"], 1)), "dinheiro", cliente_codigo=1)
    assert clientes.obter(1).credito_centavos == 2000
    assert v.resumo.credito_usado_centavos == 0


def test_usar_credito_exige_cliente(vendas, cardapio):
    with pytest.raises(DadosInvalidosError, match="cliente"):
        vendas.registrar(pedido((cardapio["coxinha"], 1)), "dinheiro", usar_credito=True)


def test_credito_maior_que_a_venda_usa_so_o_necessario(vendas, clientes, cardapio):
    clientes.cadastrar(1, "Ana")
    clientes.adicionar_credito(1, 20000)
    vendas.registrar(pedido((cardapio["coxinha"], 2)), "dinheiro", cliente_codigo=1, usar_credito=True)
    assert clientes.obter(1).credito_centavos == 20000 - 1300


def test_cliente_sem_credito_com_usar_credito_marcado(vendas, clientes, cardapio):
    clientes.cadastrar(1, "Ana")
    v = vendas.registrar(pedido((cardapio["coxinha"], 1)), "dinheiro", cliente_codigo=1, usar_credito=True)
    assert v.resumo.credito_usado_centavos == 0 and v.resumo.a_pagar_centavos == 650


def test_desconto_vem_antes_do_credito(vendas, config, clientes, cardapio):
    config.definir_valor_minimo_desconto(8000)
    clientes.cadastrar(1, "Ana")
    clientes.adicionar_credito(1, 3000)
    r = vendas.calcular(pedido((cardapio["marmita"], 4)), cliente_codigo=1, usar_credito=True)
    assert (r.subtotal_centavos, r.desconto_centavos, r.total_centavos) == (10000, 1500, 8500)
    assert (r.credito_usado_centavos, r.a_pagar_centavos) == (3000, 5500)


def test_fiado_com_credito_anota_so_o_restante(vendas, clientes, produtos, conn, cardapio):
    clientes.cadastrar(1, "Ana")
    clientes.adicionar_credito(1, 1000)
    categoria = CategoriaRepo(conn).listar()[0]
    lanche = produtos.criar("Lanche", categoria.id, 2500)
    vendas.registrar(pedido((lanche, 1)), "fiado", cliente_codigo=1, usar_credito=True)
    c = clientes.obter(1)
    assert (c.credito_centavos, c.divida_centavos) == (0, 1500)


def test_bloqueado_com_venda_toda_paga_pelo_credito_passa_no_fiado(vendas, clientes, conn, cardapio):
    """Se o crédito cobre tudo, não nasce dívida nova: o bloqueio não se aplica."""
    clientes.cadastrar(1, "Ana", 10000)
    definir_divida(conn, 1, 10100)
    clientes.adicionar_credito(1, 5000)
    vendas.registrar(pedido((cardapio["coxinha"], 1)), "fiado", cliente_codigo=1, usar_credito=True)
    c = clientes.obter(1)
    assert (c.credito_centavos, c.divida_centavos) == (5000 - 650, 10100)


def test_bloqueado_com_credito_parcial_continua_recusado(vendas, clientes, conn, cardapio):
    clientes.cadastrar(1, "Ana", 10000)
    definir_divida(conn, 1, 10100)
    clientes.adicionar_credito(1, 100)
    with pytest.raises(OperacaoNaoPermitidaError):
        vendas.registrar(pedido((cardapio["coxinha"], 1)), "fiado", cliente_codigo=1, usar_credito=True)
    assert clientes.obter(1).credito_centavos == 100


# ================================================================ tudo ou nada
def test_falha_no_meio_desfaz_a_venda_inteira(vendas, clientes, conn, produtos, cardapio, monkeypatch):
    """RNF07: se atualizar a dívida falhar, nem a venda, nem os itens, nem o crédito mudam."""
    clientes.cadastrar(1, "Ana")
    clientes.adicionar_credito(1, 1000)
    categoria = CategoriaRepo(conn).listar()[0]
    lanche = produtos.criar("Lanche", categoria.id, 2500)

    def falhar(*args, **kwargs):
        raise RuntimeError("falha simulada")

    monkeypatch.setattr(ClienteRepo, "somar_divida", falhar)
    with pytest.raises(RuntimeError):
        vendas.registrar(pedido((lanche, 1)), "fiado", cliente_codigo=1, usar_credito=True)
    assert contar(conn, "venda") == 0 and contar(conn, "item_venda") == 0
    c = clientes.obter(1)
    assert (c.credito_centavos, c.divida_centavos) == (1000, 0)


def test_falha_ao_gravar_itens_desfaz_a_venda(vendas, conn, cardapio, monkeypatch):
    def falhar(*args, **kwargs):
        raise RuntimeError("falha simulada")

    monkeypatch.setattr(VendaRepo, "inserir_itens", falhar)
    with pytest.raises(RuntimeError):
        vendas.registrar(pedido((cardapio["coxinha"], 1)), "dinheiro")
    assert contar(conn, "venda") == 0


def test_varias_vendas_seguidas_tem_ids_diferentes(vendas, cardapio):
    ids = {vendas.registrar(pedido((cardapio["coxinha"], 1)), "dinheiro").id for _ in range(3)}
    assert len(ids) == 3
