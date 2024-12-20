from fish_coins_bot.database.hotta.nuo_coins import NuoCoinsTaskWeekly

from datetime import datetime, timedelta
from tortoise.expressions import Q



async def select_or_add_this_weekly_nuo_coins_weekly_id():
    # 获取今天的日期
    today = datetime.now()

    # 计算本周的开始日期（周一）和结束日期（周日）
    start_of_week = today - timedelta(days=today.weekday())  # 本周一
    end_of_week = start_of_week + timedelta(days=6)  # 本周日

    # 去掉时间部分，仅保留日期
    start_of_week = start_of_week.date()  # 转为日期类型
    end_of_week = end_of_week.date()  # 转为日期类型

    # 查询 task_weekly_date 按日期范围
    weekly_tasks = await NuoCoinsTaskWeekly.filter(
        Q(task_weekly_date__gte=start_of_week) & Q(task_weekly_date__lte=end_of_week),
        del_flag="0"  # 可选条件，查询未删除的数据
    ).values("task_weekly_id")

    # 如果没有查到数据，则新增一条记录
    if not weekly_tasks:
        new_task = await NuoCoinsTaskWeekly.create(
            task_weekly_date=today,  # 使用当前日期时间
            del_flag="0"  # 标记为未删除
        )
        return new_task.task_weekly_id
    else:
        return weekly_tasks[0]["task_weekly_id"]