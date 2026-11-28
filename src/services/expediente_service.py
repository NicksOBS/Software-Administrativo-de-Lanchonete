"""Expediente (RF12 a RF15) e salvamento automático (RNF01).

Iniciar abre o expediente; encerrar gera a planilha das vendas feitas entre o início
e o fim e só então marca o expediente como encerrado: se a planilha não puder ser
salva (pasta inexistente, arquivo aberto no Excel), o expediente continua aberto.

Cada venda já é confirmada no banco na hora em que é registrada. O salvamento
automático acrescenta um rascunho da planilha na pasta escolhida, atualizado a
cada intervalo (60 s por padrão), e o expediente aberto sobrevive a uma queda de
energia: ao reabrir o programa ele continua de onde parou.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Callable

from src.errors import DadosInvalidosError, OperacaoNaoPermitidaError
from src.export.planilha import DadosPlanilha, gerar_planilha
from src.repos.expediente_repo import Expediente, ExpedienteRepo
from src.repos.relatorio_repo import QuantidadeProduto, RelatorioRepo, TotaisVendas
from src.services.configuracao_service import ConfiguracaoService

PERIODOS = ("hoje", "mes_atual", "mes_anterior")
FIM_ABERTO = "9999-12-31T23:59:59"


@dataclass(frozen=True)
class ResultadoEncerramento:
    expediente: Expediente
    caminho: Path
    totais: TotaisVendas


def intervalo_do_periodo(periodo: str, hoje: date) -> tuple[str, str]:
    """(início, fim exclusivo) em texto ISO para 'hoje', 'mes_atual' ou 'mes_anterior'."""
    if periodo == "hoje":
        ini, fim = hoje, date.fromordinal(hoje.toordinal() + 1)
    elif periodo == "mes_atual":
        ini = hoje.replace(day=1)
        fim = date(hoje.year + (hoje.month == 12), hoje.month % 12 + 1, 1)
    elif periodo == "mes_anterior":
        fim = hoje.replace(day=1)
        ini = date(fim.year - (fim.month == 1), (fim.month - 2) % 12 + 1, 1)
    else:
        raise ValueError(f"Período desconhecido: {periodo}")
    return f"{ini.isoformat()}T00:00:00", f"{fim.isoformat()}T00:00:00"


class ExpedienteService:
    def __init__(
        self,
        expedientes: ExpedienteRepo,
        relatorio: RelatorioRepo,
        configuracao: ConfiguracaoService,
        pasta_padrao: Path,
        agora: Callable[[], datetime] = datetime.now,
    ) -> None:
        self._expedientes = expedientes
        self._relatorio = relatorio
        self._configuracao = configuracao
        self._pasta_padrao = Path(pasta_padrao)
        self._agora = agora

    # ----------------------------------------------------------------- estado
    def aberto(self) -> Expediente | None:
        return self._expedientes.aberto()

    def exigir_aberto(self) -> Expediente:
        expediente = self.aberto()
        if expediente is None:
            raise OperacaoNaoPermitidaError(
                "O expediente não está aberto. Inicie o expediente para registrar vendas."
            )
        return expediente

    def totais_atuais(self) -> TotaisVendas | None:
        expediente = self.aberto()
        if expediente is None:
            return None
        return self._relatorio.totais(expediente.inicio, FIM_ABERTO)

    # ------------------------------------------------------------- iniciar / fim
    def iniciar(self) -> Expediente:
        atual = self.aberto()
        if atual is not None:
            raise OperacaoNaoPermitidaError(
                f"O expediente já está aberto desde {_formatar(atual.inicio)}."
            )
        inicio = self._agora().isoformat(timespec="seconds")
        return self._expedientes.buscar(self._expedientes.iniciar(inicio))

    def encerrar(self) -> ResultadoEncerramento:
        expediente = self.aberto()
        if expediente is None:
            raise OperacaoNaoPermitidaError("Não há expediente aberto para encerrar.")
        pasta = self._pasta_para_gravar()
        fim = self._agora().isoformat(timespec="seconds")
        caminho = self._caminho_livre(pasta, expediente.inicio)

        try:
            gerar_planilha(caminho, self._dados(expediente, fim))
        except OSError as erro:
            raise OperacaoNaoPermitidaError(
                f"Não foi possível salvar a planilha em {pasta}. Confira se a pasta aceita "
                f"gravação. O expediente continua aberto. ({erro.strerror or erro})"
            ) from erro

        self._expedientes.encerrar(expediente.id, fim, str(caminho))
        self._apagar_rascunho(pasta, expediente.inicio)
        encerrado = self._expedientes.buscar(expediente.id)
        return ResultadoEncerramento(encerrado, caminho, self._relatorio.totais(expediente.inicio, fim))

    # ----------------------------------------------------------------- pasta (RF14)
    def pasta_planilhas(self) -> Path:
        escolhida = self._configuracao.pasta_planilhas()
        return Path(escolhida) if escolhida else self._pasta_padrao

    def definir_pasta_planilhas(self, pasta: str | Path) -> None:
        caminho = Path(str(pasta).strip())
        if not str(pasta).strip() or not caminho.is_dir():
            raise DadosInvalidosError("Essa pasta não existe. Escolha uma pasta existente.")
        self._configuracao.definir_pasta_planilhas(str(caminho))

    def _pasta_para_gravar(self) -> Path:
        pasta = self.pasta_planilhas()
        if pasta.is_dir():
            return pasta
        if self._configuracao.pasta_planilhas() is None:  # pasta padrão: o sistema cria
            try:
                pasta.mkdir(parents=True, exist_ok=True)
                return pasta
            except OSError as erro:
                raise OperacaoNaoPermitidaError(
                    f"Não foi possível criar a pasta {pasta}. Escolha outra pasta das planilhas."
                ) from erro
        raise OperacaoNaoPermitidaError(
            f"A pasta das planilhas não existe: {pasta}\n"
            "Escolha outra pasta. O expediente continua aberto."
        )

    @staticmethod
    def _nome_base(inicio: str) -> str:
        return f"vendas_{inicio[:10]}"

    def _caminho_livre(self, pasta: Path, inicio: str) -> Path:
        base = self._nome_base(inicio)
        caminho, n = pasta / f"{base}.xlsx", 2
        while caminho.exists():  # outro expediente no mesmo dia: não sobrescreve
            caminho = pasta / f"{base}_{n}.xlsx"
            n += 1
        return caminho

    # ---------------------------------------------------------- autosave (RNF01)
    def salvar_rascunho(self) -> Path | None:
        """Grava a planilha parcial do expediente aberto. None se não há o que salvar."""
        expediente = self.aberto()
        if expediente is None:
            return None
        pasta = self.pasta_planilhas()
        if not pasta.is_dir():
            if self._configuracao.pasta_planilhas() is not None:
                return None  # pasta escolhida sumiu: o encerramento é que avisa
            pasta.mkdir(parents=True, exist_ok=True)
        caminho = pasta / f"rascunho_{self._nome_base(expediente.inicio)}.xlsx"
        gerar_planilha(caminho, self._dados(expediente, None))
        return caminho

    def _apagar_rascunho(self, pasta: Path, inicio: str) -> None:
        try:
            (pasta / f"rascunho_{self._nome_base(inicio)}.xlsx").unlink()
        except OSError:
            pass

    def _dados(self, expediente: Expediente, fim: str | None) -> DadosPlanilha:
        limite = fim or FIM_ABERTO
        return DadosPlanilha(
            data=date.fromisoformat(expediente.inicio[:10]),
            inicio=expediente.inicio,
            fim=fim,
            linhas=self._relatorio.linhas_produtos(expediente.inicio, limite),
            totais=self._relatorio.totais(expediente.inicio, limite),
        )

    # ------------------------------------------------------------ quantidades (RF15)
    def quantidades(self, periodo: str, hoje: date | None = None) -> list[QuantidadeProduto]:
        hoje = hoje or self._agora().date()
        inicio, fim = intervalo_do_periodo(periodo, hoje)
        return self._relatorio.quantidades(inicio, fim)


def _formatar(iso: str) -> str:
    return datetime.fromisoformat(iso).strftime("%d/%m/%Y %H:%M")
