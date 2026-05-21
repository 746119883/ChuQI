from rest_framework import serializers
from .models import Moment, MomentImage, Reaction, Comment
from notes.serializers import UserSerializer


class MomentImageSerializer(serializers.ModelSerializer):
    image = serializers.ImageField(use_url=True)

    class Meta:
        model = MomentImage
        fields = ('id', 'image', 'order')


class CommentSerializer(serializers.ModelSerializer):
    author = UserSerializer(read_only=True)

    class Meta:
        model = Comment
        fields = ('id', 'author', 'content', 'created_at')
        read_only_fields = ('id', 'author', 'created_at')

    def create(self, validated_data):
        validated_data['author'] = self.context['request'].user
        validated_data['moment_id'] = self.context['moment_id']
        return super().create(validated_data)


class MomentSerializer(serializers.ModelSerializer):
    author = UserSerializer(read_only=True)
    images = MomentImageSerializer(many=True, read_only=True)
    reactions_count = serializers.SerializerMethodField()
    comments_count = serializers.SerializerMethodField()
    liked_by_me = serializers.SerializerMethodField()

    class Meta:
        model = Moment
        fields = (
            'id', 'author', 'content', 'visibility',
            'images',
            'reactions_count', 'comments_count', 'liked_by_me',
            'created_at', 'updated_at',
        )
        read_only_fields = ('id', 'author', 'created_at', 'updated_at')

    def get_reactions_count(self, obj):
        return obj.reactions.count()

    def get_comments_count(self, obj):
        return obj.comments.count()

    def get_liked_by_me(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        return obj.reactions.filter(user=request.user).exists()

    def create(self, validated_data):
        validated_data['author'] = self.context['request'].user
        moment = super().create(validated_data)
        # 处理多图上传
        images = self.context['request'].FILES.getlist('images')
        for i, img in enumerate(images):
            MomentImage.objects.create(moment=moment, image=img, order=i)
        return moment
