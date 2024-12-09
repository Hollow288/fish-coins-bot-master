from tortoise import fields
from tortoise.models import Model

class Willpower(Model):
    willpower_id = fields.IntField(pk=True, auto_increment=True, comment='意志id')
    willpower_name = fields.CharField(max_length=200, null=True, comment='意志名称')
    willpower_rarity = fields.CharField(max_length=200, null=True, comment='意志稀有度')
    willpower_description = fields.CharField(max_length=500, null=True, comment='意志描述')
    willpower_thumbnail_url = fields.CharField(max_length=300, null=True, comment='意志缩略图')
    create_by = fields.BigIntField(null=True, comment='创建人')
    create_time = fields.DatetimeField(null=True, comment='创建时间')
    update_by = fields.BigIntField(null=True, comment='更新人')
    update_time = fields.DatetimeField(null=True, comment='更新时间')
    del_flag = fields.CharField(max_length=1, default='0', null=True, comment='是否删除（0未删除 1已删除）')

    class Meta:
        table = "willpower"  # 表名
        comment = "意志图鉴"  # 表的注释



class WillpowerSuit(Model):
    suit_id = fields.IntField(pk=True, auto_increment=True, comment='意志套装id')
    willpower_id = fields.IntField(null=True, comment='意志id')
    items_name = fields.CharField(max_length=200, null=True, comment='套装名称')
    items_describe = fields.CharField(max_length=5000, null=True, comment='套装描述')

    class Meta:
        table = "willpower_suit"  # 表名
        comment = "意志套装"  # 表的注释
