from rest_framework import serializers

from accounts.serializers import UserSerializer
from immich.client import asset_url

from .models import Recipe


class IngredientField(serializers.JSONField):
    """校验食材为 [{name, amount}] 列表。"""
    def to_internal_value(self, data):
        data = super().to_internal_value(data)
        if not isinstance(data, list):
            raise serializers.ValidationError('食材必须是列表')
        out = []
        for item in data:
            if not isinstance(item, dict):
                raise serializers.ValidationError('每个食材必须是对象')
            name = (item.get('name') or '').strip()
            if not name:
                continue
            out.append({'name': name, 'amount': (item.get('amount') or '').strip()})
        return out


class StepField(serializers.JSONField):
    """校验步骤为 [{text}] 列表。"""
    def to_internal_value(self, data):
        data = super().to_internal_value(data)
        if not isinstance(data, list):
            raise serializers.ValidationError('步骤必须是列表')
        out = []
        for item in data:
            if isinstance(item, str):
                text = item.strip()
            elif isinstance(item, dict):
                text = (item.get('text') or '').strip()
            else:
                raise serializers.ValidationError('步骤格式错误')
            if text:
                out.append({'text': text})
        return out


class RecipeSerializer(serializers.ModelSerializer):
    author = UserSerializer(read_only=True)
    cover_url = serializers.SerializerMethodField()
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    difficulty_display = serializers.CharField(source='get_difficulty_display', read_only=True)
    ingredients = IngredientField(required=False)
    steps = StepField(required=False)

    class Meta:
        model = Recipe
        fields = (
            'id', 'author',
            'title', 'description',
            'category', 'category_display',
            'tags', 'servings', 'total_time_min',
            'difficulty', 'difficulty_display',
            'ingredients', 'steps',
            'cover_url', 'cover_immich_asset_id',
            'visibility',
            'created_at', 'updated_at',
        )
        read_only_fields = ('id', 'author', 'created_at', 'updated_at')

    def get_cover_url(self, obj):
        request = self.context.get('request')

        def absolute(url):
            return request.build_absolute_uri(url) if request else url

        if obj.cover_immich_asset_id:
            return absolute(asset_url(obj.cover_immich_asset_id, 'preview'))
        if obj.cover:
            return absolute(obj.cover.url)
        return None

    def validate_tags(self, value):
        if value in (None, ''):
            return []
        if not isinstance(value, list):
            raise serializers.ValidationError('标签必须是列表')
        return [str(t).strip() for t in value if str(t).strip()][:20]

    def create(self, validated_data):
        validated_data['author'] = self.context['request'].user
        return super().create(validated_data)


class RecipeListSerializer(serializers.ModelSerializer):
    """列表用的精简版（不含 ingredients/steps 详情）。"""
    author = UserSerializer(read_only=True)
    cover_url = serializers.SerializerMethodField()
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    ingredient_count = serializers.SerializerMethodField()

    class Meta:
        model = Recipe
        fields = (
            'id', 'author', 'title', 'category', 'category_display',
            'tags', 'servings', 'total_time_min', 'difficulty',
            'cover_url', 'ingredient_count', 'visibility',
            'created_at', 'updated_at',
        )

    def get_cover_url(self, obj):
        request = self.context.get('request')

        def absolute(url):
            return request.build_absolute_uri(url) if request else url

        if obj.cover_immich_asset_id:
            return absolute(asset_url(obj.cover_immich_asset_id, 'thumbnail'))
        if obj.cover:
            return absolute(obj.cover.url)
        return None

    def get_ingredient_count(self, obj):
        return len(obj.ingredients or [])
