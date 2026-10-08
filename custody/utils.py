import hashlib
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import redirect

from .models import CustodyLog


def user_can_write(user):
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    profile = getattr(user, "profile", None)
    return bool(profile and profile.can_write)


def write_required(view):
    """Login + non-viewer role chahiye."""

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not user_can_write(request.user):
            messages.error(request, "Aapka role read-only hai, ye action allowed nahi hai.")
            return redirect("dashboard")
        return view(request, *args, **kwargs)

    return login_required(wrapper)


def sha256_fieldfile(fieldfile):
    h = hashlib.sha256()
    fieldfile.open("rb")
    try:
        for chunk in fieldfile.chunks():
            h.update(chunk)
    finally:
        fieldfile.close()
    return h.hexdigest()


@transaction.atomic
def register_evidence(evidence, user):
    """Naya evidence save karta hai aur chain ka pehla (genesis) record banata hai."""
    evidence.collected_by = user
    evidence.current_custodian = user
    evidence.status = "in_custody"
    evidence.save()

    notes = "Evidence collected and logged into custody."
    if evidence.file:
        evidence.file_sha256 = sha256_fieldfile(evidence.file)
        evidence.save(update_fields=["file_sha256"])
        notes += f" Attached file SHA-256: {evidence.file_sha256}"

    return CustodyLog.objects.create(
        evidence=evidence,
        action="collected",
        from_user=None,
        to_user=user,
        location=evidence.current_location or evidence.location_found,
        notes=notes,
        recorded_by=user,
    )


@transaction.atomic
def record_event(evidence, user, action, to_user, location, notes):
    """Custody event append karta hai aur evidence ki current state update karta hai."""
    log = CustodyLog.objects.create(
        evidence=evidence,
        action=action,
        from_user=evidence.current_custodian,
        to_user=to_user,
        location=location,
        notes=notes,
        recorded_by=user,
    )
    evidence.status = CustodyLog.ACTION_STATUS[action]
    evidence.current_location = location
    if to_user:
        evidence.current_custodian = to_user
    elif action in ("released", "disposed"):
        evidence.current_custodian = None
    evidence.save(update_fields=["status", "current_location", "current_custodian"])
    return log
