from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Limpa registros antigos de jobs de forma controlada, preservando approved/rejected."
    )
    parser.add_argument("--db-path", default="jobs.db", help="Caminho do SQLite.")
    parser.add_argument("--before-id", type=int, required=True, help="Remove apenas jobs com id menor que este valor.")
    parser.add_argument("--source-site", default="LinkedIn", help="Fonte a filtrar. Default: LinkedIn.")
    parser.add_argument(
        "--status",
        default="collected",
        help="Status alvo da limpeza. Default: collected.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Aplica a remocao. Sem esta flag, executa apenas dry-run.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    db_path = Path(args.db_path)
    with sqlite3.connect(db_path) as connection:
        rows = connection.execute(
            """
            SELECT id, title, company, status, created_at
            FROM jobs
            WHERE id < ?
              AND source_site = ?
              AND status = ?
            ORDER BY id
            """,
            (args.before_id, args.source_site, args.status),
        ).fetchall()

        print(f"Encontrados {len(rows)} registros para limpeza controlada.")
        for row in rows[:20]:
            print(row)

        if not args.apply:
            print("Dry-run concluido. Use --apply para remover.")
            return

        connection.execute(
            """
            DELETE FROM jobs
            WHERE id < ?
              AND source_site = ?
              AND status = ?
            """,
            (args.before_id, args.source_site, args.status),
        )
        connection.commit()
        print(f"Removidos {len(rows)} registros.")


if __name__ == "__main__":
    main()
