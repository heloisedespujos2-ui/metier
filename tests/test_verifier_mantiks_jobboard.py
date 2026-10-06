import json
import tempfile
import unittest
from pathlib import Path

from scripts.verifier_mantiks_jobboard import save_mantiks_result


class SaveMantiksResultTests(unittest.TestCase):
    def test_saves_company_result_and_job_board_counts(self):
        result = {
            "active": 2,
            "returned": 2,
            "jobs": [
                {"id": "job-1", "job_board": "welcometothejungle"},
                {"id": "job-2", "job_board": "francetravail"},
            ],
        }

        with tempfile.TemporaryDirectory() as directory:
            output_file = save_mantiks_result(
                Path(directory),
                "Crédit Agricole Assurances",
                result,
            )

            self.assertTrue(output_file.exists())
            saved = json.loads(output_file.read_text(encoding="utf-8"))
            self.assertEqual(saved["company"], "Crédit Agricole Assurances")
            self.assertEqual(saved["source"], "Mantiks")
            self.assertEqual(saved["active"], 2)
            self.assertEqual(saved["returned"], 2)
            self.assertEqual(saved["jobs"][0]["job_board"], "welcometothejungle")


if __name__ == "__main__":
    unittest.main()
