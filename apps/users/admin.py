from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import User, UserActivityLog


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = ('email', 'username', 'role', 'is_email_verified', 'is_staff')
    list_filter = ('role', 'is_email_verified', 'is_staff')
    ordering = ('email',)
    search_fields = ('email', 'username')
    fieldsets = DjangoUserAdmin.fieldsets + (
        ('Risk Radar', {'fields': ('role', 'is_email_verified')}),
    )
    add_fieldsets = (
        (
            None,
            {
                'classes': ('wide',),
                'fields': ('email', 'username', 'password1', 'password2', 'role'),
            },
        ),
    )


@admin.register(UserActivityLog)
class UserActivityLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'action_name', 'ip_address', 'timestamp')
    list_filter = ('action_name',)
    search_fields = ('user__email', 'action_name', 'ip_address')
