#### 1. python

##### 1. 1 可选依赖

```
tortoise-orm[asyncpg]>=0.19.3
```

- 方括号中的内容是 **可选依赖项**（extras）。

- 在这个例子中，`asyncpg` 是一个高性能的 PostgreSQL 异步驱动程序，用于支持 Tortoise-ORM 连接到 **PostgreSQL **数据库。

- 声明 `[asyncpg]` 表示安装 `tortoise-orm` 时会同时安装 `asyncpg` 作为依赖。
- 这有点类似于maven中的**optional**，依赖不会被全部引入，必须显式声明，才会被引入

#### 2. pyproject

##### 2.1. 类似于maven的依赖管理器？

使用 pip安装：

```
pip install poetry 
```

查看版本，是否安装成功：

```
poetry --version
```

在项目文件夹初始化项目，然后会出来一些对话，填一些项目的基本信息并初始化pyproject.toml文件：

```
poetry init
```

使用poetry安装依赖，依赖会自动被pyproject.toml文件和poetry.lock文件记录：

```
poetry add <package-name>
```

进入虚拟环境：

```
poetry shell
```

控制台会变成这样：

```
(fish-coins-bot-master-py3.13) PS C:\XM\MY\fish-coins-bot-master> 
```

在虚拟环境中启动项目：

```
python main.py
```

##### 2.2 设置pycharm环境：

查看虚拟环境的位置：

```
poetry env info --path
```

setting中搜索python interpreter,然后add interpreter->add local  interpreter ->select existing ->选择虚拟环境位置下的Scripts\python.exe

#### 3. docker

##### 3.1 windows制作镜像

先下载Docker Desktop

编写Dockerfile放到项目下面：

```
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

```

在项目目录制作镜像：

```
docker build -t nonebot-docker:python3.13 .
```

打成tar包

```
docker save -o nonebot-docker.tar nonebot-docker:python3.13
```

在centos上加载镜像

```
docker load < /usr/src/nonebot-docker.tar
```

运行

```
docker run -d --name nonebot-container -p 8080:8080 -v /opt/nonebot/.env:/app/.env nonebot-docker:python3.13
```

#### 4.  NapCat&NoneBot

napcat 启动：

```
docker run -d \
-e NAPCAT_GID=$(id -g) \
-e NAPCAT_UID=$(id -u) \
-p 3000:3000 \
-p 3001:3001 \
-p 6099:6099 \
--name napcat \
--restart=always \
-v /opt/napcat/data:/app/.config/QQ \
-v /opt/napcat/config:/app/napcat/config \
mlikiowa/napcat-docker:latest
```





nc和nb都部署后：

```
docker inspect -f '{{range.NetworkSettings.Networks}}{{.IPAddress}}{{end}}' 249e90c35dc2
```

查看地址为：172.17.0.3

nc配置反向ws地址为：ws://172.17.0.3:8080/onebot/v11/ws

