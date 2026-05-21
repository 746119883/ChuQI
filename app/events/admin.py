from django.contrib import admin
from .models import Event


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'title', 'event_type', 'date_str',
        'yearly_recurring', 'owner', 'visibility',
    )
    list_filter = ('event_type', 'is_lunar', 'yearly_recurring', 'visibility', 'owner')
    search_fields = ('title', 'description')

    @admin.display(description='日期')
    def date_str(self, obj):
        cal = '农历' if obj.is_lunar else '公历'
        year = f'{obj.date_year}-' if obj.date_year else ''
        return f'{cal} {year}{obj.date_month}/{obj.date_day}'
