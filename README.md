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
| Tela principal com 4 opções | feita (as telas internas ainda não) |
| RF02, RF03, RF06 vendas e pesquisa de produtos | próxima etapa |
| RF04, RF05 categorias e produtos | próxima etapa |
| RF07 a RF11 clientes e fiado | próxima etapa |
| RF12 a RF15 expediente e planilhas | próxima etapa |

## Decisões de implementação

- Dinheiro é guardado em **centavos** (inteiros) para evitar erros de
  arredondamento.
- Produtos e clientes removidos ficam inativos (`ativo = 0`), para não quebrar o
  histórico de vendas.
- Gravações que mexem em mais de uma tabela usam `with conn:` para ser tudo ou
  nada (RNF07).
