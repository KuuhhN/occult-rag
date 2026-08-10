# -*- coding: utf-8 -*-
"""占星择时路由：行星时计算 / 行星状态 / 做符最佳时机推荐

计算核心复用 scripts/planetary_hours.py（ephem 离线天文算法）：
- GET /planetary-hours?date=&city=&lat=&lon= → 行星时时间表 + 行星状态
- GET /planetary-hours/best-time?kind=&date=&city= → 未来 N 天最佳做符窗口

做符规则（talisman_rules）为基础版硬编码 JSON——从 PGM / Seven Spheres /
所罗门小钥匙等现有魔法文献提取的行星对应规则；资料到位后可升级为 RAG 检索增强。
"""
import datetime
import sys
import os

# planetary_hours.py 位于 global-workspace/scripts/（计算核心，不入 occult-rag 仓库）
# 候选路径覆盖：从 backend/app/routes/ 上溯到 global-workspace/scripts
_routes_dir = os.path.dirname(os.path.abspath(__file__))
_scripts_candidates = [
    os.path.join(_routes_dir, "..", "..", "..", "..", "..", "scripts"),  # workspace/scripts
    os.path.join(_routes_dir, "..", "..", "..", "..", "scripts"),        # occult-rag/scripts
]
for _p in _scripts_candidates:
    if os.path.exists(os.path.join(_p, "planetary_hours.py")):
        sys.path.insert(0, _p)
        break

from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/planetary-hours", tags=["astro"])

try:
    import planetary_hours as ph
    _ph_ok = True
except Exception:
    ph = None
    _ph_ok = False


def _load_city_table() -> dict:
    """加载内置中国城市坐标表（china_cities.json）"""
    import json
    p = os.path.join(os.path.dirname(__file__), "..", "data", "china_cities.json")
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


_CITY_TABLE = _load_city_table()


def _resolve_city(city: str | None, lat: float | None, lon: float | None):
    """解析地点：城市表精确/模糊匹配 → 经纬度 → 默认内江"""
    if lat is not None and lon is not None:
        return (lat, lon), (city or "")
    name = (city or "").strip()
    if name:
        # 精确匹配
        if name in _CITY_TABLE:
            return tuple(_CITY_TABLE[name]), name
        if ph and name in ph.CITIES:
            return ph.CITIES[name], name
        # 模糊匹配（"成都市"→"成都"，"内江市"→"内江"）
        for c, coord in _CITY_TABLE.items():
            if name in c or c in name:
                return tuple(coord), c
        for c, coord in ph.CITIES.items():
            if name in c or c in name:
                return coord, c
    # 默认内江
    if "内江" in _CITY_TABLE:
        return tuple(_CITY_TABLE["内江"]), "内江"
    return (29.5803, 105.0584), "内江"


@router.get("/cities")
async def list_cities():
    """内置中国城市坐标表（前端城市选择用）"""
    return {"cities": sorted(_CITY_TABLE.keys())}


@router.get("")
async def planetary_hours(
    date: str = Query(default="", description="日期 YYYY-MM-DD（默认今天）"),
    city: str = Query(default="", description="城市名"),
    lat: float | None = Query(default=None),
    lon: float | None = Query(default=None),
):
    """行星时时间表 + 行星状态"""
    if not _ph_ok:
        raise HTTPException(500, "行星时计算模块不可用（缺 ephem 依赖）")
    if not date:
        date = datetime.datetime.now(datetime.timezone(
            datetime.timedelta(hours=8))).strftime("%Y-%m-%d")

    (plat, plon), city_name = _resolve_city(city, lat, lon)
    result = ph.compute_planetary_hours(date, plat, plon)
    if "error" in result:
        raise HTTPException(400, result["error"])

    noon_utc = datetime.datetime.fromisoformat(
        f"{date}T12:00:00+08:00").astimezone(datetime.timezone.utc)
    planet_states = []
    for p in ph.PLANET_EPHEM:
        try:
            planet_states.append(ph.get_planet_state(
                p, plat, plon, noon_utc.strftime("%Y/%m/%d %H:%M")))
        except Exception:
            pass

    return {
        **result,
        "city": city_name,
        "planet_states": planet_states,
    }


@router.get("/best-time")
async def best_time(
    kind: str = Query(..., description="符咒类型（爱情/财富/保护/智慧/幸运/沟通）"),
    date: str = Query(default="", description="起始日期 YYYY-MM-DD（默认今天）"),
    days: int = Query(default=7, ge=1, le=30, description="扫描天数"),
    city: str = Query(default="", description="城市名"),
    lat: float | None = Query(default=None),
    lon: float | None = Query(default=None),
):
    """一键推荐最佳做符时间：匹配行星 → 扫描未来 N 天行星时 + 行星状态"""
    if not _ph_ok:
        raise HTTPException(500, "行星时计算模块不可用（缺 ephem 依赖）")
    try:
        rules = load_talisman_rules()
    except Exception:
        raise HTTPException(500, "做符规则加载失败")

    planet = rules.get(kind)
    if not planet:
        raise HTTPException(404, f"未知符咒类型: {kind}，可选: {list(rules.keys())}")

    if not date:
        date = datetime.datetime.now(datetime.timezone(
            datetime.timedelta(hours=8))).strftime("%Y-%m-%d")
    (plat, plon), city_name = _resolve_city(city, lat, lon)

    # 扫描未来 N 天：每天计算行星时 + 行星状态，找目标行星的最佳窗口
    windows = []
    start = datetime.date.fromisoformat(date)
    for i in range(days):
        d = (start + datetime.timedelta(days=i)).isoformat()
        try:
            hours = ph.compute_planetary_hours(d, plat, plon)
        except Exception:
            continue
        if "error" in hours:
            continue
        noon_utc = datetime.datetime.fromisoformat(
            f"{d}T12:00:00+08:00").astimezone(datetime.timezone.utc)
        try:
            pstate = ph.get_planet_state(
                planet, plat, plon, noon_utc.strftime("%Y/%m/%d %H:%M"))
        except Exception:
            continue

        # 行星时中属于目标行星的时段（白昼+夜晚）
        for h in hours["hours"]:
            if h["planet"] == planet:
                windows.append({
                    "date": d,
                    "day_night": h["day_night"],
                    "start": h["start"],
                    "end": h["end"],
                    "sign": pstate.get("sign", ""),
                    "retrograde": pstate.get("retrograde", False),
                    "status": pstate.get("status", []),
                    "day_ruler": hours.get("day_ruler", ""),
                })

    # 排序：入庙/擢升优先、非逆行优先、日期近优先
    def score(w):
        s = 0
        if "入庙" in w["status"]:
            s += 2
        if "擢升" in w["status"]:
            s += 3
        if w["retrograde"]:
            s -= 4
        return s

    windows.sort(key=lambda w: (-score(w), w["date"], w["start"]))
    return {
        "kind": kind,
        "planet": planet,
        "city": city_name,
        "start_date": date,
        "days": days,
        "windows": windows[:10],
    }


def load_talisman_rules() -> dict:
    """做符规则基础版：符咒类型 → 对应行星（硬编码 JSON，来源见 data/talisman_rules.json）"""
    import json
    p = os.path.join(os.path.dirname(__file__), "..", "data", "talisman_rules.json")
    with open(p, encoding="utf-8") as f:
        return json.load(f)
