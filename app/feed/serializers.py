from rest_framework import serializers

from accounts.serializers import UserSerializer
from immich.client import asset_url

from .models import Comment, EMOJI_CHAR, Moment, MomentImage


def build_reaction_summary(reactions, user_id):
    """reactions: 可迭代的 Reaction。返回 (summary_list, my_reaction_key)。

    summary_list 按数量降序：[{emoji, char, count, mine}]
    """
    counts = {}
    mine = None
    for r in reactions:
        counts[r.emoji] = counts.get(r.emoji, 0) + 1
        if r.user_id == user_id:
            mine = r.emoji
    summary = [
        {
            'emoji': key,
            'char': EMOJI_CHAR.get(key, key),
            'count': count,
            'mine': key == mine,
        }
        for key, count in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    ]
    return summary, mine


class MomentImageSerializer(serializers.ModelSerializer):
    """图片源可能是本地 ImageField，也可能是 Immich asset。前端只读 URL 即可。"""
    source = serializers.CharField(read_only=True)
    thumbnail_url = serializers.SerializerMethodField()
    preview_url = serializers.SerializerMethodField()
    original_url = serializers.SerializerMethodField()

    class Meta:
        model = MomentImage
        fields = (
            'id', 'order', 'source', 'immich_asset_id',
            'thumbnail_url', 'preview_url', 'original_url',
        )
        read_only_fields = fields

    def _abs(self, url):
        request = self.context.get('request')
        return request.build_absolute_uri(url) if request else url

    def get_thumbnail_url(self, obj):
        if obj.immich_asset_id:
            return self._abs(asset_url(obj.immich_asset_id, 'thumbnail'))
        if obj.image:
            return self._abs(obj.image.url)
        return None

    def get_preview_url(self, obj):
        if obj.immich_asset_id:
            return self._abs(asset_url(obj.immich_asset_id, 'preview'))
        if obj.image:
            return self._abs(obj.image.url)
        return None

    def get_original_url(self, obj):
        if obj.immich_asset_id:
            return self._abs(asset_url(obj.immich_asset_id, 'original'))
        if obj.image:
            return self._abs(obj.image.url)
        return None


class CommentSerializer(serializers.ModelSerializer):
    author = UserSerializer(read_only=True)
    # 写入时携带被 @ 的家庭成员 id；只写不读
    mentioned_user_ids = serializers.ListField(
        child=serializers.IntegerField(), write_only=True, required=False,
    )

    class Meta:
        model = Comment
        fields = ('id', 'author', 'content', 'mentioned_user_ids', 'created_at')
        read_only_fields = ('id', 'author', 'created_at')

    def create(self, validated_data):
        validated_data.pop('mentioned_user_ids', None)
        validated_data['author'] = self.context['request'].user
        validated_data['moment_id'] = self.context['moment_id']
        return super().create(validated_data)


class MomentSerializer(serializers.ModelSerializer):
    author = UserSerializer(read_only=True)
    images = MomentImageSerializer(many=True, read_only=True)
    reactions_count = serializers.SerializerMethodField()
    reactions_summary = serializers.SerializerMethodField()
    my_reaction = serializers.SerializerMethodField()
    comments_count = serializers.SerializerMethodField()
    liked_by_me = serializers.SerializerMethodField()

    class Meta:
        model = Moment
        fields = (
            'id', 'author', 'content', 'visibility',
            'images',
            'reactions_count', 'reactions_summary', 'my_reaction',
            'comments_count', 'liked_by_me',
            'created_at', 'updated_at',
        )
        read_only_fields = ('id', 'author', 'created_at', 'updated_at')

    def _uid(self):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return request.user.id
        return None

    def get_reactions_count(self, obj):
        return len(obj.reactions.all())

    def get_reactions_summary(self, obj):
        summary, _ = build_reaction_summary(obj.reactions.all(), self._uid())
        return summary

    def get_my_reaction(self, obj):
        _, mine = build_reaction_summary(obj.reactions.all(), self._uid())
        return mine

    def get_comments_count(self, obj):
        return len(obj.comments.all())

    def get_liked_by_me(self, obj):
        uid = self._uid()
        if uid is None:
            return False
        return any(r.user_id == uid for r in obj.reactions.all())

    def create(self, validated_data):
        request = self.context['request']
        validated_data['author'] = request.user
        moment = super().create(validated_data)

        order = 0
        # 1) 本地上传图片
        for img in request.FILES.getlist('images'):
            MomentImage.objects.create(moment=moment, image=img, order=order)
            order += 1
        # 2) 引用 Immich asset
        ids = request.data.getlist('immich_asset_ids') if hasattr(
            request.data, 'getlist'
        ) else (request.data.get('immich_asset_ids') or [])
        if isinstance(ids, str):
            ids = [ids]
        for aid in ids:
            aid = (aid or '').strip()
            if not aid:
                continue
            MomentImage.objects.create(moment=moment, immich_asset_id=aid, order=order)
            order += 1
        return moment
