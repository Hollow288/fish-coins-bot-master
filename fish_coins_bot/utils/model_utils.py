import os

from dotenv import load_dotenv
import re
import json
from pathlib import Path

# 加载 .env 文件
load_dotenv()


MINIO_HOST = os.getenv("MINIO_HOST")
FONT_HOST = os.getenv("FONT_HOST")
BACKGROUND_HOST = os.getenv("BACKGROUND_HOST")

arms_type_url = {
    '强攻': 'icon_qianggong.webp',
    '坚毅': 'icon_fangyu.webp',
    '恩赐': 'icon_zengyi.webp',
}

arms_attribute_url = {
    '物理': 'icon_element_wu.webp',
    '火焰': 'icon_element_huo.webp',
    '寒冰': 'icon_element_bing.webp',
    '雷电': 'icon_element_lei.webp',
    '异能': 'icon_element_powers.webp',
    '物火': 'icon_element_wuhuo.webp',
    '火物': 'icon_element_huowu.webp',
    '冰雷': 'icon_element_binglei.webp',
    '雷冰': 'icon_element_leibing.webp',
}

def arms_level(arms):

    # 判断并返回等级
    if arms >= 14.1:
        return "SS"
    elif arms >= 10.1:
        return "S"
    elif arms >= 7:
        return "A"
    else:
        return "B"


def highlight_numbers(text):
    # 将换行符(\n)替换为 <br> 标签
    text = re.sub(r'\n', r'<br>', text)

    # 正则表达式，匹配所有数字并高亮
    return re.sub(r'(\d+)', r'<span style="color: red;">\1</span>', text)


def yu_different_colors(text):
    try:
        # 将 text 转换为整数
        value = int(text)

        # 根据范围返回对应的背景颜色
        if 1 <= value <= 7:
            return 'background-color: rgba(253, 193, 0, 0.35);'
        elif 8 <= value <= 13:
            return 'background-color: rgba(105, 139, 34, 0.35);'
        elif 14 <= value <= 26:
            return 'background-color: rgba(32, 178, 170, 0.35);'
        elif 27 <= value <= 44:
            return 'background-color: rgba(85, 96, 143, 0.35);'
        else:
            return ''  # 如果不在范围内，返回空字符串
    except ValueError:
        # 如果 text 不是有效的数字，返回默认空样式
        return ''


def nuo_different_colors(text):
    try:
        # 将 text 转换为整数
        value = int(text)

        # 根据范围返回对应的背景颜色
        if 1 <= value <= 2:
            return 'background-color: rgba(253, 193, 0, 0.2);'
        elif 3 <= value <= 13:
            return 'background-color: rgba(255, 255, 255, 0.2);'
        else:
            return ''  # 如果不在范围内，返回空字符串
    except ValueError:
        # 如果 text 不是有效的数字，返回默认空样式
        return ''

def the_font_bold(text):
    # 使用正则表达式匹配括号及其内容，并替换为带 <strong> 标签的格式
    result = re.sub(r'(\(.*?\))', r'<strong>\1</strong>', text)
    return result


def sanitize_filename(filename):
    """清理文件名，移除非法字符"""
    return re.sub(r'[<>:"/\\|?*]', '_', filename)

# 提取用户输入的域币任务ID
async def extract_yu_coins_type_id(input_string:str):

    numbers = re.findall(r'\d+', input_string)

    numbers = list(set(int(num) for num in numbers if 1 <= int(num) <= 44))

    return numbers


async def extract_nuo_coins_type_id(input_string:str):

    numbers = re.findall(r'\d+', input_string)

    numbers = list(set(int(num) for num in numbers if 1 <= int(num) <= 44))

    return numbers


# 让arms类中的一些文字换成图片路径
def make_arms_img_url(arms: dict):
    arms["arms_type"] = MINIO_HOST + arms_type_url[arms["arms_type"]]
    arms["arms_attribute"] = MINIO_HOST + arms_attribute_url[arms["arms_attribute"]]
    arms["arms_overwhelmed"] = arms_level(arms["arms_overwhelmed"])
    arms["arms_charging_energy"] = arms_level(arms["arms_charging_energy"])
    arms["AlibabaPuHuiTi"] = FONT_HOST + "AlibabaPuHuiTi-3-55-Regular.otf"
    arms["ZCOOLKuaiLe"] = FONT_HOST + "ZCOOLKuaiLe-Regular.ttf"
    arms["background_url"] = BACKGROUND_HOST + "arms/" + f"background-{arms["arms_name"]}.jpeg"
    arms["default_background_url"] = BACKGROUND_HOST + "background.jpeg"


def make_willpower_img_url(willpower: dict):
    willpower["AlibabaPuHuiTi"] = FONT_HOST + "AlibabaPuHuiTi-3-55-Regular.otf"
    willpower["ZCOOLKuaiLe"] = FONT_HOST + "ZCOOLKuaiLe-Regular.ttf"
    willpower["background_url"] = BACKGROUND_HOST + "willpower/" + f"background-{willpower["willpower_name"]}.jpeg"
    willpower["default_background_url"] = BACKGROUND_HOST + "background.jpeg"

def make_yu_coins_img_url(yu_coins: dict):
    yu_coins["AlibabaPuHuiTi"] = FONT_HOST + "AlibabaPuHuiTi-3-45-Light.otf"
    yu_coins["ZCOOLKuaiLe"] = FONT_HOST + "ZCOOLKuaiLe-Regular.ttf"
    yu_coins["logo_ht"] = MINIO_HOST + "logo_ht.png"
    
def make_nuo_coins_img_url(nuo_coins: dict):
    nuo_coins["AlibabaPuHuiTi"] = FONT_HOST + "AlibabaPuHuiTi-3-45-Light.otf"
    nuo_coins["ZCOOLKuaiLe"] = FONT_HOST + "ZCOOLKuaiLe-Regular.ttf"
    nuo_coins["logo_ht"] = MINIO_HOST + "logo_ht.png"

def make_wiki_help_img_url(nuo_coins: dict):
    nuo_coins["AlibabaPuHuiTi"] = FONT_HOST + "AlibabaPuHuiTi-3-45-Light.otf"
    nuo_coins["ZCOOLKuaiLe"] = FONT_HOST + "ZCOOLKuaiLe-Regular.ttf"
    nuo_coins["default_background_url"] = BACKGROUND_HOST + "background-help.png"

# 检查武器名称别名
def check_arms_alias(arms_name:str):

    # 读取 alias.json 文件
    with open(Path(__file__).parent.parent / 'plugins' / 'hotta_wiki' / 'alias.json' , 'r', encoding='utf-8') as f:
        alias_data = json.load(f)

    # 获取武器的别名字典
    weapon_aliases = alias_data.get('武器', {})

    # 遍历每个武器的别名列表
    for weapon_name, aliases in weapon_aliases.items():
        # 如果传入的名字在某个别名列表中
        if arms_name in aliases:
            # 返回该武器的主名称（第一个名称作为主名称）
            return weapon_name

    # 如果没有找到对应的别名，返回原始名称
    return arms_name

# 检查意志名称别名
def check_willpower_alias(willpower_name:str):

    # 读取 alias.json 文件
    with open(Path(__file__).parent.parent / 'plugins' / 'hotta_wiki' / 'alias.json' , 'r', encoding='utf-8') as f:
        alias_data = json.load(f)

    # 获取意志的别名字典
    will_aliases = alias_data.get('意志', {})

    # 遍历每个武器的别名列表
    for will_name, aliases in will_aliases.items():
        # 如果传入的名字在某个别名列表中
        if willpower_name in aliases:
            # 返回该武器的主名称（第一个名称作为主名称）
            return will_name

    # 如果没有找到对应的别名，返回原始名称
    return willpower_name