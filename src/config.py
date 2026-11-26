"""Configurações gerais do sistema."""
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PASTA_DADOS = RAIZ / "data"
ARQUIVO_BANCO = PASTA_DADOS / "lanchonete.db"

NOME_APP = "Lanchonete - Registro de Vendas"
