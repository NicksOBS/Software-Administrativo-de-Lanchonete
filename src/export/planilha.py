"""Gera a planilha .xlsx das vendas do dia (RF13).

Conteúdo: uma linha por produto (categoria, quantidade, valor unitário e subtotal),
o total vendido e os subtotais por forma de pagamento. Os subtotais por forma somam
exatamente o total vendido: o que foi pago com saldo de crédito do cliente aparece
em linha própria.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.properties import PageSetupProperties

from src.repos.relatorio_repo import LinhaProduto, TotaisVendas

FORMATO_REAIS = '"R$" #,##0.00'
FORMAS_NA_ORDEM = [
    ("pix", "PIX"), ("credito", "Crédito"), ("debito", "Débito"),
    ("dinheiro", "Dinheiro"), ("fiado", "Fiado"),
]


@dataclass(frozen=True)
class DadosPlanilha:
    data: date
    inicio: str
    fim: str | None              # None = expediente ainda aberto (rascunho)
    linhas: list[LinhaProduto]
    totais: TotaisVendas

    @property
    def parcial(self) -> bool:
        return self.fim is None


def _reais(centavos: int) -> Decimal:
    return Decimal(centavos) / 100


def _hora(iso: str) -> str:
    return iso[11:16]


def montar(dados: DadosPlanilha) -> Workbook:
    wb = Workbook()
    ws = wb.active
    ws.title = "Vendas do dia"
    negrito = Font(bold=True)
    cabecalho_fundo = PatternFill("solid", fgColor="1F3A5F")
    cabecalho_fonte = Font(bold=True, color="FFFFFF")

    titulo = f"Vendas do dia {dados.data.strftime('%d/%m/%Y')}"
    if dados.parcial:
        titulo += " (parcial: expediente ainda aberto)"
    ws["A1"] = titulo
    ws["A1"].font = Font(bold=True, size=14)
    periodo = f"Expediente: {_hora(dados.inicio)}"
    periodo += f" às {_hora(dados.fim)}" if dados.fim else " (em andamento)"
    ws["A2"] = f"{periodo}  ·  {dados.totais.quantidade_vendas} venda(s)"

    cabecalhos = ["Produto", "Categoria", "Quantidade", "Valor unitário", "Subtotal"]
    for coluna, texto in enumerate(cabecalhos, start=1):
        c = ws.cell(row=4, column=coluna, value=texto)
        c.font, c.fill = cabecalho_fonte, cabecalho_fundo
        c.alignment = Alignment(horizontal="left" if coluna <= 2 else "right")

    linha = 5
    soma_itens = 0
    for item in dados.linhas:
        ws.cell(row=linha, column=1, value=item.produto)
        ws.cell(row=linha, column=2, value=item.categoria)
        ws.cell(row=linha, column=3, value=item.quantidade)
        ws.cell(row=linha, column=4, value=_reais(item.preco_unitario_centavos)).number_format = FORMATO_REAIS
        ws.cell(row=linha, column=5, value=_reais(item.subtotal_centavos)).number_format = FORMATO_REAIS
        soma_itens += item.subtotal_centavos
        linha += 1

    def linha_total(rotulo: str, centavos: int, destaque: bool = False) -> None:
        nonlocal linha
        r = ws.cell(row=linha, column=1, value=rotulo)
        v = ws.cell(row=linha, column=5, value=_reais(centavos))
        v.number_format = FORMATO_REAIS
        if destaque:
            r.font = v.font = negrito
        linha += 1

    linha += 1
    linha_total("Soma dos itens", soma_itens)
    linha_total("Descontos", -dados.totais.descontos_centavos)
    linha_total("Total vendido", dados.totais.total_centavos, destaque=True)

    linha += 1
    ws.cell(row=linha, column=1, value="Por forma de pagamento").font = negrito
    linha += 1
    soma_formas = 0
    for chave, nome in FORMAS_NA_ORDEM:
        valor = dados.totais.por_forma_centavos.get(chave, 0)
        linha_total(nome, valor)
        soma_formas += valor
    linha_total("Saldo de crédito do cliente", dados.totais.credito_usado_centavos)
    soma_formas += dados.totais.credito_usado_centavos
    linha_total("Total", soma_formas, destaque=True)

    for coluna, largura in enumerate([34, 20, 12, 16, 16], start=1):
        ws.column_dimensions[get_column_letter(coluna)].width = largura
    ws.freeze_panes = "A5"
    ws.sheet_properties.pageSetUpPr = PageSetupProperties(fitToPage=True)  # cabe em 1 página de largura
    ws.page_setup.fitToWidth, ws.page_setup.fitToHeight = 1, 0
    return wb


def gerar_planilha(caminho: Path, dados: DadosPlanilha) -> None:
    """Grava o arquivo por inteiro ou não grava (escreve num temporário e renomeia)."""
    caminho = Path(caminho)
    temporario = caminho.with_name(caminho.stem + ".tmp.xlsx")
    try:
        montar(dados).save(temporario)
        os.replace(temporario, caminho)
    finally:
        try:
            temporario.unlink()
        except FileNotFoundError:
            pass
