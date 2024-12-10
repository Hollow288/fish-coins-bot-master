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

##### 3.2 使用 GitHub Actions

（也要有DockerFile）项目下创建.github/workflows/deploy.yml文件（这里只实现了持续集成，没有持续部署）

```
name: Deploy to Remote Server

on:
  push:
    branches:
      - master  # 仅当代码推送到 master 分支时触发

jobs:
  build:
    runs-on: ubuntu-latest  # 使用 GitHub 提供的最新 Ubuntu 环境

    steps:
      - name: Checkout code
        uses: actions/checkout@v2  # 获取仓库代码

      - name: Set up QEMU
        uses: docker/setup-qemu-action@v2

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v2  # 配置 Docker 构建工具

      - name: Build Docker image
        run: |
          docker build -t hollow288/nonebot-docker:latest .  # 使用 Dockerfile 构建镜像

      - name: Log in to Docker Hub
        uses: docker/login-action@v2
        with:
          username: ${{ secrets.DOCKER_USERNAME }}  # GitHub Secrets 中配置的 Docker Hub 用户名
          password: ${{ secrets.DOCKER_PASSWORD }}  # GitHub Secrets 中配置的 Docker Hub 密码

      - name: Push Docker image to Docker Hub
        run: |
          docker push hollow288/nonebot-docker:latest  # 推送到 Docker Hub

# 持续部署 没有实现
#  deploy:
#    runs-on: ubuntu-latest
#
#    needs: build  # 需要在构建镜像后才执行部署
#
#    steps:
#      - name: Checkout code
#        uses: actions/checkout@v2
#
#      - name: Set up SSH
#        uses: appleboy/ssh-action@v0.1.5  # 使用 SSH 连接远程服务器
#        with:
#          host: ${{ secrets.SERVER_IP }}  # 远程服务器 IP 地址，使用 GitHub Secrets
#          username: ${{ secrets.SERVER_USER }}  # 远程服务器用户名，使用 GitHub Secrets
#          key: ${{ secrets.SERVER_SSH_KEY }}  # SSH 密钥，使用 GitHub Secrets
#          port: 22  # 如果使用非标准端口，修改端口号
#
#      - name: Deploy to remote server
#        run: |
#          ssh -o StrictHostKeyChecking=no ${{ secrets.SERVER_USER }}@${{ secrets.SERVER_IP }} "
#          docker pull my-docker-image:latest &&
#          docker stop nonebot-container &&
#          docker rm nonebot-container &&
#          docker run -d --name nonebot-container -p 8080:8080 my-docker-image:latest"  # 拉取并运行新的镜像

```

创建Docker Hub账号并创建一个仓库叫`nonebot-docker`，`hollow288`是用户名

 GitHub 仓库的 **Settings** > **Secrets and variables** > **Actions** 中添加 `DOCKER_USERNAME` 和 `DOCKER_PASSWORD`

然后提交代码到`master`分支的时候，就会自动构建docker镜像到Docker Hub

服务器拉取镜像

```
docker pull hollow288/nonebot-docker:latest
```

运行：

```
docker run -d --name nonebot-container -p 8080:8080 -v /opt/nonebot/.env:/app/.env -v /opt/nonebot/screenshots:/app/screenshots -v /opt/nonebot/alias.json:/app/fish_coins_bot/plugins/hotta_wiki/alias.json hollow288/nonebot-docker:latest
```



#### 4.  NapCat&NoneBot

##### 4.1 启动！

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
-v /opt/nonebot/screenshots:/app/screenshots \
mlikiowa/napcat-docker:latest
```





nc和nb都部署后：

```
docker inspect -f '{{range.NetworkSettings.Networks}}{{.IPAddress}}{{end}}' 249e90c35dc2
```

查看地址为：172.17.0.3

nc配置反向ws地址为：ws://172.17.0.3:8080/onebot/v11/ws



##### 4.2 其他说明

在hotta_wiki插件中，我们生成的图片路径是在nonebot文件路径下的screenshots文件夹中，我们发给napcat的文件路径是这样的：

```
image_path = Path("/app/screenshots") / f"{arms_name}.png"
image_message = MessageSegment.image(f"file://{image_path}")
```

所以napcat会去找自己文件目录下的screenshots文件夹，当然是找不到，所以，我们将本地的screenshots文件夹同时挂载到napcat和nonebot上：

```
-v /opt/nonebot/screenshots:/app/screenshots
```

