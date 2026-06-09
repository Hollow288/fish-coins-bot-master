"""把基金数据 + AI 点评渲染成一张美观长图（bytes）。

净值曲线用纯 Python 计算内联 SVG（红涨绿跌），不依赖任何 JS 图表库 / 网络，
配合 Jinja2 模板 + Playwright set_content 截图。字体走 FONT_HOST（同 model_utils）。
"""
import os
from datetime import datetime

import pytz
from jinja2 import Environment, FileSystemLoader
from nonebot.log import logger
from playwright.async_api import async_playwright

# 模板与项目其它模板统一放在根目录 templates/（loader 相对运行目录，同 image_utils.py）
_TEMPLATE_NAME = "template-fund-report.html"

# 红涨绿跌
_COLOR_UP = "#e64539"
_COLOR_DOWN = "#13a05c"
_COLOR_FLAT = "#8a8f99"


def _is_num(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _fmt_pct(value, *, signed: bool = False) -> str:
    if not _is_num(value):
        return "—"
    return f"{value:+.2f}%" if signed else f"{value:.2f}%"


def _fmt_num(value, digits: int = 2) -> str:
    if not _is_num(value):
        return "—"
    return f"{value:.{digits}f}"


def _change_class(value) -> str:
    if not _is_num(value) or value == 0:
        return "flat"
    return "up" if value > 0 else "down"


def _build_chart_svg(points: list[dict], code: str) -> str | None:
    """把走势点位算成内联 SVG 折线+渐变面积图。点数 < 2 返回 None。"""
    navs = [(p.get("unitNav"), p.get("date")) for p in points if _is_num(p.get("unitNav"))]
    if len(navs) < 2:
        return None

    width, height = 820.0, 240.0
    ml, mr, mt, mb = 12.0, 12.0, 26.0, 26.0
    plot_w = width - ml - mr
    plot_h = height - mt - mb
    bottom_y = mt + plot_h

    values = [v for v, _ in navs]
    lo, hi = min(values), max(values)
    span = hi - lo

    n = len(values)
    coords: list[tuple[float, float]] = []
    for i, v in enumerate(values):
        x = ml + plot_w * (i / (n - 1))
        if span <= 0:
            y = mt + plot_h / 2
        else:
            y = mt + plot_h * (1 - (v - lo) / span)
        coords.append((x, y))

    rising = values[-1] >= values[0]
    color = _COLOR_UP if rising else _COLOR_DOWN
    grad_id = f"fundgrad-{code}"

    line_pts = " ".join(f"{x:.2f},{y:.2f}" for x, y in coords)
    area_d = (
        f"M {coords[0][0]:.2f},{bottom_y:.2f} "
        + " ".join(f"L {x:.2f},{y:.2f}" for x, y in coords)
        + f" L {coords[-1][0]:.2f},{bottom_y:.2f} Z"
    )

    # 起点净值参考虚线（区分涨/跌区域）
    if span <= 0:
        base_y = mt + plot_h / 2
    else:
        base_y = mt + plot_h * (1 - (values[0] - lo) / span)

    sx, sy = coords[0]
    ex, ey = coords[-1]

    return (
        f'<svg class="chart" viewBox="0 0 {width:.0f} {height:.0f}" '
        f'xmlns="http://www.w3.org/2000/svg">'
        f'<defs><linearGradient id="{grad_id}" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0%" stop-color="{color}" stop-opacity="0.28"/>'
        f'<stop offset="100%" stop-color="{color}" stop-opacity="0.02"/>'
        f"</linearGradient></defs>"
        f'<line x1="{ml:.2f}" y1="{base_y:.2f}" x2="{width - mr:.2f}" y2="{base_y:.2f}" '
        f'stroke="#c9ced6" stroke-width="1" stroke-dasharray="4 4"/>'
        f'<path d="{area_d}" fill="url(#{grad_id})"/>'
        f'<polyline points="{line_pts}" fill="none" stroke="{color}" '
        f'stroke-width="2.4" stroke-linejoin="round" stroke-linecap="round"/>'
        f'<circle cx="{sx:.2f}" cy="{sy:.2f}" r="3.2" fill="#fff" stroke="{color}" stroke-width="2"/>'
        f'<circle cx="{ex:.2f}" cy="{ey:.2f}" r="3.8" fill="{color}"/>'
        f'<text x="{ml:.2f}" y="16" class="chart-hi" fill="{_COLOR_FLAT}">最高 {hi:.4f}</text>'
        f'<text x="{width - mr:.2f}" y="{height - 8:.0f}" text-anchor="end" '
        f'class="chart-lo" fill="{_COLOR_FLAT}">最低 {lo:.4f}</text>'
        f"</svg>"
    )


def _build_period_ranks(period_ranks) -> list[dict]:
    rows: list[dict] = []
    if not isinstance(period_ranks, list):
        return rows
    for item in period_ranks:
        if not isinstance(item, dict):
            continue
        rank_no = item.get("rankNo")
        rank_total = item.get("rankTotal")
        if _is_num(rank_no) and _is_num(rank_total):
            rank_display = f"{int(rank_no)}/{int(rank_total)}"
        else:
            rank_display = "—"
        rows.append(
            {
                "name": item.get("periodName") or "—",
                "fund_return": _fmt_pct(item.get("fundReturn"), signed=True),
                "fund_class": _change_class(item.get("fundReturn")),
                "similar": _fmt_pct(item.get("similarAverageReturn"), signed=True),
                "benchmark": _fmt_pct(item.get("benchmarkReturn"), signed=True),
                "rank": rank_display,
            }
        )
    return rows


def _build_fund_vm(review: dict, trend: dict | None, ai_text: str) -> dict:
    """把单只基金的接口数据 + AI 点评整理成模板可直接摆放的视图模型。"""
    code = str(review.get("fundCode") or "")

    returns = [
        {"label": "近1月", "value": _fmt_pct(review.get("return1m"), signed=True),
         "cls": _change_class(review.get("return1m"))},
        {"label": "近3月", "value": _fmt_pct(review.get("return3m"), signed=True),
         "cls": _change_class(review.get("return3m"))},
        {"label": "近6月", "value": _fmt_pct(review.get("return6m"), signed=True),
         "cls": _change_class(review.get("return6m"))},
        {"label": "近1年", "value": _fmt_pct(review.get("return1y"), signed=True),
         "cls": _change_class(review.get("return1y"))},
    ]
    has_returns = any(
        _is_num(review.get(k)) for k in ("return1m", "return3m", "return6m", "return1y")
    )

    risk = [
        {"label": "最大回撤", "value": _fmt_pct(review.get("maxDrawdown")), "cls": "down"},
        {"label": "年化波动", "value": _fmt_pct(review.get("volatility")), "cls": "flat"},
        {"label": "年化收益", "value": _fmt_pct(review.get("annualizedReturn"), signed=True),
         "cls": _change_class(review.get("annualizedReturn"))},
        {"label": "夏普比率", "value": _fmt_num(review.get("sharpeRatio")), "cls": "flat"},
        {"label": "卡玛比率", "value": _fmt_num(review.get("calmarRatio")), "cls": "flat"},
    ]
    has_risk = any(
        _is_num(review.get(k))
        for k in ("maxDrawdown", "volatility", "annualizedReturn", "sharpeRatio", "calmarRatio")
    )

    manager = {
        "name": review.get("managerName") or "—",
        "star": int(review["managerStar"]) if _is_num(review.get("managerStar")) else 0,
        "work_time": review.get("managerWorkTime") or "—",
        "size": review.get("managerSize") or "—",
        "score": _fmt_num(review.get("managerScore")),
    }
    has_manager = bool(review.get("managerName"))

    chart_svg = None
    if isinstance(trend, dict):
        chart_svg = _build_chart_svg(trend.get("points") or [], code or "x")

    return {
        "code": code,
        "name": review.get("fundName") or code or "—",
        "type": review.get("fundType") or "基金",
        "as_of": review.get("asOf") or "—",
        "nav": _fmt_num(review.get("latestNav"), 4),
        "growth": _fmt_pct(review.get("latestGrowthRate"), signed=True),
        "growth_class": _change_class(review.get("latestGrowthRate")),
        "returns": returns,
        "has_returns": has_returns,
        "risk": risk,
        "has_risk": has_risk,
        "high_nav": _fmt_num(review.get("highNav"), 4),
        "high_date": review.get("highDate") or "—",
        "low_nav": _fmt_num(review.get("lowNav"), 4),
        "low_date": review.get("lowDate") or "—",
        "similar_percent": _fmt_num(review.get("similarPercent"), 1),
        "has_similar": _is_num(review.get("similarPercent")),
        "fund_scale": _fmt_num(review.get("fundScale")),
        "has_scale": _is_num(review.get("fundScale")),
        "manager": manager,
        "has_manager": has_manager,
        "ranks": _build_period_ranks(review.get("periodRanks")),
        "chart_svg": chart_svg,
        "ai_text": ai_text,
        "note": review.get("note"),
    }


def build_view_models(items: list[dict]) -> list[dict]:
    """items: [{review, trend, ai_text}]，跳过 review 为空者。"""
    vms: list[dict] = []
    for item in items:
        review = item.get("review")
        if not isinstance(review, dict):
            continue
        vms.append(_build_fund_vm(review, item.get("trend"), item.get("ai_text") or ""))
    return vms


async def render_report(items: list[dict]) -> bytes | None:
    """渲染长图，返回 PNG bytes；无可用数据或渲染失败返回 None。"""
    vms = build_view_models(items)
    if not vms:
        logger.error("[fund] 无可渲染的基金数据，跳过出图。")
        return None

    tz = pytz.timezone("Asia/Shanghai")
    now = datetime.now(tz)
    as_of_dates = [vm["as_of"] for vm in vms if vm["as_of"] and vm["as_of"] != "—"]
    data_as_of = max(as_of_dates) if as_of_dates else now.strftime("%Y-%m-%d")

    font_host = os.getenv("FONT_HOST") or ""
    data = {
        "funds": vms,
        "count": len(vms),
        "data_as_of": data_as_of,
        "generated_at": now.strftime("%Y-%m-%d %H:%M"),
        "AlibabaPuHuiTi": font_host + "AlibabaPuHuiTi-3-45-Light.otf",
        "ZCOOLKuaiLe": font_host + "ZCOOLKuaiLe-Regular.ttf",
    }

    env = Environment(loader=FileSystemLoader("templates"), autoescape=True)
    template = env.get_template(_TEMPLATE_NAME)
    html_content = template.render(**data)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            page = await browser.new_page(
                viewport={"width": 960, "height": 900}, device_scale_factor=2
            )
            await page.set_content(html_content, timeout=60000)
            await page.wait_for_timeout(600)  # 等远程字体加载
            locator = page.locator(".report")
            image_bytes = await locator.screenshot()
            await page.close()
            return image_bytes
        finally:
            await browser.close()
