import base64
import os
import json
import pytz
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageEnhance
import httpx
import asyncio
from io import BytesIO
import io
import random
from typing import Optional
import mimetypes

from dotenv import load_dotenv
from nonebot.log import logger
from pathlib import Path
from playwright.async_api import async_playwright
from typing_extensions import Tuple

from jinja2 import Environment, FileSystemLoader
from datetime import datetime, timedelta

from fish_coins_bot.database.hotta.event_news import EventNews
from fish_coins_bot.utils.model_utils import the_font_bold,  make_wiki_help_img_url, days_diff_from_now, \
    format_datetime_with_timezone, make_event_news_end_url, make_food_img_url, tag_different_colors, \
    delta_force_map_abbreviation, clean_keyword, get_waf_cookie, common_fetch_door_pin_response, \
    tem_fetch_door_pin_response


load_dotenv()

MINIO_HOST = os.getenv("MINIO_HOST")


# 获取网络图片
async def fetch_image(url: str):
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        if response.status_code == 200:
            image = Image.open(BytesIO(response.content))
            return image
        else:
            logger.error(f"Failed to fetch image. Status code: {response.status_code}")




# bili开播图======

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





# 帮助图======

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
        env.filters['the_font_bold'] = the_font_bold  # 注册过滤器

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
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





# 活动资讯======

async def make_event_news():
    logger.warning(f"event-news.png will be create.")

    screenshot_dir = Path(__file__).parent.parent.parent / "screenshots" / "common"
    screenshot_dir.mkdir(exist_ok=True)

    tz = pytz.timezone("Asia/Shanghai")
    current_time = datetime.now(tz)

    are_info_list = await EventNews.filter(
        del_flag="0",
        news_start__lte=current_time,
        news_end__gte=current_time
    ).order_by("news_end").limit(12).values(
        "news_title",
        "news_img_url",
        "news_start",
        "news_end"
    )

    will_info_list = await EventNews.filter(
        del_flag="0",
        news_start__gt=current_time
    ).order_by("news_start").limit(4).values(
        "news_title",
        "news_img_url",
        "news_start",
        "news_end"
    )

    background_path = "fish_coins_bot/img/event_news_background.png"
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

            title_text = f">>> {event["news_title"]}"
            start_time_text = f"开始时间: {format_datetime_with_timezone(event['news_start'])}"
            end_time_text = f"结束时间: {format_datetime_with_timezone(event['news_end'])}"

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

            absolute_time = days_diff_from_now(event['news_end'])
            text_color = "red" if absolute_time <= 3 else "black"

            draw.text(icon_text_position, f"{absolute_time}天", font=font_small, fill=text_color)

            draw.text((x_positions[i], y_position_current + 5), end_time_text, font=font_small, fill=text_color)
            y_position_current += content_height + padding

            image_url = MINIO_HOST + event["news_img_url"]
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

            title_text = f">>> {event["news_title"]}"
            start_time_text = f"开始时间: {format_datetime_with_timezone(event['news_start'])}"
            end_time_text = f"结束时间: {format_datetime_with_timezone(event['news_end'])}"

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

            absolute_time = days_diff_from_now(event['news_start'])

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
            image_url = MINIO_HOST + event["news_img_url"]
            try:
                activity_image = await fetch_image(image_url)
                activity_image = activity_image.resize(image_size)
                background_image.paste(activity_image, (x_positions[i], y_position_current))
            except Exception as e:
                print(f"无法加载图片 {image_url}: {e}")

    sanitized_name = 'event-news'  # 清理文件名
    screenshot_path = screenshot_dir / f"{sanitized_name}.png"

    background_image.save(screenshot_path)

    logger.success(f"event-news.png are created.")





# 即将结束的活动======

async def make_event_news_end_image(frequency:str = None):
    logger.warning(f"event-news-end.png will be create.")

    screenshot_dir = Path(__file__).parent.parent.parent / "screenshots" / "common"
    screenshot_dir.mkdir(exist_ok=True)

    sanitized_name = 'event-news-end'  # 清理文件名
    screenshot_path = screenshot_dir / f"{sanitized_name}.png"

    if not screenshot_path.exists() or frequency is None:

        tz = pytz.timezone("Asia/Shanghai")
        current_time = datetime.now(tz)

        are_info_list = await EventNews.filter(
            del_flag="0",
            news_start__lte=current_time,
            news_end__gte=current_time
        ).order_by("news_end").values(
            "news_title",
            "news_start",
            "news_end",
            "news_img_url",
            "news_describe"
        )

        are_info_list = list(filter(lambda info: days_diff_from_now(info["news_end"]) <= 7, are_info_list))

        for item in are_info_list:
            if "news_end" in item:
                item["day_num"] = days_diff_from_now(item["news_end"])
                item["news_end"] = str(item["news_end"])[:16]
                item["news_img_url"] = MINIO_HOST + item["news_img_url"]

        data = {"nuo_coins_task_type_list": are_info_list, "title_name": "即将结束的活动"}

        # 创建 Jinja2 环境
        env = Environment(loader=FileSystemLoader('templates'))
        env.filters['tag_different_colors'] = tag_different_colors  # 注册过滤器

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            make_event_news_end_url(data)

            # 渲染 HTML
            template = env.get_template("template-event-news-end-plus.html")
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

    logger.success(f"event-news-end.png are created.")





# 粥密码======

async def make_delta_force_room():
    # 读取 JSON 数据
    with open(Path(__file__).parent.parent / 'plugins' / 'delta_force' / 'delta_force_request.json', 'r', encoding='utf-8') as f:
        request_data = json.load(f)

    FONT_PATH = "fish_coins_bot/fonts/字帮玩酷体.ttf"

    # response_data = await common_fetch_door_pin_response(request_data)
    # type = 'common'

    response_data = await tem_fetch_door_pin_response(request_data)
    type = 'tem'

    # if response_data['code'] == 1 and response_data['data'] and type == 'common':
    if response_data['code'] == 0 and response_data['data'] and type == 'tem':
        room_data = response_data['data']

        # 动态计算图片高度
        base_width = 600
        row_height = 60  # 每行的高度
        title_height = 80  # 标题的高度
        header_height = 50  # 表头的高度
        padding = 20  # 边距
        image_height = title_height + header_height + len(room_data) * row_height + padding * 2 + 45

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





# 幻塔动态======

async def random_delay(min_sec: float = 0.5, max_sec: float = 3.0):
    """随机延迟"""
    await asyncio.sleep(random.uniform(min_sec, max_sec))

async def apply_stealth(page):
    stealth_script = """
        // 隐藏 webdriver
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });

        // 模拟 Chrome 对象
        window.chrome = {
            runtime: {},
            // 其他属性可根据需要补充
        };

        // 修改语言
        Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh', 'en'] });

        // 模拟插件
        Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });

        // 修改 permissions 查询（如通知权限）
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) => (
            parameters.name === 'notifications'
                ? Promise.resolve({ state: Notification.permission })
                : originalQuery(parameters)
        );
    """
    await page.add_init_script(stealth_script)

async def screenshot_first_dyn_by_keyword(
        url: str,
        keyword: str,
        fallback_index: Optional[int] = None
) -> Optional[Image.Image]:

    # 浏览器窗口大小
    viewport_width = random.choice([1920, 1366, 1440, 1600])
    viewport_height = random.choice([1080, 768, 900, 1050])

    # 用户代理
    user_agents = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36"

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-gpu",
                "--disable-dev-shm-usage",
                "--disable-web-security",
                "--disable-infobars",
                "--hide-scrollbars",
                "--mute-audio",
                f"--window-size={viewport_width},{viewport_height}",
            ],
            # 随机启动参数
            ignore_default_args=[
                "--enable-automation",
                "--disable-popup-blocking"
            ]
        )
        context = await browser.new_context(
            viewport={"width": viewport_width, "height": viewport_height},
            user_agent=user_agents,
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
            # 媒体和权限设置
            permissions=["geolocation"],
            geolocation={"latitude": 39.3434, "longitude": 117.3616},
            color_scheme="light",
            # 随机HTTP头
            extra_http_headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Accept-Encoding": "gzip, deflate, br, zstd",
                "Referer": "https://www.bilibili.com/",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
                "sec-ch-ua": '"Not;A=Brand";v="99", "Google Chrome";v="139", "Chromium";v="139"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Windows"',
                "DNT": "1"  # 建议固定
            }
        )

        page = await context.new_page()

        await apply_stealth(page)

        # 随机化导航行为
        await random_delay(1.0, 3.0)  # 打开页面前的随机延迟

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





# 抽卡图片生成======

def add_side_glow(
    base: Image.Image,
    glow_color=(255, 140, 0),
    radius=100,
    intensity=0.8,
    y_start: int = 0,
    y_end: int = None
) -> Image.Image:
    """
    给 base 图像左右两侧添加光效（模拟发光边缘），支持限定 y 范围及上下透明渐变
    :param base: 原始图像（RGBA）
    :param glow_color: 发光颜色
    :param radius: 光柱宽度（左右各 radius 像素）
    :param intensity: 发光强度（0~1）
    :param y_start: 光效起始 y 坐标
    :param y_end: 光效结束 y 坐标（默认到底部）
    """
    width, height = base.size
    if y_end is None or y_end > height:
        y_end = height

    glow_layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(glow_layer)

    glow_height = y_end - y_start

    for i in range(radius):
        # x方向 alpha 比例
        alpha_x = 1 - (i / radius)
        for y in range(y_start, y_end):
            # y方向 alpha 比例：距离上下边界越近越暗
            dist_y = min(y - y_start, y_end - y)
            alpha_y = dist_y / (glow_height / 2)
            final_alpha = int(intensity * 255 * alpha_x * alpha_y)

            # 左边光柱
            draw.point((i, y), fill=glow_color + (final_alpha,))
            # 右边光柱
            draw.point((width - i - 1, y), fill=glow_color + (final_alpha,))

    glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(radius=radius // 3))
    base.alpha_composite(glow_layer)
    return base

def paste_image(
    base: Image.Image,
    image_path: Path,
    scale: float,
    pos_x: int,
    pos_y: int,
    opacity: float = 1.0,
    background_color: Optional[tuple[int, int, int, int]] = None
) -> Image.Image:
    """
    将图像按比例缩放并粘贴到 base 图像的指定位置，可选设置透明度与背景色
    :param base: 背景图像
    :param image_path: 要粘贴的图像路径
    :param scale: 缩放比例（例如 1.0 表示原始大小）
    :param pos_x: 粘贴位置的 x 坐标
    :param pos_y: 粘贴位置的 y 坐标
    :param opacity: 透明度，0.0 ~ 1.0（默认 1.0 不透明）
    :param background_color: (r, g, b, a)，为透明图像添加背景色（默认 None 不添加）
    """
    if not image_path.exists():
        logger.warning(f"贴图未找到：{image_path}")
        return base  # 原样返回，不贴图也不中断

    img = Image.open(image_path).convert("RGBA")

    # 按比例缩放
    new_size = (int(img.width * scale), int(img.height * scale))
    img = img.resize(new_size, resample=Image.Resampling.LANCZOS)

    # 如果需要添加背景色
    if background_color is not None:
        bg = Image.new("RGBA", img.size, background_color)
        bg.paste(img, (0, 0), img)
        img = bg

    # 调整透明度
    if opacity < 1.0:
        alpha = img.getchannel("A")
        alpha = ImageEnhance.Brightness(alpha).enhance(opacity)
        img.putalpha(alpha)

    base.paste(img, (pos_x, pos_y), img)
    return base

def draw_vertical_text(
    font_path: str,
    font_size: int,
    image: Image.Image,
    pos_x: int,
    pos_y: int,
    text: str,
    fill: Tuple[int, int, int, int] = (255, 255, 255, 255),
    vertical: bool = False
) -> Image.Image:
    """
    在图片上添加文字，支持横排或竖排显示
    :param font_path: 字体路径
    :param font_size: 字号
    :param image: 要绘制的图片
    :param pos_x: 起始 x 坐标
    :param pos_y: 起始 y 坐标
    :param text: 要绘制的文字
    :param fill: 字体颜色
    :param vertical: 是否竖排显示，默认 False（横排）
    """
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(font_path, font_size)

    if vertical:
        # 每个字符向下排列
        for i, char in enumerate(text):
            y = pos_y + i * font_size
            draw.text((pos_x, y), char, font=font, fill=fill)
    else:
        # 横排直接写整句
        draw.text((pos_x, pos_y), text, font=font, fill=fill)

    return image

def paste_cards_on_background(
    background: Image.Image,
    cards: list[Image.Image],
    start_x: int,
    start_y: int,
    gap: int = 0,
    scale: float = 1.0
) -> Image.Image:
    """
    将多个卡片图像横向排列贴到背景图上，并支持缩放倍率
    :param background: 背景图
    :param cards: 卡片图像列表
    :param start_x: 起始 x 坐标
    :param start_y: 起始 y 坐标
    :param gap: 卡片之间的间隔
    :param scale: 缩放倍率（默认 1.0 不缩放）
    """
    for i, card in enumerate(cards):
        # 缩放
        if scale != 1.0:
            new_size = (int(card.width * scale), int(card.height * scale))
            card = card.resize(new_size, resample=Image.Resampling.LANCZOS)

        pos_x = start_x + i * (card.width + gap)
        background.paste(card, (pos_x, start_y), card)
    return background

def remove_transparency(im: Image.Image, bg_color=(0, 0, 0)) -> Image.Image:
    if im.mode in ('RGBA', 'LA') or (im.mode == 'P' and 'transparency' in im.info):
        background = Image.new("RGB", im.size, bg_color)
        background.paste(im, mask=im.split()[-1])
        return background
    else:
        return im.convert("RGB")

def render_gacha_result(results: list[dict]) -> Image.Image:

    base_path = Path(__file__).parent.parent.parent / "screenshots" / "gacha-resources"
    # 主背景图
    main_back_path = base_path / "common-img" / "chouka_bg.png"
    main_back_img = Image.open(main_back_path).convert("RGBA")

    cards = []
    already_obtained = []
    for i, result in enumerate(results):
        # 每个单独生成

        quality = result.get("quality", "R")
        name = result.get("name", "电磁刃")


        back_filename = {
            "SSR": "G-1.png",
            "SR": "G-3.png",
            "R": "G-2.png"
        }.get(quality, "G-2.png")

        back_path = base_path/ "common-img" / back_filename
        base_img = Image.open(back_path).convert("RGBA")

        glow_color = {
            "SSR": (255, 165, 0),
            "SR": (180, 80, 255),
            "R": (80, 180, 255)
        }.get(quality, (255, 255, 255))  # 默认白色防止报错

        base_img = add_side_glow(base_img, glow_color=glow_color, radius=20, intensity=0.8, y_start=40, y_end=830)
        # base_img = add_side_glow(base_img, glow_color=(255, 165, 0), radius=20, intensity=0.8, y_start=40, y_end=830)
        # base_img = add_side_glow(base_img, glow_color=(180, 80, 255), radius=20, intensity=0.8, y_start=40, y_end=830)
        # base_img = add_side_glow(base_img, glow_color=(80, 180, 255), radius=20, intensity=0.8, y_start=40, y_end=830)

        base_img = paste_image(base_img, base_path / "characters-img" / f"{name}.png", 0.6, result['characters_x'], result['characters_y'], 0.9,None)

        base_img = paste_image(base_img, base_path / "common-img" / f"{quality}.png", 0.6, -10, 120,1,None)

        if quality != 'R':
            base_img = paste_image(base_img, base_path / "characters-name" / f"{name}.png", 1, result['name_x'], result['name_y'],1,None)

        if name not in already_obtained:
            base_img = paste_image(base_img, base_path / "common-img" / "new_2.png", 0.8, 8, 125,1,None)

        base_img = paste_image(base_img, base_path / "common-img" / "UI_UP_Tips01_Bkg.png", 0.6, 150, 400, 0.3,None)
        if name in already_obtained :
            if quality == 'R':
                base_img = paste_image(base_img, base_path / "common-img" / "Weapon_R_Exp01.png", 0.3, 50, 580, 0.9,(71,179,163,255))
            else :
                base_img = paste_image(base_img, base_path / "common-img" / "Icon_Item_Fusion_Core.webp", 0.6, 50, 580,0.9, (253, 231, 138, 255))

            base_img = paste_image(base_img, base_path / "common-img" / "image_yifenjie.png", 0.8, 50, 540, 1,None)

        # 添加竖排文字
        base_img = draw_vertical_text(
            font_path="fish_coins_bot/fonts/AlibabaPuHuiTi-3-55-Regular.otf",
            font_size=18,
            image=base_img,
            pos_x=162,
            pos_y=430,
            text=name,
            fill=(255, 255, 255, 255),
            vertical = True
        )

        cards.append(base_img)
        already_obtained.append(name)

    # 合并卡片到背景图
    result = paste_cards_on_background(
        background=main_back_img,
        cards=cards,
        start_x=200,  # 居中起始 x 坐标
        start_y=200,  # 根据实际背景图高度微调
        gap=0,  # 紧贴排布（不留缝）
        scale=0.8
    )

    #订购一次 订购十次 分享 返回图标
    result = paste_image(result, base_path / "common-img" / "1c.png", 0.8, 1300, 900, 1,None)
    result = paste_image(result, base_path / "common-img" / "10c.png", 0.8, 1500, 900, 1,None)
    result = paste_image(result, base_path / "common-img" / "share.png", 0.8, 1700, 900, 1,None)
    result = paste_image(result, base_path / "common-img" / "common_btn_back.png", 0.8, 30, 30, 1,None)

    #返回文字
    draw_vertical_text(
        font_path="fish_coins_bot/fonts/AlibabaPuHuiTi-3-55-Regular.otf",
        font_size=45,
        image=result,
        pos_x=200,
        pos_y=55,
        text='返回',
        fill=(255, 255, 255, 255)
    )

    return remove_transparency(result, bg_color=(0, 0, 0))


async def get_first_image_base64_and_mime(event):

    # 找到第一张图片
    first_img_url = None
    for seg in event.message:
        if seg.type == "image":
            first_img_url = seg.data.get("url")
            break

    if not first_img_url:
        return "", ""

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(first_img_url)
            resp.raise_for_status()
            img_bytes = resp.content

            # 转 Base64
            img_base64 = base64.b64encode(img_bytes).decode("utf-8")

            # 用 mimetypes 根据 URL 推测 MIME 类型
            mime_type, _ = mimetypes.guess_type(first_img_url)
            if not mime_type:
                mime_type = "application/octet-stream"

            return img_base64, mime_type
    except Exception as e:
        return "", ""