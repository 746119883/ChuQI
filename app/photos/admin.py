from django.contrib import admin
from django.utils.html import format_html
from .models import Album, Photo, Video


@admin.register(Album)
class AlbumAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'owner', 'photo_count', 'updated_at')
    search_fields = ('name',)
    list_filter = ('owner',)

    @admin.display(description='照片数')
    def photo_count(self, obj):
        return obj.photos.count()


@admin.register(Photo)
class PhotoAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'thumb_preview', 'uploader', 'album',
        'taken_at', 'uploaded_at',
    )
    list_filter = ('album', 'uploader')
    date_hierarchy = 'uploaded_at'
    readonly_fields = ('width', 'height', 'size_bytes', 'taken_at', 'uploaded_at')

    @admin.display(description='预览')
    def thumb_preview(self, obj):
        if obj.thumbnail:
            return format_html(
                '<img src="{}" style="height:50px;border-radius:4px;" />',
                obj.thumbnail.url,
            )
        return '-'


@admin.register(Video)
class VideoAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'poster_preview', 'uploader', 'album',
        'duration_display', 'taken_at', 'uploaded_at',
    )
    list_filter = ('album', 'uploader')
    date_hierarchy = 'uploaded_at'
    readonly_fields = (
        'width', 'height', 'duration', 'size_bytes',
        'taken_at', 'uploaded_at',
    )

    @admin.display(description='封面')
    def poster_preview(self, obj):
        if obj.poster:
            return format_html(
                '<img src="{}" style="height:50px;border-radius:4px;" />',
                obj.poster.url,
            )
        return '-'

    @admin.display(description='时长')
    def duration_display(self, obj):
        s = int(obj.duration or 0)
        return f'{s // 60}:{s % 60:02d}'
