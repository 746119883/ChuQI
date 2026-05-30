from django.contrib import admin

from .models import Invitation, Profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'nickname', 'role', 'relation', 'birthday', 'birthday_is_lunar')
    list_filter = ('role', 'birthday_is_lunar')
    search_fields = ('user__username', 'nickname', 'relation')


@admin.register(Invitation)
class InvitationAdmin(admin.ModelAdmin):
    list_display = ('code', 'role', 'created_by', 'created_at', 'expires_at', 'used_by', 'revoked')
    list_filter = ('role', 'revoked')
    search_fields = ('code', 'note', 'created_by__username', 'used_by__username')
    readonly_fields = ('code', 'created_at', 'used_at')
