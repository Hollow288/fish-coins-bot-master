# 使用官方 Python 3.13-slim（基于 Debian Trixie）
FROM python:3.13-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖、Poetry 和 Playwright 所需库
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    # Playwright 运行所需库
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
    libgdk-pixbuf-2.0-0 \
    libatk1.0-0 \
    libdbus-1-3 \
    libgbm1 \
    libasound2 \
    libnss3 \
    libatk-bridge2.0-0 \
    libxss1 \
    locales \
    && apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# 安装字体（中文、Arial、Noto）
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    fonts-noto \
    fonts-noto-cjk \
    fonts-liberation \
    && fc-cache -fv && \
    rm -rf /var/lib/apt/lists/*

# 安装 Poetry
RUN curl -sSL https://install.python-poetry.org | python3 -

# 将 Poetry 添加到 PATH
ENV PATH="/root/.local/bin:$PATH"

# 配置 UTF-8 环境
RUN echo "zh_CN.UTF-8 UTF-8" > /etc/locale.gen && \
    locale-gen zh_CN.UTF-8 && \
    update-locale LANG=zh_CN.UTF-8 LC_ALL=zh_CN.UTF-8

# 设置环境变量
ENV LANG=zh_CN.UTF-8
ENV LC_ALL=zh_CN.UTF-8

# 复制 Poetry 配置文件
COPY pyproject.toml poetry.lock /app/

# 安装项目依赖
RUN poetry install --no-root

# 安装 Playwright 及其浏览器
RUN poetry run python -m playwright install chromium

# 暴露端口
EXPOSE 5000

# 复制项目代码
COPY . /app/

# 容器启动命令
CMD ["poetry", "run", "python3", "bot.py"]
