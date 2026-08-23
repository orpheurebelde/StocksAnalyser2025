import unittest

from core.sec_financials import _capex_concepts, _latest_matching_difference


def fact(rows):
    return {"units": {"USD": rows}}


class SecFinancialsTests(unittest.TestCase):
    def test_fcf_uses_matching_period_and_dynamic_productive_asset_concept(self):
        facts = {"facts": {"us-gaap": {
            "NetCashProvidedByUsedInOperatingActivities": fact([
                {"start": "2025-01-01", "end": "2025-03-31", "filed": "2025-04-20", "form": "10-Q", "val": 100},
                {"start": "2025-01-01", "end": "2025-06-30", "filed": "2025-07-20", "form": "10-Q", "val": 250},
            ]),
            "PaymentsToAcquireProductiveAssets": fact([
                {"start": "2025-01-01", "end": "2025-03-31", "filed": "2025-04-20", "form": "10-Q", "val": 20},
                {"start": "2025-01-01", "end": "2025-06-30", "filed": "2025-07-20", "form": "10-Q", "val": 60},
            ]),
        }}}

        capex = _capex_concepts(facts)
        result = _latest_matching_difference(facts, ("NetCashProvidedByUsedInOperatingActivities",), capex)

        self.assertEqual(capex, ("PaymentsToAcquireProductiveAssets",))
        self.assertEqual(result, 190)

    def test_fcf_does_not_mix_periods(self):
        facts = {"facts": {"us-gaap": {
            "NetCashProvidedByUsedInOperatingActivities": fact([
                {"start": "2025-01-01", "end": "2025-06-30", "filed": "2025-07-20", "form": "10-Q", "val": 250},
            ]),
            "PaymentsToAcquirePropertyPlantAndEquipment": fact([
                {"start": "2025-01-01", "end": "2025-03-31", "filed": "2025-04-20", "form": "10-Q", "val": 20},
            ]),
        }}}

        result = _latest_matching_difference(
            facts,
            ("NetCashProvidedByUsedInOperatingActivities",),
            _capex_concepts(facts),
        )

        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
