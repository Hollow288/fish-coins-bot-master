import os

from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()




# 从环境变量中读取数据库配置
DATABASE_USERNAME = os.getenv("DATABASE_USERNAME")
DATABASE_PASSWORD = os.getenv("DATABASE_PASSWORD")
DATABASE_HOST = os.getenv("DATABASE_HOST")
DATABASE_PORT = os.getenv("DATABASE_PORT", "3306")  # 如果没有提供端口号，则默认使用 3306
DATABASE_NAME = os.getenv("DATABASE_NAME")

TORTOISE_ORM = {
    "connections": {
        "default": f"mysql://{DATABASE_USERNAME}:{DATABASE_PASSWORD}@{DATABASE_HOST}:{DATABASE_PORT}/{DATABASE_NAME}"
    },
    "apps": {
        "models": {
            "models": [
                "fish_coins_bot.database.live.models",
                "fish_coins_bot.database.hotta.arms",
                "fish_coins_bot.database.hotta.willpower",

            ],
            "default_connection": "default",
        },
    },
    # 设置时区为 Asia/Shanghai (UTC+8)
    "timezone": "Asia/Shanghai",
}
