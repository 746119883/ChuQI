from django.contrib import admin

from .models import DiningOption, MealLog


@admin.register(DiningOption)
class DiningOptionAdmin(admin.ModelAdmin):
    list_display = ('name', 'kind', 'weight', 'is_active', 'created_by', 'updated_at')
    list_filter = ('kind', 'is_active')
    search_fields = ('name', 'note')


@admin.register(MealLog)
class MealLogAdmin(admin.ModelAdmin):
    list_display = ('date', 'meal_type', 'display_name', 'recorder', 'created_at')
    list_filter = ('meal_type', 'date')
    search_fields = ('custom_name', 'note')
    date_hierarchy = 'date'
