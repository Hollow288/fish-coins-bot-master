import random
from datetime import datetime
from typing import Optional

from PIL import Image, ImageEnhance, ImageFilter, ImageDraw, ImageFont
from playwright.async_api import async_playwright
import asyncio

from typing_extensions import Tuple

from fish_coins_bot.database.hotta.gacha_record import GachaRecord
from fish_coins_bot.utils.image_utils import screenshot_first_dyn_by_keyword
from tortoise import Tortoise
import json
import asyncio
from pathlib import Path
from bilibili_api import user  # 确保你已经通过 Git 安装了 bilibili_api
from fish_coins_bot.database import database_config
from fish_coins_bot.database.bilibili.dynamics.models import DynamicsHistory
from fish_coins_bot.utils.model_utils import find_key_word_by_type, update_last_two_results


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



async def main():

    base_path = Path(__file__).parent / "templates"
    # 主背景图
    main_back_path = base_path / "chouka_bg.png"
    main_back_img = Image.open(main_back_path).convert("RGBA")

    cards = []
    for i in range(10):
        # 每个 base_img 单独生成
        back_path = base_path / "G-1.png"
        base_img = Image.open(back_path).convert("RGBA")
        base_img = add_side_glow(base_img, glow_color=(255, 165, 0), radius=20, intensity=0.8, y_start=40, y_end=830)
        # base_img = add_side_glow(base_img, glow_color=(180, 80, 255), radius=20, intensity=0.8, y_start=40, y_end=830)
        # base_img = add_side_glow(base_img, glow_color=(80, 180, 255), radius=20, intensity=0.8, y_start=40, y_end=830)
        base_img = paste_image(base_img, base_path / "UI_SSR_lh_nuola.png", 0.6, -100, 60, 0.9,None)
        base_img = paste_image(base_img, base_path / "SSR.png", 0.6, -10, 120,1,None)
        base_img = paste_image(base_img, base_path / "name_xi.png", 1, 10, 350,1,None)

        if i == 0:
            base_img = paste_image(base_img, base_path / "new_2.png", 0.8, 8, 125,1,None)
        base_img = paste_image(base_img, base_path / "UI_UP_Tips01_Bkg.png", 0.6, 150, 400, 0.3,None)
        if i >= 1 :
            base_img = paste_image(base_img, base_path / "Icon_Item_Fusion_Core.webp", 0.6, 50, 580, 0.9,(253,231,138,255))
            # base_img = paste_image(base_img, base_path / "Weapon_R_Exp01.png", 0.3, 50, 580, 0.9,(71,179,163,255))
            base_img = paste_image(base_img, base_path / "image_yifenjie.png", 0.8, 50, 540, 1,None)

        # 添加竖排文字
        base_img = draw_vertical_text(
            font_path="fish_coins_bot/fonts/AlibabaPuHuiTi-3-55-Regular.otf",
            font_size=18,
            image=base_img,
            pos_x=162,
            pos_y=430,
            text='初动重击',
            fill=(255, 255, 255, 255),
            vertical = True
        )

        cards.append(base_img)

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
    result = paste_image(result, base_path / "1c.png", 0.8, 1300, 900, 1,None)
    result = paste_image(result, base_path / "10c.png", 0.8, 1500, 900, 1,None)
    result = paste_image(result, base_path / "share.png", 0.8, 1700, 900, 1,None)
    result = paste_image(result, base_path / "common_btn_back.png", 0.8, 30, 30, 1,None)

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

    result.show()


# async def main():
#
#     await Tortoise.init(
#         config=database_config.TORTOISE_ORM
#     )
#     # 发送者的抽卡记录
#     user_id = ''
#
#     gacha_record = await GachaRecord.filter(user_id=user_id).first()
#     if not gacha_record:
#         gacha_record = await GachaRecord.create(
#             user_id=user_id,
#             ssr_gacha_count=0,
#             sr_gacha_count=0,
#             gacha_total=0,
#             ssr_total=0,
#             update_time=datetime.now()
#         )
#
#     # 开始实际的逻辑处理
#     with open(Path(__file__).parent / 'fish_coins_bot' / 'plugins' / 'hotta_wiki' /  'gacha_config.json', 'r', encoding='utf-8') as f:
#         gacha_config = json.load(f)
#
#     ssr_probability = gacha_config.get("settings", {}).get("ssr_probability", 0)
#     sr_probability = gacha_config.get("settings", {}).get("sr_probability", 0)
#     up_characters = gacha_config.get("settings", {}).get("up_characters", '')
#     ssr_list = gacha_config.get("banner", {}).get("SSR", [])
#     sr_list = gacha_config.get("banner", {}).get("SR", [])
#     r_list = gacha_config.get("banner", {}).get("R", [])
#
#     # 记录基本属性,SR累计次数,中歪记录
#     # 80SSR循环内累计次数
#     ssr_gacha_count = gacha_record.ssr_gacha_count
#     # 10SR循环内累计次数
#     sr_gacha_count = gacha_record.sr_gacha_count
#     # 最近两次SSR中歪记录
#     last_two_ssr_up_results = gacha_record.last_two_ssr_up_results
#     # 用户总累计抽卡次数
#     gacha_total = gacha_record.gacha_total
#     # 用户总累计出SSR次数
#     ssr_total = gacha_record.ssr_total
#
#     results = []  # 存储抽卡结果，最终传给画图方法的数组
#
#     for _ in range(10):
#         rand = random.random()  # [0.0, 1.0) 的随机小数
#
#         # 本次SR概率 这里官方只说明每次概率为1% 但是似乎并不是每次都是1%
#         if sr_gacha_count == 8:
#             this_sr_probability = 0.34
#         elif sr_gacha_count == 9:
#             this_sr_probability = 0.67
#         else:
#             this_sr_probability = sr_probability  # 原本的默认概率
#
#         if rand < ssr_probability or ssr_gacha_count >= 79:
#
#             if last_two_ssr_up_results == '歪歪':
#                 # 连续两次没中UP，这次必中UP
#                 character_name = up_characters
#                 last_two_ssr_up_results = '歪中'
#             elif last_two_ssr_up_results == '中中':
#                 # 连续两次都中UP，这次必中歪（非UP）
#                 # 去掉up角色再抽
#                 character_name = random.choice(ssr_list)
#                 last_two_ssr_up_results = '中歪'
#             else:
#                 # 50% 概率中UP
#                 if random.random() < 0.5:
#                     character_name = up_characters
#                     this_result = "中"
#                 else:
#                     character_name = random.choice(ssr_list)
#                     this_result = "歪"
#
#                 last_two_ssr_up_results = update_last_two_results(last_two_ssr_up_results, this_result)
#             # 加入抽卡结果
#             results.append({
#                 "name": character_name,
#                 "quality": "SSR"
#             })
#
#             ssr_gacha_count = 0  # 重置SSR累计次数
#             sr_gacha_count = 0  # 重置SR累计次数
#             ssr_total += 1
#
#         elif rand < this_sr_probability + ssr_probability or sr_gacha_count >= 9:
#             # 出 SR
#             character_name = random.choice(sr_list)
#             results.append({
#                 "name": character_name,
#                 "quality": "SR"
#             })
#             sr_gacha_count = 0  # 重置SR累计次数
#             ssr_gacha_count += 1
#         else:
#             # 出 R
#             character_name = random.choice(r_list)
#             results.append({
#                 "name": character_name,
#                 "quality": "R"
#             })
#             sr_gacha_count += 1
#             ssr_gacha_count += 1
#
#         gacha_total += 1  # 总抽卡数 +1
#
#     # 保存本次十连结果
#     gacha_record.ssr_gacha_count = ssr_gacha_count
#     gacha_record.sr_gacha_count = sr_gacha_count
#     gacha_record.ssr_total = ssr_total
#     gacha_record.gacha_total = gacha_total
#     gacha_record.last_two_ssr_up_results = last_two_ssr_up_results
#     gacha_record.update_time = datetime.now()
#     await gacha_record.save()




if __name__ == "__main__":
    asyncio.run(main())

