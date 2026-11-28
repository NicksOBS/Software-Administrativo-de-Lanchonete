from datetime import date, datetime

import pytest
from openpyxl import load_workbook

from src import database
from src.errors import DadosInvalidosError, OperacaoNaoPermitidaError
from src.export import planilha as modulo_planilha
from src.repos.categoria_repo import CategoriaRepo
from src.repos.cliente_repo import ClienteRepo
from src.repos.configuracao_repo import ConfiguracaoRepo
from src.repos.expediente_repo import ExpedienteRepo
from src.repos.produto_repo import ProdutoRepo
from src.repos.relatorio_repo import RelatorioRepo
from src.repos.venda_repo import VendaRepo
from src.services.categoria_service import CategoriaService
from src.services.cliente_service import ClienteService
from src.services.configuracao_service import (
    AUTOSAVE_MINIMO_SEGUNDOS, AUTOSAVE_PADRAO_SEGUNDOS, ConfiguracaoService,
)
from src.services.expediente_service import ExpedienteService, intervalo_do_periodo
from src.services.produto_service import ProdutoService
from src.services.venda_service import ItemPedido, VendaService


class Relogio:
    def __init__(self, quando="2026-11-27T08:00:00"):
        self.agora = datetime.fromisoformat(quando)

    def __call__(self):
        return self.agora

    def ir_para(self, quando):
        self.agora = datetime.fromisoformat(quando)


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
def pasta(tmp_path):
    p = tmp_path / "planilhas"
    p.mkdir()
    return p


@pytest.fixture
def exp(conn, config, relogio, pasta):
    servico = ExpedienteService(
        ExpedienteRepo(conn), RelatorioRepo(conn), config, tmp_padrao(pasta), relogio
    )
    servico.definir_pasta_planilhas(pasta)
    return servico


def tmp_padrao(pasta):
    return pasta.parent / "padrao"


@pytest.fixture
def vendas(conn, config, relogio, exp):
    return VendaService(
        VendaRepo(conn), ProdutoRepo(conn), ClienteRepo(conn), config, relogio, expedientes=exp
    )


@pytest.fixture
def clientes(conn):
    return ClienteService(ClienteRepo(conn))


@pytest.fixture
def cardapio(conn):
    salgado = CategoriaService(CategoriaRepo(conn)).criar("Salgado")
    bebida = CategoriaService(CategoriaRepo(conn)).criar("Bebida")
    outros = CategoriaService(CategoriaRepo(conn)).criar("Outros")
    produtos = ProdutoService(ProdutoRepo(conn), CategoriaRepo(conn))
    return {
        "coxinha": produtos.criar("Coxinha", salgado.id, 650),
        "refri": produtos.criar("Refrigerante", bebida.id, 600),
        "marmita": produtos.criar("Marmita", outros.id, 2500),
        "produtos": produtos,
    }


def pedido(*pares):
    return [ItemPedido(p.id, q) for p, q in pares]


def ler(caminho):
    """Planilha -> lista de linhas (tuplas), ignorando linhas vazias."""
    ws = load_workbook(caminho).active
    return [tuple(c.value for c in linha) for linha in ws.iter_rows() if any(c.value is not None for c in linha)]


def valor(linhas, rotulo):
    return next(l[4] for l in linhas if l[0] == rotulo)


# ================================================================== iniciar
def test_comeca_fechado(exp):
    assert exp.aberto() is None
    assert exp.totais_atuais() is None


def test_iniciar_abre_o_expediente(exp):
    e = exp.iniciar()
    assert e.aberto and e.inicio == "2026-11-27T08:00:00" and e.fim is None
    assert exp.aberto().id == e.id


def test_nao_inicia_duas_vezes(exp):
    exp.iniciar()
    with pytest.raises(OperacaoNaoPermitidaError, match="já está aberto desde 27/11/2026 08:00"):
        exp.iniciar()


def test_sem_expediente_nao_ha_venda(vendas, cardapio, conn):
    with pytest.raises(OperacaoNaoPermitidaError, match="Inicie o expediente"):
        vendas.registrar(pedido((cardapio["coxinha"], 1)), "pix")
    assert conn.execute("SELECT COUNT(*) FROM venda").fetchone()[0] == 0


def test_com_expediente_aberto_vende(vendas, exp, cardapio):
    exp.iniciar()
    vendas.registrar(pedido((cardapio["coxinha"], 1)), "pix")
    assert exp.totais_atuais().total_centavos == 650


def test_expediente_aberto_sobrevive_a_queda(tmp_path):
    """RNF01: reabrir o programa depois de uma queda mantém o expediente e as vendas."""
    caminho = tmp_path / "x.db"
    c1 = database.conectar(caminho)
    ConfiguracaoService(ConfiguracaoRepo(c1))
    s1 = ExpedienteService(ExpedienteRepo(c1), RelatorioRepo(c1), ConfiguracaoService(ConfiguracaoRepo(c1)), tmp_path)
    inicio = s1.iniciar().inicio
    c1.close()  # "queda": nada de encerrar
    c2 = database.conectar(caminho)
    s2 = ExpedienteService(ExpedienteRepo(c2), RelatorioRepo(c2), ConfiguracaoService(ConfiguracaoRepo(c2)), tmp_path)
    assert s2.aberto().inicio == inicio
    c2.close()


# ================================================================== encerrar
def test_encerrar_sem_expediente(exp):
    with pytest.raises(OperacaoNaoPermitidaError, match="Não há expediente aberto"):
        exp.encerrar()


def test_encerrar_gera_planilha_com_a_data_do_dia(exp, vendas, cardapio, relogio, pasta):
    """RF12."""
    exp.iniciar()
    vendas.registrar(pedido((cardapio["coxinha"], 2)), "dinheiro")
    relogio.ir_para("2026-11-27T18:30:00")
    r = exp.encerrar()
    assert r.caminho == pasta / "vendas_2026-11-27.xlsx" and r.caminho.exists()
    assert exp.aberto() is None
    assert r.expediente.fim == "2026-11-27T18:30:00" and r.expediente.arquivo == str(r.caminho)
    assert r.totais.total_centavos == 1300


def test_planilha_tem_produto_categoria_quantidade_e_valor(exp, vendas, cardapio, pasta):
    """RF13."""
    exp.iniciar()
    vendas.registrar(pedido((cardapio["coxinha"], 2), (cardapio["refri"], 1), (cardapio["marmita"], 1)), "pix")
    vendas.registrar(pedido((cardapio["coxinha"], 3)), "dinheiro")
    linhas = ler(exp.encerrar().caminho)
    assert linhas[0][0] == "Vendas do dia 27/11/2026"
    assert ("Produto", "Categoria", "Quantidade", "Valor unitário", "Subtotal") in linhas
    dados = {l[0]: l[1:] for l in linhas if l[0] in ("Coxinha", "Refrigerante", "Marmita")}
    assert dados["Coxinha"] == ("Salgado", 5, 6.5, 32.5)
    assert dados["Refrigerante"] == ("Bebida", 1, 6, 6)
    assert dados["Marmita"] == ("Outros", 1, 25, 25)


def test_subtotais_batem_com_o_total_vendido(exp, vendas, config, clientes, cardapio):
    """RF13: itens - descontos = total = soma das formas de pagamento (+ saldo de crédito)."""
    config.definir_valor_minimo_desconto(5000)
    clientes.cadastrar(1, "Ana")
    clientes.adicionar_credito(1, 1000)
    exp.iniciar()
    vendas.registrar(pedido((cardapio["marmita"], 4)), "pix")                         # 100 - 15 = 85
    vendas.registrar(pedido((cardapio["coxinha"], 2)), "debito")                      # 13
    vendas.registrar(pedido((cardapio["refri"], 1)), "credito")                       # 6
    vendas.registrar(pedido((cardapio["coxinha"], 1)), "dinheiro", 1, usar_credito=True)  # 6,50 pago com saldo
    vendas.registrar(pedido((cardapio["marmita"], 1)), "fiado", 1)                    # 25 no fiado
    linhas = ler(exp.encerrar().caminho)

    assert valor(linhas, "Soma dos itens") == 100 + 13 + 6 + 6.5 + 25
    assert valor(linhas, "Descontos") == -15
    total = valor(linhas, "Total vendido")
    assert total == 85 + 13 + 6 + 6.5 + 25
    assert valor(linhas, "PIX") == 85 and valor(linhas, "Débito") == 13
    assert valor(linhas, "Crédito") == 6 and valor(linhas, "Dinheiro") == 0
    assert valor(linhas, "Fiado") == 25 and valor(linhas, "Saldo de crédito do cliente") == 6.5
    assert valor(linhas, "Total") == total
    # soma das linhas de produto == soma dos itens
    produtos = [l[4] for l in linhas if l[1] in ("Salgado", "Bebida", "Outros")]
    assert sum(produtos) == valor(linhas, "Soma dos itens")


def test_planilha_so_tem_vendas_do_expediente(exp, vendas, cardapio, relogio, conn):
    """Vendas de antes do início ou depois do fim não entram."""
    VendaRepo(conn)
    with conn:
        conn.execute(
            "INSERT INTO venda (data_hora, forma_pagamento, total_centavos) VALUES (?, 'pix', 999)",
            ("2026-11-26T20:00:00",),
        )
    exp.iniciar()
    vendas.registrar(pedido((cardapio["coxinha"], 1)), "pix")
    relogio.ir_para("2026-11-27T12:00:00")
    r = exp.encerrar()
    assert r.totais.quantidade_vendas == 1 and r.totais.total_centavos == 650


def test_precos_diferentes_no_dia_viram_linhas_separadas(exp, vendas, cardapio):
    exp.iniciar()
    vendas.registrar(pedido((cardapio["coxinha"], 1)), "pix")
    p = cardapio["coxinha"]
    cardapio["produtos"].atualizar(p.id, p.nome, p.categoria_id, 800)
    vendas.registrar(pedido((cardapio["coxinha"], 2)), "pix")
    linhas = [l for l in ler(exp.encerrar().caminho) if l[0] == "Coxinha"]
    assert [(l[2], l[3]) for l in linhas] == [(1, 6.5), (2, 8)]


def test_expediente_sem_vendas_gera_planilha_zerada(exp):
    exp.iniciar()
    linhas = ler(exp.encerrar().caminho)
    assert valor(linhas, "Total vendido") == 0 and valor(linhas, "Total") == 0


def test_dois_expedientes_no_mesmo_dia_nao_se_sobrescrevem(exp, pasta):
    exp.iniciar()
    a = exp.encerrar().caminho
    exp.iniciar()
    b = exp.encerrar().caminho
    assert a.name == "vendas_2026-11-27.xlsx" and b.name == "vendas_2026-11-27_2.xlsx"
    assert a.exists() and b.exists()


def test_planilha_fecha_o_expediente_e_permite_um_novo(exp):
    exp.iniciar()
    exp.encerrar()
    assert exp.aberto() is None
    assert exp.iniciar().aberto


# ============================================================== pasta (RF14)
def test_pasta_inexistente_avisa_e_mantem_expediente_aberto(exp, config, pasta):
    exp.iniciar()
    config.definir_pasta_planilhas(str(pasta / "sumiu"))
    with pytest.raises(OperacaoNaoPermitidaError, match="não existe"):
        exp.encerrar()
    assert exp.aberto() is not None
    assert list(pasta.iterdir()) == []


def test_escolher_pasta_valida(exp, tmp_path):
    outra = tmp_path / "outra"
    outra.mkdir()
    exp.definir_pasta_planilhas(outra)
    assert exp.pasta_planilhas() == outra
    exp.iniciar()
    assert exp.encerrar().caminho.parent == outra


@pytest.mark.parametrize("texto", ["", "   "])
def test_escolher_pasta_vazia(exp, texto):
    with pytest.raises(DadosInvalidosError, match="não existe"):
        exp.definir_pasta_planilhas(texto)


def test_escolher_pasta_inexistente(exp, tmp_path):
    with pytest.raises(DadosInvalidosError, match="não existe"):
        exp.definir_pasta_planilhas(tmp_path / "nada")


def test_escolher_arquivo_no_lugar_de_pasta(exp, tmp_path):
    arquivo = tmp_path / "a.txt"
    arquivo.write_text("x")
    with pytest.raises(DadosInvalidosError):
        exp.definir_pasta_planilhas(arquivo)


def test_pasta_padrao_e_criada_quando_nada_foi_escolhido(conn, config, relogio, tmp_path):
    padrao = tmp_path / "dados" / "planilhas"
    servico = ExpedienteService(ExpedienteRepo(conn), RelatorioRepo(conn), config, padrao, relogio)
    assert servico.pasta_planilhas() == padrao
    servico.iniciar()
    assert servico.encerrar().caminho.parent == padrao and padrao.is_dir()


def test_falha_ao_gravar_mantem_expediente_aberto(exp, pasta, monkeypatch):
    def negar(caminho, dados):
        raise PermissionError(13, "Permissão negada")

    monkeypatch.setattr("src.services.expediente_service.gerar_planilha", negar)
    exp.iniciar()
    with pytest.raises(OperacaoNaoPermitidaError, match="continua aberto"):
        exp.encerrar()
    assert exp.aberto() is not None


def test_nao_sobra_arquivo_temporario_se_falhar(pasta, monkeypatch):
    def quebrar(self, destino):
        open(destino, "w").write("meio")
        raise OSError("disco cheio")

    monkeypatch.setattr(modulo_planilha.Workbook, "save", quebrar)
    dados = modulo_planilha.DadosPlanilha(
        date(2026, 11, 27), "2026-11-27T08:00:00", "2026-11-27T18:00:00", [],
        RelatorioRepo(database.conectar(":memory:")).totais("a", "z"),
    )
    with pytest.raises(OSError):
        modulo_planilha.gerar_planilha(pasta / "vendas.xlsx", dados)
    assert list(pasta.iterdir()) == []


# ============================================================ autosave (RNF01)
def test_rascunho_so_com_expediente_aberto(exp):
    assert exp.salvar_rascunho() is None


def test_rascunho_tem_as_vendas_ate_agora(exp, vendas, cardapio, pasta):
    exp.iniciar()
    vendas.registrar(pedido((cardapio["coxinha"], 2)), "pix")
    caminho = exp.salvar_rascunho()
    assert caminho == pasta / "rascunho_vendas_2026-11-27.xlsx"
    linhas = ler(caminho)
    assert "parcial" in linhas[0][0] and valor(linhas, "Total vendido") == 13
    vendas.registrar(pedido((cardapio["refri"], 1)), "pix")
    exp.salvar_rascunho()  # atualiza o mesmo arquivo
    assert valor(ler(caminho), "Total vendido") == 19
    assert sorted(p.name for p in pasta.iterdir()) == ["rascunho_vendas_2026-11-27.xlsx"]


def test_rascunho_some_ao_encerrar(exp, pasta):
    exp.iniciar()
    exp.salvar_rascunho()
    exp.encerrar()
    assert [p.name for p in pasta.iterdir()] == ["vendas_2026-11-27.xlsx"]


def test_rascunho_com_pasta_sumida_nao_quebra(exp, config, pasta):
    exp.iniciar()
    config.definir_pasta_planilhas(str(pasta / "sumiu"))
    assert exp.salvar_rascunho() is None


def test_intervalo_do_autosave_padrao_e_configuravel(config):
    assert config.autosave_segundos() == AUTOSAVE_PADRAO_SEGUNDOS == 60
    config.definir_autosave_segundos(30)
    assert config.autosave_segundos() == 30
    with pytest.raises(DadosInvalidosError, match="mínimo"):
        config.definir_autosave_segundos(AUTOSAVE_MINIMO_SEGUNDOS - 1)


def test_autosave_com_valor_estragado_usa_o_padrao(conn, config):
    ConfiguracaoRepo(conn).definir("autosave_segundos", "lixo")
    assert config.autosave_segundos() == 60
    ConfiguracaoRepo(conn).definir("autosave_segundos", "1")
    assert config.autosave_segundos() == AUTOSAVE_MINIMO_SEGUNDOS


# ======================================================== quantidades (RF15)
@pytest.mark.parametrize(
    "periodo, hoje, esperado",
    [
        ("hoje", date(2026, 12, 31), ("2026-12-31T00:00:00", "2027-01-01T00:00:00")),
        ("mes_atual", date(2026, 12, 15), ("2026-12-01T00:00:00", "2027-01-01T00:00:00")),
        ("mes_anterior", date(2026, 11, 27), ("2026-10-01T00:00:00", "2026-11-01T00:00:00")),
        ("mes_anterior", date(2026, 1, 10), ("2025-12-01T00:00:00", "2026-01-01T00:00:00")),
    ],
)
def test_intervalos_dos_periodos(periodo, hoje, esperado):
    assert intervalo_do_periodo(periodo, hoje) == esperado


def test_quantidades_do_dia_e_do_mes_anterior(exp, vendas, cardapio, relogio, conn):
    def venda_em(quando, produto, qtd, preco):
        with conn:
            vid = conn.execute(
                "INSERT INTO venda (data_hora, forma_pagamento, total_centavos) VALUES (?, 'pix', ?)",
                (quando, qtd * preco),
            ).lastrowid
            conn.execute(
                "INSERT INTO item_venda (venda_id, produto_id, quantidade, preco_unitario_centavos) "
                "VALUES (?, ?, ?, ?)", (vid, produto.id, qtd, preco),
            )

    venda_em("2026-10-03T10:00:00", cardapio["coxinha"], 4, 650)    # mês anterior
    venda_em("2026-10-31T23:59:59", cardapio["coxinha"], 1, 650)    # último segundo do mês anterior
    venda_em("2026-10-15T09:00:00", cardapio["refri"], 7, 600)
    venda_em("2026-09-30T23:59:59", cardapio["refri"], 100, 600)    # dois meses atrás: fora
    venda_em("2026-11-01T00:00:00", cardapio["refri"], 100, 600)    # mês atual: fora do anterior
    exp.iniciar()
    vendas.registrar(pedido((cardapio["coxinha"], 2), (cardapio["marmita"], 1)), "pix")

    hoje = {q.produto: q.quantidade for q in exp.quantidades("hoje")}
    assert hoje == {"Coxinha": 2, "Marmita": 1}
    anterior = [(q.produto, q.categoria, q.quantidade) for q in exp.quantidades("mes_anterior")]
    assert anterior == [("Refrigerante", "Bebida", 7), ("Coxinha", "Salgado", 5)]
    atual = {q.produto: q.quantidade for q in exp.quantidades("mes_atual")}
    assert atual == {"Coxinha": 2, "Marmita": 1, "Refrigerante": 100}


def test_quantidade_inclui_produto_removido(exp, vendas, cardapio):
    exp.iniciar()
    vendas.registrar(pedido((cardapio["coxinha"], 3)), "pix")
    cardapio["produtos"].remover(cardapio["coxinha"].id)
    assert [(q.produto, q.quantidade) for q in exp.quantidades("hoje")] == [("Coxinha", 3)]


def test_periodo_invalido(exp):
    with pytest.raises(ValueError):
        exp.quantidades("ontem")
