from django.contrib import admin
from .models import Moment, MomentImage, Reaction, Comment


class MomentImageInline(admin.TabularInline):
    model = MomentImage
    extra = 0


class CommentInline(admin.TabularInline):
    model = Comment
    extra = 0
    readonly_fields = ('author', 'content', 'created_at')


@admin.register(Moment)
class MomentAdmin(admin.ModelAdmin):
    list_display = ('id', 'author', 'short_content', 'visibility', 'created_at')
    list_filter = ('visibility', 'author', 'created_at')
    search_fields = ('content',)
    date_hierarchy = 'created_at'
    inlines = [MomentImageInline, CommentInline]

    @admin.display(description='内容')
    def short_content(self, obj):
        return obj.content[:50] or '(无)'


@admin.register(Reaction)
class ReactionAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'moment', 'created_at')


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ('id', 'author', 'moment', 'short_content', 'created_at')

    @admin.display(description='内容')
    def short_content(self, obj):
        return obj.content[:50]
