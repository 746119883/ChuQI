from django.contrib import admin

from .models import Story, StoryBlock


class StoryBlockInline(admin.TabularInline):
    model = StoryBlock
    extra = 0
    fields = ('kind', 'order', 'text', 'caption', 'immich_asset_id')


@admin.register(Story)
class StoryAdmin(admin.ModelAdmin):
    list_display = ('title', 'date', 'author', 'visibility', 'updated_at')
    list_filter = ('visibility',)
    search_fields = ('title', 'summary')
    date_hierarchy = 'date'
    inlines = [StoryBlockInline]
