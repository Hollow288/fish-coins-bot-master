from tortoise import fields
from tortoise.models import Model
from datetime import datetime

class GachaRecord(Model):
    """
    抽卡记录模型
    """
    record_id = fields.IntField(pk=True, description="记录id")
    user_id = fields.CharField(max_length=200, null=True, description="用户id/qq")
    ssr_gacha_count = fields.IntField(null=True, default=0, description="当前累积抽卡次数（用于 ssr 80 抽保底）")
    sr_gacha_count = fields.IntField(null=True, default=0, description="当前 sr 保底计数（每 10 抽内必出 sr+）")
    gacha_total = fields.IntField(null=True, default=0, description="总抽卡数")
    ssr_total = fields.IntField(null=True, default=0, description="累计获取SSR数")
    last_two_ssr_up_results = fields.CharField(max_length=300, null=True, description="中歪记录")
    update_time = fields.DatetimeField(null=True, auto_now=True, description="更新时间")

    class Meta:
        table = "gacha_record"
        table_description = "抽卡记录"
