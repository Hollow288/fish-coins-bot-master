from tortoise import fields
from tortoise.models import Model

class DynamicsHistory(Model):
    id: int = fields.IntField(pk=True, description="主键")
    platform: str = fields.CharField(max_length=32, default="bilibili", index=True, description="平台")
    uid: str = fields.CharField(max_length=200, index=True, description="平台用户ID")
    id_str: str = fields.CharField(max_length=200, index=True, description="动态/推文ID")
    created_at = fields.DatetimeField(auto_now_add=True, description="创建时间")

    class Meta:
        table = "dynamics_history"
        table_description = "跨平台动态记录历史"
        indexes = (("platform", "uid", "id_str"),)
