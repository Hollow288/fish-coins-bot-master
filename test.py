from tortoise import Tortoise
import asyncio
import re


async def make_yu_coins_weekly_image():
    # 输入的字符串
    input_string = " 1 2 11  20 "

    # 使用正则表达式提取所有数字
    numbers = re.findall(r'\d+', input_string)

    # 将字符串转化为整数类型
    numbers = [int(num) for num in numbers]

    print(numbers)

if __name__ == "__main__":
    asyncio.run(make_yu_coins_weekly_image())
    # asyncio.run(select_or_add_this_weekly_yu_coins_weekly_id())
