

import copy
import sys
import unittest
import tempfile
from pathlib import Path

# 프로젝트 경로 설정
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "v4"))

# 경로 설정이 끝난 뒤 V4 모듈 불러오기
from action_tracking import initialize_database
from register_review import register_review
from action_evidence_validation import validate_action_evidence
from kpi_comparison_validation import validate_comparison



class KPIComparisonTests(unittest.TestCase):


    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_actions.db"

        initialize_database(self.db_path)
        register_review(db_path=self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def validate_from_test_db(self, action_id):
        return validate_action_evidence(
            action_id,
            db_path=self.db_path,
        )


    def mock_verified_action(self, action_id):
        return {
            "verified": True,
            "reason": "MOCK_VERIFIED_FOR_TEST_ONLY",
        }

    def valid_data(self):
        # 테스트 전용 가상 데이터
        # 실제 제조 개선 성과가 아님
        scope = {
            "metric": "operating_ratio",
            "unit": "ratio",
            "denominator": "monitored_time",
            "aggregation": "daily",
            "product": "DEMO_PRODUCT",
            "process": "DEMO_LINE",
            "sample_count": 10,
            "data_complete": True,
        }


        return {
            "action_id": "MOCK-ACTION-001",
            "record_origin": "REAL_ACTION",
            "action_status": "COMPLETED",
            "action_timestamp": "2026-10-10T12:00:00+09:00",
            "before": {
                **copy.deepcopy(scope),
                "value": 0.70,
                "start": "2026-10-01T00:00:00+09:00",
                "end": "2026-10-09T23:59:00+09:00",
            },
            "after": {
                **copy.deepcopy(scope),
                "value": 0.82,
                "start": "2026-10-11T00:00:00+09:00",
                "end": "2026-10-20T23:59:00+09:00",
            },
        }


    def error_codes(self, result):
        return {e["code"] for e in result["errors"]}

    def test_empty_data_is_blocked(self):
        result = validate_comparison({})

        self.assertEqual(result["status"], "NOT_COMPARABLE")
        self.assertFalse(result["can_calculate_improvement"])
        self.assertIsNone(result["improvement_rate"])

    def test_demo_action_is_blocked(self):
        data = self.valid_data()
        data["record_origin"] = "DEMO_ACTION"

        result = validate_comparison(
            data,
            action_validator=self.mock_verified_action
        )

        self.assertIn("NOT_REAL_ACTION", self.error_codes(result))

    def test_incomplete_action_is_blocked(self):
        data = self.valid_data()
        data["action_status"] = "IN_PROGRESS"

        result = validate_comparison(
            data,
            action_validator=self.mock_verified_action
        )

        self.assertIn("ACTION_NOT_COMPLETED", self.error_codes(result))

    def test_insufficient_samples_are_blocked(self):
        data = self.valid_data()
        data["before"]["sample_count"] = 2

        result = validate_comparison(
            data,
            action_validator=self.mock_verified_action
        )

        self.assertIn("INSUFFICIENT_SAMPLES", self.error_codes(result))

    def test_kpi_scope_mismatch_is_blocked(self):
        data = self.valid_data()
        data["after"]["denominator"] = "planned_time"

        result = validate_comparison(
            data,
            action_validator=self.mock_verified_action
        )

        self.assertIn("COMPARISON_SCOPE_MISMATCH", self.error_codes(result))

    def test_invalid_period_is_blocked(self):
        data = self.valid_data()
        data["after"]["start"] = "2026-10-09T10:00:00+09:00"

        result = validate_comparison(
            data,
            action_validator=self.mock_verified_action
        )

        self.assertIn("PERIOD_OVERLAP", self.error_codes(result))

    def test_valid_structure_only_allows_comparison(self):
        data = self.valid_data()

        result = validate_comparison(
            data,
            action_validator=self.mock_verified_action
        )

        self.assertEqual(result["status"], "COMPARABLE")
        self.assertTrue(result["can_calculate_improvement"])
        self.assertIsNone(result["improvement_rate"])
        self.assertEqual(
            result["root_cause_status"],
            "NOT_ESTABLISHED"
        )


    def test_before_period_reversed(self):
        data = self.valid_data()
        data["before"]["start"] = "2026-10-15T00:00:00+09:00"

        result = validate_comparison(
            data,
            action_validator=self.mock_verified_action
        )

        self.assertIn(
            "INVALID_BEFORE_PERIOD",
            self.error_codes(result)
        )
        self.assertFalse(result["can_calculate_improvement"])

    def test_after_period_reversed(self):
        data = self.valid_data()
        data["after"]["end"] = "2026-10-05T00:00:00+09:00"

        result = validate_comparison(
            data,
            action_validator=self.mock_verified_action
        )

        self.assertIn(
            "INVALID_AFTER_PERIOD",
            self.error_codes(result)
        )
        self.assertFalse(result["can_calculate_improvement"])

    def test_action_outside_comparison_gap(self):
        data = self.valid_data()
        data["action_timestamp"] = "2026-10-21T12:00:00+09:00"

        result = validate_comparison(
            data,
            action_validator=self.mock_verified_action
        )

        self.assertIn(
            "ACTION_OUTSIDE_GAP",
            self.error_codes(result)
        )
        self.assertFalse(result["can_calculate_improvement"])


    def test_unknown_action_id_is_blocked(self):
        data = self.valid_data()
        data["action_id"] = "NONEXISTENT-ACTION-999"

        result = validate_comparison(
            data,
            action_validator=self.validate_from_test_db
        )

        self.assertEqual(result["status"], "NOT_COMPARABLE")
        self.assertIn(
            "ACTION_EVIDENCE_NOT_VERIFIED",
            self.error_codes(result)
        )

    def test_unverified_demo_action_is_blocked(self):
        data = self.valid_data()
        data["action_id"] = (
            "V4-REVIEW-2022-11-03-CHECK-001"
        )

        result = validate_comparison(
            data,
            action_validator=self.validate_from_test_db
        )

        self.assertEqual(result["status"], "NOT_COMPARABLE")
        self.assertFalse(result["can_calculate_improvement"])
        self.assertIn(
            "ACTION_EVIDENCE_NOT_VERIFIED",
            self.error_codes(result)
        )

if __name__ == "__main__":
    unittest.main()
