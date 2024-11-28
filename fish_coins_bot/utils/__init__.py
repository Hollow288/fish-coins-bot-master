from .image_utils import fetch_image,make_live_image
import datetime

def calc_time_total(t):
    t = int(t * 1000)
    if t < 5000:
        return f"{t} 毫秒"

    timedelta = datetime.timedelta(seconds=t // 1000)
    day = timedelta.days
    hour, mint, sec = tuple(int(n) for n in str(timedelta).split(",")[-1].split(":"))

    total = ""
    if day:
        total += f"{day} 天 "
    if hour:
        total += f"{hour} 小时 "
    if mint:
        total += f"{mint} 分钟 "
    if sec and not day and not hour:
        total += f"{sec} 秒 "
    return total



__all__ = ["fetch_image","make_live_image","calc_time_total"]  # 明确导出的函数



