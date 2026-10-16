
import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "v4"))

from next_check_engine import generate_next_checks


class NextCheckTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        path = ROOT / "results/v4/v3_bridge_demo.json"
        cls.bridge = json.loads(
            path.read_text(encoding="utf-8")
        )

    def make_bridge(self):
        return copy.deepcopy(self.bridge)

    def test_valid_evidence(self):
        result = generate_next_checks(self.make_bridge())

        self.assertEqual(len(result["checks"]), 3)
        self.assertEqual(
            result["root_cause_status"],
            "NOT_ESTABLISHED"
        )
        self.assertEqual(
            result["target_date"],
            "2022-11-03"
        )

    def test_failed_validation(self):
        bridge = self.make_bridge()
        bridge["all_factual_claims_passed"] = False

        with self.assertRaises(ValueError):
            generate_next_checks(bridge)

    def test_missing_validation_result(self):
        bridge = self.make_bridge()
        bridge["validation_results"].pop()

        with self.assertRaises(ValueError):
            generate_next_checks(bridge)

    def test_wrong_evidence_id(self):
        bridge = self.make_bridge()
        bridge["evidence_id"] = "V2-DAILY-2099-01-01"

        with self.assertRaises(ValueError):
            generate_next_checks(bridge)

    def test_wrong_screening_rank(self):
        bridge = self.make_bridge()

        for claim in bridge["factual_claims"]:
            if claim["metric"] == "screening_rank":
                claim["value"] = 99

        with self.assertRaises(ValueError):
            generate_next_checks(bridge)

    def test_tampered_operating_ratio(self):
        bridge = self.make_bridge()

        for claim in bridge["factual_claims"]:
            if claim["metric"] == "operating_ratio":
                claim["value"] = 0.99

        with self.assertRaises(ValueError):
            generate_next_checks(bridge)

    def test_tampered_event_count(self):
        bridge = self.make_bridge()

        for claim in bridge["factual_claims"]:
            if claim["metric"] == "event_count":
                claim["value"] = 999

        with self.assertRaises(ValueError):
            generate_next_checks(bridge)

    def test_tampered_unit(self):
        bridge = self.make_bridge()

        for claim in bridge["factual_claims"]:
            if claim["metric"] == "downtime_h":
                claim["unit"] = "minutes"

        with self.assertRaises(ValueError):
            generate_next_checks(bridge)

if __name__ == "__main__":
    unittest.main()
