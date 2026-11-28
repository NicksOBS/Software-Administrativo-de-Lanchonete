"""Configurações que o proprietário define (por enquanto: valor mínimo do desconto, RN02)."""
from __future__ import annotations

from src.errors import DadosInvalidosError
from src.repos.configuracao_repo import ConfiguracaoRepo

CHAVE_DESCONTO_MINIMO = "desconto_valor_minimo_centavos"
CHAVE_PASTA_PLANILHAS = "pasta_planilhas"
CHAVE_AUTOSAVE = "autosave_segundos"
VALOR_MAXIMO_CENTAVOS = 9_999_999  # R$ 99.999,99
AUTOSAVE_PADRAO_SEGUNDOS = 60      # RNF01
AUTOSAVE_MINIMO_SEGUNDOS = 10


class ConfiguracaoService:
    def __init__(self, repo: ConfiguracaoRepo) -> None:
        self._repo = repo

    def valor_minimo_desconto(self) -> int | None:
        """Vendas ACIMA deste valor (em centavos) têm desconto. None = não há desconto."""
        texto = self._repo.obter(CHAVE_DESCONTO_MINIMO)
        try:
            return int(texto) if texto else None
        except ValueError:
            return None

    def definir_valor_minimo_desconto(self, centavos: int | None) -> None:
        if centavos is not None:
            if centavos <= 0:
                raise DadosInvalidosError(
                    "O valor deve ser maior que zero (deixe em branco para não dar desconto)."
                )
            if centavos > VALOR_MAXIMO_CENTAVOS:
                raise DadosInvalidosError("O valor máximo permitido é R$ 99.999,99.")
        self._repo.definir(CHAVE_DESCONTO_MINIMO, None if centavos is None else str(centavos))

    # ------------------------------------------------------- planilhas (RF14)
    def pasta_planilhas(self) -> str | None:
        """Pasta escolhida pelo proprietário; None = usar a pasta padrão do sistema."""
        return self._repo.obter(CHAVE_PASTA_PLANILHAS) or None

    def definir_pasta_planilhas(self, pasta: str | None) -> None:
        self._repo.definir(CHAVE_PASTA_PLANILHAS, pasta or None)

    # --------------------------------------------------------- autosave (RNF01)
    def autosave_segundos(self) -> int:
        texto = self._repo.obter(CHAVE_AUTOSAVE)
        try:
            valor = int(texto) if texto else AUTOSAVE_PADRAO_SEGUNDOS
        except ValueError:
            valor = AUTOSAVE_PADRAO_SEGUNDOS
        return max(valor, AUTOSAVE_MINIMO_SEGUNDOS)

    def definir_autosave_segundos(self, segundos: int) -> None:
        if segundos < AUTOSAVE_MINIMO_SEGUNDOS:
            raise DadosInvalidosError(
                f"O intervalo mínimo do salvamento automático é {AUTOSAVE_MINIMO_SEGUNDOS} segundos."
            )
        self._repo.definir(CHAVE_AUTOSAVE, str(segundos))
