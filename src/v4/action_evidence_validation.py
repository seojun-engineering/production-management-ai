
import sqlite3
from contextlib import closing

from action_tracking import DB_PATH


def validate_action_evidence(action_id, db_path=DB_PATH):
    if not isinstance(action_id, str) or not action_id.strip():
        return {
            "verified": False,
            "reason": "INVALID_ACTION_ID",
        }

    with closing(sqlite3.connect(db_path)) as conn:
        conn.row_factory = sqlite3.Row

        action = conn.execute(
            """
            SELECT action_id, status, closure_type,
                   action_description, created_at, updated_at
            FROM actions
            WHERE action_id = ?
            """,
            (action_id,),
        ).fetchone()

    if action is None:
        return {
            "verified": False,
            "reason": "ACTION_NOT_FOUND",
        }

    # 현재 V4-C에는 실제 조치 수행 시각,
    # 원천 증빙 ID, 증빙 승인자 정보가 없다.
    # 따라서 완료된 조치도 실제 수행 증빙으로 인정하지 않는다.
    return {
        "verified": False,
        "reason": "EXECUTION_EVIDENCE_NOT_AVAILABLE",
        "action_id": action["action_id"],
        "action_status": action["status"],
        "closure_type": action["closure_type"],
        "execution_verified": False,
    }


if __name__ == "__main__":
    result = validate_action_evidence(
        "V4-REVIEW-2022-11-03-CHECK-001"
    )

    print("=== V4-D ACTION EVIDENCE VALIDATION ===")
    print(result)
