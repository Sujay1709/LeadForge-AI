"""Usage tracking and credit system for LeadForge AI monetization.

Lightweight credit-based usage tracker using local JSON storage.
Replace with a database (Supabase, Firebase, PostgreSQL) for production.
"""

import json
import os
import time
from datetime import datetime, timedelta
from typing import Optional


PLANS = {
    "free": {
        "name": "Free",
        "credits_per_month": 10,
        "price": 0,
        "features": ["10 searches/month", "5 pages per search", "CSV export"],
    },
    "starter": {
        "name": "Starter",
        "credits_per_month": 100,
        "price": 29,
        "features": ["100 searches/month", "10 pages per search", "CSV + Sheets export", "Research mode"],
    },
    "pro": {
        "name": "Pro",
        "credits_per_month": 500,
        "price": 79,
        "features": ["500 searches/month", "20 pages per search", "All exports", "Research mode", "Priority support"],
    },
    "scale": {
        "name": "Scale",
        "credits_per_month": 2000,
        "price": 199,
        "features": ["2000 searches/month", "Unlimited pages", "All exports", "API access", "Dedicated support"],
    },
}

CREDIT_COSTS = {
    "search": 1,
    "extract_page": 0.5,
    "sheets_export": 1,
    "research": 0.5,
}

_USAGE_FILE = os.path.join(os.path.dirname(__file__), ".usage.json")


class UsageTracker:
    """Track per-user credit consumption."""

    def __init__(self, user_id: str = "default"):
        self.user_id = user_id
        self.data = self._load()

    def _load(self) -> dict:
        if os.path.exists(_USAGE_FILE):
            try:
                with open(_USAGE_FILE) as f:
                    all_data = json.load(f)
                return all_data.get(self.user_id, self._default_user())
            except (json.JSONDecodeError, IOError):
                pass
        return self._default_user()

    def _save(self):
        all_data = {}
        if os.path.exists(_USAGE_FILE):
            try:
                with open(_USAGE_FILE) as f:
                    all_data = json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        all_data[self.user_id] = self.data
        with open(_USAGE_FILE, "w") as f:
            json.dump(all_data, f, indent=2)

    def _default_user(self) -> dict:
        return {
            "plan": "free",
            "credits_used": 0,
            "credits_reset_at": (datetime.now().replace(day=1) + timedelta(days=32)).replace(day=1).isoformat(),
            "total_searches": 0,
            "total_leads": 0,
            "history": [],
            "created_at": datetime.now().isoformat(),
        }

    def _maybe_reset(self):
        reset_at = datetime.fromisoformat(self.data["credits_reset_at"])
        if datetime.now() >= reset_at:
            self.data["credits_used"] = 0
            self.data["credits_reset_at"] = (
                datetime.now().replace(day=1) + timedelta(days=32)
            ).replace(day=1).isoformat()
            self._save()

    @property
    def plan(self) -> dict:
        return PLANS[self.data.get("plan", "free")]

    @property
    def credits_remaining(self) -> float:
        self._maybe_reset()
        return self.plan["credits_per_month"] - self.data["credits_used"]

    def can_afford(self, action: str, quantity: int = 1) -> bool:
        cost = CREDIT_COSTS.get(action, 0) * quantity
        return self.credits_remaining >= cost

    def consume(self, action: str, quantity: int = 1, metadata: Optional[dict] = None):
        cost = CREDIT_COSTS.get(action, 0) * quantity
        self.data["credits_used"] += cost
        self.data["history"].append({
            "action": action,
            "cost": cost,
            "quantity": quantity,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {},
        })
        self.data["history"] = self.data["history"][-100:]
        self._save()

    def record_search(self, query: str, leads_found: int):
        self.data["total_searches"] += 1
        self.data["total_leads"] += leads_found
        self._save()

    def get_stats(self) -> dict:
        self._maybe_reset()
        return {
            "plan_name": self.plan["name"],
            "credits_used": self.data["credits_used"],
            "credits_total": self.plan["credits_per_month"],
            "credits_remaining": self.credits_remaining,
            "total_searches": self.data["total_searches"],
            "total_leads": self.data["total_leads"],
            "usage_pct": (self.data["credits_used"] / self.plan["credits_per_month"]) * 100
                if self.plan["credits_per_month"] > 0 else 0,
        }


def render_usage_bar(tracker: UsageTracker) -> str:
    stats = tracker.get_stats()
    pct = min(stats["usage_pct"], 100)
    color = "#c6ff00" if pct < 70 else "#ffab00" if pct < 90 else "#ff5252"
    return f"""
    <div style=\"margin:12px 0;\">
        <div style=\"display:flex;justify-content:space-between;font-size:0.72rem;color:#888;margin-bottom:4px;\">
            <span>{stats['plan_name']} Plan</span>
            <span>{stats['credits_remaining']:.0f} / {stats['credits_total']} credits</span>
        </div>
        <div style=\"background:#1a1a1a;border-radius:6px;height:6px;overflow:hidden;\">
            <div style=\"background:{color};height:100%;width:{pct:.1f}%;border-radius:6px;
                        transition:width 0.5s cubic-bezier(.4,0,.2,1);\"></div>
        </div>
        <div style=\"font-size:0.65rem;color:#555;margin-top:4px;text-align:right;\">
            Resets monthly
        </div>
    </div>
    """
