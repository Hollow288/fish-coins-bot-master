#### 1. python

##### 1. 1 

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