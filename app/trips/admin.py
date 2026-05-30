from django.contrib import admin

from .models import Trip, TripItem


class TripItemInline(admin.TabularInline):
    model = TripItem
    extra = 0


@admin.register(Trip)
class TripAdmin(admin.ModelAdmin):
    list_display = ('title', 'destination', 'start_date', 'end_date', 'owner', 'visibility')
    list_filter = ('visibility',)
    search_fields = ('title', 'destination', 'owner__username')
    inlines = [TripItemInline]


@admin.register(TripItem)
class TripItemAdmin(admin.ModelAdmin):
    list_display = ('date', 'time', 'item_type', 'title', 'trip')
    list_filter = ('item_type',)
