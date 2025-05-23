import nonebot
from nonebot.adapters.onebot.v11 import Adapter as ONEBOT_V11Adapter
from fish_coins_bot.utils.startup_tasks import initialize_live_state
from tortoise import Tortoise
from fish_coins_bot.database import database_config
from fish_coins_bot.utils.image_utils import make_all_arms_image, make_all_willpower_image, make_yu_coins_type_image, \
    make_yu_coins_weekly_image, make_nuo_coins_type_image, make_nuo_coins_weekly_image, make_all_arms_attack_image, \
    make_wiki_help, make_event_consultation, make_food_image, make_event_consultation_end_image

# 初始化 NoneBot
nonebot.init()

# 注册适配器
driver = nonebot.get_driver()
driver.register_adapter(ONEBOT_V11Adapter)


@driver.on_startup
async def do_something():
    # 初始化数据库
    await Tortoise.init(
        config=database_config.TORTOISE_ORM
    )
    # 帮助
    await make_wiki_help(frequency="first")
    # 即将结束的活动
    await make_event_consultation_end_image(frequency="first")
    # 活动资讯
    await make_event_consultation()
    # 初始化开播状态
    await initialize_live_state()
    # 初始化武器图片
    await make_all_arms_image()
    # 初始化武器攻击模组图片
    await make_all_arms_attack_image()
    # 初始化意志图片
    await make_all_willpower_image()
    #食物图鉴
    await make_food_image()
    # 初始化每周域币汇总图片
    await make_yu_coins_type_image(frequency="first")
    # 初始化本周域币任务图片
    await make_yu_coins_weekly_image(frequency="first")
    # 初始化每周诺元汇总图片
    await make_nuo_coins_type_image(frequency="first")
    # 初始化本周诺元任务图片
    await make_nuo_coins_weekly_image(frequency="first")


# 在这里加载插件
# nonebot.load_builtin_plugins("echo")  # 内置插件
# nonebot.load_plugin("thirdparty_plugin")  # 第三方插件
nonebot.load_plugins("fish_coins_bot/plugins")  # 本地插件

if __name__ == "__main__":
    nonebot.run()