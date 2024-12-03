from tortoise.models import Model
from tortoise import fields


class Arms(Model):
    """
    武器基本信息模型
    """
    arms_id = fields.IntField(pk=True, description="武器ID")
    arms_name = fields.CharField(max_length=200, null=True, description="武器名称")
    arms_rarity = fields.CharField(max_length=200, null=True, description="武器稀有度")
    arms_type = fields.CharField(max_length=100, null=True, description="武器定位")
    arms_attribute = fields.CharField(max_length=100, null=True, description="武器属性")
    arms_overwhelmed = fields.DecimalField(max_digits=18, decimal_places=4, null=True, description="武器破防")
    arms_charging_energy = fields.DecimalField(max_digits=18, decimal_places=4, null=True, description="武器充能")
    arms_aggressivity_start = fields.DecimalField(max_digits=18, decimal_places=4, null=True, description="武器攻击力-初始")
    arms_blood_volume_start = fields.DecimalField(max_digits=18, decimal_places=4, null=True, description="武器血量-初始")
    arms_defense_capability_start = fields.DecimalField(max_digits=18, decimal_places=4, null=True, description="武器全抗-初始")
    arms_critical_strike_start = fields.DecimalField(max_digits=18, decimal_places=4, null=True, description="武器暴击-初始")
    arms_aggressivity_end = fields.DecimalField(max_digits=18, decimal_places=4, null=True, description="武器攻击-满级")
    arms_blood_volume_end = fields.DecimalField(max_digits=18, decimal_places=4, null=True, description="武器血量-满级")
    arms_defense_capability_end = fields.DecimalField(max_digits=18, decimal_places=4, null=True, description="武器全抗-满级")
    arms_critical_strike_end = fields.DecimalField(max_digits=18, decimal_places=4, null=True, description="武器暴击-满级")
    arms_thumbnail_url = fields.CharField(max_length=200, null=True, description="武器缩略图地址")
    arms_description = fields.CharField(max_length=500, null=True, description="武器描述")
    create_by = fields.BigIntField(null=True, description="创建人")
    create_time = fields.DatetimeField(null=True, description="创建时间")
    update_by = fields.BigIntField(null=True, description="更新人")
    update_time = fields.DatetimeField(null=True, description="更新时间")
    del_flag = fields.CharField(max_length=1, default="0", description="是否删除（0未删除 1已删除）")

    class Meta:
        table = "arms"  # 数据库中的表名
        table_description = "武器基本信息"


class ArmsStarRatings(Model):
    """
    武器星级信息模型
    """
    star_ratings_id = fields.IntField(pk=True, description="星级id")
    arms = fields.ForeignKeyField(
        "models.Arms",
        related_name="star_ratings",
        on_delete=fields.CASCADE,
        description="关联的武器"
    )
    items_name = fields.CharField(max_length=200, null=True, description="词条名称")
    items_describe = fields.TextField(null=True, description="词条描述")

    class Meta:
        table = "arms_star_ratings"
        table_description = "武器星级"
