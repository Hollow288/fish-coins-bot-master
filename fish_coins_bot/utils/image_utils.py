from itertools import groupby

from PIL import Image, ImageDraw, ImageFilter, ImageFont
import httpx
import asyncio
from io import BytesIO

from nonebot.internal.matcher import Matcher
from nonebot.log import logger
from pathlib import Path
from playwright.async_api import async_playwright
from fish_coins_bot.database.hotta.arms import Arms,ArmsStarRatings,ArmsCharacteristics,ArmsExclusives
from jinja2 import Environment, FileSystemLoader
from datetime import datetime, timedelta

from fish_coins_bot.database.hotta.nuo_coins import NuoCoinsTaskType, NuoCoinsTaskWeeklyDetail
from fish_coins_bot.database.hotta.willpower import Willpower, WillpowerSuit
from fish_coins_bot.database.hotta.yu_coins import YuCoinsTaskType, YuCoinsTaskWeeklyDetail
from fish_coins_bot.utils.model_utils import make_arms_img_url, highlight_numbers, sanitize_filename, \
    make_willpower_img_url, make_yu_coins_img_url,  the_font_bold, make_nuo_coins_img_url, \
    yu_different_colors, nuo_different_colors
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
async def make_live_image(live_cover_url: str,live_avatar_url: str,live_name: str,live_address: str,live_title:str):
    # live_cover_url = "https://i0.hdslb.com/bfs/live/new_room_cover/90d1125ffdf5a51549404aa88a52ebb624b6b59c.jpg"
    # live_avatar_url = "https://i1.hdslb.com/bfs/face/463cab30630a0230e997625c07aa1213b19905b2.jpg"
    icon_path = "fish_coins_bot/img/icon.png"

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
    font_path_kbl = "fish_coins_bot/fonts/日出而作日落想你.ttf"

    # 修改文字内容
    # live_name = "喵不动了喵"
    # live_address = "https://live.bilibili.com/3786110"
    # live_title = "《！州一下 可扶贫》"
    live_icon_text = "开播啦!"

    # 设置字体大小
    main_font_size = avatar_size[1] * 0.7
    main_font = ImageFont.truetype(font_path, size=int(main_font_size))
    small_font_size = avatar_size[1] * 0.3
    small_font = ImageFont.truetype(font_path, size=int(small_font_size))
    title_font_size = 30
    title_font = ImageFont.truetype(font_path, size=title_font_size)
    icon_text_font_size = 100
    icon_text_font = ImageFont.truetype(font_path_kbl, size=icon_text_font_size)

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
    small_text_position = (main_text_position[0] + main_bbox[2] - small_bbox[2], main_text_position[1] + main_text_height + 10)

    draw = ImageDraw.Draw(background_with_overlay)
    draw.text(main_text_position, live_name, font=main_font, fill=(255, 255, 255))
    draw.text(small_text_position, live_address, font=small_font, fill=(255, 255, 255), underline=True)

    # 绘制图标和附加文字
    icon_position = ((target_size[0] - icon_size[0]) // 2 - 180, icon_position_top)
    icon_text_position = (icon_position[0] + icon_size[0] + 10, icon_position[1] + (icon_size[1] - icon_text_font_size) // 2 - 12)
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

    arms_list = await Arms.filter(del_flag="0").values("arms_id", "arms_type", "arms_attribute", "arms_name", "arms_overwhelmed",
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
            # 专属
            star_exclusives = await ArmsExclusives.filter(arms_id=arms["arms_id"]).values("items_name",
                                                                                          "items_describe")

            arms["star_ratings"] = star_ratings
            arms["star_characteristics"] = star_characteristics
            arms["star_exclusives"] = star_exclusives

            # 渲染 HTML
            template = env.get_template("template-arms.html")
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

    logger.success(f"All arms files are created.")


async def make_yu_coins_type_image():

    logger.warning(f"yu-coins-task-type.png will be create.")

    screenshot_dir = Path(__file__).parent.parent.parent / "screenshots" / "yu-coins"
    screenshot_dir.mkdir(exist_ok=True)

    yu_coins_task_type_list = await YuCoinsTaskType.filter(del_flag="0").order_by("task_type_id").values("task_type_id","task_type_region", "task_type_npc", "task_type_position","task_type_details","task_type_reward")
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



    data = {"yu_coins_task_type_list":yu_coins_task_type_list,"title_name":"每周域币任务汇总","title_date":None}

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

        sanitized_name = 'yu-coins-task-type'  # 清理文件名
        screenshot_path = screenshot_dir / f"{sanitized_name}.png"
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

    willpower_list = await Willpower.filter(del_flag="0").values("willpower_id", "willpower_name", "willpower_thumbnail_url")

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
            willpower_suit = await WillpowerSuit.filter(willpower_id=willpower["willpower_id"]).values("items_name", "items_describe")

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


async def make_yu_coins_weekly_image():

    logger.warning(f"yu-coins-task-weekly.png will be create.")

    screenshot_dir = Path(__file__).parent.parent.parent / "screenshots" / "yu-coins"
    screenshot_dir.mkdir(exist_ok=True)

    task_weekly_id = await select_or_add_this_weekly_yu_coins_weekly_id()

    weekly_details = await YuCoinsTaskWeeklyDetail.filter(del_flag="0",task_weekly_id=task_weekly_id).select_related("task_type")

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
                "weekly_detail_id": detail.weekly_detail_id,  # 加入明细ID
            }
            for detail in weekly_details if detail.task_type  # 确保 task_type 存在
        ],
        key=lambda x: x["task_type_region"],  # 按 task_type_region 排序
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

    data = {"task_type_list":task_type_list,"title_name":"本周域币任务","start_of_week":start_of_week,"end_of_week":end_of_week}
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

        sanitized_name = 'yu-coins-task-weekly'  # 清理文件名
        screenshot_path = screenshot_dir / f"{sanitized_name}.png"
        await locator.screenshot(path=str(screenshot_path))

        # 关闭当前页面
        await page.close()

        await browser.close()

    logger.success(f"yu-coins-task-weekly.png are created.")
    
    
async def make_nuo_coins_type_image():

    logger.warning(f"nuo-coins-task-type.png will be create.")

    screenshot_dir = Path(__file__).parent.parent.parent / "screenshots" / "nuo-coins"
    screenshot_dir.mkdir(exist_ok=True)

    nuo_coins_task_type_list = await NuoCoinsTaskType.filter(del_flag="0").order_by("task_type_id").values("task_type_id","task_type_region", "task_type_npc", "task_type_position","task_type_details","task_type_reward")
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



    data = {"nuo_coins_task_type_list":nuo_coins_task_type_list,"title_name":"每周诺元任务汇总","title_date":None}

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

        sanitized_name = 'nuo-coins-task-type'  # 清理文件名
        screenshot_path = screenshot_dir / f"{sanitized_name}.png"
        await locator.screenshot(path=str(screenshot_path))

        # 关闭当前页面
        await page.close()

        await browser.close()

    logger.success(f"nuo-coins-task-type.png are created.")
    
    
async def make_nuo_coins_weekly_image():

    logger.warning(f"nuo-coins-task-weekly.png will be create.")

    screenshot_dir = Path(__file__).parent.parent.parent / "screenshots" / "nuo-coins"
    screenshot_dir.mkdir(exist_ok=True)

    task_weekly_id = await select_or_add_this_weekly_nuo_coins_weekly_id()

    weekly_details = await NuoCoinsTaskWeeklyDetail.filter(del_flag="0",task_weekly_id=task_weekly_id).select_related("task_type")

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
                "weekly_detail_id": detail.weekly_detail_id,  # 加入明细ID
            }
            for detail in weekly_details if detail.task_type  # 确保 task_type 存在
        ],
        key=lambda x: x["task_type_region"],  # 按 task_type_region 排序
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

    data = {"task_type_list":task_type_list,"title_name":"本周诺元任务","start_of_week":start_of_week,"end_of_week":end_of_week}
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

        sanitized_name = 'nuo-coins-task-weekly'  # 清理文件名
        screenshot_path = screenshot_dir / f"{sanitized_name}.png"
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
                f"本周{type_name}任务图片处理完成☀️\n使用指令'/本周{type_name}任务'进行查看吧！"
            )