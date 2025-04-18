import os
from itertools import groupby
import json
import pytz
from PIL import Image, ImageDraw, ImageFilter, ImageFont
import httpx
import asyncio
from io import BytesIO
import io
import time

from nonebot.internal.matcher import Matcher
from nonebot.log import logger
from pathlib import Path
from playwright.async_api import async_playwright
from fish_coins_bot.database.hotta.arms import Arms, ArmsStarRatings, ArmsCharacteristics, ArmsExclusives, \
    ArmsPrimaryAttacks, ArmsDodgeAttacks, ArmsCooperationAttacks, ArmsSkillAttacks, ArmsSynesthesia
from jinja2 import Environment, FileSystemLoader
from datetime import datetime, timedelta

from fish_coins_bot.database.hotta.event_consultation import EventConsultation
from fish_coins_bot.database.hotta.food import Food
from fish_coins_bot.database.hotta.nuo_coins import NuoCoinsTaskType, NuoCoinsTaskWeeklyDetail
from fish_coins_bot.database.hotta.willpower import Willpower, WillpowerSuit
from fish_coins_bot.database.hotta.yu_coins import YuCoinsTaskType, YuCoinsTaskWeeklyDetail
from fish_coins_bot.utils.model_utils import make_arms_img_url, highlight_numbers, sanitize_filename, \
    make_willpower_img_url, make_yu_coins_img_url, the_font_bold, make_nuo_coins_img_url, \
    yu_different_colors, nuo_different_colors, make_wiki_help_img_url, days_diff_from_now, \
    format_datetime_with_timezone, make_event_consultation_end_url, make_food_img_url, tag_different_colors, \
    delta_force_map_abbreviation, clean_keyword
from fish_coins_bot.utils.nuo_coins_utils import select_or_add_this_weekly_nuo_coins_weekly_id
from fish_coins_bot.utils.yu_coins_utils import select_or_add_this_weekly_yu_coins_weekly_id

# 定义一个 asyncio.Lock，用于控制方法的执行
lock = asyncio.Lock()

# 全局变量，表示方法是否正在执行
is_processing = False


# 获取网络图片
async def fetch_image(url: str):
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        if response.status_code == 200:
            image = Image.open(BytesIO(response.content))
            return image
        else:
            logger.error(f"Failed to fetch image. Status code: {response.status_code}")


# 制作开播图
async def make_live_image(live_cover_url: str, live_avatar_url: str, live_name: str, live_address: str,
                          live_title: str):

    icon_path = "fish_coins_bot/img/icon-bili.png"

    # 获取背景图片
    background_image = await fetch_image(live_cover_url)

    # 调整背景图片尺寸到 640x360
    target_size = (640, 360)
    resized_background = background_image.resize(target_size, Image.Resampling.LANCZOS)

    # 步骤 1: 应用高斯模糊
    blurred_background = resized_background.filter(ImageFilter.GaussianBlur(2))  # 模糊半径为 10

    # 步骤 2: 制造颗粒感（降低分辨率再放大）
    small = blurred_background.resize(
        (blurred_background.size[0], blurred_background.size[1]),
        resample=Image.NEAREST
    )
    frosted_glass_background = small.resize(blurred_background.size, Image.NEAREST)

    # 步骤 3: 添加半透明黑色遮罩 (RGBA)
    overlay = Image.new("RGBA", frosted_glass_background.size, (0, 0, 0, 100))  # 黑色遮罩，透明度 100

    # 步骤 4: 合成磨砂玻璃背景和遮罩
    background_with_overlay = Image.alpha_composite(frosted_glass_background.convert("RGBA"), overlay)

    # 获取头像图片
    avatar_image = await fetch_image(live_avatar_url)

    # 调整头像图片尺寸到 100x100
    avatar_size = (100, 100)
    resized_avatar = avatar_image.resize(avatar_size, Image.Resampling.LANCZOS)

    # 创建圆形头像蒙版
    mask = Image.new("L", avatar_size, 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, avatar_size[0], avatar_size[1]), fill=255)

    # 将圆形蒙版应用到头像
    rounded_avatar = Image.new("RGBA", avatar_size, (255, 255, 255, 0))
    rounded_avatar.paste(resized_avatar, (0, 0), mask)

    # 创建阴影
    shadow = Image.new("RGBA", (avatar_size[0] + 10, avatar_size[1] + 10), (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    shadow_draw.ellipse((5, 5, avatar_size[0] + 5, avatar_size[1] + 5), fill=(0, 0, 0, 150))
    shadow = shadow.filter(ImageFilter.GaussianBlur(5))

    # 加载字体
    font_path = "fish_coins_bot/fonts/ZCOOLKuaiLe-Regular.ttf"
    main_font_path = "fish_coins_bot/fonts/字帮玩酷体.ttf"
    font_path_kbl = os.getenv("FONT_HOST") + "rcez.ttf"
    response = httpx.get(font_path_kbl)


    live_icon_text = "开播啦!"

    # 设置字体大小
    main_font_size = avatar_size[1] * 0.7
    main_font = ImageFont.truetype(main_font_path, size=int(main_font_size))
    small_font_size = avatar_size[1] * 0.3
    small_font = ImageFont.truetype(font_path, size=int(small_font_size))
    title_font_size = 30
    title_font = ImageFont.truetype(font_path, size=title_font_size)
    icon_text_font_size = 100
    icon_text_font = ImageFont.truetype(BytesIO(response.content), size=icon_text_font_size)

    # 加载图标并调整大小
    icon_image = Image.open(icon_path)
    icon_size = (150, 150)
    resized_icon = icon_image.resize(icon_size, Image.Resampling.LANCZOS)

    # 计算主文字和小文字的总高度
    main_bbox = main_font.getbbox(live_name)
    main_text_height = main_bbox[3] - main_bbox[1]

    small_bbox = small_font.getbbox(live_address)
    small_text_height = small_bbox[3] - small_bbox[1]

    total_text_height = main_text_height + small_text_height + 10

    # 计算标题文字高度
    title_bbox = title_font.getbbox(live_title)
    title_text_height = title_bbox[3] - title_bbox[1]

    # 设置布局
    layout_top = 20
    icon_position_top = layout_top + total_text_height + 30

    # 绘制头像
    avatar_position = (target_size[0] - avatar_size[0] - 20, layout_top + (total_text_height - avatar_size[1]) // 2)
    background_with_overlay.paste(shadow, (avatar_position[0] - 5, avatar_position[1] - 5), shadow)
    background_with_overlay.paste(rounded_avatar, avatar_position, rounded_avatar)

    # 设置主文字和小文字
    main_text_position = (avatar_position[0] - main_bbox[2] - 20, layout_top)
    small_text_position = (
        main_text_position[0] + main_bbox[2] - small_bbox[2], main_text_position[1] + main_text_height + 10)

    draw = ImageDraw.Draw(background_with_overlay)
    draw.text(main_text_position, live_name, font=main_font, fill=(255, 255, 255))
    draw.text(small_text_position, live_address, font=small_font, fill=(255, 255, 255), underline=True)

    # 绘制图标和附加文字
    icon_position = ((target_size[0] - icon_size[0]) // 2 - 180, icon_position_top)
    icon_text_position = (
        icon_position[0] + icon_size[0] + 10, icon_position[1] + (icon_size[1] - icon_text_font_size) // 2 - 12)
    background_with_overlay.paste(resized_icon, icon_position, resized_icon)
    draw.text(icon_text_position, live_icon_text, font=icon_text_font, fill=(255, 192, 203))

    # 绘制标题
    title_position = ((target_size[0] - title_bbox[2]) // 2, target_size[1] - title_text_height - 20)
    draw.text(title_position, live_title, font=title_font, fill=(255, 255, 255))

    # 显示和保存最终图片
    return background_with_overlay


async def make_all_arms_image():
    screenshot_dir = Path(__file__).parent.parent.parent / "screenshots" / "arms"
    screenshot_dir.mkdir(exist_ok=True)

    files = [file.stem for file in screenshot_dir.iterdir() if file.is_file()]
    logger.warning(f"The following arms documents already exist: {files}. Skip")

    arms_list = await Arms.filter(del_flag="0").values("arms_id", "arms_type", "arms_attribute", "arms_name",
                                                       "arms_overwhelmed",
                                                       "arms_charging_energy", "arms_thumbnail_url")

    arms_list = [arms for arms in arms_list if arms["arms_name"] not in files]
    arms_names = [arms["arms_name"] for arms in arms_list]

    logger.warning(f"The following arms documents will be created: {arms_names}.")

    # 创建 Jinja2 环境
    env = Environment(loader=FileSystemLoader('templates'))
    env.filters['highlight_numbers'] = highlight_numbers  # 注册过滤器

    async with async_playwright() as p:
        browser = await p.firefox.launch(headless=True)

        for arms in arms_list:
            make_arms_img_url(arms)

            # 星级
            star_ratings = await ArmsStarRatings.filter(arms_id=arms["arms_id"]).values("items_name", "items_describe")
            # 特质
            star_characteristics = await ArmsCharacteristics.filter(arms_id=arms["arms_id"]).values("items_name",
                                                                                                    "items_describe")
            # 通感
            arms_synesthesia = await ArmsSynesthesia.filter(arms_id=arms["arms_id"]).values("items_name",
                                                                                                    "items_describe")
            # 专属
            star_exclusives = await ArmsExclusives.filter(arms_id=arms["arms_id"]).values("items_name",
                                                                                          "items_describe")

            arms["star_ratings"] = star_ratings if len(star_ratings) > 0 else None
            arms["star_characteristics"] = star_characteristics if len(star_characteristics) > 0 else None
            arms["star_exclusives"] = star_exclusives if len(star_exclusives) > 0 else None
            arms["arms_synesthesia"] = arms_synesthesia if len(arms_synesthesia) > 0 else None

            # 渲染 HTML
            template = env.get_template("template-arms.html")
            html_content = template.render(**arms)

            # 创建新的页面
            page = await browser.new_page()  # 每次处理新数据时创建新标签页

            # 加载 HTML 内容
            await page.set_content(html_content, timeout=600000)  # 60 秒

            # 截图特定区域 (定位到 .card)
            locator = page.locator(".card")

            sanitized_name = sanitize_filename(arms['arms_name'])  # 清理文件名
            screenshot_path = screenshot_dir / f"{sanitized_name}.png"
            await locator.screenshot(path=str(screenshot_path))

            # 关闭当前页面
            await page.close()

        await browser.close()

    logger.success(f"All arms files are created.")


async def make_yu_coins_type_image(frequency:str = None):
    logger.warning(f"yu-coins-task-type.png will be create.")

    screenshot_dir = Path(__file__).parent.parent.parent / "screenshots" / "yu-coins"
    screenshot_dir.mkdir(exist_ok=True)

    sanitized_name = 'yu-coins-task-type'  # 清理文件名
    screenshot_path = screenshot_dir / f"{sanitized_name}.png"

    if not screenshot_path.exists() or frequency is None:

        yu_coins_task_type_list = await YuCoinsTaskType.filter(del_flag="0").order_by("task_type_id").values("task_type_id",
                                                                                                             "task_type_region",
                                                                                                             "task_type_npc",
                                                                                                             "task_type_position",
                                                                                                             "task_type_details",
                                                                                                             "task_type_reward")
        processed_list = []
        for region, group in groupby(yu_coins_task_type_list, key=lambda x: x["task_type_region"]):
            group = list(group)  # 转成列表以便多次操作
            rowspan = len(group)  # 当前组的行数
            for idx, item in enumerate(group):
                if idx == 0:
                    item["rowspan"] = rowspan  # 第一项标记 rowspan
                else:
                    item["task_type_region"] = None  # 其余项置空
                processed_list.append(item)

        data = {"yu_coins_task_type_list": yu_coins_task_type_list, "title_name": "每周域币任务汇总", "title_date": None}

        # 创建 Jinja2 环境
        env = Environment(loader=FileSystemLoader('templates'))
        env.filters['different_colors'] = yu_different_colors  # 注册过滤器
        env.filters['the_font_bold'] = the_font_bold  # 注册过滤器

        async with async_playwright() as p:
            browser = await p.firefox.launch(headless=True)
            make_yu_coins_img_url(data)

            # 渲染 HTML
            template = env.get_template("template-yu-coins-type.html")
            html_content = template.render(**data)

            # 创建新的页面
            page = await browser.new_page()  # 每次处理新数据时创建新标签页

            # 加载 HTML 内容
            await page.set_content(html_content, timeout=60000)  # 60 秒

            # 截图特定区域 (定位到 .card)
            locator = page.locator(".card")

            await locator.screenshot(path=str(screenshot_path))

            # 关闭当前页面
            await page.close()

            await browser.close()

    logger.success(f"yu-coins-task-type.png are created.")


async def make_all_willpower_image():
    screenshot_dir = Path(__file__).parent.parent.parent / "screenshots" / "willpower"
    screenshot_dir.mkdir(exist_ok=True)

    files = [file.stem for file in screenshot_dir.iterdir() if file.is_file()]
    logger.warning(f"The following willpower documents already exist: {files}. Skip")

    willpower_list = await Willpower.filter(del_flag="0").values("willpower_id", "willpower_name",
                                                                 "willpower_thumbnail_url")

    willpower_list = [willpower for willpower in willpower_list if willpower["willpower_name"] not in files]
    willpower_names = [willpower["willpower_name"] for willpower in willpower_list]

    logger.warning(f"The following willpower documents will be created: {willpower_names}.")

    # 创建 Jinja2 环境
    env = Environment(loader=FileSystemLoader('templates'))
    env.filters['highlight_numbers'] = highlight_numbers  # 注册过滤器

    async with async_playwright() as p:
        browser = await p.firefox.launch(headless=True)

        for willpower in willpower_list:
            make_willpower_img_url(willpower)

            # 套装
            willpower_suit = await WillpowerSuit.filter(willpower_id=willpower["willpower_id"]).values("items_name",
                                                                                                       "items_describe")

            willpower["willpower_suit"] = willpower_suit

            # 渲染 HTML
            template = env.get_template("template-willpower.html")
            html_content = template.render(**willpower)

            # 创建新的页面
            page = await browser.new_page()  # 每次处理新数据时创建新标签页

            # 加载 HTML 内容
            await page.set_content(html_content, timeout=60000)  # 60 秒

            # 截图特定区域 (定位到 .card)
            locator = page.locator(".card")

            sanitized_name = sanitize_filename(willpower['willpower_name'])  # 清理文件名
            screenshot_path = screenshot_dir / f"{sanitized_name}.png"
            await locator.screenshot(path=str(screenshot_path))

            # 关闭当前页面
            await page.close()

        await browser.close()

    logger.success(f"All willpower files are created.")


async def make_yu_coins_weekly_image(frequency:str = None):
    logger.warning(f"yu-coins-task-weekly.png will be create.")

    screenshot_dir = Path(__file__).parent.parent.parent / "screenshots" / "yu-coins"
    screenshot_dir.mkdir(exist_ok=True)

    sanitized_name = 'yu-coins-task-weekly'  # 清理文件名
    screenshot_path = screenshot_dir / f"{sanitized_name}.png"

    if not screenshot_path.exists() or frequency is None:

        task_weekly_id = await select_or_add_this_weekly_yu_coins_weekly_id()

        weekly_details = await YuCoinsTaskWeeklyDetail.filter(del_flag="0", task_weekly_id=task_weekly_id).select_related(
            "task_type")

        # 收集 task_type 数据，并添加 task_weekly_contributors
        task_type_list = sorted(
            [
                {
                    "task_type_region": detail.task_type.task_type_region,
                    "task_type_npc": detail.task_type.task_type_npc,
                    "task_type_position": detail.task_type.task_type_position,
                    "task_type_details": detail.task_type.task_type_details,
                    "task_type_reward": detail.task_type.task_type_reward,
                    "task_weekly_contributors": detail.task_weekly_contributors,  # 加入贡献者信息
                    "task_type_id": detail.task_type.task_type_id,  # 改为任务种类ID
                }
                for detail in weekly_details if detail.task_type  # 确保 task_type 存在
            ],
            key=lambda x: x["task_type_id"],  # 按 task_type_region 排序
        )

        today = datetime.now()

        # 计算本周的开始日期（周一）和结束日期（周日）
        start_of_week = today - timedelta(days=today.weekday())  # 本周一
        end_of_week = start_of_week + timedelta(days=6)  # 本周日

        # 去掉时间部分，仅保留日期
        start_of_week = start_of_week.date()  # 转为日期类型
        end_of_week = end_of_week.date()  # 转为日期类型

        processed_list = []
        for region, group in groupby(task_type_list, key=lambda x: x["task_type_region"]):
            group = list(group)  # 转成列表以便多次操作
            rowspan = len(group)  # 当前组的行数
            for idx, item in enumerate(group):
                if idx == 0:
                    item["rowspan"] = rowspan  # 第一项标记 rowspan
                else:
                    item["task_type_region"] = None  # 其余项置空
                processed_list.append(item)

        data = {"task_type_list": task_type_list, "title_name": "本周域币任务", "start_of_week": start_of_week,
                "end_of_week": end_of_week}
        # 创建 Jinja2 环境
        env = Environment(loader=FileSystemLoader('templates'))
        env.filters['the_font_bold'] = the_font_bold  # 注册过滤器

        async with async_playwright() as p:
            browser = await p.firefox.launch(headless=True)

            make_yu_coins_img_url(data)

            # 渲染 HTML
            template = env.get_template("template-yu-coins-weekly.html")
            html_content = template.render(**data)

            # 创建新的页面
            page = await browser.new_page()  # 每次处理新数据时创建新标签页

            # 加载 HTML 内容
            await page.set_content(html_content, timeout=60000)  # 60 秒

            # 截图特定区域 (定位到 .card)
            locator = page.locator(".card")

            await locator.screenshot(path=str(screenshot_path))

            # 关闭当前页面
            await page.close()

            await browser.close()

    logger.success(f"yu-coins-task-weekly.png are created.")


async def make_nuo_coins_type_image(frequency:str = None):
    logger.warning(f"nuo-coins-task-type.png will be create.")

    screenshot_dir = Path(__file__).parent.parent.parent / "screenshots" / "nuo-coins"
    screenshot_dir.mkdir(exist_ok=True)

    sanitized_name = 'yu-coins-task-weekly'  # 清理文件名
    screenshot_path = screenshot_dir / f"{sanitized_name}.png"

    if not screenshot_path.exists() or frequency is None:

        nuo_coins_task_type_list = await NuoCoinsTaskType.filter(del_flag="0").order_by("task_type_id").values(
            "task_type_id", "task_type_region", "task_type_npc", "task_type_position", "task_type_details",
            "task_type_reward")
        processed_list = []
        for region, group in groupby(nuo_coins_task_type_list, key=lambda x: x["task_type_region"]):
            group = list(group)  # 转成列表以便多次操作
            rowspan = len(group)  # 当前组的行数
            for idx, item in enumerate(group):
                if idx == 0:
                    item["rowspan"] = rowspan  # 第一项标记 rowspan
                else:
                    item["task_type_region"] = None  # 其余项置空
                processed_list.append(item)

        data = {"nuo_coins_task_type_list": nuo_coins_task_type_list, "title_name": "每周诺元任务汇总", "title_date": None}

        # 创建 Jinja2 环境
        env = Environment(loader=FileSystemLoader('templates'))
        env.filters['different_colors'] = nuo_different_colors  # 注册过滤器
        env.filters['the_font_bold'] = the_font_bold  # 注册过滤器

        async with async_playwright() as p:
            browser = await p.firefox.launch(headless=True)
            make_nuo_coins_img_url(data)

            # 渲染 HTML
            template = env.get_template("template-nuo-coins-type.html")
            html_content = template.render(**data)

            # 创建新的页面
            page = await browser.new_page()  # 每次处理新数据时创建新标签页

            # 加载 HTML 内容
            await page.set_content(html_content, timeout=60000)  # 60 秒

            # 截图特定区域 (定位到 .card)
            locator = page.locator(".card")

            await locator.screenshot(path=str(screenshot_path))

            # 关闭当前页面
            await page.close()

            await browser.close()

    logger.success(f"nuo-coins-task-type.png are created.")


async def make_nuo_coins_weekly_image(frequency:str = None):
    logger.warning(f"nuo-coins-task-weekly.png will be create.")

    screenshot_dir = Path(__file__).parent.parent.parent / "screenshots" / "nuo-coins"
    screenshot_dir.mkdir(exist_ok=True)

    sanitized_name = 'nuo-coins-task-weekly'  # 清理文件名
    screenshot_path = screenshot_dir / f"{sanitized_name}.png"

    if not screenshot_path.exists() or frequency is None:

        task_weekly_id = await select_or_add_this_weekly_nuo_coins_weekly_id()

        weekly_details = await NuoCoinsTaskWeeklyDetail.filter(del_flag="0", task_weekly_id=task_weekly_id).select_related(
            "task_type")

        # 收集 task_type 数据，并添加 task_weekly_contributors
        task_type_list = sorted(
            [
                {
                    "task_type_region": detail.task_type.task_type_region,
                    "task_type_npc": detail.task_type.task_type_npc,
                    "task_type_position": detail.task_type.task_type_position,
                    "task_type_details": detail.task_type.task_type_details,
                    "task_type_reward": detail.task_type.task_type_reward,
                    "task_weekly_contributors": detail.task_weekly_contributors,  # 加入贡献者信息
                    "task_type_id": detail.task_type.task_type_id,  # 加入明细ID
                }
                for detail in weekly_details if detail.task_type  # 确保 task_type 存在
            ],
            key=lambda x: x["task_type_id"],  # 按 task_type_region 排序
        )

        today = datetime.now()

        # 计算本周的开始日期（周一）和结束日期（周日）
        start_of_week = today - timedelta(days=today.weekday())  # 本周一
        end_of_week = start_of_week + timedelta(days=6)  # 本周日

        # 去掉时间部分，仅保留日期
        start_of_week = start_of_week.date()  # 转为日期类型
        end_of_week = end_of_week.date()  # 转为日期类型

        processed_list = []
        for region, group in groupby(task_type_list, key=lambda x: x["task_type_region"]):
            group = list(group)  # 转成列表以便多次操作
            rowspan = len(group)  # 当前组的行数
            for idx, item in enumerate(group):
                if idx == 0:
                    item["rowspan"] = rowspan  # 第一项标记 rowspan
                else:
                    item["task_type_region"] = None  # 其余项置空
                processed_list.append(item)

        data = {"task_type_list": task_type_list, "title_name": "本周诺元任务", "start_of_week": start_of_week,
                "end_of_week": end_of_week}
        # 创建 Jinja2 环境
        env = Environment(loader=FileSystemLoader('templates'))
        env.filters['the_font_bold'] = the_font_bold  # 注册过滤器

        async with async_playwright() as p:
            browser = await p.firefox.launch(headless=True)

            make_nuo_coins_img_url(data)

            # 渲染 HTML
            template = env.get_template("template-nuo-coins-weekly.html")
            html_content = template.render(**data)

            # 创建新的页面
            page = await browser.new_page()  # 每次处理新数据时创建新标签页

            # 加载 HTML 内容
            await page.set_content(html_content, timeout=60000)  # 60 秒

            # 截图特定区域 (定位到 .card)
            locator = page.locator(".card")

            await locator.screenshot(path=str(screenshot_path))

            # 关闭当前页面
            await page.close()

            await browser.close()

    logger.success(f"nuo-coins-task-weekly.png are created.")


async def flushed_yu_nuo_weekly_images(matcher: Matcher, type_name: str):
    global is_processing

    if lock.locked():
        await matcher.finish(f"本周{type_name}任务图片正在处理中,请3-5分钟后重试...")
    async with lock:
        if is_processing:
            await matcher.finish(f"本周{type_name}任务图片正在处理中,请3-5分钟后重试...")
        is_processing = True
        try:
            await matcher.send(f"正在处理本周{type_name}任务图片,请稍等...")
            await make_yu_coins_weekly_image()
            await make_nuo_coins_weekly_image()
        finally:
            is_processing = False
            await matcher.finish(
                f"本周{type_name}任务图片处理完成☀️\n使用指令'本周{type_name}任务'进行查看吧！"
            )


async def make_all_arms_attack_image():
    screenshot_dir = Path(__file__).parent.parent.parent / "screenshots" / "arms-attack"
    screenshot_dir.mkdir(exist_ok=True)

    files = [file.stem for file in screenshot_dir.iterdir() if file.is_file()]
    logger.warning(f"The following arms-attack documents already exist: {files}. Skip")

    arms_list = await Arms.filter(del_flag="0").values("arms_id", "arms_type", "arms_attribute", "arms_name",
                                                       "arms_overwhelmed",
                                                       "arms_charging_energy", "arms_thumbnail_url")

    arms_list = [arms for arms in arms_list if arms["arms_name"] not in files]
    arms_names = [arms["arms_name"] for arms in arms_list]

    logger.warning(f"The following arms-attack documents will be created: {arms_names}.")

    # 创建 Jinja2 环境
    env = Environment(loader=FileSystemLoader('templates'))
    env.filters['highlight_numbers'] = highlight_numbers  # 注册过滤器

    async with async_playwright() as p:
        browser = await p.firefox.launch(headless=True)

        for arms in arms_list:
            make_arms_img_url(arms)

            # 普攻
            primary_attacks = await ArmsPrimaryAttacks.filter(arms_id=arms["arms_id"]).values("items_name",
                                                                                              "items_describe")
            # 闪攻
            dodge_attacks = await ArmsDodgeAttacks.filter(arms_id=arms["arms_id"]).values("items_name",
                                                                                          "items_describe")
            # 联携
            cooperation_attacks = await ArmsCooperationAttacks.filter(arms_id=arms["arms_id"]).values("items_name",
                                                                                                      "items_describe")
            # 技能
            skill_attacks = await ArmsSkillAttacks.filter(arms_id=arms["arms_id"]).values("items_name",
                                                                                          "items_describe")

            arms["primary_attacks"] = primary_attacks
            arms["dodge_attacks"] = dodge_attacks
            arms["cooperation_attacks"] = cooperation_attacks
            arms["skill_attacks"] = skill_attacks

            # 渲染 HTML
            template = env.get_template("template-arms-attack.html")
            html_content = template.render(**arms)

            # 创建新的页面
            page = await browser.new_page()  # 每次处理新数据时创建新标签页

            # 加载 HTML 内容
            await page.set_content(html_content, timeout=60000)  # 60 秒

            # 截图特定区域 (定位到 .card)
            locator = page.locator(".card")

            sanitized_name = sanitize_filename(arms['arms_name'])  # 清理文件名
            screenshot_path = screenshot_dir / f"{sanitized_name}.png"
            await locator.screenshot(path=str(screenshot_path))

            # 关闭当前页面
            await page.close()

        await browser.close()

    logger.success(f"All arms-attack files are created.")


async def make_wiki_help(frequency:str = None):
    logger.warning(f"wiki-help.png will be create.")

    screenshot_dir = Path(__file__).parent.parent.parent / "screenshots" / "common"
    screenshot_dir.mkdir(exist_ok=True)

    sanitized_name = 'wiki-help'  # 清理文件名
    screenshot_path = screenshot_dir / f"{sanitized_name}.png"

    if not screenshot_path.exists() or frequency is None:
        data = {}

        # 创建 Jinja2 环境
        env = Environment(loader=FileSystemLoader('templates'))
        env.filters['different_colors'] = nuo_different_colors  # 注册过滤器
        env.filters['the_font_bold'] = the_font_bold  # 注册过滤器

        async with async_playwright() as p:
            browser = await p.firefox.launch(headless=True)
            make_wiki_help_img_url(data)

            # 渲染 HTML
            template = env.get_template("template-wiki-help.html")
            html_content = template.render(**data)

            # 创建新的页面
            page = await browser.new_page()  # 每次处理新数据时创建新标签页

            # 加载 HTML 内容
            await page.set_content(html_content, timeout=60000)  # 60 秒

            # 截图特定区域 (定位到 .card)
            locator = page.locator(".card")

            await locator.screenshot(path=str(screenshot_path))

            # 关闭当前页面
            await page.close()

            await browser.close()

    logger.success(f"wiki-help.png are created.")

async def make_event_consultation():
    logger.warning(f"event-consultation.png will be create.")

    screenshot_dir = Path(__file__).parent.parent.parent / "screenshots" / "common"
    screenshot_dir.mkdir(exist_ok=True)

    tz = pytz.timezone("Asia/Shanghai")
    current_time = datetime.now(tz)

    are_info_list = await EventConsultation.filter(
        del_flag="0",
        consultation_start__lte=current_time,
        consultation_end__gte=current_time
    ).order_by("consultation_end").limit(12).values(
        "consultation_title",
        "consultation_thumbnail_url",
        "consultation_start",
        "consultation_end"
    )

    will_info_list = await EventConsultation.filter(
        del_flag="0",
        consultation_start__gt=current_time
    ).order_by("consultation_start").limit(4).values(
        "consultation_title",
        "consultation_thumbnail_url",
        "consultation_start",
        "consultation_end"
    )

    background_path = "fish_coins_bot/img/event_consultation_background.png"
    icon_path = "fish_coins_bot/img/icon-clock.png"
    font_path = "fish_coins_bot/fonts/ZCOOLKuaiLe-Regular.ttf"
    font_path_title = "fish_coins_bot/fonts/AlibabaPuHuiTi-3-55-Regular.otf"
    font_path_kbl = os.getenv("FONT_HOST") + "rcez.ttf"
    response = httpx.get(font_path_kbl)

    background_image = Image.open(background_path)
    background_image = background_image.resize((1920, 1080))

    draw = ImageDraw.Draw(background_image)

    # 加载字体
    font_size_large = 50
    font_size_medium = 40
    font_size_small = 15
    font_size_title = 18
    font_large = ImageFont.truetype(font_path, font_size_large)
    # font_medium = ImageFont.truetype(font_big_title, font_size_medium)
    font_medium = ImageFont.truetype(BytesIO(response.content), size=font_size_medium)
    font_small = ImageFont.truetype(font_path, font_size_small)
    font_title = ImageFont.truetype(font_path_title, font_size_title)

    icon_size = (85, 85)  # 图标大小
    icon = Image.open(icon_path).resize(icon_size)

    icon_text_spacing = 5
    text_icon_spacing = 5

    padding = 10
    title_height = font_size_large + padding - 15
    subtitle_height = font_size_medium + padding
    content_height = font_size_small + padding
    image_size = (350, 200)

    title_text = ""
    bbox = draw.textbbox((0, 0), title_text, font=font_large)
    text_width, text_height = bbox[2] - bbox[0], bbox[3] - bbox[1]
    title_position = ((background_image.width - text_width) // 2, padding)
    draw.text(title_position, title_text, font=font_large, fill="black")

    subtitle_text = "正在进行中..."
    bbox = draw.textbbox((0, 0), subtitle_text, font=font_medium)
    text_width, text_height = bbox[2] - bbox[0], bbox[3] - bbox[1]
    subtitle_position = (padding, title_height + padding)
    draw.text(subtitle_position, subtitle_text, font=font_medium, fill="black")

    x_padding = 65

    x_positions = [
        x_padding,
        520,
        980,
        1440
    ]

    y_position = subtitle_position[1] + subtitle_height + padding

    if ((len(are_info_list) + 3) // 4) < 3 or len(will_info_list) == 0:
        max_rows = (len(are_info_list) + 3) // 4
    else:
        max_rows = 2

    for row in range(max_rows):
        for i in range(4):
            index = row * 4 + i
            if index >= len(are_info_list):
                continue

            event = are_info_list[index]

            title_text = f">>> {event["consultation_title"]}"
            start_time_text = f"开始时间: {format_datetime_with_timezone(event['consultation_start'])}"
            end_time_text = f"结束时间: {format_datetime_with_timezone(event['consultation_end'])}"

            draw.text((x_positions[i], y_position), title_text, font=font_title, fill="black")
            y_position_current = y_position + content_height

            draw.text((x_positions[i], y_position_current + 5), start_time_text, font=font_small, fill="black")

            y_position_current += content_height

            start_time_position = (x_positions[i], y_position_current)

            start_time_bbox = draw.textbbox((0, 0), start_time_text, font=font_small)
            text_width = start_time_bbox[2] - start_time_bbox[0]

            # 绘制图标
            icon_position = (
                start_time_position[0] + text_width + text_icon_spacing + 20,
                start_time_position[1] - 60
            )
            background_image.paste(icon, icon_position, mask=icon)

            # 在图标下方绘制 "X天"
            icon_text_position = (
                icon_position[0] + 30,
                icon_position[1] + icon_size[1] + icon_text_spacing - 20
            )

            absolute_time = days_diff_from_now(event['consultation_end'])
            text_color = "red" if absolute_time <= 3 else "black"

            draw.text(icon_text_position, f"{absolute_time}天", font=font_small, fill=text_color)

            draw.text((x_positions[i], y_position_current + 5), end_time_text, font=font_small, fill=text_color)
            y_position_current += content_height + padding

            image_url = event["consultation_thumbnail_url"]
            try:
                activity_image = await fetch_image(image_url)
                activity_image = activity_image.resize(image_size)
                background_image.paste(activity_image, (x_positions[i], y_position_current))
            except Exception as e:
                print(f"无法加载图片 {image_url}: {e}")

        y_position += max(content_height * 3 + 220, image_size[1]) + padding


    if len(will_info_list) > 0 :

        subtitle_text = "未开始..."
        bbox = draw.textbbox((0, 0), subtitle_text, font=font_medium)
        text_width, text_height = bbox[2] - bbox[0], bbox[3] - bbox[1]
        subtitle_position = (padding, y_position)
        draw.text(subtitle_position, subtitle_text, font=font_medium, fill="black")

        y_position += 50

        for i in range(len(will_info_list)):

            event = will_info_list[i]

            title_text = f">>> {event["consultation_title"]}"
            start_time_text = f"开始时间: {format_datetime_with_timezone(event['consultation_start'])}"
            end_time_text = f"结束时间: {format_datetime_with_timezone(event['consultation_end'])}"

            draw.text((x_positions[i], y_position), title_text, font=font_title, fill="black")
            y_position_current = y_position + content_height

            draw.text((x_positions[i], y_position_current + 5), start_time_text, font=font_small, fill="black")
            y_position_current += content_height

            #
            start_time_position = (x_positions[i], y_position_current)
            start_time_bbox = draw.textbbox((0, 0), start_time_text, font=font_small)
            text_width = start_time_bbox[2] - start_time_bbox[0]

            # 绘制图标
            icon_position = (
                start_time_position[0] + text_width + text_icon_spacing + 20,
                start_time_position[1] - 60
            )
            background_image.paste(icon, icon_position, mask=icon)

            absolute_time = days_diff_from_now(event['consultation_start'])

            # 在图标下方绘制 "X天"
            icon_text_position = (
                icon_position[0] + 30,
                icon_position[1] + icon_size[1] + icon_text_spacing - 20
            )
            draw.text(icon_text_position, f"{absolute_time}天", font=font_small, fill="black")
            #
            draw.text((x_positions[i], y_position_current + 5), end_time_text, font=font_small, fill="black")
            y_position_current += content_height + padding

            #
            image_url = event["consultation_thumbnail_url"]
            try:
                activity_image = await fetch_image(image_url)
                activity_image = activity_image.resize(image_size)
                background_image.paste(activity_image, (x_positions[i], y_position_current))
            except Exception as e:
                print(f"无法加载图片 {image_url}: {e}")

    sanitized_name = 'event-consultation'  # 清理文件名
    screenshot_path = screenshot_dir / f"{sanitized_name}.png"

    background_image.save(screenshot_path)

    logger.success(f"event-consultation.png are created.")


async def make_event_consultation_end_image(frequency:str = None):
    logger.warning(f"event-consultation-end.png will be create.")

    screenshot_dir = Path(__file__).parent.parent.parent / "screenshots" / "common"
    screenshot_dir.mkdir(exist_ok=True)

    sanitized_name = 'event-consultation-end'  # 清理文件名
    screenshot_path = screenshot_dir / f"{sanitized_name}.png"

    if not screenshot_path.exists() or frequency is None:

        tz = pytz.timezone("Asia/Shanghai")
        current_time = datetime.now(tz)

        are_info_list = await EventConsultation.filter(
            del_flag="0",
            consultation_start__lte=current_time,
            consultation_end__gte=current_time
        ).order_by("consultation_end").values(
            "consultation_title",
            "consultation_start",
            "consultation_end",
            "consultation_thumbnail_url",
            "consultation_describe"
        )

        are_info_list = list(filter(lambda info: days_diff_from_now(info["consultation_end"]) <= 7, are_info_list))

        for item in are_info_list:
            if "consultation_end" in item:
                item["day_num"] = days_diff_from_now(item["consultation_end"])
                item["consultation_end"] = str(item["consultation_end"])[:16]

        data = {"nuo_coins_task_type_list": are_info_list, "title_name": "即将结束的活动"}

        # 创建 Jinja2 环境
        env = Environment(loader=FileSystemLoader('templates'))
        env.filters['tag_different_colors'] = tag_different_colors  # 注册过滤器

        async with async_playwright() as p:
            browser = await p.firefox.launch(headless=True)
            make_event_consultation_end_url(data)

            # 渲染 HTML
            template = env.get_template("template-event-consultation-end-plus.html")
            html_content = template.render(**data)

            # 创建新的页面
            page = await browser.new_page()  # 每次处理新数据时创建新标签页

            # 加载 HTML 内容
            await page.set_content(html_content, timeout=60000)  # 60 秒

            # 截图特定区域 (定位到 .card)
            locator = page.locator(".calendar-wrapper")

            await locator.screenshot(path=str(screenshot_path))

            # 关闭当前页面
            await page.close()

            await browser.close()

    logger.success(f"event-consultation-end.png are created.")


async def make_food_image():

    screenshot_dir = Path(__file__).parent.parent.parent  / "screenshots" / "food"
    screenshot_dir.mkdir(exist_ok=True)

    files = [file.stem for file in screenshot_dir.iterdir() if file.is_file()]
    logger.warning(f"The following food documents already exist: {files}. Skip")
    food_list = await Food.filter(del_flag="0").prefetch_related("food_formulas")

    food_list = [food for food in food_list if food.food_name not in files]
    food_names = [food.food_name for food in food_list]

    logger.warning(f"The following arms-attack documents will be created: {food_names}.")

    # 创建 Jinja2 环境
    env = Environment(loader=FileSystemLoader('templates'))
    env.filters['highlight_numbers'] = highlight_numbers  # 注册过滤器

    async with async_playwright() as p:
        browser = await p.firefox.launch(headless=True)

        for food in food_list:
            food_formulas = []
            make_food_img_url(food)
            for formula in food.food_formulas:

                ingredient_food = await Food.filter(food_id=formula.ingredients_id).first()

                if ingredient_food:
                    formula_dict = formula.__dict__.copy()  # 转换为字典
                    formula_dict["ingredient_food_thumbnail_url"] = ingredient_food.food_thumbnail_url
                    formula_dict["ingredient_food_name"] = ingredient_food.food_name
                    food_formulas.append(formula_dict)

            # 渲染 HTML
            template = env.get_template("template-food.html")

            food_data = {key: value for key, value in food.__dict__.items() if value is not None}
            food_data['food_formulas'] = food_formulas
            html_content = template.render(**food_data)

            # 创建新的页面
            page = await browser.new_page()  # 每次处理新数据时创建新标签页

            # 加载 HTML 内容
            await page.set_content(html_content, timeout=60000)  # 60 秒

            # 截图特定区域 (定位到 .card)
            locator = page.locator(".card")

            sanitized_name = sanitize_filename(food_data["food_name"])  # 清理文件名
            screenshot_path = screenshot_dir / f"{sanitized_name}.png"
            await locator.screenshot(path=str(screenshot_path))

            # 关闭当前页面
            await page.close()

        await browser.close()

    logger.success(f"All food files are created.")


async def make_delta_force_room():
    # 读取 JSON 数据
    with open(Path(__file__).parent.parent / 'plugins' / 'delta_force' / 'delta_force_request.json', 'r', encoding='utf-8') as f:
        request_data = json.load(f)

    FONT_PATH = "fish_coins_bot/fonts/字帮玩酷体.ttf"

    version_request_info = request_data.get('getVersion', {})
    door_pin_request_info = request_data.get('getDoorPin', {})

    # 提取请求头和 URL
    version_headers = version_request_info.get('headers', {})
    version_url = version_request_info.get('url', '')

    door_pin_headers = door_pin_request_info.get('headers', {})
    door_pin_url = door_pin_request_info.get('url', '')

    # 发送 HTTP 请求获取数据
    with httpx.Client() as client:
        version_response = client.post(version_url, headers=version_headers)
        php_sess_id = version_response.cookies.get("PHPSESSID")
        version_response_data = version_response.json()
        built_ver = str(version_response_data["built_ver"])
        door_pin_headers["Cookie"] += php_sess_id

    with httpx.Client() as client:
        request_data = "version=" + built_ver
        door_pin_response = client.post(door_pin_url, headers=door_pin_headers, data=request_data)
        response_data = door_pin_response.json()

        if response_data['code'] == 1 and response_data['data']:
            room_data = response_data['data']

            # 动态计算图片高度
            base_width = 600
            row_height = 60  # 每行的高度
            title_height = 80  # 标题的高度
            header_height = 50  # 表头的高度
            padding = 20  # 边距
            image_height = title_height + header_height + len(room_data) * row_height + padding * 2 + 40

            # 创建图片
            image = Image.new('RGB', (base_width, image_height), color=(245, 245, 245))

            background_path = "fish_coins_bot/img/password_background.png"
            background_image = Image.open(background_path)
            background_image = background_image.resize((base_width, image_height))  # 调整尺寸匹配新图片

            image.paste(background_image, (0, 0))

            draw = ImageDraw.Draw(image)

            # 加载自定义字体
            try:
                font_title = ImageFont.truetype(FONT_PATH, 36)  # 标题字体
                font_header = ImageFont.truetype(FONT_PATH, 28)  # 表头字体
                font_text = ImageFont.truetype(FONT_PATH, 26)  # 正文字体
            except IOError:
                print("字体文件无法加载，改用默认字体")
                font_title = ImageFont.load_default()
                font_header = ImageFont.load_default()
                font_text = ImageFont.load_default()

            # 绘制标题
            title_text = ""
            title_bbox = draw.textbbox((0, 0), title_text, font=font_title)  # 获取文本边界
            text_width = title_bbox[2] - title_bbox[0]
            draw.text(((base_width - text_width) / 2, padding), title_text, fill=(0, 0, 0), font=font_title)

            # 画分割线
            line_y = padding + title_height - 10
            # draw.line([(padding, line_y), (base_width - padding, line_y)], fill=(0, 0, 0), width=3)

            # 表头
            y_position = line_y + 40  # 表头起始位置
            col_map = 50  # 地图列起点
            col_pass = 250  # 密码列起点
            col_date = 450  # 日期列起点
            draw.text((col_map, y_position), "地图", fill=(0, 0, 0), font=font_header)
            draw.text((col_pass, y_position), "密码", fill=(0, 0, 0), font=font_header)
            draw.text((col_date, y_position), "日期", fill=(0, 0, 0), font=font_header)

            # 画分割线
            y_position += header_height - 10
            # draw.line([(padding, y_position), (base_width - padding, y_position)], fill=(0, 0, 0), width=2)

            # 绘制房间信息
            y_position += 20  # 数据起始行
            for map, data in room_data.items():
                map_name = delta_force_map_abbreviation.get(map, map)  # 获取地图中文名
                password = data['password']
                updated_raw = data['updated'][:8]
                updated = f"{updated_raw[:4]}-{updated_raw[4:6]}-{updated_raw[6:]}"  # 格式化为 YYYY-MM-DD

                draw.text((col_map, y_position), map_name, fill=(50, 50, 50), font=font_text)
                draw.text((col_pass, y_position), password, fill=(50, 50, 50), font=font_text)
                draw.text((col_date - 20, y_position), updated, fill=(50, 50, 50), font=font_text)

                y_position += row_height  # 调整行距

            return image

        else:
            return None


def create_rounded_rectangle_mask(size, radius):
    """创建带有圆角的蒙版"""
    w, h = size
    mask = Image.new("L", (w, h), 0)  # 创建黑色蒙版（完全透明）
    draw = ImageDraw.Draw(mask)

    # 画一个圆角矩形
    draw.rounded_rectangle((0, 0, w, h), radius=radius, fill=40)  # 255 = 完全不透明

    return mask

async def make_delta_force_produce():
    # 读取 JSON 数据
    with open(Path(__file__).parent.parent / 'plugins' / 'delta_force' / 'delta_force_request.json', 'r', encoding='utf-8') as f:
        request_data = json.load(f)

    FONT_PATH = "fish_coins_bot/fonts/字帮玩酷体.ttf"

    version_request_info = request_data.get('getVersion', {})
    door_pin_request_info = request_data.get('getProduce', {})

    # 提取请求头和 URL
    version_headers = version_request_info.get('headers', {})
    version_url = version_request_info.get('url', '')

    door_pin_headers = door_pin_request_info.get('headers', {})
    door_pin_url = door_pin_request_info.get('url', '')

    # 发送 HTTP 请求获取数据
    with httpx.Client() as client:
        version_response = client.post(version_url, headers=version_headers)
        php_sess_id = version_response.cookies.get("PHPSESSID")
        version_response_data = version_response.json()
        built_ver = str(version_response_data["built_ver"])
        door_pin_headers["Cookie"] += php_sess_id

    with httpx.Client() as client:
        request_data = "version=" + built_ver
        door_pin_response = client.post(door_pin_url, headers=door_pin_headers, data=request_data)
        response_data = door_pin_response.json()

        # 存储每个 placeName 下 profit 最大的对象
        place_max_profit = {}

        for item in response_data['data']:
            place = item["placeName"]
            if place not in place_max_profit or item["profit"] > place_max_profit[place]["profit"]:
                place_max_profit[place] = item

        # 结果列表
        result = list(place_max_profit.values())

        if response_data['code'] == 1 and response_data['data']:
            room_data = result

            # 动态计算图片高度
            base_width = 650
            row_height = 60  # 每行的高度
            title_height = 80  # 标题的高度
            header_height = 50  # 表头的高度
            padding = 20  # 边距
            image_height = title_height + header_height + len(room_data) * row_height + padding * 2 + 40

            # 创建图片
            image = Image.new('RGB', (base_width, image_height), color=(245, 245, 245))

            background_path = "fish_coins_bot/img/produce_background.png"
            background_image = Image.open(background_path)
            background_image = background_image.resize((base_width, image_height))  # 调整尺寸匹配新图片

            image.paste(background_image, (0, 0))

            draw = ImageDraw.Draw(image)

            # 加载自定义字体
            try:
                font_title = ImageFont.truetype(FONT_PATH, 36)  # 标题字体
                font_header = ImageFont.truetype(FONT_PATH, 28)  # 表头字体
                font_text = ImageFont.truetype(FONT_PATH, 26)  # 正文字体
            except IOError:
                print("字体文件无法加载，改用默认字体")
                font_title = ImageFont.load_default()
                font_header = ImageFont.load_default()
                font_text = ImageFont.load_default()

            # 绘制标题
            title_text = ""
            title_bbox = draw.textbbox((0, 0), title_text, font=font_title)  # 获取文本边界
            text_width = title_bbox[2] - title_bbox[0]
            draw.text(((base_width - text_width) / 2, padding), title_text, fill=(0, 0, 0), font=font_title)

            # 画分割线
            line_y = padding + title_height - 10
            # draw.line([(padding, line_y), (base_width - padding, line_y)], fill=(0, 0, 0), width=3)

            # 表头
            y_position = line_y + 40  # 表头起始位置
            col_place = 50
            col_item = 200
            col_profit = 520
            draw.text((col_place, y_position), "地点", fill=(0, 0, 0), font=font_header)
            draw.text((col_item, y_position), "制作物", fill=(0, 0, 0), font=font_header)
            draw.text((col_profit, y_position), "收益", fill=(0, 0, 0), font=font_header)

            # 画分割线
            y_position += header_height - 20
            # draw.line([(padding, y_position), (base_width - padding, y_position)], fill=(0, 0, 0), width=2)

            # 绘制房间信息
            y_position += 20  # 数据起始行
            for data in room_data:
                place_name = data['placeName']
                pic = data['pic']
                item_name = data['itemName']
                item_grade = data['itemGrade']
                profit = str(data['profit']).split('.')[0]

                # 下载图片
                response = httpx.get(pic)
                if response.status_code == 200:
                    item_image = Image.open(BytesIO(response.content)).convert("RGBA")  # 确保是 RGBA 格式
                    item_image = item_image.resize((30, 30))  # 调整大小

                    # # 创建相同大小的透明蒙版
                    # mask = item_image.split()[3]  # 提取 alpha 通道（透明度）
                    #
                    # # 贴图，保留透明度
                    # image.paste(item_image, (col_pass - 40, y_position), mask)

                    if item_grade == 5:
                        bg_color = (250, 118, 0, 100)
                    elif item_grade == 4:
                        bg_color = (114, 86, 255, 100)
                    elif item_grade == 3:
                        bg_color = (36, 172, 242, 100)
                    else:
                        bg_color = (255, 255, 255, 0)

                    bg_image = Image.new("RGBA", item_image.size, bg_color)

                    # 2. 创建圆角蒙版
                    rounded_mask = create_rounded_rectangle_mask(item_image.size, radius=5)  # 半径10像素的圆角

                    # 3. 应用蒙版到背景，使背景变成圆角
                    bg_image.putalpha(rounded_mask)

                    # 4. 叠加原始图片，保留透明度
                    combined = Image.alpha_composite(bg_image, item_image)

                    # 5. 贴到主图上，保留透明效果
                    image.paste(combined, (col_item, y_position), combined)

                    # 绘制文本
                draw.text((col_place, y_position), place_name, fill=(50, 50, 50), font=font_text)
                draw.text((col_item + 40, y_position), item_name, fill=(50, 50, 50), font=font_text)
                draw.text((col_profit , y_position), profit, fill=(50, 50, 50), font=font_text)

                y_position += row_height

            return image

        else:
            return None


async def screenshot_first_dyn_by_keyword(url: str, keyword: str, fallback_index: int | None = None) -> Image.Image | None:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--disable-gpu", "--no-sandbox"])
        context = await browser.new_context(viewport={"width": 1920, "height": 1080})
        page = await context.new_page()

        await page.goto(url, timeout=60000, wait_until="networkidle")

        # 处理可能的登录弹窗
        try:
            close_btn = await page.query_selector("div.bili-mini-close-icon")
            if close_btn:
                logger.info("检测到登录弹窗，尝试点击关闭按钮")
                await close_btn.click()
                await page.wait_for_timeout(5000)  # 给动画留一点时间
        except Exception as e:
            logger.warning(f"检测或点击登录弹窗关闭按钮时出错：{e}")


        try:
            await page.wait_for_selector("div.bili-dyn-list__item", timeout=90000)
        except Exception:
            logger.error("元素等待超时，尝试截图页面")

            error_img_dir = "/app/screenshots/error-img"
            os.makedirs(error_img_dir, exist_ok=True)

            # 生成带时间戳的文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            screenshot_path = os.path.join(error_img_dir, f"timeout_{timestamp}.png")

            await page.screenshot(path=screenshot_path, full_page=True)

            html_path = os.path.join(error_img_dir, f"timeout_{timestamp}.html")
            await page.content()
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(await page.content())

            logger.info(f"超时截图已保存到 {screenshot_path}")

            raise  # 或者 return None


        # 优先通过关键字匹配
        element = await page.query_selector(f'div.bili-dyn-list__item:has-text("{clean_keyword(keyword)}")')

        if (element is None and fallback_index is not None) or not clean_keyword(keyword):
            logger.warning(f"未找到包含 “{keyword}” 的动态，尝试使用第 {fallback_index} 个动态作为备选")
            all_items = await page.query_selector_all('div.bili-dyn-list__item')
            if fallback_index < len(all_items):
                element = all_items[fallback_index]
            else:
                logger.error(f"页面中没有第 {fallback_index} 个动态")
                await browser.close()
                return None

        if element is None:
            logger.error(f"未找到包含 “{keyword}” 的动态，也没有指定备用索引")
            await browser.close()
            return None

        await element.scroll_into_view_if_needed()
        await page.evaluate("window.scrollBy(0, -3000)")
        await page.wait_for_timeout(500)

        # 将截图保存为字节流
        image_bytes = await element.screenshot()
        await browser.close()

        image = Image.open(io.BytesIO(image_bytes))
        return image
