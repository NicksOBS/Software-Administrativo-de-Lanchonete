import sqlite3

import pytest

from src import database

TABELAS = {
    "usuario", "categoria", "produto", "cliente",
    "venda", "item_venda", "pagamento_divida", "configuracao",
}


@pytest.fixture
def conn():
    c = database.conectar(":memory:")
    yield c
    c.close()


def test_cria_todas_as_tabelas(conn):
    linhas = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    nomes = {linha["name"] for linha in linhas}
    assert TABELAS <= nomes


def test_inicializar_pode_rodar_varias_vezes(conn):
    database.inicializar(conn)
    database.inicializar(conn)


def test_chaves_estrangeiras_estao_ativas(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO produto (nome, categoria_id, preco_centavos) VALUES ('X', 999, 100)"
        )


def test_codigo_de_cliente_e_unico(conn):
    """RF07: cadastro com código já existente é recusado."""
    conn.execute("INSERT INTO cliente (codigo, nome) VALUES (1, 'Ana')")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO cliente (codigo, nome) VALUES (1, 'Bia')")


def test_venda_fiado_exige_cliente(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO venda (data_hora, forma_pagamento, total_centavos) "
            "VALUES ('2026-11-25T10:00:00', 'fiado', 500)"
        )


def test_venda_a_vista_nao_exige_cliente(conn):
    conn.execute(
        "INSERT INTO venda (data_hora, forma_pagamento, total_centavos) "
        "VALUES ('2026-11-25T10:00:00', 'pix', 500)"
    )


def test_forma_de_pagamento_invalida_e_recusada(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO venda (data_hora, forma_pagamento, total_centavos) "
            "VALUES ('2026-11-25T10:00:00', 'cheque', 500)"
        )


def test_divida_nao_pode_ser_negativa(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO cliente (codigo, nome, divida_centavos) VALUES (2, 'Caio', -1)")


def test_transacao_desfaz_tudo_em_caso_de_erro(conn):
    """RNF07: ou grava tudo ou não grava nada."""
    with pytest.raises(sqlite3.IntegrityError):
        with conn:
            conn.execute("INSERT INTO cliente (codigo, nome) VALUES (10, 'Dani')")
            conn.execute("INSERT INTO cliente (codigo, nome) VALUES (10, 'Repetido')")
    total = conn.execute("SELECT COUNT(*) FROM cliente").fetchone()[0]
    assert total == 0


def test_banco_em_arquivo_cria_a_pasta(tmp_path):
    caminho = tmp_path / "subpasta" / "teste.db"
    c = database.conectar(caminho)
    c.close()
    assert caminho.exists()
