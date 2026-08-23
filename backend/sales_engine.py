# -*- coding: utf-8 -*-
"""Sales BI aggregation, customer segmentation (RFM) and sales performance attribution."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from typing import Any


def _numeric(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _month_key(value: Any) -> str:
    """Normalise a date string to YYYY-MM, tolerating ISO date strings and datetimes."""
    if not value:
        return ""
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y-%m-%d %H:%M:%S", "%Y%m%d", "%d/%m/%Y"):
        try:
            parsed = datetime.strptime(text[:19], fmt)
            return parsed.strftime("%Y-%m")
        except (ValueError, TypeError):
            continue
    return text[:7]


def analyze_sales_bi(orders: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate real sales orders into BI KPIs, trend, category/region mix and alerts."""
    if len(orders) > 100000:
        raise ValueError("单次最多分析100000条销售订单")
    if not orders:
        return {
            "kpis": {"revenue": 0.0, "units": 0, "orders": 0, "avg_order_value": 0.0},
            "by_month": [], "by_category": [], "by_region": [], "top_products": [],
            "alerts": [], "method": "sales-bi-v1",
        }

    total_revenue = 0.0
    total_units = 0.0
    month_revenue: dict[str, float] = defaultdict(float)
    category_revenue: dict[str, float] = defaultdict(float)
    region_revenue: dict[str, float] = defaultdict(float)
    product_revenue: dict[str, dict[str, float]] = defaultdict(lambda: {"revenue": 0.0, "units": 0.0, "orders": 0})

    for order in orders:
        quantity = _numeric(order.get("quantity"), 1.0)
        unit_price = _numeric(order.get("unit_price"), 0.0)
        revenue = quantity * unit_price
        if revenue == 0 and order.get("revenue") is not None:
            revenue = _numeric(order.get("revenue"), 0.0)
        total_revenue += revenue
        total_units += quantity
        month = _month_key(order.get("date"))
        if month:
            month_revenue[month] += revenue
        category = str(order.get("category") or "未分类")
        category_revenue[category] += revenue
        region = str(order.get("region") or "未分区")
        region_revenue[region] += revenue
        product = str(order.get("product") or "未命名产品")
        product_revenue[product]["revenue"] += revenue
        product_revenue[product]["units"] += quantity
        product_revenue[product]["orders"] += 1

    order_count = len(orders)
    avg_order_value = total_revenue / order_count if order_count else 0.0
    by_month = [
        {"month": month, "revenue": round(month_revenue[month], 2)}
        for month in sorted(month_revenue)
    ]
    # Growth vs previous month, using the latest two periods.
    if len(by_month) >= 2:
        prev, current = by_month[-2]["revenue"], by_month[-1]["revenue"]
        growth = ((current - prev) / prev * 100.0) if prev else 100.0
        by_month[-1]["growth"] = round(growth, 1)

    by_category = sorted(
        ({"category": key, "revenue": round(amount, 2)} for key, amount in category_revenue.items()),
        key=lambda item: item["revenue"], reverse=True,
    )
    by_region = sorted(
        ({"region": key, "revenue": round(amount, 2)} for key, amount in region_revenue.items()),
        key=lambda item: item["revenue"], reverse=True,
    )
    top_products = sorted(
        (
            {"product": key, "revenue": round(item["revenue"], 2), "units": round(item["units"], 2),
             "orders": item["orders"]}
            for key, item in product_revenue.items()
        ),
        key=lambda row: row["revenue"], reverse=True,
    )[:10]

    alerts: list[str] = []
    if len(by_month) >= 2 and by_month[-1].get("growth", 0) < 0 and by_month[-1]["revenue"] > 0:
        alerts.append("最近一个月营收环比下降，建议核查促销与渠道投入。")
    if by_category:
        top = by_category[0]["revenue"]
        total_cat = sum(item["revenue"] for item in by_category)
        if total_cat and top / total_cat > 0.6:
            alerts.append("单一品类营收占比超过60%，存在集中度风险。")
    declining = [row["product"] for row in top_products if row["revenue"] <= 0 and row["units"] > 0]
    for name in declining[:3]:
        alerts.append(f"产品“{name}”有销量但营收为零，请核对定价与折扣。")
    if total_revenue <= 0:
        alerts.append("当前期间总营收为零，请确认订单数据是否完整。")

    return {
        "kpis": {"revenue": round(total_revenue, 2), "units": round(total_units, 2),
                 "orders": order_count, "avg_order_value": round(avg_order_value, 2)},
        "by_month": by_month, "by_category": by_category, "by_region": by_region,
        "top_products": top_products, "alerts": alerts, "method": "sales-bi-v1",
    }


def _rfm_score(value: float, scale: float = 5.0) -> float:
    return max(1.0, min(5.0, round(value * scale, 2)))


def segment_customers(customers: list[dict[str, Any]]) -> dict[str, Any]:
    """Score each customer with RFM and assign a value tier and churn risk."""
    if len(customers) > 100000:
        raise ValueError("单次最多分析100000位客户")
    if not customers:
        return {"customers": [], "count": 0, "tiers": {}, "method": "rfm-v1"}

    today = date.today()
    ranked: list[dict[str, Any]] = []
    for customer in customers:
        name = str(customer.get("name") or customer.get("customer_name") or "未命名客户")
        order_count = _numeric(customer.get("order_count"), 0.0)
        total_spend = _numeric(customer.get("total_spend"), _numeric(customer.get("monetary"), 0.0))
        last_order = customer.get("last_order_date") or customer.get("last_order")
        days_since = 3650
        if last_order:
            text = str(last_order).strip()
            for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y"):
                try:
                    parsed = datetime.strptime(text[:19], fmt).date()
                    days_since = max(0, (today - parsed).days)
                    break
                except (ValueError, TypeError):
                    continue
        recency = _rfm_score(max(0.0, 1.0 - days_since / 365.0))
        frequency = _rfm_score(min(order_count / 10.0, 1.0)) if order_count else 1.0
        max_monetary = max(float(c.get("total_spend", 0) or 0) for c in customers) or 1.0
        monetary = _rfm_score(total_spend / max_monetary) if total_spend else 1.0
        composite = round((recency + frequency + monetary) / 3.0 * 20.0, 1)

        if composite >= 85 and days_since <= 90:
            tier, churn = "VIP", "低"
        elif composite >= 65:
            tier, churn = "高价值", "低" if days_since <= 120 else "中"
        elif composite >= 45:
            tier, churn = "普通", "中" if days_since <= 180 else "高"
        else:
            tier, churn = "待唤醒", "高" if days_since > 180 else "中"

        suggestion = "安排专属顾问回访并推送新品。" if tier == "VIP" else (
            "季度触达，提升复购频次。" if tier == "高价值" else (
                "发送优惠券激活，避免沉默。" if tier == "普通" else "定向唤醒，确认流失原因。"
            )
        )
        ranked.append({
            **customer,
            "name": name, "order_count": int(order_count), "total_spend": round(total_spend, 2),
            "days_since_last_order": days_since,
            "rfm": {"recency": recency, "frequency": frequency, "monetary": monetary},
            "score": composite, "tier": tier, "churn_risk": churn, "suggestion": suggestion,
        })

    ranked.sort(key=lambda row: (row["score"], -row["total_spend"]), reverse=True)
    tier_map: dict[str, int] = defaultdict(int)
    for row in ranked:
        tier_map[row["tier"]] += 1
    return {
        "customers": ranked, "count": len(ranked),
        "tiers": {key: tier_map[key] for key in ("VIP", "高价值", "普通", "待唤醒")},
        "method": "rfm-v1",
    }


def analyze_performance(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Attribute real sales results to people, compare to targets and rank them."""
    if len(records) > 100000:
        raise ValueError("单次最多分析100000条业绩记录")
    if not records:
        return {"records": [], "count": 0, "method": "performance-v1"}

    by_person: dict[str, dict[str, float]] = defaultdict(lambda: {"revenue": 0.0, "orders": 0.0, "target": 0.0})
    for record in records:
        person = str(record.get("salesperson") or record.get("name") or "未分配")
        by_person[person]["revenue"] += _numeric(record.get("revenue"), 0.0)
        by_person[person]["orders"] += _numeric(record.get("orders"), 1.0)
        by_person[person]["target"] += _numeric(record.get("target"), 0.0)

    rows: list[dict[str, Any]] = []
    for person, agg in by_person.items():
        attainment = (agg["revenue"] / agg["target"] * 100.0) if agg["target"] else 0.0
        tier = "达标" if attainment >= 100 else "接近" if attainment >= 85 else "待提升"
        rows.append({
            "salesperson": person, "revenue": round(agg["revenue"], 2),
            "orders": int(agg["orders"]), "target": round(agg["target"], 2),
            "attainment": round(attainment, 1), "tier": tier,
        })
    rows.sort(key=lambda row: row["attainment"], reverse=True)
    total_revenue = sum(row["revenue"] for row in rows)
    total_target = sum(row["target"] for row in rows)
    return {
        "records": rows, "count": len(rows),
        "summary": {
            "total_revenue": round(total_revenue, 2),
            "total_target": round(total_target, 2),
            "overall_attainment": round(total_revenue / total_target * 100.0, 1) if total_target else 0.0,
        },
        "method": "performance-v1",
    }
