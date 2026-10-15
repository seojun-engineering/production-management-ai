import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src' / 'v4'))
from evidence_validation import registry, validate


class EvidenceValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index = registry(ROOT)

    def valid(self):
        return {
            'evidence_id': 'V2-DAILY-2022-11-03', 'date': '2022-11-03',
            'product': '3', 'metric': 'operating_ratio',
            'value': float(self.index['V2-DAILY-2022-11-03']['row']['operating_ratio']),
            'unit': 'ratio', 'aggregation': 'daily',
            'selection_rule': 'screening_top_5',
            'cause_status': 'NOT_ESTABLISHED', 'effect_verified': False,
        }

    def assert_code(self, claim, code):
        result = validate(claim, self.index)
        self.assertFalse(result['passed'])
        self.assertIn(code, [x['code'] for x in result['errors']])

    def test_valid(self):
        self.assertTrue(validate(self.valid(), self.index)['passed'])

    def test_missing_id(self):
        x = self.valid(); x['evidence_id'] = 'V2-DAILY-2099-01-01'
        self.assert_code(x, 'UNKNOWN_EVIDENCE_ID')

    def test_wrong_value(self):
        x = self.valid(); x['value'] = 0.99
        self.assert_code(x, 'VALUE_MISMATCH')

    def test_wrong_unit(self):
        x = self.valid(); x['unit'] = 'percent'
        self.assert_code(x, 'UNIT_MISMATCH')

    def test_wrong_date(self):
        x = self.valid(); x['date'] = '2022-11-04'
        self.assert_code(x, 'DATE_MISMATCH')

    def test_wrong_product(self):
        x = self.valid(); x['product'] = '5'
        self.assert_code(x, 'PRODUCT_MISMATCH')

    def test_wrong_aggregation(self):
        x = self.valid(); x['aggregation'] = 'hourly'
        self.assert_code(x, 'AGGREGATION_MISMATCH')

    def test_wrong_screening_rule(self):
        x = self.valid(); x['evidence_id'] = 'V2-DAILY-2022-12-06'; x['date'] = '2022-12-06'; x.pop('product')
        self.assert_code(x, 'SELECTION_RULE_FAILED')

    def test_unverified_cause(self):
        x = self.valid(); x['cause_status'] = 'CONFIRMED'
        self.assert_code(x, 'UNVERIFIED_CAUSAL_CLAIM')

    def test_unverified_effect(self):
        x = self.valid(); x['effect_verified'] = True
        self.assert_code(x, 'UNVERIFIED_EFFECT_CLAIM')

    def test_interpretation_needs_human_review(self):
        x = self.valid(); x['interpretation'] = 'The shift schedule explains the loss.'
        result = validate(x, self.index)
        self.assertTrue(result['passed'])
        self.assertTrue(result['review_required'])


if __name__ == '__main__':
    unittest.main()
