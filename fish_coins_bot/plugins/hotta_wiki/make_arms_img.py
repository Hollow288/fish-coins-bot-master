
from nonebot import get_bot,require
from pathlib import Path
from playwright.async_api import async_playwright
from fish_coins_bot.database.hotta.arms import Arms,ArmsStarRatings,ArmsCharacteristics,ArmsExclusives
from jinja2 import Environment, FileSystemLoader
from fish_coins_bot.utils.model_utils import make_arms_img_url, highlight_numbers, sanitize_filename

require("nonebot_plugin_apscheduler")

from nonebot_plugin_apscheduler import scheduler

@scheduler.scheduled_job("cron", hour=3, minute=0, second=0, id="arms_img_scheduled")
async def arms_img_scheduled():
    arms_list = await Arms.all().values("arms_id", "arms_type", "arms_attribute", "arms_name", "arms_overwhelmed",
                                        "arms_charging_energy", "arms_thumbnail_url")

    # 创建 Jinja2 环境
    env = Environment(loader=FileSystemLoader('templates'))
    env.filters['highlight_numbers'] = highlight_numbers  # 注册过滤器

    async with async_playwright() as p:
        browser = await p.firefox.launch(headless=True)
        page = await browser.new_page()

        for arms in arms_list:
            make_arms_img_url(arms)

            # 星级
            star_ratings = await ArmsStarRatings.filter(arms_id=arms["arms_id"]).values("items_name", "items_describe")
            # 特质
            star_characteristics = await ArmsCharacteristics.filter(arms_id=arms["arms_id"]).values("items_name",
                                                                                                    "items_describe")
            # 专属
            star_exclusives = await ArmsExclusives.filter(arms_id=arms["arms_id"]).values("items_name",
                                                                                          "items_describe")

            arms["star_ratings"] = star_ratings
            arms["star_characteristics"] = star_characteristics
            arms["star_exclusives"] = star_exclusives
            # 渲染 HTML
            template = env.get_template("template.html")
            html_content = template.render(**arms)

            # 加载 HTML 内容
            await page.set_content(html_content)

            # 截图特定区域 (定位到 .card)
            locator = page.locator(".card")
            screenshot_dir = Path(__file__).parent / "screenshots"
            screenshot_dir.mkdir(exist_ok=True)
            sanitized_name = sanitize_filename(arms['arms_name'])  # 清理文件名
            screenshot_path = screenshot_dir / f"{sanitized_name}.png"
            await locator.screenshot(path=str(screenshot_path))

        await browser.close()