"""Researcher panel, mounted at /admin.

It shows the answer key (which clip of each pair is the original), so it only
answers on the host names listed in ADMIN_HOSTS. The public host is not in
that list and its ingress does not route /admin to this server at all.
"""

import io
import math
import statistics
from collections import Counter, defaultdict

from flask import Blueprint, Response as HttpResponse, abort, current_app, render_template, request

from .export import write_csv
from .models import Pair, Participant, Response

admin = Blueprint("admin", __name__, url_prefix="/admin")

QUESTION_LABELS = {
    "fit": "Qual música combina mais com o jogo?",
    "ai": "Qual música foi gerada por IA?",
    "preference": "Qual música você prefere?",
}
LEVELS = ["Nenhuma", "Menos de 1 ano", "1 a 5 anos", "Mais de 5 anos"]
CHIPTUNE = ["Nunca ouvi", "Já ouvi", "Ouço às vezes", "Ouço muito ou componho"]
FAMILIARITY = ["Não conhecia", "Conhecia o jogo", "Conhecia uma das músicas", "Conhecia o jogo e a música"]


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


def binomial_p(k, n):
    """Two-sided exact binomial test against 0.5."""
    if n == 0:
        return None
    tail = sum(math.comb(n, i) for i in range(0, min(k, n - k) + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def wilson(k, n, z=1.96):
    if n == 0:
        return None
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return max(0.0, centre - half), min(1.0, centre + half)


def summary(responses):
    """Share of answers that picked the original clip."""
    n = len(responses)
    k = sum(1 for r in responses if r.chose_human)
    return {"n": n, "k": k, "share": k / n if n else None, "ci": wilson(k, n), "p": binomial_p(k, n)}


def catalog_checks(catalog, pairs):
    songs = {s["id"]: s for s in catalog["songs"]}
    audio_dir, image_dir = current_app.config["AUDIO_DIR"], current_app.config["IMAGE_DIR"]
    pool = [p for p in catalog["pairs"] if p.get("role", "pool") == "pool"]
    per_tag = Counter(p["tag"] for p in pool)
    checks = []

    def add(name, ok, detail):
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    add("Pares por tag", len(set(per_tag.values())) == 1 and set(per_tag) == set(catalog["tags"]),
        ", ".join(f"{t}: {per_tag.get(t, 0)}" for t in catalog["tags"]))
    need = current_app.config["PAIRS_PER_TAG"]
    add("Pares suficientes por participante", all(per_tag.get(t, 0) >= need for t in catalog["tags"]),
        f"cada participante ouve {need} por tag")
    bad = [p["id"] for p in catalog["pairs"]
           if songs[p["human"]]["kind"] != "human" or songs[p["genai"]]["kind"] != "genai"]
    add("Cada par tem uma original e uma gerada", not bad, f"{len(catalog['pairs']) - len(bad)} de {len(catalog['pairs'])}")
    wrong = [p["id"] for p in pool if songs[p["genai"]].get("tag") != p["tag"] or songs[p["human"]].get("tag") != p["tag"]]
    add("Original e gerada têm a tag do par", not wrong, f"{len(pool) - len(wrong)} de {len(pool)}")
    systems = Counter(songs[p["genai"]]["system"] for p in pool)
    add("Geradas do mesmo modelo", len(systems) == 1, ", ".join(f"{s}: {n}" for s, n in systems.items()))
    tids = Counter(str(p["game"]["tid"]) for p in catalog["pairs"])
    add("Um jogo por par", max(tids.values()) == 1, f"{len(tids)} jogos distintos")
    used = Counter(p["human"] for p in catalog["pairs"]) + Counter(p["genai"] for p in catalog["pairs"])
    add("Nenhum clipe repetido entre pares", max(used.values()) == 1, f"{len(used)} clipes")
    missing = [s for s in used if not (audio_dir / f"{s}.mp3").is_file()]
    add("Arquivos de áudio presentes", not missing, f"faltam {len(missing)}" if missing else f"{len(used)} MP3")
    missing = [p["image"] for p in catalog["pairs"] if not (image_dir / f"{p['image']}.webp").is_file()]
    add("Imagens dos jogos presentes", not missing, f"faltam {len(missing)}" if missing else f"{len(catalog['pairs'])} imagens")
    lengths = {round(songs[s].get("seconds", 0)) for s in used}
    add("Clipes com a mesma duração", len(lengths) == 1, ", ".join(f"{x} s" for x in sorted(lengths)))
    in_db = {p.id for p in pairs if p.active}
    add("Banco igual ao catálogo", in_db == {p["id"] for p in catalog["pairs"]}, f"{len(in_db)} pares ativos no banco")
    return checks


@admin.get("/")
def panel():
    catalog = current_app.config["CATALOG"]
    songs = {s["id"]: s for s in catalog["songs"]}
    pairs = Pair.query.all()
    participants = Participant.query.all()
    answered = Response.query.filter(Response.answered_at.isnot(None)).all()
    assigned = Response.query.count()

    by_participant = defaultdict(list)
    for r in answered:
        by_participant[r.participant_id].append(r)
    started = len(by_participant)
    per_participant = len(catalog["tags"]) * current_app.config["PAIRS_PER_TAG"] + sum(
        1 for p in catalog["pairs"] if p.get("role") == "anchor")
    finished = sum(1 for rs in by_participant.values() if len(rs) >= per_participant)
    completed = [p for p in participants if p.profile_completed_at]
    times = [r.time_spent_ms / 1000 for r in answered if r.time_spent_ms]

    questions = sorted({r.question for r in answered}) or [current_app.config["STUDY_QUESTION"]]
    results = []
    for question in questions:
        rs = [r for r in answered if r.question == question and r.pair.role == "pool"]
        fresh = [r for r in rs if r.familiarity == 0]
        rows = [{"label": "Todos os pares", **summary(rs)},
                {"label": "Só quem não conhecia o jogo nem a música", **summary(fresh)}]
        rows += [{"label": f"Tag {tag}", **summary([r for r in rs if r.pair.tag == tag])} for tag in catalog["tags"]]
        anchor = [r for r in answered if r.question == question and r.pair.role == "anchor"]
        rows.append({"label": "Par de controle (original contra Markov)", **summary(anchor)})
        results.append({"question": question, "label": QUESTION_LABELS[question], "rows": rows})

    by_pair = defaultdict(list)
    for r in answered:
        by_pair[r.pair_id].append(r)
    spec = {p["id"]: p for p in catalog["pairs"]}
    cards = []
    for pair in sorted(pairs, key=lambda p: (not p.active, p.role != "pool", p.tag, p.id)):
        s = spec.get(pair.id, {})
        cards.append({
            "pair": pair, "human": songs.get(pair.human_id, {}), "genai": songs.get(pair.genai_id, {}),
            "similarity": s.get("clap_similarity"), **summary(by_pair[pair.id]),
        })

    def dist(values, labels):
        counts = Counter(v for v in values if v is not None)
        return [(labels[i], counts.get(i, 0)) for i in range(len(labels))]

    ages = [p.age for p in completed if p.age]
    profile = {
        "n": len(completed),
        "age": (round(statistics.mean(ages), 1), statistics.median(ages)) if ages else None,
        "language": Counter(p.language for p in completed).most_common(),
        "practical": dist([p.practical_experience for p in completed], LEVELS),
        "formal": dist([p.formal_experience for p in completed], LEVELS),
        "chiptune": dist([p.chiptune_familiarity for p in completed], CHIPTUNE),
        "knows_ai": sum(1 for p in completed if p.knows_ai_music),
    }
    days = Counter(r.answered_at.strftime("%d/%m") for r in sorted(answered, key=lambda r: r.answered_at))
    comments = [r for r in sorted(answered, key=lambda r: r.answered_at, reverse=True) if r.comments]

    return render_template(
        "admin.html",
        question=QUESTION_LABELS[current_app.config["STUDY_QUESTION"]],
        totals={
            "registered": len(participants), "started": started, "finished": finished,
            "completed": len(completed), "answers": len(answered), "assigned": assigned,
            "median_time": round(statistics.median(times)) if times else None,
        },
        results=results, checks=catalog_checks(catalog, pairs), cards=cards, profile=profile,
        days=list(days.items()), comments=comments[:200], familiarity=dist([r.familiarity for r in answered], FAMILIARITY),
        catalog=catalog,
    )


@admin.get("/answers.csv")
def answers_csv():
    out = io.StringIO()
    write_csv(out)
    return HttpResponse(out.getvalue(), mimetype="text/csv",
                        headers={"Content-Disposition": "attachment; filename=answers.csv"})
