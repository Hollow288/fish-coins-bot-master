from tortoise.models import Model
from tortoise import fields

class BotLiveState(Model):
    """
    机器人-推送直播间
    """
    id = fields.IntField(pk=True, description="主键")
    live_id = fields.IntField(unique=True, description="主播间ID，必须唯一")
    live_state = fields.CharField(max_length=1, null=True, description="主播间状态")
    del_flag = fields.CharField(max_length=1, default="0", null=True, description="是否删除（0未删除 1已删除）")

    class Meta:
        table = "bot_live_state"  # 指定数据库表名
        table_description = "机器人-推送直播间"  # 表描述
