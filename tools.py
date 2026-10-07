"""Three 311 tools, their model-facing descriptions, and a small dispatcher."""

import json
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests

API_URL = "https://data.cityofnewyork.us/resource/erm2-nwe9.json"
SOURCE = "https://data.cityofnewyork.us/d/erm2-nwe9"

# These are our transparent keyword groupings, not official 311 categories.
# A complaint type can match multiple concerns (e.g. unsanitary housing).
CONCERNS = {
    "noise": ["noise"],
    "sanitation": ["sanitation", "unsanitary", "dirty", "garbage", "trash", "dumping"],
    "rodents": ["rodent"],
    "housing": ["heat/hot water", "plumbing", "paint/plaster", "door/window", "water leak", "unsanitary condition", "electric", "flooring/stairs"],
    "parking": ["parking", "blocked driveway"],
}
CAVEATS = [
    "311 counts resident reports, not verified or unique incidents; repeated reports are possible.",
    "Counts and shares are not population-adjusted. Reporting habits and ZIP sizes differ.",
    "Report dates are submission dates, not necessarily incident dates; recent data may lag.",
    "ZIP codes do not exactly match neighborhoods. Fewer reports do not prove better conditions.",
]


def validate(zip_code: str, days: int):
    """Check the few inputs used in our fixed API queries."""
    if not isinstance(zip_code, str) or len(zip_code) != 5 or not zip_code.isascii() or not zip_code.isdigit():
        raise ValueError("Use a five-digit ZIP code as a string, for example '10027'.")
    if not isinstance(days, int) or not 1 <= days <= 90:
        raise ValueError("days must be a whole number from 1 to 90.")


def report_counts(zip_code: str, start: datetime, end: datetime) -> dict:
    """Aggregate in Socrata, so we do not download thousands of individual reports."""
    params = {
        "$select": "complaint_type, count(*) AS reports, max(created_date) AS latest_report",
        "$where": (
            f"incident_zip='{zip_code}' "
            f"AND created_date >= '{start:%Y-%m-%dT00:00:00}' "
            f"AND created_date < '{end:%Y-%m-%dT00:00:00}'"
        ),
        "$group": "complaint_type",
        "$order": "reports DESC, complaint_type ASC",
        "$limit": 1000,
    }
    headers = {}
    if os.getenv("SOCRATA_APP_TOKEN"):
        headers["X-App-Token"] = os.environ["SOCRATA_APP_TOKEN"]
    response = requests.get(API_URL, params=params, headers=headers, timeout=30)
    response.raise_for_status()
    rows = response.json()
    counts = {row.get("complaint_type", "Unknown"): int(row["reports"]) for row in rows}
    return {
        "zip_code": zip_code,
        "period": {"start": start.date().isoformat(), "end_exclusive": end.date().isoformat(), "timezone": "America/New_York"},
        "total_reports": sum(counts.values()),
        "latest_report_in_window": max((row["latest_report"] for row in rows), default=None),
        "counts_by_type": counts,
        "query_url": response.url,
    }


def concern_counts(report: dict, concern: str) -> dict:
    matched = {
        name: count for name, count in report["counts_by_type"].items()
        if any(keyword in name.lower() for keyword in CONCERNS[concern])
    }
    count = sum(matched.values())
    total = report["total_reports"]
    return {
        "reports": count,
        "share_of_all_reports_percent": round(100 * count / total, 1) if total else None,
        "matching_complaint_types": matched,
    }


def today() -> datetime:
    return datetime.now(ZoneInfo("America/New_York")).replace(hour=0, minute=0, second=0, microsecond=0)


def get_zip_report(zip_code: str, days: int = 30) -> dict:
    """Summarize all 311 report types for a ZIP during complete calendar days."""
    validate(zip_code, days)
    end = today()
    report = report_counts(zip_code, end - timedelta(days=days), end)
    return {
        **report,
        "concerns": {name: concern_counts(report, name) for name in CONCERNS},
        "note": "No reports found. Check the ZIP or try a longer window." if not report["total_reports"] else "Concern groups use keywords and may overlap.",
        "source": SOURCE,
        "caveats": CAVEATS,
    }


def compare_zip_priorities(zip_a: str, zip_b: str, concerns: list[str], days: int = 30) -> dict:
    """Our original 'what would bother me?' comparison, with counts and shares."""
    validate(zip_a, days)
    validate(zip_b, days)
    if not concerns or any(name not in CONCERNS for name in concerns):
        raise ValueError(f"Choose at least one concern from {list(CONCERNS)}.")
    if zip_a == zip_b:
        raise ValueError("Choose two different ZIP codes to compare.")
    end = today()
    a = report_counts(zip_a, end - timedelta(days=days), end)
    b = report_counts(zip_b, end - timedelta(days=days), end)
    differences = []
    for concern in dict.fromkeys(concerns):
        left, right = concern_counts(a, concern), concern_counts(b, concern)
        share_a, share_b = left["share_of_all_reports_percent"], right["share_of_all_reports_percent"]
        differences.append({
            "concern": concern,
            "zip_a": left,
            "zip_b": right,
            "share_difference_percentage_points_a_minus_b": round(share_a - share_b, 1) if share_a is not None and share_b is not None else None,
        })
    return {
        "zip_a": {key: value for key, value in a.items() if key != "counts_by_type"},
        "zip_b": {key: value for key, value in b.items() if key != "counts_by_type"},
        "priority_comparison": differences,
        "interpretation": "Shares describe the mix of reports, not the likelihood of experiencing a problem. No overall winner is calculated. Null shares mean there were no reports to compare.",
        "source": SOURCE,
        "caveats": CAVEATS,
    }


def get_concern_trend(zip_code: str, concern: str, days: int = 30) -> dict:
    """Compare a concern across adjacent equal-length windows of complete days."""
    validate(zip_code, days)
    if concern not in CONCERNS:
        raise ValueError(f"Choose one concern from {list(CONCERNS)}.")
    end = today()
    middle = end - timedelta(days=days)
    previous = report_counts(zip_code, middle - timedelta(days=days), middle)
    recent = report_counts(zip_code, middle, end)
    before, after = concern_counts(previous, concern), concern_counts(recent, concern)
    change = after["reports"] - before["reports"]
    return {
        "zip_code": zip_code,
        "concern": concern,
        "previous": {"period": previous["period"], "all_reports": previous["total_reports"], **before},
        "recent": {"period": recent["period"], "all_reports": recent["total_reports"], "latest_report_in_window": recent["latest_report_in_window"], **after},
        "change_in_reports": change,
        "change_percent": round(100 * change / before["reports"], 1) if before["reports"] else None,
        "interpretation": "Changes describe reporting activity, not proven changes in conditions. Percent change is undefined when the earlier count is zero; small counts can produce large percentages.",
        "query_urls": [previous["query_url"], recent["query_url"]],
        "source": SOURCE,
        "caveats": CAVEATS,
    }


ZIP = {"type": "string", "description": "Five-digit NYC ZIP code, e.g. '10027'. Ask the user if unknown."}
DAYS = {"type": "integer", "minimum": 1, "maximum": 90, "description": "Complete calendar days per window, 1–90; defaults to 30."}
CONCERN = {"type": "string", "enum": list(CONCERNS), "description": "Our keyword-based concern group, not an official 311 category."}
TOOLS = [
    {"type": "function", "function": {
        "name": "get_zip_report",
        "description": "Fetch live NYC 311 totals and complaint-type counts for one ZIP. Use for an overview, common reported issues, or report counts. Includes dates, source, and limitations.",
        "parameters": {"type": "object", "properties": {"zip_code": ZIP, "days": DAYS}, "required": ["zip_code"]},
    }},
    {"type": "function", "function": {
        "name": "compare_zip_priorities",
        "description": "Compare two ZIPs by the nuisances the user cares about. Fetches live 311 counts and calculates each concern's share of all reports and percentage-point differences. Use for personal tradeoffs, never safety rankings.",
        "parameters": {"type": "object", "properties": {"zip_a": ZIP, "zip_b": ZIP, "concerns": {"type": "array", "items": CONCERN, "minItems": 1, "description": "User's selected concerns, e.g. ['noise', 'rodents']. Ask if unspecified."}, "days": DAYS}, "required": ["zip_a", "zip_b", "concerns"]},
    }},
    {"type": "function", "function": {
        "name": "get_concern_trend",
        "description": "Fetch a ZIP's live 311 reports for the most recent N complete days and the preceding N days. Calculate one concern's count and percentage change. Use for 'has reporting increased?' questions.",
        "parameters": {"type": "object", "properties": {"zip_code": ZIP, "concern": CONCERN, "days": DAYS}, "required": ["zip_code", "concern"]},
    }},
]
TOOL_MAP = {"get_zip_report": get_zip_report, "compare_zip_priorities": compare_zip_priorities, "get_concern_trend": get_concern_trend}


def run_tool(name: str, args: dict) -> str:
    """Return actionable tool errors to Gemini instead of crashing the chat."""
    if name not in TOOL_MAP:
        return json.dumps({"error": f"Unknown tool. Choose from {list(TOOL_MAP)}."})
    try:
        return json.dumps(TOOL_MAP[name](**args))
    except requests.HTTPError as error:
        status = error.response.status_code
        advice = "Try later or configure SOCRATA_APP_TOKEN." if status == 429 else "Check the dataset endpoint and query fields; retry if the service is unavailable."
        return json.dumps({"error": f"NYC Open Data returned HTTP {status}. {advice}"})
    except requests.RequestException:
        return json.dumps({"error": "Could not reach NYC Open Data within 30 seconds. Check the connection or try again later; do not invent counts."})
    except (TypeError, ValueError) as error:
        return json.dumps({"error": f"Could not complete {name}: {error}. Check the arguments or dataset response."})
