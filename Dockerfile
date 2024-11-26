# 使用官方 Python 3.13 作为基础镜像
FROM python:3.13-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖，Poetry 和其他必要工具
RUN apt-get update && \
    apt-get install -y \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 安装 Poetry
RUN curl -sSL https://install.python-poetry.org | python3 -

# 设置 Poetry 为全局可用
ENV PATH="/root/.local/bin:$PATH"

# 复制 Poetry 的配置文件
COPY pyproject.toml poetry.lock /app/

# 安装项目依赖
RUN poetry install

# 复制项目源代码到工作目录
COPY . /app/

# 设置环境变量（例如：NoneBot 配置文件路径）
# ENV NONEBOT_CONFIG=/app/config.yaml

# 容器启动时执行命令
CMD ["poetry", "run", "python3", "bot.py"]
