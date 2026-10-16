
import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "v4"))

from kpi_comparison_validation import validate_comparison


class KPIComparisonTests(unittest.TestCase):

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
            "record_origin": "REAL_ACTION",
            "action_status": "COMPLETED",
            "action_timestamp": "2026-10-10T12:00:00+09:00",
            "before": {
                **copy.deepcopy(scope),
                "value": 0.70,
                "end": "2026-10-09T23:59:00+09:00",
            },
            "after": {
                **copy.deepcopy(scope),
                "value": 0.82,
                "start": "2026-10-11T00:00:00+09:00",
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

        result = validate_comparison(data)

        self.assertIn("NOT_REAL_ACTION", self.error_codes(result))

    def test_incomplete_action_is_blocked(self):
        data = self.valid_data()
        data["action_status"] = "IN_PROGRESS"

        result = validate_comparison(data)

        self.assertIn("ACTION_NOT_COMPLETED", self.error_codes(result))

    def test_insufficient_samples_are_blocked(self):
        data = self.valid_data()
        data["before"]["sample_count"] = 2

        result = validate_comparison(data)

        self.assertIn("INSUFFICIENT_SAMPLES", self.error_codes(result))

    def test_kpi_scope_mismatch_is_blocked(self):
        data = self.valid_data()
        data["after"]["denominator"] = "planned_time"

        result = validate_comparison(data)

        self.assertIn("COMPARISON_SCOPE_MISMATCH", self.error_codes(result))

    def test_invalid_period_is_blocked(self):
        data = self.valid_data()
        data["after"]["start"] = "2026-10-09T10:00:00+09:00"

        result = validate_comparison(data)

        self.assertIn("PERIOD_OVERLAP", self.error_codes(result))

    def test_valid_structure_only_allows_comparison(self):
        data = self.valid_data()

        result = validate_comparison(data)

        self.assertEqual(result["status"], "COMPARABLE")
        self.assertTrue(result["can_calculate_improvement"])
        self.assertIsNone(result["improvement_rate"])
        self.assertEqual(
            result["root_cause_status"],
            "NOT_ESTABLISHED"
        )


if __name__ == "__main__":
    unittest.main()
