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