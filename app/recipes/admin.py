from django.contrib import admin

from .models import Recipe


@admin.register(Recipe)
class RecipeAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'category', 'difficulty', 'visibility', 'updated_at')
    list_filter = ('category', 'difficulty', 'visibility')
    search_fields = ('title', 'description', 'author__username')
