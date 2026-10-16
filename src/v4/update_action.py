
from pathlib import Path
from datetime import datetime, timezone, date
import sqlite3

from action_tracking import DB_PATH


ALLOWED_STATUSES = {
    "NOT_REVIEWED",
    "UNDER_REVIEW",
    "ACTION_PLANNED",
    "IN_PROGRESS",
    "COMPLETED",
    "ON_HOLD",
}

# 허용되는 상태 전환 경로
ALLOWED_TRANSITIONS = {
    "NOT_REVIEWED": {"UNDER_REVIEW"},
    "UNDER_REVIEW": {"ACTION_PLANNED", "ON_HOLD"},
    "ACTION_PLANNED": {"IN_PROGRESS", "ON_HOLD"},
    "IN_PROGRESS": {"COMPLETED", "ON_HOLD"},
    "ON_HOLD": {"UNDER_REVIEW", "ACTION_PLANNED", "IN_PROGRESS"},
    "COMPLETED": set(),
}

def utc_now():
    return datetime.now(timezone.utc).isoformat()


def update_action(
    action_id,
    changed_by,
    assignee=None,
    status=None,
    finding=None,
    action_description=None,
    due_date=None,
    follow_up_metric=None,
    db_path=DB_PATH,
):
    if not changed_by or not changed_by.strip():
        raise ValueError("changed_by is required")

    if status is not None and status not in ALLOWED_STATUSES:
        raise ValueError(f"Invalid status: {status}")

    # Validate due_date before writing to SQLite
    if due_date is not None:
        try:
            parsed_date = date.fromisoformat(due_date)

            if parsed_date.isoformat() != due_date:
                raise ValueError

        except (ValueError, TypeError):
            raise ValueError(
                "due_date must be a valid YYYY-MM-DD date"
            )

    changes = {
        "assignee": assignee,
        "status": status,
        "finding": finding,
        "action_description": action_description,
        "due_date": due_date,
        "follow_up_metric": follow_up_metric,
    }

    # None은 변경하지 않는다는 뜻
    changes = {
        key: value
        for key, value in changes.items()
        if value is not None
    }

    if not changes:
        raise ValueError("No changes requested")

    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys = ON")

        # 읽기와 변경을 하나의 트랜잭션으로 처리
        conn.execute("BEGIN IMMEDIATE")

        conn.row_factory = sqlite3.Row

        existing = conn.execute(
            """
            SELECT *
            FROM actions
            WHERE action_id = ?
            """,
            (action_id,),
        ).fetchone()

        if existing is None:
            raise ValueError(f"Action not found: {action_id}")

        # 현재 상태에서 다음 상태로 이동할 수 있는지 확인
        if status is not None:
            current_status = existing["status"]

            if status != current_status:
                allowed = ALLOWED_TRANSITIONS.get(
                    current_status, set()
                )

                if status not in allowed:
                    raise ValueError(
                        f"Invalid status transition: "
                        f"{current_status} -> {status}"
                    )

        # 조치 완료에는 수행한 조치의 기록이 필요함
        if status == "COMPLETED":
            current_description = existing["action_description"]

            final_description = (
                action_description
                if action_description is not None
                else current_description
            )

            if not final_description or not final_description.strip():
                raise ValueError(
                    "COMPLETED requires action_description"
                )

        # 보류 상태로 변경하려면 사유를 기록해야 함
        if status == "ON_HOLD":
            current_finding = existing["finding"]

            final_finding = (
                finding
                if finding is not None
                else current_finding
            )

            if not final_finding or not final_finding.strip():
                raise ValueError(
                    "ON_HOLD requires finding"
                )

        changed_fields = []

        for field, new_value in changes.items():
            old_value = existing[field]

            if old_value == new_value:
                continue

            changed_fields.append(
                (field, old_value, new_value)
            )

        if not changed_fields:
            return {
                "action_id": action_id,
                "changes": 0,
                "message": "No actual changes",
            }

        now = utc_now()

        for field, old_value, new_value in changed_fields:
            # field는 고정된 허용 목록에서만 선택됨
            conn.execute(
                f"""
                UPDATE actions
                SET {field} = ?, updated_at = ?
                WHERE action_id = ?
                """,
                (new_value, now, action_id),
            )

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
                    field,
                    None if old_value is None else str(old_value),
                    str(new_value),
                    changed_by,
                    now,
                ),
            )

        conn.commit()

    return {
        "action_id": action_id,
        "changes": len(changed_fields),
        "changed_by": changed_by,
        "changed_at": now,
    }


def main():
    action_id = "V4-REVIEW-2022-11-03-CHECK-001"

    result = update_action(
        action_id=action_id,
        changed_by="DEMO_USER",
        assignee="DEMO_MANAGER",
        status="UNDER_REVIEW",
    )

    print("=== V4-C ACTION UPDATE ===")
    print("Action:", result["action_id"])
    print("Changes:", result["changes"])

    with sqlite3.connect(DB_PATH) as conn:
        history = conn.execute(
            """
            SELECT field_name, old_value, new_value,
                   changed_by, changed_at
            FROM action_history
            WHERE action_id = ?
            ORDER BY history_id
            """,
            (action_id,),
        ).fetchall()

    print("\n=== CHANGE HISTORY ===")

    for field, old, new, who, when in history:
        print(f"{field}: {old} -> {new} ({who}, {when})")


if __name__ == "__main__":
    main()
