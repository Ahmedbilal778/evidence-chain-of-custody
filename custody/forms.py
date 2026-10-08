from django import forms
from django.contrib.auth import get_user_model
from django.utils import timezone

from .models import Case, CustodyLog, Evidence

User = get_user_model()
DT_FORMAT = "%Y-%m-%dT%H:%M"


class BootstrapMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            css = "form-select" if isinstance(widget, forms.Select) else "form-control"
            widget.attrs["class"] = f"{widget.attrs.get('class', '')} {css}".strip()


def _user_label(user):
    return user.get_full_name() or user.username


class CaseForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Case
        fields = ["title", "status", "lead", "description"]
        widgets = {"description": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["lead"].queryset = User.objects.filter(is_active=True).order_by("username")
        self.fields["lead"].label_from_instance = _user_label


class EvidenceForm(BootstrapMixin, forms.ModelForm):
    collected_at = forms.DateTimeField(
        label="Collected on",
        input_formats=[DT_FORMAT],
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}, format=DT_FORMAT),
    )

    class Meta:
        model = Evidence
        fields = [
            "case",
            "name",
            "category",
            "location_found",
            "collected_at",
            "current_location",
            "description",
            "file",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "file": forms.FileInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["case"].queryset = Case.objects.exclude(status="closed")
        self.fields["current_location"].help_text = "Locker, shelf or room where it is kept now."
        if not self.is_bound and "collected_at" not in self.initial:
            self.initial["collected_at"] = timezone.localtime().replace(second=0, microsecond=0)


class TransferForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = CustodyLog
        fields = ["action", "to_user", "location", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 4})}
        labels = {"action": "What happened?", "location": "Location now"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["action"].choices = [
            c for c in CustodyLog.ACTIONS if c[0] != "collected"
        ]
        to_user = self.fields["to_user"]
        to_user.queryset = User.objects.filter(is_active=True).order_by("username")
        to_user.label_from_instance = _user_label
        to_user.empty_label = "No change of custodian"
        to_user.required = False
        self.fields["location"].required = True
        self.fields["notes"].required = True
        self.fields["notes"].help_text = "Condition of the item, seal number, reason for the hand-over."

    def clean(self):
        cleaned = super().clean()
        action, to_user = cleaned.get("action"), cleaned.get("to_user")
        if action in ("transferred", "sent_to_lab") and not to_user:
            self.add_error("to_user", "Choose who receives the evidence.")
        return cleaned
