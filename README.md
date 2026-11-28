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
| Tela principal com 4 opções | feita (Produtos, Clientes e Vendas têm tela; completa) |
| RF04 categorias (criar, renomear, remover) | feito |
| RF05 produtos (cadastrar, editar, remover) | feito |
| RF06 pesquisa de produtos (nome ou categoria, sem acento) | feito |
| RF02, RF03 registro de vendas | feito |
| RN02 desconto de 15% | feito (valor mínimo definido pelo botão "Desconto") |
| RF07 cadastro de clientes (código único) | feito |
| RF08 pesquisa de clientes por código ou nome | feito |
| RF09 lista de clientes com o que cada um deve | feito |
| RF11 "Pagou": pagamento total ou parcial da dívida | feito |
| RN01 limite de dívida | feito (cliente bloqueado não compra no fiado) |
| RN03 crédito do cliente | feito (depósito e uso nas compras) |
| RF10 venda no fiado | feito |
| RF12 iniciar e encerrar o expediente (gera a planilha .xlsx) | feito |
| RF13 planilha com produto, categoria, quantidade, valor e subtotais por forma | feito |
| RF14 escolha da pasta das planilhas | feito |
| RF15 quantidade vendida no dia e no mês anterior | feito (também "Este mês") |
| RNF01 salvamento automático (60 s, configurável) | feito |
| RNF02 aviso ao fechar com expediente aberto | feito |
| RNF04 calculadora (`=(3*4,50)`) nos campos de valor | feito |

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
  nada (RNF07). Os métodos de gravação do `ClienteRepo` não confirmam sozinhos:
  quem chama abre a transação com `with repo.transacao():`, para que uma venda
  no fiado (venda + dívida) possa ser gravada numa transação só.
- Limite de dívida (RN01): é por cliente e opcional (em branco = sem limite). O
  cliente fica "Bloqueado" quando a dívida passa do limite, e é liberado quando
  paga até o limite, como no Documento de Software.
- Pagamento maior que a dívida é recusado; o excedente deve ser lançado em
  "+ Crédito". Cliente só pode ser removido sem dívida e sem crédito, e o código
  de um cliente removido não é reutilizado.
- Desconto (RN02): o proprietário define o valor mínimo no botão "Desconto" da
  tela de vendas (em branco = sem desconto). Vale para vendas **acima** desse
  valor (estritamente maior), é de 15% do subtotal arredondado ao centavo
  (metade para cima) e vem antes do crédito.
- Crédito do cliente (RN03): é abatido só se a opção "Usar crédito" estiver
  marcada, até o total da venda; o que sobra continua com o cliente. No fiado,
  só o restante vira dívida. Se o crédito cobre tudo, nada vira dívida e a venda
  passa mesmo com o cliente bloqueado.
- O preço de cada item é gravado na venda: mudar o preço depois não altera
  vendas antigas. A venda, os itens e a atualização do cliente são gravados numa
  transação só (RNF07).
- Bancos criados antes desta etapa recebem a coluna `credito_usado_centavos`
  automaticamente ao abrir o programa.
- O botão "Crédito" na venda é o cartão de crédito; o saldo do cliente aparece
  como "Crédito do cliente".
- Expediente (RF12): vendas só são registradas com o expediente aberto. Ao
  encerrar, entram na planilha as vendas feitas entre o início e o fim. Se a
  planilha não puder ser salva (pasta inexistente, arquivo aberto no Excel), o
  expediente continua aberto. Dois expedientes no mesmo dia geram
  `vendas_AAAA-MM-DD.xlsx` e `vendas_AAAA-MM-DD_2.xlsx`, sem sobrescrever.
- Planilha (RF13): itens − descontos = total vendido = soma das formas de
  pagamento (PIX, crédito, débito, dinheiro, fiado) + o que foi pago com saldo
  de crédito do cliente, em linha própria.
- Pasta (RF14): se o proprietário não escolher, usa `data/planilhas`.
- Salvamento automático (RNF01): cada venda já é confirmada no banco na hora.
  A cada 60 s (chave `autosave_segundos`, mínimo 10) o sistema também grava
  `rascunho_vendas_AAAA-MM-DD.xlsx` com o dia até agora; ele é apagado ao
  encerrar. O expediente aberto sobrevive a uma queda de energia.
- Aviso ao fechar (RNF02): com expediente aberto (ou pedido não finalizado) o
  programa pergunta antes de fechar.
- Calculadora (RNF04): qualquer campo de valor aceita uma conta começando com
  `=`, como `=(3*4,50)` (13,50). Usa + - * / e parênteses, com vírgula decimal;
  resultado arredondado ao centavo. Não usa `eval`: o texto é lido por um
  analisador próprio. Nas janelas de pagamento, crédito e desconto o resultado
  aparece embaixo enquanto se digita, e Enter troca a conta pelo resultado.
  Conta inválida ou divisão por zero mostra mensagem e não trava.
