import nonebot
from nonebot.adapters.onebot.v11 import Adapter as ONEBOT_V11Adapter
from fish_coins_bot.database.startup_tasks import initialize_live_state
from tortoise import Tortoise
from fish_coins_bot.database import database_config

# 初始化 NoneBot
nonebot.init()

# 注册适配器
driver = nonebot.get_driver()
driver.register_adapter(ONEBOT_V11Adapter)


@driver.on_startup
async def do_something():
    await Tortoise.init(
        config=database_config.TORTOISE_ORM
    )
    await initialize_live_state()

# 在这里加载插件
# nonebot.load_builtin_plugins("echo")  # 内置插件
# nonebot.load_plugin("thirdparty_plugin")  # 第三方插件
nonebot.load_plugins("fish_coins_bot/plugins")  # 本地插件

if __name__ == "__main__":
    nonebot.run()