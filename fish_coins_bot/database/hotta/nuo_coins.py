from tortoise import fields
from tortoise.models import Model

class NuoCoinsTaskType(Model):
    task_type_id = fields.IntField(pk=True, auto_increment=True, description="种类ID")
    task_type_region = fields.CharField(max_length=100, null=True, description="地区")
    task_type_npc = fields.CharField(max_length=100, null=True, description="NPC")
    task_type_position = fields.CharField(max_length=100, null=True, description="位置")
    task_type_details = fields.CharField(max_length=100, null=True, description="任务详情")
    task_type_reward = fields.CharField(max_length=100, null=True, description="任务奖励")
    del_flag = fields.CharField(max_length=1, default="0", null=True, description="是否删除（0未删除 1已删除）")

    class Meta:
        table = "nuo_coins_task_type"
        comments = "每周诺元任务种类"

class NuoCoinsTaskWeekly(Model):
    task_weekly_id = fields.IntField(pk=True, auto_increment=True, description="任务ID")
    task_weekly_date = fields.DatetimeField(null=True, description="发布时间")
    del_flag = fields.CharField(max_length=1, default="0", null=True, description="是否删除（0未删除 1已删除）")

    class Meta:
        table = "nuo_coins_task_weekly"
        comments = "每周诺元任务"


class NuoCoinsTaskWeeklyDetail(Model):
    """
    每周诺元任务明细
    """
    weekly_detail_id = fields.IntField(pk=True, description="明细ID")
    task_weekly_id = fields.IntField(null=True, description="每周任务ID")
    task_type = fields.ForeignKeyField('models.NuoCoinsTaskType', related_name='weekly_details', on_delete=fields.CASCADE, null=True, description="任务种类ID")
    task_weekly_contributors = fields.CharField(max_length=500, null=True, description="贡献者")
    del_flag = fields.CharField(max_length=1, default="0", description="是否删除（0未删除 1已删除）")

    class Meta:
        table = "nuo_coins_task_weekly_detail"
        table_description = "每周诺元任务明细"