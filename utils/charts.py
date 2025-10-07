from __future__ import annotations
from typing import List, Dict, Any
import pandas as pd
import plotly.express as px


def tasks_by_status_chart(rows: List[Dict[str, Any]]):
	if not rows:
		return None
	df = pd.DataFrame(rows)
	counts = df.groupby("status")["id"].count().reset_index(name="count")
	fig = px.pie(counts, names="status", values="count", title="Tasks by status")
	fig.update_layout(legend_title_text="Status")
	return fig


def upcoming_deadlines_table(rows: List[Dict[str, Any]]):
	if not rows:
		return None
	df = pd.DataFrame(rows)
	if "due_date" in df.columns:
		df = df.sort_values("due_date")
	return df[["title", "due_date", "priority", "status", "estimated_hours", "hours_logged"]]


def risk_score(row: Dict[str, Any], days_until_due: float, daily_capacity_hours: float = 2.0) -> float:
	remaining = max(0.0, float(row.get("estimated_hours", 0) or 0) - float(row.get("hours_logged", 0) or 0))
	available = max(0.0, days_until_due * max(0.0, daily_capacity_hours))
	return float("inf") if available == 0 else remaining / available


def tasks_risk_dataframe(rows: List[Dict[str, Any]], today) -> pd.DataFrame:
	if not rows:
		return pd.DataFrame(columns=["title", "due_date", "remaining_h", "risk"])
	df = pd.DataFrame(rows)
	df["remaining_h"] = (
		df["estimated_hours"].astype(float).fillna(0.0)
		- df["hours_logged"].astype(float).fillna(0.0)
	).clip(lower=0.0)
	df["days_until_due"] = (pd.to_datetime(df["due_date"]) - pd.to_datetime(today)).dt.days.clip(lower=0)
	df["risk"] = df.apply(lambda r: risk_score(r.to_dict(), r["days_until_due"]), axis=1)
	return df[["title", "due_date", "remaining_h", "risk"]].sort_values(["risk", "due_date"], ascending=[False, True])
