from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("cases/", views.case_list, name="case_list"),
    path("cases/new/", views.case_create, name="case_create"),
    path("cases/<int:pk>/", views.case_detail, name="case_detail"),
    path("cases/<int:pk>/edit/", views.case_edit, name="case_edit"),
    path("evidence/", views.evidence_list, name="evidence_list"),
    path("evidence/new/", views.evidence_create, name="evidence_create"),
    path("evidence/<int:pk>/", views.evidence_detail, name="evidence_detail"),
    path("evidence/<int:pk>/transfer/", views.evidence_transfer, name="evidence_transfer"),
    path("evidence/<int:pk>/verify/", views.evidence_verify, name="evidence_verify"),
    path("evidence/<int:pk>/report/", views.evidence_report, name="evidence_report"),
    path("integrity/", views.integrity_check, name="integrity_check"),
]
