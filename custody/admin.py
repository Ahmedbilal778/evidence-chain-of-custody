from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import Case, CustodyLog, Evidence, Profile

User = get_user_model()


class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False


class UserAdmin(BaseUserAdmin):
    inlines = [ProfileInline]


admin.site.unregister(User)
admin.site.register(User, UserAdmin)


@admin.register(Case)
class CaseAdmin(admin.ModelAdmin):
    list_display = ("case_number", "title", "status", "lead", "created_at")
    list_filter = ("status",)
    search_fields = ("case_number", "title")


@admin.register(Evidence)
class EvidenceAdmin(admin.ModelAdmin):
    list_display = ("evidence_id", "name", "case", "status", "current_custodian")
    list_filter = ("status", "category")
    search_fields = ("evidence_id", "name")
    readonly_fields = ("evidence_id", "file_sha256")


@admin.register(CustodyLog)
class CustodyLogAdmin(admin.ModelAdmin):
    """Ledger read-only hai: admin se bhi edit/delete nahi hota."""

    list_display = ("evidence", "action", "from_user", "to_user", "timestamp", "hash")
    list_filter = ("action",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
