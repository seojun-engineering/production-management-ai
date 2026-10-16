from contextlib import closing
from pathlib import Path
from datetime import datetime, timezone
import json
import sqlite3

from action_tracking import DB_PATH, initialize_database

ROOT = Path(__file__).resolve().parents[2]

INPUT_PATH = ROOT / "results/v4/next_check_demo.json"


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def register_review(input_path=INPUT_PATH, db_path=DB_PATH):
    data = json.loads(
        Path(input_path).read_text(encoding="utf-8")
    )

    # 이번 단계에서는 시연용 날짜 한 건만 허용
    if data["review_id"] != "V4-REVIEW-2022-11-03":
        raise ValueError("Unexpected review ID")

    if data["root_cause_status"] != "NOT_ESTABLISHED":
        raise ValueError("Root cause must remain unestablished")

    initialize_database(db_path)

    now = utc_now()
    inserted_actions = 0

    with closing(sqlite3.connect(db_path)) as conn:
        with conn:
            conn.execute("PRAGMA foreign_keys = ON")

            # Review 생성: 중복 실행 시 기존 기록을 덮어쓰지 않음
            conn.execute(
                """
                INSERT OR IGNORE INTO reviews (
                    review_id,
                    target_date,
                    target_type,
                    evidence_ids,
                    selection_reason,
                    root_cause_status,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    data["review_id"],
                    data["target_date"],
                    data["target_type"],
                    json.dumps(data["evidence_ids"]),
                    data["selection_reason"],
                    data["root_cause_status"],
                    now,
                ),
            )

            for check in data["checks"]:
                action_id = (
                    f"{data['review_id']}-{check['check_id']}"
                )

                cursor = conn.execute(
                    """
                    INSERT OR IGNORE INTO actions (
                        action_id,
                        review_id,
                        check_id,
                        assignee,
                        check_question,
                        status,
                        check_completed,
                        cause_confirmed,
                        effect_verified,
                        created_at,
                        updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        action_id,
                        data["review_id"],
                        check["check_id"],
                        None,
                        check["question"],
                        "NOT_REVIEWED",
                        0,
                        0,
                        0,
                        now,
                        now,
                    ),
                )

                if cursor.rowcount == 1:
                    inserted_actions += 1

                    # 신규 생성 기록도 이력에 남김
                    conn.execute(
                        """
                        INSERT INTO action_history (
                            action_id,
                            field_name,
                            old_value,
                            new_value,
                            changed_by,
                            changed_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            action_id,
                            "status",
                            None,
                            "NOT_REVIEWED",
                            "SYSTEM_DEMO",
                            now,
                        ),
                    )

            conn.commit()

            saved = conn.execute(
                """
                SELECT
                    action_id,
                    check_id,
                    check_question,
                    status,
                    check_completed,
                    cause_confirmed,
                    effect_verified
                FROM actions
                WHERE review_id = ?
                ORDER BY check_id
                """,
                (data["review_id"],),
            ).fetchall()

    return {
        "review_id": data["review_id"],
        "inserted_actions": inserted_actions,
        "saved_actions": saved,
    }


def main():
    result = register_review()

    print("=== V4-C REVIEW REGISTRATION ===")
    print("Review ID:", result["review_id"])
    print("New Actions:", result["inserted_actions"])

    for action in result["saved_actions"]:
        print(
            f"{action[1]} | "
            f"{action[3]} | "
            f"Check={action[4]} "
            f"Cause={action[5]} "
            f"Effect={action[6]}"
        )


if __name__ == "__main__":
    main()
