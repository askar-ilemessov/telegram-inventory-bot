"""
Admin configuration for Core app.
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import Location, StaffProfile


class StaffProfileInline(admin.StackedInline):
    """Inline admin for StaffProfile."""
    model = StaffProfile
    can_delete = False
    verbose_name_plural = 'Staff Profile'
    fk_name = 'user'
    fields = ('telegram_id', 'role', 'location', 'is_active')


class UserAdmin(BaseUserAdmin):
    """Extended User admin with StaffProfile inline."""
    inlines = (StaffProfileInline,)
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'get_telegram_id', 'get_role')
    list_select_related = ('staff_profile',)

    def get_telegram_id(self, obj):
        """Get Telegram ID from profile."""
        return obj.staff_profile.telegram_id if hasattr(obj, 'staff_profile') else '-'
    get_telegram_id.short_description = 'Telegram ID'

    def get_role(self, obj):
        """Get role from profile."""
        return obj.staff_profile.get_role_display() if hasattr(obj, 'staff_profile') else '-'
    get_role.short_description = 'Role'


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    """Admin for Location model."""
    list_display = ('name', 'address', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'address')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        (None, {
            'fields': ('name', 'address', 'is_active')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(StaffProfile)
class StaffProfileAdmin(admin.ModelAdmin):
    """Admin for StaffProfile model."""
    list_display = ('user', 'telegram_id', 'role', 'location', 'is_active', 'created_at')
    list_filter = ('role', 'is_active', 'location', 'created_at')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'telegram_id')
    readonly_fields = ('created_at', 'updated_at')
    raw_id_fields = ('user',)
    fieldsets = (
        (None, {
            'fields': ('user', 'telegram_id', 'role', 'location', 'is_active')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


# Re-register UserAdmin
admin.site.unregister(User)
admin.site.register(User, UserAdmin)

