# todo-simulador

Aplicativo desktop de lista de tarefas feito com **Python**, **tkinter** e **SQLite**.

## Funcionalidades

- Adicionar, concluir/reabrir e excluir tarefas
- Filtrar por todas, pendentes ou concluídas
- Limpar tarefas concluídas
- Persistência local em banco SQLite (`todos.db`)

## Como executar

Requisitos: Python 3.10+ (tkinter incluso na instalação padrão).

```bash
python todo_app.py
```

## Estrutura

| Arquivo       | Descrição                          |
|---------------|------------------------------------|
| `todo_app.py` | Interface e lógica do aplicativo   |
| `todos.db`    | Banco SQLite (gerado ao executar)  |
