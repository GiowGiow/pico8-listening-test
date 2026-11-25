"""Researcher panel, mounted at /admin.

It shows how the collection is going and lets the team audit the package. It
does not know which clip of a scenario is which: that key stays with the
research team. It only answers on the host names listed in ADMIN_HOSTS.
"""

import functools
import io
import statistics
import wave
from collections import Counter

from flask import Blueprint, Response as HttpResponse, abort, current_app, render_template, request

from . import questionnaire
from .export import write_csv
from .models import Participant, Reservation, Scenario, utcnow
from .scenarios import SLOTS

admin = Blueprint("admin", __name__, url_prefix="/admin")


@admin.before_request
def only_internal_hosts():
    allowed = current_app.config["ADMIN_HOSTS"]
    hosts = {request.host.split(":")[0].lower()}
    forwarded = request.headers.get("X-Forwarded-Host")
    if forwarded:
        hosts |= {h.strip().split(":")[0].lower() for h in forwarded.split(",")}
    if not hosts <= allowed:
        abort(404)


@admin.after_request
def headers(response):
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = (
        "default-src 'none'; img-src 'self'; media-src 'self'; style-src 'unsafe-inline'; "
        "base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
    )
    return response


@functools.lru_cache(maxsize=1)
def audit_files(study_dir, ids):
    """Read every file of the package once: which are missing, and the WAV formats found."""
    missing, formats = [], Counter()
    for eid in ids:
        folder = study_dir / "scenarios" / eid
        if not (folder / "context.png").is_file():
            missing.append(f"{eid}/context.png")
        for slot in SLOTS:
            try:
                with wave.open(str(folder / f"{slot}.wav"), "rb") as w:
                    formats[(w.getnchannels(), w.getsampwidth() * 8, w.getframerate(),
                             round(w.getnframes() / w.getframerate(), 2))] += 1
            except (OSError, wave.Error, EOFError):
                missing.append(f"{eid}/{slot}.wav")
    return missing, dict(formats)


def package_checks(records, scenarios, completed):
    checks = []

    def add(name, ok, detail):
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    add("Cenários no pacote", len(records) == 240, f"{len(records)} cenários")
    orders = sorted(r["collection_order_v2"] for r in records.values())
    add("Fila contínua (collection_order_v2)", orders == list(range(len(records))),
        f"de {orders[0]} a {orders[-1]}" if orders else "vazia")
    missing, formats = audit_files(current_app.config["STUDY_DIR"], tuple(sorted(records)))
    add("Arquivos presentes", not missing,
        f"faltam {len(missing)}: {', '.join(missing[:3])}" if missing else f"{len(records)} imagens e {4 * len(records)} áudios")
    add("Áudios no mesmo formato", len(formats) == 1,
        "; ".join(f"{n} arquivos: {ch} canal, {bits} bits, {rate} Hz, {sec:g} s" for (ch, bits, rate, sec), n in formats.items()))
    descriptions = [r for r in records.values() if not (r.get("description") or "").strip()]
    add("Todo cenário tem descrição", not descriptions, f"{len(records) - len(descriptions)} de {len(records)}")
    add("Banco igual ao pacote", {s.external_id: s.position for s in scenarios}
        == {eid: r["collection_order_v2"] for eid, r in records.items()}, f"{len(scenarios)} cenários no banco")
    per_scenario = Counter(r.scenario_id for r in completed)
    repeated = [eid for eid, n in per_scenario.items() if n > 1]
    add("Nenhum cenário avaliado duas vezes", not repeated, f"{len(per_scenario)} cenários avaliados")
    by_id = {s.external_id: s for s in scenarios}
    loose = [r.id for r in completed if by_id[r.scenario_id].holder_id != r.id or by_id[r.scenario_id].completed_at is None]
    add("Avaliação e fila coerentes", not loose and len(per_scenario) == sum(1 for s in scenarios if s.completed_at),
        f"{sum(1 for s in scenarios if s.completed_at)} cenários fora da fila")
    bad = [r.id for r in completed if any(v not in (1, 2, 3, 4, 5) for v in r.ratings.values())]
    add("Quatro notas de 1 a 5 em toda avaliação", not bad, f"{len(completed) - len(bad)} de {len(completed)}")
    return checks


@admin.get("/")
def panel():
    study = current_app.config["STUDY"]
    records = current_app.config["SCENARIOS"]
    now = utcnow()
    scenarios = Scenario.query.order_by(Scenario.position).all()
    participants = Participant.query.all()
    reservations = Reservation.query.all()
    by_id = {r.id: r for r in reservations}
    completed = sorted((r for r in reservations if r.state == "completed"), key=lambda r: r.completed_at, reverse=True)

    queue = []
    for s in scenarios:
        holder = by_id.get(s.holder_id)
        if s.completed_at:
            state = "done"
        elif holder is not None and holder.expires_at > now:
            state = "held"
        else:
            state = "free"
        queue.append({"scenario": s, "state": state, "holder": holder, "record": records[s.external_id]})
    counts = Counter(q["state"] for q in queue)

    profiled = [p for p in participants if p.profile_completed_at]
    times = [r.time_spent_ms / 1000 for r in completed if r.time_spent_ms]
    labels = [s["label"] for s in study["scale"]]
    by_slot = {slot: Counter(r.ratings[slot] for r in completed) for slot in SLOTS}
    overall = Counter()
    for c in by_slot.values():
        overall.update(c)
    ratings = {
        "labels": labels,
        "rows": [{"label": f"Player {slot}", "counts": [by_slot[slot].get(v, 0) for v in range(1, 6)],
                  "mean": statistics.mean(r.ratings[slot] for r in completed) if completed else None}
                 for slot in SLOTS],
        "total": [overall.get(v, 0) for v in range(1, 6)],
    }
    profile = [
        {"label": field["label"],
         "rows": [(label, sum(1 for p in profiled if getattr(p, field["name"]) == code)) for code, label in field["options"]]}
        for field in questionnaire.FIELDS
    ]
    days = Counter(r.completed_at.strftime("%d/%m") for r in sorted(completed, key=lambda r: r.completed_at))

    show_all = request.args.get("todos") == "1"
    upcoming = [q for q in queue if q["state"] != "done"]
    done = sorted((q for q in queue if q["state"] == "done"), key=lambda q: q["scenario"].completed_at, reverse=True)
    cards = done + (upcoming if show_all else upcoming[:8])

    return render_template(
        "admin.html",
        study=study, version=questionnaire.VERSION, minutes=current_app.config["RESERVATION_MINUTES"],
        totals={
            "registered": len(participants), "profiled": len(profiled),
            "finished": sum(1 for p in participants if p.finished_at),
            "done": counts["done"], "held": counts["held"], "free": counts["free"], "total": len(queue),
            "lost": sum(1 for r in reservations if r.state == "lost"),
            "median_time": round(statistics.median(times)) if times else None,
        },
        queue=queue, checks=package_checks(records, scenarios, completed), ratings=ratings, profile=profile,
        days=list(days.items()), cards=cards, show_all=show_all, hidden=len(upcoming) - 8, slots=SLOTS,
    )


@admin.get("/ratings.csv")
def ratings_csv():
    out = io.StringIO()
    write_csv(out)
    return HttpResponse(out.getvalue(), mimetype="text/csv",
                        headers={"Content-Disposition": "attachment; filename=ratings.csv"})
