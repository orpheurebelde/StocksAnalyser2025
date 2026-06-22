import unittest
from unittest.mock import patch

from routers import quarter_earnings


class ReprocessJobTests(unittest.TestCase):
    def test_background_job_records_completion_and_progress(self):
        job_id = "test-job"
        quarter_earnings._reprocess_jobs[job_id] = {
            "job_id": job_id,
            "ticker": None,
            "status": "queued",
        }

        def fake_reprocess(_ticker, callback):
            callback({"processed_reports": 2, "total_reports": 3, "updated_reports": 2, "skipped_reports": 0})
            return {"updated_reports": 3, "skipped_reports": 0}

        with patch.object(quarter_earnings, "reprocess_stored_reports", side_effect=fake_reprocess):
            quarter_earnings._run_reprocess_job(job_id, None)

        job = quarter_earnings._reprocess_jobs.pop(job_id)
        self.assertEqual(job["status"], "completed")
        self.assertEqual(job["processed_reports"], 2)
        self.assertEqual(job["result"]["updated_reports"], 3)


if __name__ == "__main__":
    unittest.main()
