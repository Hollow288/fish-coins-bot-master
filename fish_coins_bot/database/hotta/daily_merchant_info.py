from tortoise import fields
from tortoise.models import Model

class DailyMerchantInfo(Model):
    info_id = fields.IntField(auto_increment=True, pk=True, description='ID')
    info_name = fields.CharField(max_length=100, null=True, description='发布名称')
    info_position = fields.DatetimeField(null=True, description='发布备注')
    info_date = fields.DatetimeField(null=True, description='发布时间')
    info_user_id = fields.DatetimeField(null=True, description='发布人ID')
    info_group_id = fields.DatetimeField(null=True, description='发布群号')
    del_flag = fields.CharField(max_length=1, default='0', null=True, description='是否删除（0未删除 1已删除）')
    # 表名
    class Meta:
        table = "daily_merchant_info"
        # 添加表注释（如果需要支持）
        table_description = "每日商人"