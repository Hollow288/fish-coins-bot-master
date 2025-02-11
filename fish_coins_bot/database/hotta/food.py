from tortoise import fields
from tortoise.models import Model

class Food(Model):
    food_id = fields.IntField(pk=True, autoincrement=True, comment='食物ID')
    food_name = fields.CharField(max_length=200, null=True, comment='食物名称')
    food_rarity = fields.CharField(max_length=100, null=True, comment='食物稀有度')
    food_type = fields.CharField(max_length=200, null=True, comment='食物种类')
    food_effect = fields.CharField(max_length=300, null=True, comment='食物效果')
    food_source = fields.CharField(max_length=300, null=True, comment='食物来源')
    food_describe = fields.CharField(max_length=300, null=True, comment='食物描述')
    food_thumbnail_url = fields.CharField(max_length=200, null=True, comment='食物缩略图地址')
    del_flag = fields.CharField(max_length=1, default='0', null=True, comment='是否删除（0未删除 1已删除）')

    class Meta:
        table = "food"
        comment = "食物图鉴"


from tortoise import fields
from tortoise.models import Model

class FoodFormula(Model):
    formula_id = fields.IntField(pk=True, autoincrement=True, comment='配方ID')
    food = fields.ForeignKeyField("models.Food", related_name="food_formulas", null=True, comment='食物ID')
    ingredients_id = fields.IntField(null=True, comment='食材ID')  # 食材ID，关联到Food表的food_id
    ingredients_num = fields.IntField(null=True, comment='食材数量')

    class Meta:
        table = "food_formula"
        comment = "食物配方"
