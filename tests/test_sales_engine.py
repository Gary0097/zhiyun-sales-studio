import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from sales_engine import analyze_performance, analyze_sales_bi, segment_customers


class SalesEngineTests(unittest.TestCase):
    def test_bi_aggregates_kpis_and_mix(self):
        orders = [
            {"date": "2026-07-01", "product": "电机", "category": "动力", "region": "华东", "quantity": 40, "unit_price": 320},
            {"date": "2026-07-15", "product": "控制器", "category": "电子", "region": "华南", "quantity": 25, "unit_price": 180},
            {"date": "2026-08-02", "product": "电机", "category": "动力", "region": "华东", "quantity": 48, "unit_price": 320},
        ]
        result = analyze_sales_bi(orders)
        self.assertEqual(result["kpis"]["orders"], 3)
        self.assertEqual(result["kpis"]["units"], 113)
        self.assertEqual(len(result["by_month"]), 2)
        self.assertEqual(result["top_products"][0]["product"], "电机")
        self.assertIn("method", result)

    def test_bi_empty_returns_zero_kpis(self):
        result = analyze_sales_bi([])
        self.assertEqual(result["kpis"]["revenue"], 0)
        self.assertEqual(result["kpis"]["orders"], 0)

    def test_segment_assigns_vip_for_high_rfm(self):
        customers = [
            {"name": "广东超能", "order_count": 12, "total_spend": 86000, "last_order_date": "2026-08-10"},
            {"name": "华东装备", "order_count": 3, "total_spend": 15000, "last_order_date": "2026-03-01"},
        ]
        result = segment_customers(customers)
        self.assertEqual(result["count"], 2)
        self.assertEqual(result["customers"][0]["name"], "广东超能")
        self.assertIn(result["customers"][0]["tier"], ("VIP", "高价值"))
        self.assertEqual(result["tiers"]["VIP"] + result["tiers"]["高价值"], 1)

    def test_performance_ranks_by_attainment(self):
        records = [
            {"salesperson": "李工", "revenue": 450000, "orders": 28, "target": 400000},
            {"salesperson": "王工", "revenue": 310000, "orders": 19, "target": 450000},
        ]
        result = analyze_performance(records)
        self.assertEqual(result["count"], 2)
        self.assertEqual(result["records"][0]["salesperson"], "李工")
        self.assertGreater(result["records"][0]["attainment"], result["records"][1]["attainment"])
        self.assertEqual(result["records"][0]["tier"], "达标")


if __name__ == "__main__":
    unittest.main()
