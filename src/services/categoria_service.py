"""Regras de negócio das categorias de produtos (RF04)."""
from __future__ import annotations

from src.errors import (
    DadosInvalidosError,
    NaoEncontradoError,
    OperacaoNaoPermitidaError,
    RegistroDuplicadoError,
)
from src.repos.categoria_repo import Categoria, CategoriaRepo
from src.textos import limpar_espacos

NOME_MAX = 40


class CategoriaService:
    def __init__(self, repo: CategoriaRepo) -> None:
        self._repo = repo

    def listar(self) -> list[Categoria]:
        return self._repo.listar()

    def obter(self, categoria_id: int) -> Categoria:
        categoria = self._repo.buscar_por_id(categoria_id)
        if categoria is None:
            raise NaoEncontradoError("Essa categoria não existe mais.")
        return categoria

    def criar(self, nome: str) -> Categoria:
        nome = self._validar_nome(nome)
        return self._repo.criar(nome)

    def renomear(self, categoria_id: int, nome: str) -> Categoria:
        self.obter(categoria_id)
        nome = self._validar_nome(nome, ignorar_id=categoria_id)
        self._repo.renomear(categoria_id, nome)
        return Categoria(id=categoria_id, nome=nome)

    def remover(self, categoria_id: int) -> None:
        categoria = self.obter(categoria_id)
        quantidade = self._repo.contar_produtos_ativos(categoria_id)
        if quantidade > 0:
            plural = "produto cadastrado" if quantidade == 1 else "produtos cadastrados"
            raise OperacaoNaoPermitidaError(
                f'A categoria "{categoria.nome}" tem {quantidade} {plural}. '
                "Mude ou remova esses produtos antes de apagá-la."
            )
        self._repo.remover(categoria_id)

    def _validar_nome(self, nome: str, ignorar_id: int | None = None) -> str:
        nome = limpar_espacos(nome)
        if not nome:
            raise DadosInvalidosError("Informe o nome da categoria.")
        if len(nome) > NOME_MAX:
            raise DadosInvalidosError(f"O nome da categoria pode ter até {NOME_MAX} caracteres.")
        if self._repo.existe_nome(nome, ignorar_id):
            raise RegistroDuplicadoError("Já existe uma categoria com esse nome.")
        return nome
