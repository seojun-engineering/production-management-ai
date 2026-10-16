from contextlib import closing
from pathlib import Path
import sqlite3

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "data/v4/action_tracking.db"


def initialize_database(db_path=DB_PATH):
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with closing(sqlite3.connect(db_path)) as conn:
        with conn:
            conn.execute("PRAGMA foreign_keys = ON")

            conn.executescript("""
            CREATE TABLE IF NOT EXISTS reviews (
                review_id TEXT PRIMARY KEY,
                target_date TEXT NOT NULL,
                target_type TEXT NOT NULL,
                evidence_ids TEXT NOT NULL,
                selection_reason TEXT NOT NULL,
                root_cause_status TEXT NOT NULL
                    DEFAULT 'NOT_ESTABLISHED',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS actions (
                action_id TEXT PRIMARY KEY,
                review_id TEXT NOT NULL,
                check_id TEXT NOT NULL,
                assignee TEXT,
                check_question TEXT NOT NULL,
                finding TEXT,
                action_description TEXT,
                due_date TEXT,
                status TEXT NOT NULL
                    DEFAULT 'NOT_REVIEWED'
                    CHECK (
                        status IN (
                            'NOT_REVIEWED',
                            'UNDER_REVIEW',
                            'ACTION_PLANNED',
                            'IN_PROGRESS',
                            'COMPLETED',
                            'ON_HOLD'
                        )
                    ),
                check_completed INTEGER NOT NULL DEFAULT 0,
                cause_confirmed INTEGER NOT NULL DEFAULT 0,
                effect_verified INTEGER NOT NULL DEFAULT 0,
                follow_up_metric TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (review_id)
                    REFERENCES reviews(review_id),
                UNIQUE(review_id, check_id)
            );

            CREATE TABLE IF NOT EXISTS action_history (
                history_id INTEGER PRIMARY KEY AUTOINCREMENT,
                action_id TEXT NOT NULL,
                field_name TEXT NOT NULL,
                old_value TEXT,
                new_value TEXT,
                changed_by TEXT NOT NULL,
                changed_at TEXT NOT NULL,
                FOREIGN KEY (action_id)
                    REFERENCES actions(action_id)
            );
            """)

            # 기존 DB를 유지하면서 closure_type 필드 추가
            columns = {
                row[1]
                for row in conn.execute(
                    "PRAGMA table_info(actions)"
                ).fetchall()
            }

            if "closure_type" not in columns:
                conn.execute(
                    "ALTER TABLE actions ADD COLUMN closure_type TEXT"
                )

            conn.commit()

    print("=== V4-C DATABASE INITIALIZATION ===")
    print("Database:", db_path)
    print("Tables: reviews, actions, action_history")
    print("Status: CREATED / VERIFIED")


if __name__ == "__main__":
    initialize_database()
