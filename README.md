# Sistema de Registro de Vendas e Fiado para Lanchonete

Projeto da disciplina ECOT11A (Laboratório de Engenharia de Software I, UNIFEI).
Implementa o MVP descrito no Documento de Software.

## Como executar (Windows)

Requisitos: Python 3.13 com Tkinter (já incluído na instalação padrão).

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python main.py
```

No primeiro acesso o sistema pede para criar o usuário do proprietário. O banco
de dados é criado automaticamente em `data/lanchonete.db`.

## Testes

```powershell
python -m pytest
```

## Estrutura

```
main.py            ponto de entrada
src/
  config.py        caminhos e nome do app
  errors.py        erros de negócio (mensagens para o usuário)
  database.py      schema SQLite (seção 9.2 do documento) e conexão
  repos/           camada de persistência (SQL fica só aqui)
  services/        regras de negócio (login, hash de senha, ...)
  ui/              telas CustomTkinter
  export/          gerador de planilhas (próximas etapas)
tests/             testes automatizados (pytest)
```

A organização em camadas segue a arquitetura da seção 7 do documento: a
interface chama os serviços, os serviços chamam os repositórios, e só os
repositórios conhecem o SQL.

## Estado atual do MVP

| Requisito | Situação |
|-----------|----------|
| RF01 login e cadastro de usuários | feito |
| RNF08 senhas com hash (PBKDF2) | feito |
| Banco SQLite com todas as tabelas | feito |
| Tela principal com 4 opções | feita (só Produtos tem tela por enquanto) |
| RF04 categorias (criar, renomear, remover) | feito |
| RF05 produtos (cadastrar, editar, remover) | feito |
| RF06 pesquisa de produtos (nome ou categoria, sem acento) | feito |
| RF02, RF03 registro de vendas | próxima etapa |
| RF07 a RF11 clientes e fiado | próxima etapa |
| RF12 a RF15 expediente e planilhas | próxima etapa |

## Decisões de implementação

- Dinheiro é guardado em **centavos** (inteiros) para evitar erros de
  arredondamento.
- Produtos e clientes removidos ficam inativos (`ativo = 0`), para não quebrar o
  histórico de vendas.
- Nomes de categorias e de produtos são comparados sem diferenciar acentos nem
  maiúsculas: "Pão" e "PAO" contam como o mesmo nome, e a pesquisa por "pao"
  encontra "Pão de queijo".
- O preço aceita `6`, `6,5`, `6,50`, `R$ 6,50` e `1.234,56`. Precisa ser maior
  que zero e no máximo R$ 9.999,99, para barrar erros de digitação.
- Gravações que mexem em mais de uma tabela usam `with conn:` para ser tudo ou
  nada (RNF07).
