from datetime import datetime

import pytest

from src import database
from src.errors import (
    DadosInvalidosError,
    NaoEncontradoError,
    OperacaoNaoPermitidaError,
    RegistroDuplicadoError,
)
from src.repos.cliente_repo import ClienteRepo
from src.services.cliente_service import (
    CODIGO_MAXIMO,
    NOME_MAX,
    VALOR_MAXIMO_CENTAVOS,
    ClienteService,
)


@pytest.fixture
def conn():
    c = database.conectar(":memory:")
    yield c
    c.close()


class Relogio:
    def __init__(self):
        self.agora = datetime(2026, 11, 26, 10, 30, 0)

    def __call__(self):
        return self.agora


@pytest.fixture
def relogio():
    return Relogio()


@pytest.fixture
def clientes(conn, relogio):
    return ClienteService(ClienteRepo(conn), agora=relogio)


def definir_divida(conn, codigo, centavos):
    with conn:
        conn.execute("UPDATE cliente SET divida_centavos = ? WHERE codigo = ?", (centavos, codigo))


def nomes(lista):
    return [c.nome for c in lista]


# ----------------------------------------------------------------- cadastro
def test_cadastrar_cliente(clientes):
    c = clientes.cadastrar(7, "Maria Silva", 10000)
    assert (c.codigo, c.nome, c.divida_centavos, c.credito_centavos, c.limite_centavos) == (
        7, "Maria Silva", 0, 0, 10000)


def test_cadastrar_sem_limite(clientes):
    assert clientes.cadastrar(1, "Ana").limite_centavos is None


def test_nome_e_limpo(clientes):
    assert clientes.cadastrar(1, "  Maria   da  Silva ").nome == "Maria da Silva"


def test_nome_vazio_e_recusado(clientes):
    with pytest.raises(DadosInvalidosError):
        clientes.cadastrar(1, "   ")


def test_nome_muito_longo_e_recusado(clientes):
    with pytest.raises(DadosInvalidosError):
        clientes.cadastrar(1, "x" * (NOME_MAX + 1))


@pytest.mark.parametrize("codigo", [0, -1, CODIGO_MAXIMO + 1])
def test_codigo_fora_da_faixa_e_recusado(clientes, codigo):
    with pytest.raises(DadosInvalidosError, match="código"):
        clientes.cadastrar(codigo, "Ana")


def test_codigo_repetido_e_recusado(clientes):
    """RF07: cadastro com código já existente é recusado."""
    clientes.cadastrar(1, "Ana")
    with pytest.raises(RegistroDuplicadoError, match="código 1"):
        clientes.cadastrar(1, "Bia")
    assert nomes(clientes.listar()) == ["Ana"]


def test_codigo_de_cliente_removido_nao_pode_ser_reutilizado(clientes):
    clientes.cadastrar(1, "Ana")
    clientes.remover(1)
    with pytest.raises(RegistroDuplicadoError, match="removido"):
        clientes.cadastrar(1, "Bia")


def test_nomes_iguais_com_codigos_diferentes_sao_permitidos(clientes):
    clientes.cadastrar(1, "João Silva")
    clientes.cadastrar(2, "João Silva")
    assert len(clientes.listar()) == 2


@pytest.mark.parametrize("limite", [0, -100])
def test_limite_precisa_ser_positivo(clientes, limite):
    with pytest.raises(DadosInvalidosError, match="limite"):
        clientes.cadastrar(1, "Ana", limite)


def test_limite_maximo(clientes):
    with pytest.raises(DadosInvalidosError, match="máximo"):
        clientes.cadastrar(1, "Ana", VALOR_MAXIMO_CENTAVOS + 1)


def test_sugerir_codigo(clientes):
    assert clientes.sugerir_codigo() == 1
    clientes.cadastrar(1, "Ana")
    clientes.cadastrar(5, "Bia")
    assert clientes.sugerir_codigo() == 6
    clientes.remover(5)
    assert clientes.sugerir_codigo() == 6, "código de removido não volta a ser sugerido"


# ------------------------------------------------------------------ edição
def test_atualizar_nome_e_limite(clientes):
    clientes.cadastrar(1, "Ana", 5000)
    c = clientes.atualizar(1, "Ana Paula", 8000)
    assert (c.nome, c.limite_centavos) == ("Ana Paula", 8000)


def test_atualizar_removendo_o_limite(clientes):
    clientes.cadastrar(1, "Ana", 5000)
    assert clientes.atualizar(1, "Ana", None).limite_centavos is None


def test_atualizar_nao_mexe_nos_saldos(clientes, conn):
    clientes.cadastrar(1, "Ana")
    definir_divida(conn, 1, 2500)
    clientes.adicionar_credito(1, 1000)
    c = clientes.atualizar(1, "Ana Paula", None)
    assert (c.divida_centavos, c.credito_centavos) == (2500, 1000)


def test_atualizar_cliente_inexistente(clientes):
    with pytest.raises(NaoEncontradoError):
        clientes.atualizar(99, "X")


# ----------------------------------------------------------------- pesquisa
@pytest.fixture
def carteira(clientes, conn):
    clientes.cadastrar(1, "Maria Silva")
    clientes.cadastrar(2, "José Almeida")
    clientes.cadastrar(3, "João Silva")
    clientes.cadastrar(12, "Ana Paula")
    clientes.cadastrar(30, "Cliente 2")
    definir_divida(conn, 1, 1500)
    definir_divida(conn, 3, 700)
    return clientes


def test_listar_em_ordem_alfabetica(carteira):
    assert nomes(carteira.listar()) == [
        "Ana Paula", "Cliente 2", "João Silva", "José Almeida", "Maria Silva"]


def test_busca_por_codigo_devolve_exatamente_um(carteira):
    """RF08: a busca por código retorna exatamente um cliente."""
    assert nomes(carteira.listar("12")) == ["Ana Paula"]
    assert nomes(carteira.listar(" 1 ")) == ["Maria Silva"]


def test_busca_por_codigo_inexistente_procura_o_numero_no_nome(carteira):
    """Não existe o código 2? Não: existe. Então só o José aparece, e não o 'Cliente 2'."""
    assert nomes(carteira.listar("2")) == ["José Almeida"]
    # código 99 não existe: cai para a busca no nome (nenhum nome tem 99)
    assert carteira.listar("99") == []


def test_busca_numerica_sem_codigo_correspondente_cai_para_o_nome(clientes):
    clientes.cadastrar(1, "Cliente 7")
    assert nomes(clientes.listar("7")) == ["Cliente 7"]


def test_busca_por_nome_traz_todos_que_contem(carteira):
    """RF08: por nome, todos os que contêm o texto."""
    assert nomes(carteira.listar("silva")) == ["João Silva", "Maria Silva"]


def test_busca_ignora_acentos_e_maiusculas(carteira):
    assert nomes(carteira.listar("JOAO")) == ["João Silva"]
    assert nomes(carteira.listar("jose")) == ["José Almeida"]
    assert nomes(carteira.listar("josé")) == ["José Almeida"]


def test_busca_sem_resultado(carteira):
    assert carteira.listar("xyz") == []


def test_busca_vazia_lista_todos(carteira):
    assert len(carteira.listar("   ")) == 5


@pytest.mark.parametrize("termo", ["%", "_"])
def test_caracteres_especiais_valem_como_texto(carteira, termo):
    assert carteira.listar(termo) == []


def test_somente_devedores(carteira):
    """RF09: a lista mostra a dívida atual de cada cliente."""
    devedores = carteira.listar(somente_devedores=True)
    assert [(c.nome, c.divida_centavos) for c in devedores] == [
        ("João Silva", 700), ("Maria Silva", 1500)]


def test_somente_devedores_combinado_com_busca(carteira):
    assert nomes(carteira.listar("maria", somente_devedores=True)) == ["Maria Silva"]
    assert carteira.listar("ana", somente_devedores=True) == []
    assert carteira.listar("12", somente_devedores=True) == []


def test_removidos_nao_aparecem(carteira):
    carteira.remover(12)
    assert "Ana Paula" not in nomes(carteira.listar())
    assert carteira.listar("12") == []


# -------------------------------------------------------- pagamento (RF11)
def test_pagamento_parcial(clientes, conn):
    """RF11: dívida de R$ 50,00 com pagamento de R$ 20,00 resulta em R$ 30,00."""
    clientes.cadastrar(1, "Ana")
    definir_divida(conn, 1, 5000)
    assert clientes.registrar_pagamento(1, 2000).divida_centavos == 3000


def test_pagamento_total(clientes, conn):
    clientes.cadastrar(1, "Ana")
    definir_divida(conn, 1, 5000)
    assert clientes.registrar_pagamento(1, 5000).divida_centavos == 0


def test_varios_pagamentos_seguidos(clientes, conn):
    clientes.cadastrar(1, "Ana")
    definir_divida(conn, 1, 5000)
    clientes.registrar_pagamento(1, 1000)
    assert clientes.registrar_pagamento(1, 1500).divida_centavos == 2500


def test_pagamento_maior_que_a_divida_e_recusado(clientes, conn):
    clientes.cadastrar(1, "Ana")
    definir_divida(conn, 1, 5000)
    with pytest.raises(OperacaoNaoPermitidaError, match="R\\$ 50,00"):
        clientes.registrar_pagamento(1, 5001)
    assert clientes.obter(1).divida_centavos == 5000


def test_pagamento_de_quem_nao_deve_e_recusado(clientes):
    clientes.cadastrar(1, "Ana")
    with pytest.raises(OperacaoNaoPermitidaError, match="não tem dívida"):
        clientes.registrar_pagamento(1, 100)


@pytest.mark.parametrize("valor", [0, -100])
def test_pagamento_precisa_ser_positivo(clientes, conn, valor):
    clientes.cadastrar(1, "Ana")
    definir_divida(conn, 1, 5000)
    with pytest.raises(DadosInvalidosError, match="maior que zero"):
        clientes.registrar_pagamento(1, valor)


def test_pagamento_fica_no_historico_com_data(clientes, conn, relogio):
    clientes.cadastrar(1, "Ana")
    definir_divida(conn, 1, 5000)
    clientes.registrar_pagamento(1, 2000)
    relogio.agora = datetime(2026, 11, 27, 9, 0, 0)
    clientes.registrar_pagamento(1, 500)
    linhas = conn.execute(
        "SELECT cliente_codigo, data_hora, valor_centavos FROM pagamento_divida ORDER BY id"
    ).fetchall()
    assert [tuple(l) for l in linhas] == [
        (1, "2026-11-26T10:30:00", 2000),
        (1, "2026-11-27T09:00:00", 500),
    ]


def test_pagamento_e_tudo_ou_nada(clientes, conn, monkeypatch):
    """RNF07: se gravar o histórico falhar, a dívida não pode ter sido abatida."""
    clientes.cadastrar(1, "Ana")
    definir_divida(conn, 1, 5000)

    def falhar(*args, **kwargs):
        raise RuntimeError("falha simulada")

    monkeypatch.setattr(ClienteRepo, "registrar_pagamento", falhar)
    with pytest.raises(RuntimeError):
        clientes.registrar_pagamento(1, 2000)
    assert clientes.obter(1).divida_centavos == 5000
    assert conn.execute("SELECT COUNT(*) FROM pagamento_divida").fetchone()[0] == 0


# ---------------------------------------------------------- crédito (RN03)
def test_adicionar_credito(clientes):
    clientes.cadastrar(1, "Ana")
    assert clientes.adicionar_credito(1, 2000).credito_centavos == 2000
    assert clientes.adicionar_credito(1, 500).credito_centavos == 2500


def test_credito_nao_mexe_na_divida(clientes, conn):
    clientes.cadastrar(1, "Ana")
    definir_divida(conn, 1, 3000)
    c = clientes.adicionar_credito(1, 1000)
    assert (c.divida_centavos, c.credito_centavos) == (3000, 1000)


@pytest.mark.parametrize("valor", [0, -1])
def test_credito_precisa_ser_positivo(clientes, valor):
    clientes.cadastrar(1, "Ana")
    with pytest.raises(DadosInvalidosError):
        clientes.adicionar_credito(1, valor)


def test_credito_valor_maximo(clientes):
    clientes.cadastrar(1, "Ana")
    with pytest.raises(DadosInvalidosError, match="máximo"):
        clientes.adicionar_credito(1, VALOR_MAXIMO_CENTAVOS + 1)


def test_credito_cliente_inexistente(clientes):
    with pytest.raises(NaoEncontradoError):
        clientes.adicionar_credito(99, 1000)


# --------------------------------------------------------- limite (RN01)
def test_cliente_acima_do_limite_fica_bloqueado(clientes, conn):
    """RN01: limite de R$ 100,00 e dívida de R$ 101,00 => bloqueado."""
    clientes.cadastrar(1, "Ana", 10000)
    definir_divida(conn, 1, 10100)
    assert clientes.obter(1).bloqueado


def test_pagando_ate_o_limite_o_cliente_e_liberado(clientes, conn):
    """RN01: após pagamento que reduza a dívida ao limite ou abaixo, volta a ser aceito."""
    clientes.cadastrar(1, "Ana", 10000)
    definir_divida(conn, 1, 10100)
    assert clientes.registrar_pagamento(1, 100).bloqueado is False  # exatamente no limite


def test_cliente_no_limite_ou_abaixo_nao_e_bloqueado(clientes, conn):
    clientes.cadastrar(1, "Ana", 10000)
    definir_divida(conn, 1, 10000)
    assert not clientes.obter(1).bloqueado
    definir_divida(conn, 1, 0)
    assert not clientes.obter(1).bloqueado


def test_cliente_sem_limite_nunca_e_bloqueado(clientes, conn):
    clientes.cadastrar(1, "Ana")
    definir_divida(conn, 1, 9_000_000)
    assert not clientes.obter(1).bloqueado


# -------------------------------------------------------------------- remoção
def test_remover_cliente_sem_saldo(clientes):
    clientes.cadastrar(1, "Ana")
    clientes.remover(1)
    assert clientes.listar() == []
    with pytest.raises(NaoEncontradoError):
        clientes.obter(1)


def test_remover_cliente_com_divida_e_recusado(clientes, conn):
    clientes.cadastrar(1, "Ana")
    definir_divida(conn, 1, 2500)
    with pytest.raises(OperacaoNaoPermitidaError, match="R\\$ 25,00"):
        clientes.remover(1)
    assert len(clientes.listar()) == 1


def test_remover_cliente_com_credito_e_recusado(clientes):
    clientes.cadastrar(1, "Ana")
    clientes.adicionar_credito(1, 1000)
    with pytest.raises(OperacaoNaoPermitidaError, match="crédito"):
        clientes.remover(1)


def test_remover_cliente_depois_de_quitar(clientes, conn):
    clientes.cadastrar(1, "Ana")
    definir_divida(conn, 1, 2500)
    clientes.registrar_pagamento(1, 2500)
    clientes.remover(1)
    assert clientes.listar() == []


def test_remover_mantem_historico_de_pagamentos(clientes, conn):
    clientes.cadastrar(1, "Ana")
    definir_divida(conn, 1, 2500)
    clientes.registrar_pagamento(1, 2500)
    clientes.remover(1)
    assert conn.execute("SELECT COUNT(*) FROM pagamento_divida").fetchone()[0] == 1


def test_remover_cliente_inexistente(clientes):
    with pytest.raises(NaoEncontradoError):
        clientes.remover(99)
