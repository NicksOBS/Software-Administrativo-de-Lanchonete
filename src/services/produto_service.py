"""Regras de negócio dos produtos (RF05 e RF06)."""
from __future__ import annotations

from src.errors import DadosInvalidosError, NaoEncontradoError, RegistroDuplicadoError
from src.repos.categoria_repo import CategoriaRepo
from src.repos.produto_repo import Produto, ProdutoRepo
from src.textos import limpar_espacos

NOME_MAX = 60
PRECO_MAXIMO_CENTAVOS = 999_999  # R$ 9.999,99: barra erros de digitação como 6500 em vez de 6,50


class ProdutoService:
    def __init__(self, repo: ProdutoRepo, categorias: CategoriaRepo) -> None:
        self._repo = repo
        self._categorias = categorias

    def listar(self, busca: str = "", categoria_id: int | None = None) -> list[Produto]:
        return self._repo.listar(busca, categoria_id)

    def obter(self, produto_id: int) -> Produto:
        produto = self._repo.buscar_por_id(produto_id)
        if produto is None or not produto.ativo:
            raise NaoEncontradoError("Esse produto não existe mais.")
        return produto

    def criar(self, nome: str, categoria_id: int | None, preco_centavos: int) -> Produto:
        nome = self._validar(nome, categoria_id, preco_centavos)
        return self._repo.criar(nome, categoria_id, preco_centavos)

    def atualizar(
        self, produto_id: int, nome: str, categoria_id: int | None, preco_centavos: int
    ) -> Produto:
        self.obter(produto_id)
        nome = self._validar(nome, categoria_id, preco_centavos, ignorar_id=produto_id)
        self._repo.atualizar(produto_id, nome, categoria_id, preco_centavos)
        return self.obter(produto_id)

    def remover(self, produto_id: int) -> None:
        self.obter(produto_id)
        self._repo.desativar(produto_id)

    def _validar(
        self,
        nome: str,
        categoria_id: int | None,
        preco_centavos: int,
        ignorar_id: int | None = None,
    ) -> str:
        nome = limpar_espacos(nome)
        if not nome:
            raise DadosInvalidosError("Informe o nome do produto.")
        if len(nome) > NOME_MAX:
            raise DadosInvalidosError(f"O nome do produto pode ter até {NOME_MAX} caracteres.")

        if categoria_id is None or self._categorias.buscar_por_id(categoria_id) is None:
            raise DadosInvalidosError("Escolha uma categoria para o produto.")

        if preco_centavos <= 0:
            raise DadosInvalidosError("O preço deve ser maior que zero.")
        if preco_centavos > PRECO_MAXIMO_CENTAVOS:
            raise DadosInvalidosError("O preço máximo permitido é R$ 9.999,99.")

        if self._repo.existe_nome_ativo(nome, ignorar_id):
            raise RegistroDuplicadoError("Já existe um produto com esse nome.")
        return nome
