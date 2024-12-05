# 使用官方 Python 3.13 作为基础镜像
FROM python:3.13-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖、Poetry 和其他必要工具
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    xorg \
    xvfb \
    libx11-xcb1 \
    libxcb1 \
    libxcomposite1 \
    libxcursor1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxi6 \
    libxrandr2 \
    libgtk-3-0 \
    libpango-1.0-0 \
    libcairo2 \
    libgdk-pixbuf2.0-0 \
    libatk1.0-0 \
    libdbus-1-3 \
    libgbm1 \
    libasound2 \
    && apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# 安装 Poetry
RUN curl -sSL https://install.python-poetry.org | python3 -

# 设置 Poetry 为全局可用
ENV PATH="/root/.local/bin:$PATH"

# 复制 Poetry 的配置文件
COPY pyproject.toml poetry.lock /app/

# 安装项目依赖
RUN poetry install --no-root

# 安装 Playwright 及其依赖的浏览器
RUN poetry run python -m playwright install firefox

# 暴露端口
EXPOSE 5000

# 复制项目源代码到工作目录
COPY . /app/

# 设置环境变量（如果有特定配置路径可以在这里设置）
# ENV NONEBOT_CONFIG=/app/config.yaml

# 容器启动时执行命令
CMD ["poetry", "run", "python3", "bot.py"]
