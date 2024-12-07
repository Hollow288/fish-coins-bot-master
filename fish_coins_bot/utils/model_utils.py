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
    if arms >= 13:
        return "SS"
    elif arms >= 10:
        return "S"
    elif arms >= 7:
        return "A"
    else:
        return "B"



def highlight_numbers(text):
    # 正则表达式，匹配所有数字
    return re.sub(r'(\d+)', r'<span style="color: red;">\1</span>', text)


def sanitize_filename(filename):
    """清理文件名，移除非法字符"""
    return re.sub(r'[<>:"/\\|?*]', '_', filename)


# 让arms类中的一些文字换成图片路径
def make_arms_img_url(arms: dict):
    arms["arms_type"] = MINIO_HOST + arms_type_url[arms["arms_type"]]
    arms["arms_attribute"] = MINIO_HOST + arms_attribute_url[arms["arms_attribute"]]
    arms["arms_overwhelmed"] = arms_level(arms["arms_overwhelmed"])
    arms["arms_charging_energy"] = arms_level(arms["arms_charging_energy"])
    arms["AlibabaPuHuiTi"] = FONT_HOST + "AlibabaPuHuiTi-3-55-Regular.otf"
    arms["ZCOOLKuaiLe"] = FONT_HOST + "ZCOOLKuaiLe-Regular.ttf"
    arms["background_url"] = BACKGROUND_HOST + f"background-{arms["arms_name"]}.jpeg"
    arms["default_background_url"] = BACKGROUND_HOST + "background.jpeg"

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