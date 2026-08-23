import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from sales_workflow import SalesWorkflowStore


class SalesWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = SalesWorkflowStore(Path(self.tmp.name) / "sales.db")

    def tearDown(self):
        self.tmp.cleanup()

    def test_artifact_lifecycle(self):
        created = self.store.create_artifact("bi", "销售BI", {"kpis": {}})
        self.assertEqual(created["status"], "pending_review")
        reviewed = self.store.review_artifact(created["id"], "accept", "刘经理", "数据可信")
        self.assertEqual(reviewed["status"], "accepted")
        self.assertEqual(len(reviewed["reviews"]), 1)

    def test_reviewer_required(self):
        created = self.store.create_artifact("customers", "客户价值", {"customers": []})
        with self.assertRaises(ValueError):
            self.store.review_artifact(created["id"], "accept", "")

    def test_export_only_accepted(self):
        created = self.store.create_artifact("performance", "业绩", {"records": []})
        with self.assertRaises(ValueError):
            self.store.export_artifact(created["id"])
        self.store.review_artifact(created["id"], "accept", "刘经理")
        content, media_type = self.store.export_artifact(created["id"])
        self.assertEqual(media_type, "application/json")
        self.assertIn("performance", content)

    def test_invalid_kind(self):
        with self.assertRaises(ValueError):
            self.store.create_artifact("bogus", "标题", {})


if __name__ == "__main__":
    unittest.main()
