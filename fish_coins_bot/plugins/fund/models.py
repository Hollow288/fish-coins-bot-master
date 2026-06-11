from tortoise import fields
from tortoise.models import Model


class FundSubscription(Model):
    """用户与基金的订阅绑定：(user_id, fund_code) 一行，「基金走势」按此查个人基金。"""

    id = fields.IntField(pk=True, description="主键")
    user_id = fields.CharField(max_length=32, index=True, description="绑定人QQ")
    fund_code = fields.CharField(max_length=6, index=True, description="基金代码(6位)")
    fund_name = fields.CharField(max_length=100, null=True, description="基金名称(添加成功时回填,仅展示用)")
    created_at = fields.DatetimeField(auto_now_add=True, description="绑定时间")
    updated_at = fields.DatetimeField(auto_now=True, description="更新时间")

    class Meta:
        table = "fund_subscription"
        table_description = "用户与基金的订阅绑定"
        unique_together = (("user_id", "fund_code"),)
