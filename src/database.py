"""Banco de dados SQLite: criação das tabelas e conexão.

O modelo segue a seção 9.2 do Documento de Software. Decisões de implementação:

* Valores em dinheiro são guardados em CENTAVOS (inteiros). Isso evita erros
  de arredondamento do tipo 0.1 + 0.2 != 0.3 ao somar vendas e dívidas.
* Produtos e clientes "removidos" ficam com ativo = 0 (remoção lógica), para
  que vendas antigas continuem apontando para um registro que existe.
* O código do cliente (RF07) é informado pelo proprietário e é a chave
  primária da tabela, então o SQLite já recusa códigos repetidos.
* A tabela `configuracao` guarda valores definidos pelo proprietário
  (limite de dívida padrão, valor mínimo para desconto, pasta das planilhas).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from src.config import ARQUIVO_BANCO

VERSAO_SCHEMA = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS usuario (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    login       TEXT NOT NULL UNIQUE COLLATE NOCASE,
    senha_hash  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS categoria (
    id    INTEGER PRIMARY KEY AUTOINCREMENT,
    nome  TEXT NOT NULL UNIQUE COLLATE NOCASE
);

CREATE TABLE IF NOT EXISTS produto (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    nome            TEXT NOT NULL,
    categoria_id    INTEGER REFERENCES categoria(id),
    preco_centavos  INTEGER NOT NULL CHECK (preco_centavos >= 0),
    ativo           INTEGER NOT NULL DEFAULT 1 CHECK (ativo IN (0, 1))
);

CREATE TABLE IF NOT EXISTS cliente (
    codigo            INTEGER PRIMARY KEY,
    nome              TEXT NOT NULL,
    divida_centavos   INTEGER NOT NULL DEFAULT 0 CHECK (divida_centavos >= 0),
    credito_centavos  INTEGER NOT NULL DEFAULT 0 CHECK (credito_centavos >= 0),
    limite_centavos   INTEGER CHECK (limite_centavos IS NULL OR limite_centavos >= 0),
    ativo             INTEGER NOT NULL DEFAULT 1 CHECK (ativo IN (0, 1))
);

CREATE TABLE IF NOT EXISTS venda (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    data_hora          TEXT NOT NULL,
    cliente_codigo     INTEGER REFERENCES cliente(codigo),
    forma_pagamento    TEXT NOT NULL
        CHECK (forma_pagamento IN ('credito', 'debito', 'dinheiro', 'pix', 'fiado')),
    desconto_centavos  INTEGER NOT NULL DEFAULT 0 CHECK (desconto_centavos >= 0),
    total_centavos     INTEGER NOT NULL CHECK (total_centavos >= 0),
    CHECK (forma_pagamento <> 'fiado' OR cliente_codigo IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS item_venda (
    venda_id                 INTEGER NOT NULL REFERENCES venda(id) ON DELETE CASCADE,
    produto_id               INTEGER NOT NULL REFERENCES produto(id),
    quantidade               INTEGER NOT NULL CHECK (quantidade > 0),
    preco_unitario_centavos  INTEGER NOT NULL CHECK (preco_unitario_centavos >= 0),
    PRIMARY KEY (venda_id, produto_id)
);

CREATE TABLE IF NOT EXISTS pagamento_divida (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    cliente_codigo  INTEGER NOT NULL REFERENCES cliente(codigo),
    data_hora       TEXT NOT NULL,
    valor_centavos  INTEGER NOT NULL CHECK (valor_centavos > 0)
);

CREATE TABLE IF NOT EXISTS configuracao (
    chave  TEXT PRIMARY KEY,
    valor  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_venda_data ON venda (data_hora);
CREATE INDEX IF NOT EXISTS idx_produto_nome ON produto (nome);
CREATE INDEX IF NOT EXISTS idx_cliente_nome ON cliente (nome);
"""


def inicializar(conn: sqlite3.Connection) -> None:
    """Cria as tabelas que ainda não existem. Pode ser chamada várias vezes."""
    conn.executescript(SCHEMA)
    conn.execute(f"PRAGMA user_version = {VERSAO_SCHEMA}")
    conn.commit()


def conectar(caminho: str | Path | None = None) -> sqlite3.Connection:
    """Abre (e prepara) o banco de dados.

    Sem argumentos usa o arquivo padrão em data/lanchonete.db. Use ":memory:"
    para um banco temporário, útil nos testes.

    Para gravar várias alterações de uma vez (RNF07), use a conexão como
    gerenciador de contexto: ``with conn: ...`` confirma tudo se der certo e
    desfaz tudo se acontecer algum erro no meio.
    """
    if caminho is None:
        caminho = ARQUIVO_BANCO
    if str(caminho) != ":memory:":
        Path(caminho).parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(caminho))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    inicializar(conn)
    return conn
