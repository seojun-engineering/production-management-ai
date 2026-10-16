
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from contextlib import closing

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "v4"))

from next_check_engine import generate_next_checks
from register_review import register_review
from update_action import update_action


class V4IntegrationTests(unittest.TestCase):

    def test_evidence_to_action_closure(self):
        # 1. V3 Bridge 결과 읽기
        bridge_path = ROOT / "results/v4/v3_bridge_demo.json"

        bridge = json.loads(
            bridge_path.read_text(encoding="utf-8")
        )

        # 2. V4-A 재검증 + V4-B 점검 생성
        next_checks = generate_next_checks(bridge)

        self.assertEqual(
            next_checks["target_date"],
            "2022-11-03"
        )
        self.assertEqual(len(next_checks["checks"]), 3)
        self.assertEqual(
            next_checks["root_cause_status"],
            "NOT_ESTABLISHED"
        )

        # 3. 임시 DB와 임시 JSON 사용
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            db_path = temp_path / "integration.db"
            json_path = temp_path / "next_checks.json"

            json_path.write_text(
                json.dumps(
                    next_checks,
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            # 4. V4-C: Review와 Action 3개 등록
            registration = register_review(
                input_path=json_path,
                db_path=db_path,
            )

            self.assertEqual(
                registration["inserted_actions"],
                3
            )
            self.assertEqual(
                len(registration["saved_actions"]),
                3
            )

            # 5. CHECK-001을 검토 시작 상태로 변경
            action_id = (
                "V4-REVIEW-2022-11-03-CHECK-001"
            )

            update_action(
                action_id=action_id,
                changed_by="INTEGRATION_TEST",
                assignee="DEMO_MANAGER",
                status="UNDER_REVIEW",
                db_path=db_path,
            )

            # 6. 추가 조치 없는 검토 종료
            # 아래 finding은 시연용 입력이며
            # 실제 점검 결과가 아님
            update_action(
                action_id=action_id,
                changed_by="INTEGRATION_TEST",
                status="COMPLETED",
                closure_type="REVIEW_CLOSED_NO_ACTION",
                finding=(
                    "DEMO ONLY: Assumed review found "
                    "no further action necessary"
                ),
                db_path=db_path,
            )

            # 7. 저장 상태 및 원인/효과 플래그 확인
            with closing(sqlite3.connect(db_path)) as conn, conn:
                result = conn.execute(
                    """
                    SELECT status, closure_type,
                           finding, action_description,
                           check_completed,
                           cause_confirmed,
                           effect_verified
                    FROM actions
                    WHERE action_id = ?
                    """,
                    (action_id,),
                ).fetchone()

                action_count = conn.execute(
                    """
                    SELECT COUNT(*)
                    FROM actions
                    """
                ).fetchone()[0]

                history_count = conn.execute(
                    """
                    SELECT COUNT(*)
                    FROM action_history
                    WHERE action_id = ?
                    """,
                    (action_id,),
                ).fetchone()[0]

            self.assertEqual(action_count, 3)
            self.assertEqual(result[0], "COMPLETED")
            self.assertEqual(
                result[1],
                "REVIEW_CLOSED_NO_ACTION"
            )
            self.assertTrue(
                result[2].startswith("DEMO ONLY:")
            )
            self.assertIsNone(result[3])
            self.assertEqual(result[4:], (0, 0, 0))

            # 최초 등록 + 담당자 + 상태 변경 + 종료 관련 변경
            self.assertGreaterEqual(history_count, 5)


if __name__ == "__main__":
    unittest.main()
