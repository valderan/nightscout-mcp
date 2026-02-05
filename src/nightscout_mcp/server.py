"""Nightscout MCP Server - Access CGM data from Nightscout."""

import os
import asyncio
from datetime import datetime, timezone
from urllib.parse import urlparse
import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Configuration from environment
NIGHTSCOUT_URL = os.environ.get("NIGHTSCOUT_URL", "")
NIGHTSCOUT_API_SECRET = os.environ.get("NIGHTSCOUT_API_SECRET", "")

# Glucose units: "mgdl" or "mmol"
GLUCOSE_UNITS = os.environ.get("GLUCOSE_UNITS", "mmol").lower()

# Locale: "en" or "ru"
LOCALE = os.environ.get("LOCALE", "en").lower()

STRINGS = {
    "en": {
        "unknown_tool": "Unknown tool: {name}",
        "error": "Error: {error}",
        "no_glucose": "No glucose readings available",
        "current_glucose": "Current glucose: {value} {arrow}",
        "time_utc": "Time: {time} UTC",
        "delta": "Delta: {sign}{delta}",
        "device": "Device: {device}",
        "history_title": "Glucose history for {hours}h ({count} readings)",
        "statistics": "Statistics:",
        "average": "Average: {value}",
        "min_max": "Min/Max: {min}–{max}",
        "tir": "TIR ({range}): {value}%",
        "cv": "CV: {value}%",
        "recent_readings": "Recent readings:",
        "more_readings": "... and {count} more readings",
        "no_data_hours": "No data for the last {hours} hours",
        "not_enough_data": "Not enough data for analysis",
        "analysis_title": "Glucose Analysis: {from_date} — {to_date} ({days} days, {count} readings)",
        "key_metrics": "Key Metrics:",
        "avg_glucose": "Average glucose: {value}",
        "std_dev": "Standard deviation: {value}",
        "estimated_a1c": "Estimated HbA1c: {value}%",
        "time_in_ranges": "Time in Ranges:",
        "severe_hypo": "Severe hypo (<3.0 mmol): {value}% (goal <1%)",
        "hypo": "Hypoglycemia (3.0-3.9 mmol): {value}% (goal <4%)",
        "in_target": "In target ({range}): {value}% {status} (goal ≥{goal}%)",
        "above_target": "Above target: {value}%",
        "high": "High (10.0-13.9 mmol): {value}%",
        "very_high": "Very high (>13.9 mmol): {value}% (goal <5%)",
        "assessment": "Assessment:",
        "tir_goal_met": "✅ TIR goal of {goal}% achieved!",
        "tir_goal_away": "⚠️ {diff}% away from TIR goal of {goal}%",
        "cv_excellent": "✅ Excellent glucose stability",
        "cv_good": "📊 Good stability",
        "cv_high": "⚠️ High variability",
        "monthly_title": "Glucose Analysis for {year} (TIR goal: {goal}%)",
        "month_header": "Month │  TIR ({range})  │  Avg  │   CV   │  A1c  │ Readings",
        "no_data": "No data",
        "summary": "SUMMARY ({months} months, {count} readings)",
        "avg_tir": "Average TIR ({range}): {value}% — {status}",
        "avg_glucose": "Average glucose: {value}",
        "avg_cv": "Average CV: {value}% — {status}",
        "cv_status_stable": "✅ Stable",
        "cv_status_ok": "📊 OK",
        "cv_status_high": "⚠️ High",
        "avg_a1c": "Estimated HbA1c: {value}%",
        "best_tir": "Best TIR: {month} — {value}%",
        "worst_tir": "Worst TIR: {month} — {value}%",
        "treatments_title": "Treatments for {hours}h:",
        "no_treatments": "No treatments in the last {hours} hours",
        "totals": "Totals:",
        "status_title": "Nightscout Status:",
        "status_name": "Name: {value}",
        "status_version": "Version: {value}",
        "status_time": "Server time: {value}",
        "status_units": "Units: {value}",
        "thresholds": "Thresholds:",
        "high_label": "High: {value} mg/dL",
        "target_top": "Target top: {value} mg/dL",
        "target_bottom": "Target bottom: {value} mg/dL",
        "low_label": "Low: {value} mg/dL",
        "devices_title": "Device Status:",
        "no_device_data": "No device data available",
        "uploader": "Uploader: battery {value}%",
        "pump": "Pump: reservoir {reservoir}U, battery {battery}%",
        "device_label": "Device: {value}",
    },
    "ru": {
        "unknown_tool": "Неизвестный инструмент: {name}",
        "error": "Ошибка: {error}",
        "no_glucose": "Нет данных о глюкозе",
        "current_glucose": "Текущая глюкоза: {value} {arrow}",
        "time_utc": "Время: {time} UTC",
        "delta": "Дельта: {sign}{delta}",
        "device": "Устройство: {device}",
        "history_title": "История глюкозы за {hours}ч ({count} измерений)",
        "statistics": "Статистика:",
        "average": "Среднее: {value}",
        "min_max": "Мин/Макс: {min}–{max}",
        "tir": "В диапазоне ({range}): {value}%",
        "cv": "CV: {value}%",
        "recent_readings": "Последние измерения:",
        "more_readings": "... и еще {count} измерений",
        "no_data_hours": "Нет данных за последние {hours} часов",
        "not_enough_data": "Недостаточно данных для анализа",
        "analysis_title": "Анализ глюкозы: {from_date} — {to_date} ({days} дней, {count} измерений)",
        "key_metrics": "Ключевые метрики:",
        "avg_glucose": "Средняя глюкоза: {value}",
        "std_dev": "Стандартное отклонение: {value}",
        "estimated_a1c": "Оценочный HbA1c: {value}%",
        "time_in_ranges": "Время в диапазонах:",
        "severe_hypo": "Тяжелая гипо (<3.0 ммоль): {value}% (цель <1%)",
        "hypo": "Гипогликемия (3.0-3.9 ммоль): {value}% (цель <4%)",
        "in_target": "В цели ({range}): {value}% {status} (цель ≥{goal}%)",
        "above_target": "Выше цели: {value}%",
        "high": "Высокий (10.0-13.9 ммоль): {value}%",
        "very_high": "Очень высокий (>13.9 ммоль): {value}% (цель <5%)",
        "assessment": "Оценка:",
        "tir_goal_met": "✅ Цель TIR {goal}% достигнута!",
        "tir_goal_away": "⚠️ До цели TIR {goal}% не хватает {diff}%",
        "cv_excellent": "✅ Отличная стабильность",
        "cv_good": "📊 Хорошая стабильность",
        "cv_high": "⚠️ Высокая вариабельность",
        "monthly_title": "Анализ глюкозы за {year} (цель TIR: {goal}%)",
        "month_header": "Месяц │  TIR ({range})  │  Средн │   CV   │  A1c  │ Измерения",
        "no_data": "Нет данных",
        "summary": "ИТОГО ({months} мес., {count} измерений)",
        "avg_tir": "Средний TIR ({range}): {value}% — {status}",
        "avg_glucose": "Средняя глюкоза: {value}",
        "avg_cv": "Средний CV: {value}% — {status}",
        "cv_status_stable": "✅ Стабильно",
        "cv_status_ok": "📊 Нормально",
        "cv_status_high": "⚠️ Высоко",
        "avg_a1c": "Оценочный HbA1c: {value}%",
        "best_tir": "Лучший TIR: {month} — {value}%",
        "worst_tir": "Худший TIR: {month} — {value}%",
        "treatments_title": "Терапии за {hours}ч:",
        "no_treatments": "Нет терапий за последние {hours} часов",
        "totals": "Итого:",
        "status_title": "Статус Nightscout:",
        "status_name": "Имя: {value}",
        "status_version": "Версия: {value}",
        "status_time": "Время сервера: {value}",
        "status_units": "Ед. измерения: {value}",
        "thresholds": "Пороги:",
        "high_label": "Высокий: {value} mg/dL",
        "target_top": "Верх цели: {value} mg/dL",
        "target_bottom": "Низ цели: {value} mg/dL",
        "low_label": "Низкий: {value} mg/dL",
        "devices_title": "Статус устройств:",
        "no_device_data": "Нет данных об устройствах",
        "uploader": "Загрузчик: батарея {value}%",
        "pump": "Помпа: резервуар {reservoir}U, батарея {battery}%",
        "device_label": "Устройство: {value}",
    },
}


def t(key: str, **kwargs) -> str:
    lang = "ru" if LOCALE == "ru" else "en"
    template = STRINGS[lang].get(key, STRINGS["en"].get(key, key))
    return template.format(**kwargs)

# TIR range from environment (in mg/dL, will convert if mmol specified)
def parse_glucose_value(env_var: str, default_mgdl: float) -> float:
    """Parse glucose value from env, auto-detect units."""
    val = os.environ.get(env_var, "")
    if not val:
        return default_mgdl
    try:
        num = float(val)
        # If value < 30, assume it's mmol/L and convert to mg/dL
        if num < 30:
            return num * 18.0182
        return num
    except ValueError:
        return default_mgdl

# TIR range: default 70-140 mg/dL (3.9-7.8 mmol/L)
GLUCOSE_LOW = parse_glucose_value("GLUCOSE_LOW", 70)   # 3.9 mmol/L
GLUCOSE_HIGH = parse_glucose_value("GLUCOSE_HIGH", 140)  # 7.8 mmol/L

# Minimum valid glucose reading (below this is sensor error)
# 40 mg/dL = 2.2 mmol/L - readings below this are almost certainly sensor artifacts
GLUCOSE_MIN_VALID = 40  # mg/dL

# Direction arrows
DIRECTION_ARROWS = {
    "DoubleUp": "⇈",
    "SingleUp": "↑",
    "FortyFiveUp": "↗",
    "Flat": "→",
    "FortyFiveDown": "↘",
    "SingleDown": "↓",
    "DoubleDown": "⇊",
    "NOT COMPUTABLE": "?",
    "RATE OUT OF RANGE": "⚠️",
}

def parse_nightscout_url(url_str: str) -> dict:
    """Parse Nightscout URL to extract base URL, optional path, and token."""
    try:
        parsed = urlparse(url_str)
        path = parsed.path.rstrip("/")
        if path == "":
            path = ""
        return {
            "base_url": f"{parsed.scheme}://{parsed.hostname}" + (f":{parsed.port}" if parsed.port else "") + path,
            "token": parsed.username or "",
        }
    except Exception:
        return {"base_url": url_str.rstrip("/"), "token": ""}


def mgdl_to_mmol(mgdl: float) -> float:
    """Convert mg/dL to mmol/L."""
    return mgdl / 18.0182

def format_glucose(mgdl: float) -> str:
    """Format glucose value based on configured units."""
    if GLUCOSE_UNITS == "mgdl":
        return f"{int(round(mgdl))} mg/dL"
    else:
        return f"{mgdl_to_mmol(mgdl):.1f} mmol/L"

def format_glucose_short(mgdl: float) -> str:
    """Format glucose value (short, no units)."""
    if GLUCOSE_UNITS == "mgdl":
        return str(int(round(mgdl)))
    else:
        return f"{mgdl_to_mmol(mgdl):.1f}"

def get_tir_range_label() -> str:
    """Get TIR range label in configured units."""
    if GLUCOSE_UNITS == "mgdl":
        return f"{int(GLUCOSE_LOW)}-{int(GLUCOSE_HIGH)} mg/dL"
    else:
        return f"{mgdl_to_mmol(GLUCOSE_LOW):.1f}-{mgdl_to_mmol(GLUCOSE_HIGH):.1f} mmol/L"


def filter_valid_sgv(entries: list) -> list[int]:
    """Extract valid SGV values, filtering out sensor errors."""
    return [
        e["sgv"] for e in entries 
        if e.get("sgv") and e["sgv"] >= GLUCOSE_MIN_VALID
    ]


def calculate_stats(sgv_values: list[int]) -> dict | None:
    """Calculate glucose statistics."""
    if not sgv_values:
        return None
    
    n = len(sgv_values)
    avg = sum(sgv_values) / n
    variance = sum((v - avg) ** 2 for v in sgv_values) / n
    std_dev = variance ** 0.5
    cv = (std_dev / avg * 100) if avg > 0 else 0
    
    # Fixed ranges in mg/dL
    very_low = sum(1 for v in sgv_values if v < 54)           # <3.0 mmol/L
    low = sum(1 for v in sgv_values if 54 <= v < 70)          # 3.0-3.9 mmol/L
    # TIR uses configurable range
    in_range = sum(1 for v in sgv_values if GLUCOSE_LOW <= v <= GLUCOSE_HIGH)
    # Above target: from GLUCOSE_HIGH to 180 mg/dL (10 mmol/L)
    above_target = sum(1 for v in sgv_values if GLUCOSE_HIGH < v <= 180)
    high = sum(1 for v in sgv_values if 180 < v <= 250)       # 10.0-13.9 mmol/L
    very_high = sum(1 for v in sgv_values if v > 250)         # >13.9 mmol/L
    
    return {
        "count": n,
        "avg": round(avg, 1),
        "avg_formatted": format_glucose_short(avg),
        "std_dev": round(std_dev, 1),
        "std_dev_formatted": format_glucose_short(std_dev),
        "cv": round(cv, 1),
        "min": min(sgv_values),
        "max": max(sgv_values),
        "tir": round(in_range / n * 100, 1),
        "very_low_pct": round(very_low / n * 100, 1),
        "low_pct": round(low / n * 100, 1),
        "above_target_pct": round(above_target / n * 100, 1),
        "high_pct": round(high / n * 100, 1),
        "very_high_pct": round(very_high / n * 100, 1),
        "a1c": round((avg + 46.7) / 28.7, 1),
    }


def parse_date_to_timestamp(date_str: str) -> int:
    """Parse date string to timestamp (ms)."""
    import re
    
    # Relative: 7d, 2w, 3m, 1y
    match = re.match(r"^(\d+)([dwmy])$", date_str, re.I)
    if match:
        num = int(match.group(1))
        unit = match.group(2).lower()
        now = int(datetime.now(timezone.utc).timestamp() * 1000)
        multipliers = {"d": 86400000, "w": 604800000, "m": 2592000000, "y": 31536000000}
        return now - num * multipliers[unit]
    
    # YYYY-MM
    if re.match(r"^\d{4}-\d{2}$", date_str):
        dt = datetime.strptime(date_str + "-01", "%Y-%m-%d").replace(tzinfo=timezone.utc)
        return int(dt.timestamp() * 1000)
    
    # YYYY-MM-DD
    dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


class NightscoutClient:
    """HTTP client for Nightscout API."""
    
    def __init__(self):
        config = parse_nightscout_url(NIGHTSCOUT_URL)
        self.base_url = config["base_url"]
        self.token = config["token"]
        self.api_secret = NIGHTSCOUT_API_SECRET
    
    def _get_headers(self) -> dict:
        headers = {}
        # Try api-secret header (works with hashed secrets)
        if self.api_secret and len(self.api_secret) in (40, 64):
            # Looks like SHA1 (40) or SHA256 (64), use as header
            headers["api-secret"] = self.api_secret
        return headers
    
    def _add_token_param(self, params: dict | None) -> dict:
        """Add token query parameter for authentication."""
        result = dict(params) if params else {}
        if self.token:
            result["token"] = self.token
        return result
    
    async def fetch(self, endpoint: str, params: dict | None = None) -> list | dict:
        if not self.base_url:
            raise ValueError("NIGHTSCOUT_URL environment variable is not set")
        
        async with httpx.AsyncClient() as client:
            url = f"{self.base_url}{endpoint}"
            return await self._get_json_with_fallback(client, url, params)

    async def _get_json_with_fallback(
        self,
        client: httpx.AsyncClient,
        url: str,
        params: dict | None = None,
    ) -> list | dict:
        headers = dict(self._get_headers())
        headers["Accept"] = "application/json"

        resp = await client.get(
            url,
            params=self._add_token_param(params),
            headers=headers,
            timeout=30.0,
        )
        resp.raise_for_status()
        try:
            return resp.json()
        except ValueError:
            if not url.endswith(".json"):
                return await self._get_json_with_fallback(client, url + ".json", params)
            snippet = resp.text[:300].replace("\n", " ").strip()
            raise ValueError(f"Non-JSON response from {url}: {snippet}")
    
    async def fetch_entries_in_range(self, start_ts: int, end_ts: int, max_per_request: int = 10000) -> list:
        """Fetch all entries in date range with pagination."""
        all_entries = []
        current_end = end_ts
        
        for _ in range(100):  # Safety limit
            params = {
                "count": max_per_request,
                "find[date][$gte]": start_ts,
                "find[date][$lt]": current_end,
                "find[type]": "sgv",
            }
            
            async with httpx.AsyncClient() as client:
                url = f"{self.base_url}/api/v1/entries"
                entries = await self._get_json_with_fallback(client, url, params)
            
            if not entries:
                break
            
            all_entries.extend(entries)
            oldest_date = min(e["date"] for e in entries)
            
            if len(entries) < max_per_request or oldest_date <= start_ts:
                break
            
            current_end = oldest_date
        
        return all_entries


# Create server
server = Server("nightscout")
client = NightscoutClient()


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="glucose_current",
            description="Get the current blood glucose reading from Nightscout",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="glucose_history",
            description="Get blood glucose history for a specified time period",
            inputSchema={
                "type": "object",
                "properties": {
                    "hours": {
                        "type": "number",
                        "description": "Number of hours of history (1-720, i.e. up to 30 days)",
                        "default": 6,
                        "minimum": 1,
                        "maximum": 720,
                    },
                    "count": {
                        "type": "number",
                        "description": "Maximum readings to show in output",
                        "default": 100,
                        "minimum": 1,
                        "maximum": 1000,
                    },
                },
            },
        ),
        Tool(
            name="analyze",
            description="Analyze glucose patterns for any date range. Supports dates (YYYY-MM-DD), months (YYYY-MM), or relative periods (7d, 2w, 3m, 1y)",
            inputSchema={
                "type": "object",
                "properties": {
                    "from": {
                        "type": "string",
                        "description": "Start date: YYYY-MM-DD, YYYY-MM, or relative (7d, 2w, 3m, 1y)",
                        "default": "7d",
                    },
                    "to": {
                        "type": "string",
                        "description": "End date (optional, defaults to now): YYYY-MM-DD or YYYY-MM",
                    },
                    "tirGoal": {
                        "type": "number",
                        "description": "TIR goal percentage",
                        "default": 70,
                        "minimum": 50,
                        "maximum": 100,
                    },
                },
            },
        ),
        Tool(
            name="analyze_monthly",
            description="Analyze glucose data broken down by month. Great for yearly reviews.",
            inputSchema={
                "type": "object",
                "properties": {
                    "year": {
                        "type": "number",
                        "description": "Year to analyze",
                        "minimum": 2015,
                        "maximum": 2030,
                    },
                    "fromMonth": {
                        "type": "number",
                        "description": "Starting month (1-12)",
                        "default": 1,
                        "minimum": 1,
                        "maximum": 12,
                    },
                    "toMonth": {
                        "type": "number",
                        "description": "Ending month (1-12)",
                        "default": 12,
                        "minimum": 1,
                        "maximum": 12,
                    },
                    "tirGoal": {
                        "type": "number",
                        "description": "TIR goal percentage",
                        "default": 85,
                        "minimum": 50,
                        "maximum": 100,
                    },
                },
                "required": ["year"],
            },
        ),
        Tool(
            name="treatments",
            description="Get recent treatments (insulin doses, carbs, etc.)",
            inputSchema={
                "type": "object",
                "properties": {
                    "hours": {
                        "type": "number",
                        "description": "Hours of history (up to 7 days)",
                        "default": 24,
                        "minimum": 1,
                        "maximum": 168,
                    },
                    "count": {
                        "type": "number",
                        "description": "Maximum treatments to return",
                        "default": 50,
                        "minimum": 1,
                        "maximum": 200,
                    },
                },
            },
        ),
        Tool(
            name="status",
            description="Get Nightscout server status and settings",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="devices",
            description="Get status of connected devices (pump, CGM, phone)",
            inputSchema={
                "type": "object",
                "properties": {
                    "count": {
                        "type": "number",
                        "description": "Number of device status entries",
                        "default": 5,
                        "minimum": 1,
                        "maximum": 20,
                    },
                },
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    try:
        if name == "glucose_current":
            return await glucose_current()
        elif name == "glucose_history":
            return await glucose_history(
                arguments.get("hours", 6),
                arguments.get("count", 100),
            )
        elif name == "analyze":
            return await analyze(
                arguments.get("from", "7d"),
                arguments.get("to"),
                arguments.get("tirGoal", 70),
            )
        elif name == "analyze_monthly":
            return await analyze_monthly(
                arguments["year"],
                arguments.get("fromMonth", 1),
                arguments.get("toMonth", 12),
                arguments.get("tirGoal", 85),
            )
        elif name == "treatments":
            return await treatments(
                arguments.get("hours", 24),
                arguments.get("count", 50),
            )
        elif name == "status":
            return await status()
        elif name == "devices":
            return await devices(arguments.get("count", 5))
        else:
            return [TextContent(type="text", text=t("unknown_tool", name=name))]
    except Exception as e:
        return [TextContent(type="text", text=t("error", error=e))]


async def glucose_current() -> list[TextContent]:
    entries = await client.fetch("/api/v1/entries", {"count": 1})
    if not entries:
        return [TextContent(type="text", text=t("no_glucose"))]
    
    e = entries[0]
    arrow = DIRECTION_ARROWS.get(e.get("direction", ""), e.get("direction", ""))
    dt = datetime.fromtimestamp(e["date"] / 1000, tz=timezone.utc)
    delta = e.get('delta', 0)
    delta_formatted = format_glucose_short(abs(delta)) if GLUCOSE_UNITS == "mmol" else str(int(delta))
    
    text = (
        f"🩸 {t('current_glucose', value=format_glucose(e['sgv']), arrow=arrow)}\n"
        f"📅 {t('time_utc', time=dt.strftime('%Y-%m-%d %H:%M'))}\n"
        f"📈 {t('delta', sign='+' if delta >= 0 else '-', delta=delta_formatted)}\n"
        f"📱 {t('device', device=e.get('device', 'N/A'))}"
    )
    
    return [TextContent(type="text", text=text)]


async def glucose_history(hours: int, count: int) -> list[TextContent]:
    now = int(datetime.now(timezone.utc).timestamp() * 1000)
    start_ts = now - hours * 60 * 60 * 1000
    
    entries = await client.fetch_entries_in_range(start_ts, now)
    if not entries:
        return [TextContent(type="text", text=t("no_data_hours", hours=hours))]
    
    sgv_values = filter_valid_sgv(entries)
    stats = calculate_stats(sgv_values)
    
    text = (
        f"📊 {t('history_title', hours=hours, count=len(sgv_values))}\n\n"
        f"📈 {t('statistics')}\n"
        f"• {t('average', value=stats['avg_formatted'])}\n"
        f"• {t('min_max', min=format_glucose_short(stats['min']), max=format_glucose_short(stats['max']))}\n"
        f"• {t('tir', range=get_tir_range_label(), value=stats['tir'])}\n"
        f"• {t('cv', value=stats['cv'])}\n\n"
        f"📋 {t('recent_readings')}"
    )
    
    # Filter out sensor errors for display
    valid_entries = [e for e in entries if e.get("sgv") and e["sgv"] >= GLUCOSE_MIN_VALID]
    for e in valid_entries[:min(count, 15)]:
        dt = datetime.fromtimestamp(e["date"] / 1000, tz=timezone.utc)
        arrow = DIRECTION_ARROWS.get(e.get("direction", ""), "")
        text += f"\n• {dt.strftime('%m-%d %H:%M')}: {format_glucose_short(e['sgv'])} {arrow}"
    
    if len(valid_entries) > 15:
        text += f"\n{t('more_readings', count=len(valid_entries) - 15)}"
    
    return [TextContent(type="text", text=text)]


async def analyze(from_date: str, to_date: str | None, tir_goal: int) -> list[TextContent]:
    start_ts = parse_date_to_timestamp(from_date)
    end_ts = int(datetime.now(timezone.utc).timestamp() * 1000) if not to_date else parse_date_to_timestamp(to_date)
    
    # Adjust end date if month format
    if to_date and len(to_date) == 7:  # YYYY-MM
        year, month = map(int, to_date.split("-"))
        if month == 12:
            end_ts = int(datetime(year + 1, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
        else:
            end_ts = int(datetime(year, month + 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
    elif to_date and len(to_date) == 10:  # YYYY-MM-DD
        end_ts += 86400000  # End of day
    
    entries = await client.fetch_entries_in_range(start_ts, end_ts)
    if len(entries) < 10:
        return [TextContent(type="text", text=t("not_enough_data"))]
    
    sgv_values = filter_valid_sgv(entries)
    stats = calculate_stats(sgv_values)
    
    from_dt = datetime.fromtimestamp(start_ts / 1000, tz=timezone.utc)
    to_dt = datetime.fromtimestamp(end_ts / 1000, tz=timezone.utc)
    days = (end_ts - start_ts) // 86400000
    
    tir_status = "✅" if stats["tir"] >= tir_goal else "⚠️" if stats["tir"] >= 70 else "❌"
    cv_status = "✅" if stats["cv"] <= 33 else "⚠️" if stats["cv"] <= 36 else "❌"
    
    tir_label = get_tir_range_label()
    
    count_str = f"{stats['count']:,}"
    text = (
        f"📊 {t('analysis_title', from_date=from_dt.strftime('%Y-%m-%d'), to_date=to_dt.strftime('%Y-%m-%d'), days=days, count=count_str)}\n\n"
        f"📈 {t('key_metrics')}\n"
        f"• {t('avg_glucose', value=stats['avg_formatted'])}\n"
        f"• {t('min_max', min=format_glucose_short(stats['min']), max=format_glucose_short(stats['max']))}\n"
        f"• {t('std_dev', value=stats['std_dev_formatted'])}\n"
        f"• {t('cv', value=stats['cv'])} {cv_status}\n"
        f"• {t('estimated_a1c', value=stats['a1c'])}\n\n"
        f"🎯 {t('time_in_ranges')}\n"
        f"• 🔴 {t('severe_hypo', value=stats['very_low_pct'])}\n"
        f"• 🟠 {t('hypo', value=stats['low_pct'])}\n"
        f"• 🟢 {t('in_target', range=tir_label, value=stats['tir'], status=tir_status, goal=tir_goal)}\n"
        f"• 🟡 {t('above_target', value=stats['above_target_pct'])}\n"
        f"• 🟠 {t('high', value=stats['high_pct'])}\n"
        f"• 🔴 {t('very_high', value=stats['very_high_pct'])}\n\n"
        f"💡 {t('assessment')}"
    )
    
    if stats["tir"] >= tir_goal:
        text += f"\n• {t('tir_goal_met', goal=tir_goal)}"
    else:
        diff_str = f"{tir_goal - stats['tir']:.1f}"
        text += f"\n• {t('tir_goal_away', diff=diff_str, goal=tir_goal)}"
    
    if stats["cv"] <= 33:
        text += f"\n• {t('cv_excellent')}"
    elif stats["cv"] <= 36:
        text += f"\n• {t('cv_good')}"
    else:
        text += f"\n• {t('cv_high')}"
    
    return [TextContent(type="text", text=text)]


async def analyze_monthly(year: int, from_month: int, to_month: int, tir_goal: int) -> list[TextContent]:
    if LOCALE == "ru":
        month_names = ["", "Янв", "Фев", "Мар", "Апр", "Май", "Июн", "Июл", "Авг", "Сен", "Окт", "Ноя", "Дек"]
    else:
        month_names = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    results = []
    
    tir_label = get_tir_range_label()
    
    text = f"📊 {t('monthly_title', year=year, goal=tir_goal)}\n"
    text += "=" * 80 + "\n"
    text += f"{t('month_header', range=tir_label)}\n"
    text += "-" * 80 + "\n"
    
    for month in range(from_month, to_month + 1):
        start_dt = datetime(year, month, 1, tzinfo=timezone.utc)
        if month == 12:
            end_dt = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            end_dt = datetime(year, month + 1, 1, tzinfo=timezone.utc)
        
        start_ts = int(start_dt.timestamp() * 1000)
        end_ts = int(end_dt.timestamp() * 1000)
        
        try:
            entries = await client.fetch_entries_in_range(start_ts, end_ts)
            sgv_values = filter_valid_sgv(entries)
            stats = calculate_stats(sgv_values)
            
            if stats and stats["count"] > 0:
                results.append({"month": month, "stats": stats})
                tir_emoji = "✅" if stats["tir"] >= tir_goal else "⚠️" if stats["tir"] >= 70 else "❌"
                cv_emoji = "✅" if stats["cv"] <= 33 else "⚠️" if stats["cv"] <= 36 else "❌"
                text += f"{month_names[month]:5} │ {stats['tir']:6.1f}% {tir_emoji}    │ {stats['avg_formatted']:>5} │ {stats['cv']:5.1f}% {cv_emoji} │ {stats['a1c']:4.1f}% │ {stats['count']:>8,}\n"
            else:
                text += f"{month_names[month]:5} │ {t('no_data')}\n"
        except Exception as e:
            text += f"{month_names[month]:5} │ Error: {str(e)[:40]}\n"
    
    text += "=" * 80 + "\n"
    
    if results:
        avg_tir = sum(r["stats"]["tir"] for r in results) / len(results)
        avg_cv = sum(r["stats"]["cv"] for r in results) / len(results)
        avg_glucose = sum(r["stats"]["avg"] for r in results) / len(results)
        avg_a1c = sum(r["stats"]["a1c"] for r in results) / len(results)
        total_count = sum(r["stats"]["count"] for r in results)
        
        tir_status = "✅ GOAL MET" if avg_tir >= tir_goal else f"⚠️ {tir_goal - avg_tir:.1f}% to goal"
        
        total_str = f"{total_count:,}"
        text += f"\n📈 {t('summary', months=len(results), count=total_str)}\n"
        text += "-" * 60 + "\n"
        text += f"🎯 {t('avg_tir', range=tir_label, value=f'{avg_tir:.1f}', status=tir_status)}\n"
        text += f"📊 {t('avg_glucose', value=format_glucose(avg_glucose))}\n"
        if avg_cv <= 33:
            cv_status_label = t("cv_status_stable")
        elif avg_cv <= 36:
            cv_status_label = t("cv_status_ok")
        else:
            cv_status_label = t("cv_status_high")
        text += f"📉 {t('avg_cv', value=f'{avg_cv:.1f}', status=cv_status_label)}\n"
        text += f"🩸 {t('avg_a1c', value=f'{avg_a1c:.1f}')}\n"
        
        # Best/worst
        best = max(results, key=lambda r: r["stats"]["tir"])
        worst = min(results, key=lambda r: r["stats"]["tir"])
        best_tir_str = f"{best['stats']['tir']:.1f}"
        worst_tir_str = f"{worst['stats']['tir']:.1f}"
        text += f"\n🏆 {t('best_tir', month=month_names[best['month']], value=best_tir_str)}\n"
        text += f"📉 {t('worst_tir', month=month_names[worst['month']], value=worst_tir_str)}\n"
    
    return [TextContent(type="text", text=text)]


async def treatments(hours: int, count: int) -> list[TextContent]:
    now = datetime.now(timezone.utc)
    start_dt = now.timestamp() * 1000 - hours * 60 * 60 * 1000
    
    params = {
        "count": count,
        "find[created_at][$gte]": datetime.fromtimestamp(start_dt / 1000, tz=timezone.utc).isoformat(),
    }
    
    data = await client.fetch("/api/v1/treatments", params)
    if not data:
        return [TextContent(type="text", text=t("no_treatments", hours=hours))]
    
    total_insulin = 0
    total_carbs = 0
    text = f"💉 {t('treatments_title', hours=hours)}\n"
    
    for t in data:
        dt = datetime.fromisoformat(t["created_at"].replace("Z", "+00:00"))
        line = f"• {dt.strftime('%m-%d %H:%M')}: "
        if t.get("eventType"):
            line += f"[{t['eventType']}] "
        if t.get("insulin"):
            line += f"💉 {t['insulin']} U "
            total_insulin += t["insulin"]
        if t.get("carbs"):
            line += f"🍞 {t['carbs']} g "
            total_carbs += t["carbs"]
        if t.get("notes"):
            line += f"📝 {t['notes']}"
        text += line + "\n"
    
    text += f"\n📊 {t('totals')}"
    if total_insulin > 0:
        text += f" 💉 {total_insulin:.1f} U"
    if total_carbs > 0:
        text += f" 🍞 {total_carbs} g"
    
    return [TextContent(type="text", text=text)]


async def status() -> list[TextContent]:
    data = await client.fetch("/api/v1/status")
    
    text = (
        f"⚙️ {t('status_title')}\n"
        f"• {t('status_name', value=data.get('name', 'N/A'))}\n"
        f"• {t('status_version', value=data.get('version', 'N/A'))}\n"
        f"• {t('status_time', value=data.get('serverTime', 'N/A'))}\n"
        f"• {t('status_units', value=data.get('settings', {}).get('units', 'mg/dl'))}"
    )
    
    thresholds = data.get("settings", {}).get("thresholds")
    if thresholds:
        text += (
            f"\n\n🎯 {t('thresholds')}\n"
            f"• {t('high_label', value=thresholds.get('bgHigh'))}\n"
            f"• {t('target_top', value=thresholds.get('bgTargetTop'))}\n"
            f"• {t('target_bottom', value=thresholds.get('bgTargetBottom'))}\n"
            f"• {t('low_label', value=thresholds.get('bgLow'))}"
        )
    
    return [TextContent(type="text", text=text)]


async def devices(count: int) -> list[TextContent]:
    data = await client.fetch("/api/v1/devicestatus", {"count": count})
    if not data:
        return [TextContent(type="text", text=t("no_device_data"))]
    
    text = f"📱 {t('devices_title')}\n"
    
    for d in data:
        dt = datetime.fromisoformat(d["created_at"].replace("Z", "+00:00"))
        text += f"\n⏰ {dt.strftime('%H:%M')}:"
        if d.get("uploader"):
            text += f"\n  📱 {t('uploader', value=d['uploader'].get('battery', '?'))}"
        if d.get("pump"):
            pump = d["pump"]
            text += f"\n  💉 {t('pump', reservoir=pump.get('reservoir', '?'), battery=pump.get('battery', {}).get('percent', '?'))}"
        if d.get("device"):
            text += f"\n  📡 {t('device_label', value=d['device'])}"
    
    return [TextContent(type="text", text=text)]


def main():
    """Main entry point."""
    async def run():
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())
    
    asyncio.run(run())


if __name__ == "__main__":
    main()
