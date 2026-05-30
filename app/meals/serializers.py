from rest_framework import serializers

from accounts.serializers import UserSerializer
from immich.client import asset_url

from .models import DiningOption, MealLog


class DiningOptionSerializer(serializers.ModelSerializer):
    created_by = UserSerializer(read_only=True)
    kind_display = serializers.CharField(source='get_kind_display', read_only=True)

    class Meta:
        model = DiningOption
        fields = (
            'id', 'created_by',
            'name', 'kind', 'kind_display',
            'note', 'weight', 'is_active',
            'created_at', 'updated_at',
        )
        read_only_fields = ('id', 'created_by', 'created_at', 'updated_at')

    def validate_weight(self, value):
        # 限制在 1~10，避免某个选项把摇号池压垮
        return max(1, min(int(value or 1), 10))

    def create(self, validated_data):
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)


def recipe_cover_url(recipe, request, size='thumbnail'):
    """复刻 recipes 的封面取址逻辑，供摇号结果用。"""
    if not recipe:
        return None

    def absolute(url):
        return request.build_absolute_uri(url) if request else url

    if recipe.cover_immich_asset_id:
        return absolute(asset_url(recipe.cover_immich_asset_id, size))
    if recipe.cover:
        return absolute(recipe.cover.url)
    return None


class MealLogSerializer(serializers.ModelSerializer):
    recorder = UserSerializer(read_only=True)
    meal_type_display = serializers.CharField(source='get_meal_type_display', read_only=True)
    display_name = serializers.CharField(read_only=True)
    cover_url = serializers.SerializerMethodField()

    class Meta:
        model = MealLog
        fields = (
            'id', 'recorder',
            'date', 'meal_type', 'meal_type_display',
            'recipe', 'option', 'custom_name',
            'display_name', 'cover_url',
            'note', 'created_at',
        )
        read_only_fields = ('id', 'recorder', 'created_at')

    def get_cover_url(self, obj):
        return recipe_cover_url(obj.recipe, self.context.get('request'))

    def validate(self, attrs):
        # 三种来源至少给一个
        recipe = attrs.get('recipe', getattr(self.instance, 'recipe', None))
        option = attrs.get('option', getattr(self.instance, 'option', None))
        custom = attrs.get('custom_name', getattr(self.instance, 'custom_name', ''))
        if not recipe and not option and not (custom or '').strip():
            raise serializers.ValidationError('请选择菜谱、就餐选项，或填写吃了什么')
        return attrs

    def create(self, validated_data):
        validated_data['recorder'] = self.context['request'].user
        return super().create(validated_data)


class RollResultSerializer(serializers.Serializer):
    """摇号结果里的一个候选（菜谱或就餐选项统一结构）。"""
    type = serializers.CharField()        # 'recipe' | 'option'
    id = serializers.IntegerField()
    name = serializers.CharField()
    kind = serializers.CharField(allow_null=True)        # 仅 option 有
    kind_display = serializers.CharField(allow_null=True)
    cover_url = serializers.CharField(allow_null=True)    # 仅 recipe 可能有
