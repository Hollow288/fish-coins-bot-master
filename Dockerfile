# syntax=docker/dockerfile:1.3

# ===== 构建依赖阶段 =====
FROM python:3.13-slim AS builder

WORKDIR /app

# 安装系统依赖、字体、Playwright 运行库
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential libpq-dev curl \
    xorg xvfb libx11-xcb1 libxcb1 libxcomposite1 libxcursor1 libxdamage1 \
    libxext6 libxfixes3 libxi6 libxrandr2 libgtk-3-0 libpango-1.0-0 \
    libcairo2 libgdk-pixbuf-2.0-0 libatk1.0-0 libdbus-1-3 libgbm1 \
    libasound2 libnss3 libatk-bridge2.0-0 libxss1 locales \
    fonts-noto fonts-noto-cjk fonts-liberation \
    && apt-get clean && rm -rf /var/lib/apt/lists/* && fc-cache -fv

# 安装 Poetry
RUN curl -sSL https://install.python-poetry.org | python3 -
ENV PATH="/root/.local/bin:$PATH"

# 配置 UTF-8
RUN echo "zh_CN.UTF-8 UTF-8" > /etc/locale.gen && \
    locale-gen zh_CN.UTF-8 && \
    update-locale LANG=zh_CN.UTF-8 LC_ALL=zh_CN.UTF-8
ENV LANG=zh_CN.UTF-8
ENV LC_ALL=zh_CN.UTF-8

# 只复制依赖声明文件
COPY pyproject.toml poetry.lock ./

# 安装项目依赖（不包含项目代码）
RUN poetry install --no-root --no-interaction --no-ansi

# 安装 Playwright 浏览器
RUN poetry run python -m playwright install chromium


# ===== 最终运行阶段 =====
FROM python:3.13-slim

WORKDIR /app

# 复制依赖层
COPY --from=builder /root/.local /root/.local
COPY --from=builder /usr/local /usr/local
ENV PATH="/root/.local/bin:$PATH"
ENV LANG=zh_CN.UTF-8
ENV LC_ALL=zh_CN.UTF-8

# 最后复制代码层（改动只影响这一层）
COPY . .

# 暴露端口
EXPOSE 5000

# 启动命令
CMD ["poetry", "run", "python3", "bot.py"]
