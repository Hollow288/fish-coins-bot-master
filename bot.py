import nonebot
from nonebot.adapters.onebot.v11 import Adapter as ONEBOT_V11Adapter
from fish_coins_bot.utils.startup_tasks import initialize_live_state
from tortoise import Tortoise
from fish_coins_bot.database import database_config
from fish_coins_bot.utils.image_utils import make_wiki_help, make_event_news_end_image, make_event_news

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
    await make_event_news_end_image(frequency="first")
    # 活动资讯
    await make_event_news()
    # 初始化开播状态
    await initialize_live_state()


# 在这里加载插件
# nonebot.load_builtin_plugins("echo")  # 内置插件
# nonebot.load_plugin("thirdparty_plugin")  # 第三方插件
nonebot.load_plugins("fish_coins_bot/plugins")  # 本地插件

if __name__ == "__main__":
    nonebot.run()