from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from .forms import CaseForm, EvidenceForm, TransferForm
from .models import Case, CustodyLog, Evidence
from .utils import record_event, register_evidence, write_required


@login_required
def dashboard(request):
    evidence_list = list(Evidence.objects.select_related("case", "current_custodian"))
    health = []
    for ev in evidence_list:
        ok, _ = ev.verify_chain()
        health.append({"ev": ev, "ok": ok})
    issues = [h for h in health if not h["ok"]]

    active_states = ("in_custody", "in_storage", "in_lab", "in_court")
    context = {
        "total_cases": Case.objects.count(),
        "open_cases": Case.objects.exclude(status="closed").count(),
        "total_evidence": len(evidence_list),
        "active_evidence": sum(1 for e in evidence_list if e.status in active_states),
        "total_logs": CustodyLog.objects.count(),
        "health": health[:40],
        "issues": issues,
        "chart_status": {
            "labels": [label for _, label in Evidence.STATUS],
            "values": [sum(1 for e in evidence_list if e.status == k) for k, _ in Evidence.STATUS],
        },
        "chart_category": {
            "labels": [label for _, label in Evidence.CATEGORIES],
            "values": [sum(1 for e in evidence_list if e.category == k) for k, _ in Evidence.CATEGORIES],
        },
        "my_items": [
            e
            for e in evidence_list
            if e.current_custodian_id == request.user.id and not e.is_closed
        ][:6],
        "recent_logs": CustodyLog.objects.select_related(
            "evidence", "from_user", "to_user", "recorded_by"
        ).order_by("-id")[:8],
    }
    return render(request, "custody/dashboard.html", context)


# ---------- Cases ----------
@login_required
def case_list(request):
    cases = Case.objects.select_related("lead")
    q = request.GET.get("q", "").strip()
    status = request.GET.get("status", "")
    if q:
        cases = cases.filter(
            Q(case_number__icontains=q) | Q(title__icontains=q) | Q(description__icontains=q)
        )
    if status:
        cases = cases.filter(status=status)
    page = Paginator(cases, 10).get_page(request.GET.get("page"))
    params = request.GET.copy()
    params.pop("page", None)
    return render(
        request,
        "custody/case_list.html",
        {"page": page, "q": q, "status": status, "statuses": Case.STATUS, "qs": params.urlencode()},
    )


@write_required
def case_create(request):
    form = CaseForm(request.POST or None, initial={"lead": request.user.pk})
    if request.method == "POST" and form.is_valid():
        case = form.save(commit=False)
        case.created_by = request.user
        case.save()
        messages.success(request, f"Case {case.case_number} created.")
        return redirect("case_detail", pk=case.pk)
    return render(request, "custody/form.html", {"form": form, "title": "Open a new case", "back": "case_list"})


@write_required
def case_edit(request, pk):
    case = get_object_or_404(Case, pk=pk)
    form = CaseForm(request.POST or None, instance=case)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"Case {case.case_number} updated.")
        return redirect("case_detail", pk=case.pk)
    return render(
        request,
        "custody/form.html",
        {"form": form, "title": f"Edit {case.case_number}", "back": "case_list"},
    )


@login_required
def case_detail(request, pk):
    case = get_object_or_404(Case.objects.select_related("lead", "created_by"), pk=pk)
    items = case.evidence.select_related("current_custodian")
    return render(request, "custody/case_detail.html", {"case": case, "items": items})


# ---------- Evidence ----------
@login_required
def evidence_list(request):
    items = Evidence.objects.select_related("case", "current_custodian")
    q = request.GET.get("q", "").strip()
    status = request.GET.get("status", "")
    category = request.GET.get("category", "")
    if q:
        items = items.filter(
            Q(evidence_id__icontains=q)
            | Q(name__icontains=q)
            | Q(description__icontains=q)
            | Q(case__case_number__icontains=q)
            | Q(case__title__icontains=q)
        )
    if status:
        items = items.filter(status=status)
    if category:
        items = items.filter(category=category)
    page = Paginator(items, 9).get_page(request.GET.get("page"))
    params = request.GET.copy()
    params.pop("page", None)
    context = {
        "page": page,
        "q": q,
        "status": status,
        "category": category,
        "statuses": Evidence.STATUS,
        "categories": Evidence.CATEGORIES,
        "qs": params.urlencode(),
    }
    return render(request, "custody/evidence_list.html", context)


@write_required
def evidence_create(request):
    initial = {}
    if request.GET.get("case"):
        initial["case"] = request.GET["case"]
    form = EvidenceForm(request.POST or None, request.FILES or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        evidence = register_evidence(form.save(commit=False), request.user)
        messages.success(request, f"{evidence.evidence_id} logged. Custody chain started.")
        return redirect("evidence_detail", pk=evidence.pk)
    return render(
        request,
        "custody/form.html",
        {"form": form, "title": "Log new evidence", "back": "evidence_list", "multipart": True},
    )


@login_required
def evidence_detail(request, pk):
    evidence = get_object_or_404(
        Evidence.objects.select_related("case", "collected_by", "current_custodian"), pk=pk
    )
    chain_ok, items = evidence.verify_detail()
    broken_at = next((i for i, (_, ok) in enumerate(items, 1) if not ok), None)
    context = {
        "ev": evidence,
        "items": items,
        "chain_ok": chain_ok,
        "broken_at": broken_at,
        "file_ok": evidence.file_matches(),
    }
    return render(request, "custody/evidence_detail.html", context)


@write_required
def evidence_transfer(request, pk):
    evidence = get_object_or_404(Evidence, pk=pk)
    if evidence.is_closed:
        messages.error(request, f"{evidence.evidence_id} is {evidence.get_status_display().lower()}; its chain is closed.")
        return redirect("evidence_detail", pk=pk)
    form = TransferForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        record_event(
            evidence,
            request.user,
            data["action"],
            data["to_user"],
            data["location"],
            data["notes"],
        )
        messages.success(request, "Event added to the custody chain.")
        return redirect("evidence_detail", pk=pk)
    return render(
        request,
        "custody/form.html",
        {
            "form": form,
            "title": f"Log custody event for {evidence.evidence_id}",
            "subtitle": f"{evidence.name} - currently with "
            f"{evidence.current_custodian.get_full_name() or evidence.current_custodian.username if evidence.current_custodian else 'nobody'}",
            "back": "evidence_detail",
            "back_pk": pk,
        },
    )


@login_required
def evidence_verify(request, pk):
    evidence = get_object_or_404(Evidence, pk=pk)
    ok, items = evidence.verify_detail()
    return JsonResponse(
        {
            "ok": ok,
            "total": len(items),
            "links": [{"id": log.id, "ok": good} for log, good in items],
            "file": evidence.file_matches(),
        }
    )


@login_required
def evidence_report(request, pk):
    evidence = get_object_or_404(
        Evidence.objects.select_related("case", "collected_by", "current_custodian"), pk=pk
    )
    chain_ok, items = evidence.verify_detail()
    return render(
        request,
        "custody/report.html",
        {"ev": evidence, "items": items, "chain_ok": chain_ok, "file_ok": evidence.file_matches()},
    )


@login_required
def integrity_check(request):
    rows = []
    for ev in Evidence.objects.select_related("case"):
        ok, broken_at = ev.verify_chain()
        rows.append(
            {
                "ev": ev,
                "ok": ok,
                "broken_at": broken_at,
                "records": ev.logs.count(),
                "file_ok": ev.file_matches(),
            }
        )
    bad = sum(1 for r in rows if not r["ok"] or r["file_ok"] is False)
    return render(request, "custody/integrity.html", {"rows": rows, "bad": bad})
