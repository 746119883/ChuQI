from rest_framework import serializers
from .models import Album, Photo, Video
from notes.serializers import UserSerializer


class PhotoSerializer(serializers.ModelSerializer):
    type = serializers.SerializerMethodField()
    uploader = UserSerializer(read_only=True)
    image = serializers.ImageField(use_url=True, read_only=True)
    thumbnail = serializers.ImageField(use_url=True, read_only=True)

    class Meta:
        model = Photo
        fields = (
            'type', 'id', 'uploader', 'album',
            'image', 'thumbnail',
            'width', 'height', 'size_bytes',
            'caption',
            'taken_at', 'uploaded_at',
        )
        read_only_fields = (
            'id', 'uploader',
            'image', 'thumbnail',
            'width', 'height', 'size_bytes',
            'taken_at', 'uploaded_at',
        )

    def get_type(self, obj):
        return 'photo'


class VideoSerializer(serializers.ModelSerializer):
    type = serializers.SerializerMethodField()
    uploader = UserSerializer(read_only=True)
    file = serializers.FileField(use_url=True, read_only=True)
    poster = serializers.ImageField(use_url=True, read_only=True)

    class Meta:
        model = Video
        fields = (
            'type', 'id', 'uploader', 'album',
            'file', 'poster',
            'width', 'height', 'duration', 'size_bytes',
            'caption',
            'taken_at', 'uploaded_at',
        )
        read_only_fields = (
            'id', 'uploader',
            'file', 'poster',
            'width', 'height', 'duration', 'size_bytes',
            'taken_at', 'uploaded_at',
        )

    def get_type(self, obj):
        return 'video'


class AlbumSerializer(serializers.ModelSerializer):
    owner = UserSerializer(read_only=True)
    cover_thumbnail = serializers.SerializerMethodField()
    photo_count = serializers.SerializerMethodField()
    video_count = serializers.SerializerMethodField()

    class Meta:
        model = Album
        fields = (
            'id', 'name', 'description',
            'owner',
            'cover_thumbnail', 'photo_count', 'video_count',
            'created_at', 'updated_at',
        )
        read_only_fields = (
            'id', 'owner',
            'cover_thumbnail', 'photo_count', 'video_count',
            'created_at', 'updated_at',
        )

    def get_cover_thumbnail(self, obj):
        request = self.context.get('request')
        # 先看手动指定的封面 (Photo)
        photo = obj.cover_photo
        if not photo:
            photo = obj.photos.order_by('-uploaded_at').first()
        if photo and photo.thumbnail:
            url = photo.thumbnail.url
            return request.build_absolute_uri(url) if request else url
        # 退一步:用最新视频的封面
        video = obj.videos.order_by('-uploaded_at').first()
        if video and video.poster:
            url = video.poster.url
            return request.build_absolute_uri(url) if request else url
        return None

    def get_photo_count(self, obj):
        return obj.photos.count()

    def get_video_count(self, obj):
        return obj.videos.count()

    def create(self, validated_data):
        validated_data['owner'] = self.context['request'].user
        return super().create(validated_data)
