from tortoise import fields
from tortoise.models import Model

class DynamicsHistory(Model):
    id: int = fields.IntField(pk=True, description="主键")
    uid: str = fields.CharField(max_length=200, description="用户UID")
    id_str: str = fields.CharField(max_length=200, description="动态ID")

    class Meta:
        table = "dynamics_history"
        table_description = "动态记录历史"
