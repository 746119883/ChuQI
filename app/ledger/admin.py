from django.contrib import admin

from .models import LedgerEntry


@admin.register(LedgerEntry)
class LedgerEntryAdmin(admin.ModelAdmin):
    list_display = ('date', 'entry_type', 'amount', 'category', 'title', 'recorder')
    list_filter = ('entry_type', 'category', 'visibility')
    search_fields = ('title', 'note', 'recorder__username')
    date_hierarchy = 'date'
