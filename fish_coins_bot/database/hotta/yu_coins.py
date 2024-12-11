from tortoise import fields
from tortoise.models import Model

class YuCoinsTaskType(Model):
    task_type_id = fields.IntField(pk=True, auto_increment=True, description="种类ID")
    task_type_region = fields.CharField(max_length=100, null=True, description="地区")
    task_type_npc = fields.CharField(max_length=100, null=True, description="NPC")
    task_type_position = fields.CharField(max_length=100, null=True, description="位置")
    task_type_details = fields.CharField(max_length=100, null=True, description="任务详情")
    task_type_reward = fields.CharField(max_length=100, null=True, description="任务奖励")
    del_flag = fields.CharField(max_length=1, default="0", null=True, description="是否删除（0未删除 1已删除）")

    class Meta:
        table = "yu_coins_task_type"
        comments = "每周域币任务种类"

class YuCoinsTaskWeekly(Model):
    task_weekly_id = fields.IntField(pk=True, auto_increment=True, description="任务ID")
    task_type_ids = fields.CharField(max_length=100, null=True, description="每周任务IDS")
    task_weekly_date = fields.DatetimeField(null=True, description="发布时间")
    del_flag = fields.CharField(max_length=1, default="0", null=True, description="是否删除（0未删除 1已删除）")

    class Meta:
        table = "yu_coins_task_weekly"
        comments = "每周域币任务"