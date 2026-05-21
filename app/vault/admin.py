from django.contrib import admin
from .models import Folder, File


@admin.register(Folder)
class FolderAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'parent', 'visibility', 'owner', 'updated_at')
    list_filter = ('visibility', 'owner')
    search_fields = ('name',)


@admin.register(File)
class FileAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'name', 'folder', 'mime_type',
        'is_important', 'expires_at', 'uploader', 'created_at',
    )
    list_filter = ('is_important', 'visibility', 'uploader', 'folder')
    search_fields = ('name', 'description')
    date_hierarchy = 'created_at'
    readonly_fields = ('size_bytes', 'mime_type', 'created_at', 'updated_at')
