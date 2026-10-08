import hashlib

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

GENESIS_HASH = "0" * 64


def _next_code(model, field, prefix, width):
    """CS-2026-001 / EV-2026-0001 jaise sequential codes banata hai."""
    last = (
        model.objects.filter(**{f"{field}__startswith": prefix})
        .order_by(f"-{field}")
        .first()
    )
    number = int(getattr(last, field).split("-")[-1]) + 1 if last else 1
    return f"{prefix}{number:0{width}d}"


class Profile(models.Model):
    ROLES = [
        ("admin", "Administrator"),
        ("investigator", "Investigator"),
        ("analyst", "Lab analyst"),
        ("viewer", "Viewer (read only)"),
    ]
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile"
    )
    role = models.CharField(max_length=20, choices=ROLES, default="viewer")
    badge_number = models.CharField(max_length=30, blank=True)
    department = models.CharField(max_length=80, blank=True)

    def __str__(self):
        return f"{self.user.get_username()} ({self.get_role_display()})"

    @property
    def can_write(self):
        return self.user.is_superuser or self.role != "viewer"


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.get_or_create(
            user=instance, defaults={"role": "admin" if instance.is_superuser else "viewer"}
        )


class Case(models.Model):
    STATUS = [
        ("open", "Open"),
        ("investigating", "Under investigation"),
        ("court", "In court"),
        ("closed", "Closed"),
    ]
    case_number = models.CharField(max_length=20, unique=True, editable=False)
    title = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS, default="open")
    lead = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="led_cases",
        verbose_name="Lead investigator",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_cases",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.case_number} - {self.title}"

    def save(self, *args, **kwargs):
        if not self.case_number:
            self.case_number = _next_code(
                Case, "case_number", f"CS-{timezone.now().year}-", 3
            )
        super().save(*args, **kwargs)


class Evidence(models.Model):
    CATEGORIES = [
        ("physical", "Physical object"),
        ("digital", "Digital media"),
        ("document", "Document"),
        ("biological", "Biological sample"),
        ("weapon", "Weapon"),
        ("other", "Other"),
    ]
    STATUS = [
        ("in_custody", "In custody"),
        ("in_storage", "In storage"),
        ("in_lab", "At forensic lab"),
        ("in_court", "In court"),
        ("released", "Released"),
        ("disposed", "Disposed"),
    ]
    CLOSED_STATES = ("released", "disposed")

    evidence_id = models.CharField(max_length=20, unique=True, editable=False)
    case = models.ForeignKey(Case, on_delete=models.PROTECT, related_name="evidence")
    name = models.CharField(max_length=160)
    category = models.CharField(max_length=20, choices=CATEGORIES, default="physical")
    description = models.TextField(blank=True)
    location_found = models.CharField(max_length=200, verbose_name="Where it was found")
    collected_at = models.DateTimeField(default=timezone.now)
    collected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="collected_items"
    )
    file = models.FileField(
        upload_to="evidence/%Y/%m/", blank=True, verbose_name="Attach file (photo, scan, disk image)"
    )
    file_sha256 = models.CharField(max_length=64, blank=True, editable=False)
    status = models.CharField(max_length=20, choices=STATUS, default="in_custody")
    current_custodian = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="held_items",
    )
    current_location = models.CharField(max_length=200, blank=True, verbose_name="Stored at")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "evidence"

    def __str__(self):
        return f"{self.evidence_id} - {self.name}"

    def save(self, *args, **kwargs):
        if not self.evidence_id:
            self.evidence_id = _next_code(
                Evidence, "evidence_id", f"EV-{timezone.now().year}-", 4
            )
        super().save(*args, **kwargs)

    CATEGORY_ICONS = {
        "physical": "bi-box-seam",
        "digital": "bi-device-hdd",
        "document": "bi-file-earmark-text",
        "biological": "bi-droplet-half",
        "weapon": "bi-shield-slash",
        "other": "bi-tag",
    }

    @property
    def icon(self):
        return self.CATEGORY_ICONS.get(self.category, "bi-tag")

    @property
    def is_closed(self):
        return self.status in self.CLOSED_STATES

    def verify_detail(self):
        """Poori chain dobara compute karke har link ka result deta hai."""
        expected_prev = GENESIS_HASH
        results = []
        for log in self.logs.select_related("from_user", "to_user", "recorded_by").order_by("id"):
            ok = log.prev_hash == expected_prev and log.hash == log.compute_hash()
            results.append((log, ok))
            expected_prev = log.hash
        return all(ok for _, ok in results), results

    def verify_chain(self):
        ok, results = self.verify_detail()
        broken_at = next((i for i, (_, good) in enumerate(results, 1) if not good), None)
        return ok, broken_at

    def file_matches(self):
        """None = file nahi hai, True/False = stored hash se match."""
        if not self.file:
            return None
        h = hashlib.sha256()
        try:
            self.file.open("rb")
            try:
                for chunk in self.file.chunks():
                    h.update(chunk)
            finally:
                self.file.close()
        except (FileNotFoundError, ValueError):
            return False
        return h.hexdigest() == self.file_sha256


class CustodyLog(models.Model):
    ACTIONS = [
        ("collected", "Collected"),
        ("transferred", "Transferred"),
        ("stored", "Placed in storage"),
        ("sent_to_lab", "Sent to lab"),
        ("analyzed", "Analyzed"),
        ("court", "Presented in court"),
        ("released", "Released"),
        ("disposed", "Disposed"),
    ]
    ACTION_STATUS = {
        "collected": "in_custody",
        "transferred": "in_custody",
        "stored": "in_storage",
        "sent_to_lab": "in_lab",
        "analyzed": "in_lab",
        "court": "in_court",
        "released": "released",
        "disposed": "disposed",
    }
    ACTION_ICONS = {
        "collected": "bi-bag-check",
        "transferred": "bi-arrow-left-right",
        "stored": "bi-safe2",
        "sent_to_lab": "bi-truck",
        "analyzed": "bi-eyedropper",
        "court": "bi-bank",
        "released": "bi-box-arrow-up-right",
        "disposed": "bi-trash3",
    }

    evidence = models.ForeignKey(Evidence, on_delete=models.PROTECT, related_name="logs")
    action = models.CharField(max_length=20, choices=ACTIONS)
    from_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="handed_over_logs",
    )
    to_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="received_logs",
        verbose_name="New custodian",
    )
    location = models.CharField(max_length=200)
    notes = models.TextField()
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="recorded_logs"
    )
    timestamp = models.DateTimeField(editable=False)
    prev_hash = models.CharField(max_length=64, editable=False)
    hash = models.CharField(max_length=64, editable=False)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.evidence.evidence_id}: {self.get_action_display()}"

    @property
    def icon(self):
        return self.ACTION_ICONS.get(self.action, "bi-circle")

    @property
    def short_hash(self):
        return f"{self.hash[:8]}…{self.hash[-6:]}"

    @property
    def short_prev(self):
        if self.prev_hash == GENESIS_HASH:
            return "genesis"
        return f"{self.prev_hash[:8]}…{self.prev_hash[-6:]}"

    def compute_hash(self):
        ts = self.timestamp.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        payload = "|".join(
            [
                self.evidence.evidence_id,
                self.action,
                self.from_user.username if self.from_user else "-",
                self.to_user.username if self.to_user else "-",
                self.location,
                self.notes,
                self.recorded_by.username,
                ts,
                self.prev_hash,
            ]
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Custody records append-only hain, inhe edit nahi kar sakte.")
        self.timestamp = timezone.now().replace(microsecond=0)
        previous = (
            CustodyLog.objects.filter(evidence=self.evidence).order_by("-id").first()
        )
        self.prev_hash = previous.hash if previous else GENESIS_HASH
        self.hash = self.compute_hash()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Custody records delete nahi ho sakte.")
