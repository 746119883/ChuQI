from django.contrib import admin

from .models import Milestone


@admin.register(Milestone)
class MilestoneAdmin(admin.ModelAdmin):
    list_display = ('id', 'date', 'title', 'milestone_type', 'created_by', 'visibility')
    list_filter = ('milestone_type', 'visibility')
    search_fields = ('title', 'description')
