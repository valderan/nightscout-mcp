"""Local console test client for Nightscout MCP tools."""

import asyncio
import os
from typing import Callable, Awaitable


def load_dotenv(path: str = ".env") -> None:
    if not os.path.isfile(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip("'").strip('"')
            if key and key not in os.environ:
                os.environ[key] = value


load_dotenv()

from nightscout_mcp import server as ns


LOCALE = os.environ.get("LOCALE", "en").lower()

STRINGS = {
    "en": {
        "missing_env": "Missing NIGHTSCOUT_URL in environment.",
        "client_title": "Nightscout MCP Local Test Client",
        "choose_tool": "Choose a tool:",
        "select": "Select",
        "exit": "exit",
        "unknown_option": "Unknown option.",
        "enter_int": "Enter a valid integer.",
        "glucose_current": "glucose_current",
        "glucose_history": "glucose_history",
        "analyze": "analyze",
        "analyze_monthly": "analyze_monthly",
        "treatments": "treatments",
        "status": "status",
        "devices": "devices",
        "insulin_log": "insulin_log",
        "pump_reservoir": "pump_reservoir",
        "run_all": "run all",
        "hours": "Hours (1-720)",
        "max_readings": "Max readings to show",
        "from_date": "From (YYYY-MM-DD | YYYY-MM | 7d/2w/3m/1y)",
        "to_date": "To (YYYY-MM-DD | YYYY-MM | empty for now)",
        "tir_goal": "TIR goal %",
        "year": "Year",
        "from_month": "From month (1-12)",
        "to_month": "To month (1-12)",
        "treatments_hours": "Hours (1-168)",
        "treatments_count": "Max treatments to return",
        "device_count": "Device entries count",
        "insulin_hours": "Hours (1-168)",
        "insulin_count": "Max insulin entries to return",
        "error": "Error: {error}",
    },
    "ru": {
        "missing_env": "Отсутствует NIGHTSCOUT_URL в окружении.",
        "client_title": "Nightscout MCP Локальный Тест Клиент",
        "choose_tool": "Выберите инструмент:",
        "select": "Выбор",
        "exit": "выход",
        "unknown_option": "Неизвестный вариант.",
        "enter_int": "Введите корректное целое число.",
        "glucose_current": "glucose_current",
        "glucose_history": "glucose_history",
        "analyze": "analyze",
        "analyze_monthly": "analyze_monthly",
        "treatments": "treatments",
        "status": "status",
        "devices": "devices",
        "insulin_log": "insulin_log",
        "pump_reservoir": "pump_reservoir",
        "run_all": "запустить все",
        "hours": "Часы (1-720)",
        "max_readings": "Макс. показаний",
        "from_date": "С (YYYY-MM-DD | YYYY-MM | 7d/2w/3m/1y)",
        "to_date": "До (YYYY-MM-DD | YYYY-MM | пусто = сейчас)",
        "tir_goal": "Цель TIR %",
        "year": "Год",
        "from_month": "С какого месяца (1-12)",
        "to_month": "До какого месяца (1-12)",
        "treatments_hours": "Часы (1-168)",
        "treatments_count": "Макс. терапий",
        "device_count": "Кол-во записей устройств",
        "insulin_hours": "Часы (1-168)",
        "insulin_count": "Макс. инсулин. записей",
        "error": "Ошибка: {error}",
    },
}


def t(key: str, **kwargs) -> str:
    lang = "ru" if LOCALE == "ru" else "en"
    template = STRINGS[lang].get(key, STRINGS["en"].get(key, key))
    return template.format(**kwargs)


def _require_env() -> None:
    if not os.environ.get("NIGHTSCOUT_URL"):
        raise SystemExit(t("missing_env"))


def _print_result(result) -> None:
    if isinstance(result, list):
        for item in result:
            text = getattr(item, "text", str(item))
            print(text)
    else:
        print(result)


async def _call_glucose_current() -> None:
    _print_result(await ns.glucose_current())


async def _call_glucose_history() -> None:
    hours = _read_int(t("hours"), default=6)
    count = _read_int(t("max_readings"), default=100)
    _print_result(await ns.glucose_history(hours, count))


async def _call_analyze() -> None:
    from_date = _read_str(t("from_date"), default="7d")
    to_date = _read_str(t("to_date"), default="")
    tir_goal = _read_int(t("tir_goal"), default=70)
    _print_result(await ns.analyze(from_date, to_date or None, tir_goal))


async def _call_analyze_monthly() -> None:
    year = _read_int(t("year"), default=2025)
    from_month = _read_int(t("from_month"), default=1)
    to_month = _read_int(t("to_month"), default=12)
    tir_goal = _read_int(t("tir_goal"), default=85)
    _print_result(await ns.analyze_monthly(year, from_month, to_month, tir_goal))


async def _call_treatments() -> None:
    hours = _read_int(t("treatments_hours"), default=24)
    count = _read_int(t("treatments_count"), default=50)
    _print_result(await ns.treatments(hours, count))


async def _call_status() -> None:
    _print_result(await ns.status())


async def _call_devices() -> None:
    count = _read_int(t("device_count"), default=5)
    _print_result(await ns.devices(count))


async def _call_insulin_log() -> None:
    hours = _read_int(t("insulin_hours"), default=24)
    count = _read_int(t("insulin_count"), default=50)
    _print_result(await ns.insulin_log(hours, count))


async def _call_pump_reservoir() -> None:
    _print_result(await ns.pump_reservoir())


async def _call_all() -> None:
    print("\n== glucose_current ==")
    await _call_glucose_current()
    print("\n== glucose_history ==")
    await _call_glucose_history()
    print("\n== analyze ==")
    await _call_analyze()
    print("\n== analyze_monthly ==")
    await _call_analyze_monthly()
    print("\n== treatments ==")
    await _call_treatments()
    print("\n== insulin_log ==")
    await _call_insulin_log()
    print("\n== pump_reservoir ==")
    await _call_pump_reservoir()
    print("\n== status ==")
    await _call_status()
    print("\n== devices ==")
    await _call_devices()


def _read_str(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{prompt}{suffix}: ").strip()
    return value or default


def _read_int(prompt: str, default: int = 0) -> int:
    while True:
        raw = _read_str(prompt, str(default) if default else "")
        try:
            return int(raw)
        except ValueError:
            print(t("enter_int"))


MENU: dict[str, tuple[str, Callable[[], Awaitable[None]]]] = {
    "1": (t("glucose_current"), _call_glucose_current),
    "2": (t("glucose_history"), _call_glucose_history),
    "3": (t("analyze"), _call_analyze),
    "4": (t("analyze_monthly"), _call_analyze_monthly),
    "5": (t("treatments"), _call_treatments),
    "6": (t("insulin_log"), _call_insulin_log),
    "7": (t("pump_reservoir"), _call_pump_reservoir),
    "8": (t("status"), _call_status),
    "9": (t("devices"), _call_devices),
    "10": (t("run_all"), _call_all),
}


def main() -> None:
    _require_env()
    print(f"{t('client_title')}\n")
    while True:
        print(f"\n{t('choose_tool')}")
        for key, (label, _) in MENU.items():
            print(f"{key}. {label}")
        print(f"0. {t('exit')}")
        choice = input(f"\n{t('select')}: ").strip()
        if choice == "0":
            return
        if choice not in MENU:
            print(t("unknown_option"))
            continue
        _, fn = MENU[choice]
        try:
            asyncio.run(fn())
        except Exception as exc:
            print(t("error", error=exc))


if __name__ == "__main__":
    main()
