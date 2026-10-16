
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from contextlib import closing

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "v4"))

from action_tracking import initialize_database
from register_review import register_review
from update_action import update_action


class ActionTrackingTests(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_actions.db"

        initialize_database(self.db_path)

        register_review(db_path=self.db_path)

        self.action_id = (
            "V4-REVIEW-2022-11-03-CHECK-001"
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def get_action(self):
        with closing(sqlite3.connect(self.db_path)) as conn, conn:
            return conn.execute(
                """
                SELECT status,
                       check_completed,
                       cause_confirmed,
                       effect_verified
                FROM actions
                WHERE action_id = ?
                """,
                (self.action_id,),
            ).fetchone()

    def get_history_count(self):
        with closing(sqlite3.connect(self.db_path)) as conn, conn:
            return conn.execute(
                """
                SELECT COUNT(*)
                FROM action_history
                WHERE action_id = ?
                """,
                (self.action_id,),
            ).fetchone()[0]

    
    
    
    def test_status_does_not_confirm_cause(self):
        statuses = [
            "UNDER_REVIEW",
            "ACTION_PLANNED",
            "IN_PROGRESS",
            "COMPLETED",
        ]

        for status in statuses:
            update_action(
                action_id=self.action_id,
                changed_by="TEST_USER",
                status=status,
                action_description=(
                    "DEMO: Completed record reconciliation"
                    if status == "COMPLETED"
                    else None
                ),
                closure_type=(
                    "ACTION_COMPLETED"
                    if status == "COMPLETED"
                    else None
                ),
                db_path=self.db_path,
            )

        status, check, cause, effect = self.get_action()

        self.assertEqual(status, "COMPLETED")
        self.assertEqual((check, cause, effect), (0, 0, 0))

        with closing(sqlite3.connect(self.db_path)) as conn, conn:
            closure_type = conn.execute(
                """
                SELECT closure_type
                FROM actions
                WHERE action_id = ?
                """,
                (self.action_id,),
            ).fetchone()[0]

        self.assertEqual(closure_type, "ACTION_COMPLETED")

    def test_assignee_change_preserves_independent_flags(self):
        update_action(
            action_id=self.action_id,
            changed_by="TEST_USER",
            assignee="TEST_MANAGER",
            db_path=self.db_path,
        )

        status, check, cause, effect = self.get_action()

        self.assertEqual(status, "NOT_REVIEWED")
        self.assertEqual((check, cause, effect), (0, 0, 0))

    def test_change_history_is_recorded(self):
        before = self.get_history_count()

        update_action(
            action_id=self.action_id,
            changed_by="TEST_USER",
            status="UNDER_REVIEW",
            db_path=self.db_path,
        )

        after = self.get_history_count()

        self.assertEqual(after, before + 1)

    def test_repeated_update_does_not_duplicate_history(self):
        update_action(
            action_id=self.action_id,
            changed_by="TEST_USER",
            status="UNDER_REVIEW",
            db_path=self.db_path,
        )

        before = self.get_history_count()

        update_action(
            action_id=self.action_id,
            changed_by="TEST_USER",
            status="UNDER_REVIEW",
            db_path=self.db_path,
        )

        self.assertEqual(
            self.get_history_count(),
            before,
        )

    def test_invalid_status_is_rejected(self):
        with self.assertRaises(ValueError):
            update_action(
                action_id=self.action_id,
                changed_by="TEST_USER",
                status="ROOT_CAUSE_CONFIRMED",
                db_path=self.db_path,
            )

    def test_finding_and_action_are_recorded(self):
        result = update_action(
            action_id=self.action_id,
            changed_by="TEST_USER",
            finding="DEMO: Downtime records need reconciliation",
            action_description="DEMO: Request event log review",
            due_date="2026-10-23",
            follow_up_metric="downtime_h",
            db_path=self.db_path,
        )

        self.assertEqual(result["changes"], 4)

        with closing(sqlite3.connect(self.db_path)) as conn, conn:
            row = conn.execute(
                """
                SELECT finding, action_description,
                       due_date, follow_up_metric,
                       cause_confirmed, effect_verified
                FROM actions
                WHERE action_id = ?
                """,
                (self.action_id,),
            ).fetchone()

        self.assertEqual(
            row[0],
            "DEMO: Downtime records need reconciliation"
        )
        self.assertEqual(row[2], "2026-10-23")
        self.assertEqual(row[3], "downtime_h")
        self.assertEqual(row[4:], (0, 0))


    def test_invalid_due_date_is_rejected(self):
        before = self.get_history_count()

        with self.assertRaises(ValueError):
            update_action(
                action_id=self.action_id,
                changed_by="TEST_USER",
                due_date="2026-99-99",
                db_path=self.db_path,
            )

        # 잘못된 입력은 DB와 이력을 변경하지 않아야 함
        with closing(sqlite3.connect(self.db_path)) as conn, conn:
            due_date = conn.execute(
                """
                SELECT due_date
                FROM actions
                WHERE action_id = ?
                """,
                (self.action_id,),
            ).fetchone()[0]

        self.assertIsNone(due_date)
        self.assertEqual(self.get_history_count(), before)


    def test_invalid_status_transition_is_rejected(self):
        before = self.get_history_count()

        with self.assertRaises(ValueError):
            update_action(
                action_id=self.action_id,
                changed_by="TEST_USER",
                status="COMPLETED",
                db_path=self.db_path,
            )

        status, check, cause, effect = self.get_action()

        self.assertEqual(status, "NOT_REVIEWED")
        self.assertEqual((check, cause, effect), (0, 0, 0))
        self.assertEqual(self.get_history_count(), before)

    def test_completed_without_action_description_is_rejected(self):
        for status in [
            "UNDER_REVIEW",
            "ACTION_PLANNED",
            "IN_PROGRESS",
        ]:
            update_action(
                action_id=self.action_id,
                changed_by="TEST_USER",
                status=status,
                db_path=self.db_path,
            )

        before = self.get_history_count()

        with self.assertRaises(ValueError):
            update_action(
                action_id=self.action_id,
                changed_by="TEST_USER",
                status="COMPLETED",
                closure_type="ACTION_COMPLETED",
                db_path=self.db_path,
            )

        current_status, check, cause, effect = self.get_action()

        self.assertEqual(current_status, "IN_PROGRESS")
        self.assertEqual((check, cause, effect), (0, 0, 0))
        self.assertEqual(self.get_history_count(), before)


    def test_on_hold_requires_finding(self):
        update_action(
            action_id=self.action_id,
            changed_by="TEST_USER",
            status="UNDER_REVIEW",
            db_path=self.db_path,
        )

        before = self.get_history_count()

        with self.assertRaises(ValueError):
            update_action(
                action_id=self.action_id,
                changed_by="TEST_USER",
                status="ON_HOLD",
                db_path=self.db_path,
            )

        self.assertEqual(
            self.get_action()[0],
            "UNDER_REVIEW"
        )
        self.assertEqual(
            self.get_history_count(),
            before
        )

        update_action(
            action_id=self.action_id,
            changed_by="TEST_USER",
            status="ON_HOLD",
            finding="DEMO: Additional operation records required",
            db_path=self.db_path,
        )

        self.assertEqual(
            self.get_action()[0],
            "ON_HOLD"
        )

        update_action(
            action_id=self.action_id,
            changed_by="TEST_USER",
            status="UNDER_REVIEW",
            db_path=self.db_path,
        )

        self.assertEqual(
            self.get_action(),
            ("UNDER_REVIEW", 0, 0, 0)
        )


    def test_no_action_closure_success(self):
        update_action(
            action_id=self.action_id,
            changed_by="TEST_USER",
            status="UNDER_REVIEW",
            db_path=self.db_path,
        )

        update_action(
            action_id=self.action_id,
            changed_by="TEST_USER",
            status="COMPLETED",
            closure_type="REVIEW_CLOSED_NO_ACTION",
            finding="DEMO: Records reviewed; no action required",
            db_path=self.db_path,
        )

        with closing(sqlite3.connect(self.db_path)) as conn, conn:
            row = conn.execute(
                """
                SELECT status, closure_type,
                       action_description,
                       cause_confirmed, effect_verified
                FROM actions
                WHERE action_id = ?
                """,
                (self.action_id,),
            ).fetchone()

        self.assertEqual(row[0], "COMPLETED")
        self.assertEqual(row[1], "REVIEW_CLOSED_NO_ACTION")
        self.assertIsNone(row[2])
        self.assertEqual(row[3:], (0, 0))

    def test_no_action_closure_requires_finding(self):
        update_action(
            action_id=self.action_id,
            changed_by="TEST_USER",
            status="UNDER_REVIEW",
            db_path=self.db_path,
        )

        before = self.get_history_count()

        with self.assertRaises(ValueError):
            update_action(
                action_id=self.action_id,
                changed_by="TEST_USER",
                status="COMPLETED",
                closure_type="REVIEW_CLOSED_NO_ACTION",
                db_path=self.db_path,
            )

        self.assertEqual(self.get_action()[0], "UNDER_REVIEW")
        self.assertEqual(self.get_history_count(), before)

    def test_no_action_closure_rejects_action_description(self):
        update_action(
            action_id=self.action_id,
            changed_by="TEST_USER",
            status="UNDER_REVIEW",
            db_path=self.db_path,
        )

        before = self.get_history_count()

        with self.assertRaises(ValueError):
            update_action(
                action_id=self.action_id,
                changed_by="TEST_USER",
                status="COMPLETED",
                closure_type="REVIEW_CLOSED_NO_ACTION",
                finding="DEMO: No further action required",
                action_description="DEMO: Replaced equipment",
                db_path=self.db_path,
            )

        self.assertEqual(self.get_action()[0], "UNDER_REVIEW")
        self.assertEqual(self.get_history_count(), before)

    def test_completed_action_cannot_be_modified(self):
        update_action(
            action_id=self.action_id,
            changed_by="TEST_USER",
            status="UNDER_REVIEW",
            db_path=self.db_path,
        )

        update_action(
            action_id=self.action_id,
            changed_by="TEST_USER",
            status="COMPLETED",
            closure_type="REVIEW_CLOSED_NO_ACTION",
            finding="DEMO: Review completed without action",
            db_path=self.db_path,
        )

        before = self.get_history_count()

        with self.assertRaises(ValueError):
            update_action(
                action_id=self.action_id,
                changed_by="TEST_USER",
                finding="DEMO: Modified after closure",
                db_path=self.db_path,
            )

        with closing(sqlite3.connect(self.db_path)) as conn, conn:
            row = conn.execute(
                """
                SELECT status, finding, closure_type
                FROM actions
                WHERE action_id = ?
                """,
                (self.action_id,),
            ).fetchone()

        self.assertEqual(row[0], "COMPLETED")
        self.assertEqual(
            row[1],
            "DEMO: Review completed without action"
        )
        self.assertEqual(
            row[2],
            "REVIEW_CLOSED_NO_ACTION"
        )
        self.assertEqual(
            self.get_history_count(),
            before
        )


    def test_transaction_rollback_on_history_failure(self):
        before = self.get_history_count()

        # 이력 저장을 의도적으로 실패시키는 트리거
        with closing(sqlite3.connect(self.db_path)) as conn, conn:
            conn.execute("""
                CREATE TRIGGER reject_history_insert
                BEFORE INSERT ON action_history
                BEGIN
                    SELECT RAISE(
                        ABORT,
                        'Simulated history failure'
                    );
                END;
            """)

        # 담당자 변경 중 이력 INSERT가 실패해야 함
        with self.assertRaises(sqlite3.DatabaseError):
            update_action(
                action_id=self.action_id,
                changed_by="TEST_USER",
                assignee="TEST_MANAGER",
                db_path=self.db_path,
            )

        # UPDATE까지 롤백되었는지 확인
        with closing(sqlite3.connect(self.db_path)) as conn, conn:
            assignee = conn.execute(
                """
                SELECT assignee
                FROM actions
                WHERE action_id = ?
                """,
                (self.action_id,),
            ).fetchone()[0]

        self.assertIsNone(assignee)
        self.assertEqual(self.get_history_count(), before)

if __name__ == "__main__":
    unittest.main()
