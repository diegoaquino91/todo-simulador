"""todo-simulador — ToDo com interface gráfica (tkinter) e SQLite."""

from __future__ import annotations

import json
import sqlite3
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Literal
from uuid import uuid4

DB_FILE = Path(__file__).with_name("todos.db")
LEGACY_JSON = Path(__file__).with_name("todos.json")
FilterMode = Literal["todas", "pendentes", "concluidas"]


class TodoApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("todo-simulador")
        self.geometry("720x520")
        self.minsize(560, 420)
        self.configure(bg="#f4f6f8")

        self.tasks: list[dict] = []
        self.filter_mode: FilterMode = "todas"
        self._item_to_id: dict[str, str] = {}

        self.conn = sqlite3.connect(DB_FILE)
        self.conn.row_factory = sqlite3.Row
        self._init_db()
        self._migrate_json_if_needed()

        self._setup_style()
        self._build_ui()
        self._load_tasks()
        self._refresh_list()

        self.bind("<Return>", lambda _e: self.add_task())
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _init_db(self) -> None:
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                done INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            )
            """
        )
        self.conn.commit()

    def _migrate_json_if_needed(self) -> None:
        """Importa tarefas de todos.json (se existir) e remove o arquivo antigo."""
        if not LEGACY_JSON.exists():
            return

        count = self.conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        if count > 0:
            return

        try:
            data = json.loads(LEGACY_JSON.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return

        if not isinstance(data, list):
            return

        for item in data:
            task_id = str(item.get("id") or uuid4())
            title = str(item.get("title", "")).strip()
            if not title:
                continue
            done = 1 if item.get("done") else 0
            created_at = str(
                item.get("created_at")
                or datetime.now().strftime("%d/%m/%Y %H:%M")
            )
            self.conn.execute(
                """
                INSERT OR IGNORE INTO tasks (id, title, done, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (task_id, title, done, created_at),
            )
        self.conn.commit()
        LEGACY_JSON.rename(LEGACY_JSON.with_suffix(".json.bak"))

    def _setup_style(self) -> None:
        style = ttk.Style(self)
        if "clam" in style.theme_names():
            style.theme_use("clam")

        style.configure("Root.TFrame", background="#f4f6f8")
        style.configure("Card.TFrame", background="#ffffff")
        style.configure(
            "Title.TLabel",
            background="#f4f6f8",
            foreground="#1a2332",
            font=("Segoe UI", 20, "bold"),
        )
        style.configure(
            "Subtitle.TLabel",
            background="#f4f6f8",
            foreground="#5b6b7c",
            font=("Segoe UI", 10),
        )
        style.configure(
            "Stats.TLabel",
            background="#ffffff",
            foreground="#3d4f63",
            font=("Segoe UI", 9),
        )
        style.configure("TEntry", padding=8, font=("Segoe UI", 11))
        style.configure(
            "Accent.TButton",
            font=("Segoe UI", 10, "bold"),
            padding=(14, 8),
            background="#2563eb",
            foreground="#ffffff",
        )
        style.map(
            "Accent.TButton",
            background=[("active", "#1d4ed8"), ("pressed", "#1e40af")],
        )
        style.configure("Action.TButton", font=("Segoe UI", 9), padding=(10, 6))
        style.configure(
            "Filter.TRadiobutton",
            background="#ffffff",
            foreground="#334155",
            font=("Segoe UI", 9),
            padding=(8, 4),
        )

    def _build_ui(self) -> None:
        root = ttk.Frame(self, style="Root.TFrame", padding=20)
        root.pack(fill="both", expand=True)

        header = ttk.Frame(root, style="Root.TFrame")
        header.pack(fill="x", pady=(0, 16))
        ttk.Label(header, text="todo-simulador", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            header,
            text="Organize suas tarefas — adicione, conclua e filtre",
            style="Subtitle.TLabel",
        ).pack(anchor="w", pady=(2, 0))

        card = ttk.Frame(root, style="Card.TFrame", padding=16)
        card.pack(fill="both", expand=True)

        entry_row = ttk.Frame(card, style="Card.TFrame")
        entry_row.pack(fill="x", pady=(0, 12))

        self.task_var = tk.StringVar()
        self.entry = ttk.Entry(entry_row, textvariable=self.task_var)
        self.entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.entry.focus_set()

        ttk.Button(
            entry_row,
            text="Adicionar",
            style="Accent.TButton",
            command=self.add_task,
        ).pack(side="left")

        toolbar = ttk.Frame(card, style="Card.TFrame")
        toolbar.pack(fill="x", pady=(0, 10))

        self.filter_var = tk.StringVar(value="todas")
        for value, label in (
            ("todas", "Todas"),
            ("pendentes", "Pendentes"),
            ("concluidas", "Concluídas"),
        ):
            ttk.Radiobutton(
                toolbar,
                text=label,
                value=value,
                variable=self.filter_var,
                style="Filter.TRadiobutton",
                command=self._on_filter_change,
            ).pack(side="left", padx=(0, 6))

        actions = ttk.Frame(toolbar, style="Card.TFrame")
        actions.pack(side="right")
        ttk.Button(
            actions,
            text="Concluir / Reabrir",
            style="Action.TButton",
            command=self.toggle_selected,
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            actions,
            text="Excluir",
            style="Action.TButton",
            command=self.delete_selected,
        ).pack(side="left")

        list_frame = ttk.Frame(card, style="Card.TFrame")
        list_frame.pack(fill="both", expand=True)

        columns = ("status", "titulo", "criada")
        self.tree = ttk.Treeview(
            list_frame,
            columns=columns,
            show="headings",
            selectmode="browse",
        )
        self.tree.heading("status", text="Status")
        self.tree.heading("titulo", text="Tarefa")
        self.tree.heading("criada", text="Criada em")
        self.tree.column("status", width=100, anchor="center", stretch=False)
        self.tree.column("titulo", width=360, anchor="w")
        self.tree.column("criada", width=140, anchor="center", stretch=False)

        scrollbar = ttk.Scrollbar(
            list_frame, orient="vertical", command=self.tree.yview
        )
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.tree.tag_configure("done", foreground="#64748b")
        self.tree.tag_configure("pending", foreground="#0f172a")
        self.tree.bind("<Double-1>", lambda _e: self.toggle_selected())
        self.tree.bind("<Delete>", lambda _e: self.delete_selected())

        footer = ttk.Frame(card, style="Card.TFrame")
        footer.pack(fill="x", pady=(12, 0))
        self.stats_label = ttk.Label(footer, text="", style="Stats.TLabel")
        self.stats_label.pack(side="left")
        ttk.Button(
            footer,
            text="Limpar concluídas",
            style="Action.TButton",
            command=self.clear_completed,
        ).pack(side="right")

    def add_task(self) -> None:
        title = self.task_var.get().strip()
        if not title:
            messagebox.showinfo("ToDo", "Digite o nome da tarefa.")
            return

        task = {
            "id": str(uuid4()),
            "title": title,
            "done": False,
            "created_at": datetime.now().strftime("%d/%m/%Y %H:%M"),
        }
        self.conn.execute(
            """
            INSERT INTO tasks (id, title, done, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (task["id"], task["title"], 0, task["created_at"]),
        )
        self.conn.commit()

        self.tasks.append(task)
        self.task_var.set("")
        self.entry.focus_set()
        self._refresh_list()

    def toggle_selected(self) -> None:
        task = self._selected_task()
        if task is None:
            messagebox.showinfo("ToDo", "Selecione uma tarefa.")
            return

        task["done"] = not task["done"]
        self.conn.execute(
            "UPDATE tasks SET done = ? WHERE id = ?",
            (1 if task["done"] else 0, task["id"]),
        )
        self.conn.commit()
        self._refresh_list()

    def delete_selected(self) -> None:
        task = self._selected_task()
        if task is None:
            messagebox.showinfo("ToDo", "Selecione uma tarefa.")
            return
        if not messagebox.askyesno("ToDo", f"Excluir \"{task['title']}\"?"):
            return

        self.conn.execute("DELETE FROM tasks WHERE id = ?", (task["id"],))
        self.conn.commit()
        self.tasks = [t for t in self.tasks if t["id"] != task["id"]]
        self._refresh_list()

    def clear_completed(self) -> None:
        completed = [t for t in self.tasks if t["done"]]
        if not completed:
            messagebox.showinfo("ToDo", "Não há tarefas concluídas.")
            return
        if not messagebox.askyesno(
            "ToDo", f"Remover {len(completed)} tarefa(s) concluída(s)?"
        ):
            return

        self.conn.execute("DELETE FROM tasks WHERE done = 1")
        self.conn.commit()
        self.tasks = [t for t in self.tasks if not t["done"]]
        self._refresh_list()

    def _on_filter_change(self) -> None:
        self.filter_mode = self.filter_var.get()  # type: ignore[assignment]
        self._refresh_list()

    def _selected_task(self) -> dict | None:
        selection = self.tree.selection()
        if not selection:
            return None
        task_id = self._item_to_id.get(selection[0])
        if task_id is None:
            return None
        for task in self.tasks:
            if task["id"] == task_id:
                return task
        return None

    def _filtered_tasks(self) -> list[dict]:
        if self.filter_mode == "pendentes":
            return [t for t in self.tasks if not t["done"]]
        if self.filter_mode == "concluidas":
            return [t for t in self.tasks if t["done"]]
        return list(self.tasks)

    def _refresh_list(self) -> None:
        self.tree.delete(*self.tree.get_children())
        self._item_to_id.clear()

        for task in self._filtered_tasks():
            status = "✓ Concluída" if task["done"] else "○ Pendente"
            tags = ("done",) if task["done"] else ("pending",)
            item_id = self.tree.insert(
                "",
                "end",
                values=(status, task["title"], task["created_at"]),
                tags=tags,
            )
            self._item_to_id[item_id] = task["id"]

        total = len(self.tasks)
        done = sum(1 for t in self.tasks if t["done"])
        pending = total - done
        self.stats_label.configure(
            text=f"{total} no total  ·  {pending} pendente(s)  ·  {done} concluída(s)"
        )

    def _load_tasks(self) -> None:
        rows = self.conn.execute(
            """
            SELECT id, title, done, created_at
            FROM tasks
            ORDER BY rowid ASC
            """
        ).fetchall()
        self.tasks = [
            {
                "id": row["id"],
                "title": row["title"],
                "done": bool(row["done"]),
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def _on_close(self) -> None:
        self.conn.close()
        self.destroy()


if __name__ == "__main__":
    app = TodoApp()
    app.mainloop()
