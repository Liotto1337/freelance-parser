"""Веб-дашборд заказов.

    python app.py   # http://127.0.0.1:8080
"""
import json
import secrets
from datetime import datetime, timedelta
from urllib.parse import urlencode

from flask import Flask, Response, abort, jsonify, render_template, request

import config
import db
from sources import utcnow

app = Flask(__name__)

SITES = {
    "kwork": "Kwork",
    "fl": "FL.ru",
    "freelanceru": "freelance.ru",
}
PAGE_SIZE = 60


@app.before_request
def basic_auth():
    if not config.DASHBOARD_PASSWORD:
        return None
    auth = request.authorization
    if (auth and secrets.compare_digest(auth.username or "", config.DASHBOARD_USER)
            and secrets.compare_digest(auth.password or "", config.DASHBOARD_PASSWORD)):
        return None
    return Response("Нужен вход", 401, {"WWW-Authenticate": 'Basic realm="orders"'})


def _filters():
    a = request.args
    return {
        "sites": a.getlist("site"),
        "skills": a.getlist("skill"),
        "status": a.get("status", "active"),
        "min_budget": a.get("min_budget", type=int),
        "q": (a.get("q") or "").strip(),
        "matched": a.get("matched", "1") == "1",
        "period": a.get("period", "all"),
    }


def _query(f, limit, offset):
    where, params = [], []
    if f["sites"]:
        where.append(f"site IN ({','.join('?' * len(f['sites']))})")
        params += f["sites"]
    if f["status"] == "active":
        where.append("status IN ('new','interesting')")
    elif f["status"] in db.STATUSES:
        where.append("status = ?")
        params.append(f["status"])
    if f["min_budget"]:
        where.append("budget >= ?")
        params.append(f["min_budget"])
    if f["q"]:
        where.append("(instr(ulower(title), ?) > 0 OR instr(ulower(description), ?) > 0)")
        params += [f["q"].lower()] * 2
    if f["matched"]:
        where.append("skills != '[]'")
    if f["skills"]:
        where.append("(" + " OR ".join("skills LIKE ?" for _ in f["skills"]) + ")")
        params += [f'%"{s}"%' for s in f["skills"]]
    hours = {"24h": 24, "3d": 72, "7d": 168}.get(f["period"])
    if hours:
        where.append("published_at >= ?")
        params.append((utcnow() - timedelta(hours=hours)).isoformat())
    sql_where = ("WHERE " + " AND ".join(where)) if where else ""
    with db.connect() as c:
        total = c.execute(f"SELECT COUNT(*) FROM orders {sql_where}", params).fetchone()[0]
        rows = c.execute(
            f"SELECT * FROM orders {sql_where} ORDER BY published_at DESC, id DESC LIMIT ? OFFSET ?",
            params + [limit, offset]).fetchall()
    return total, [_row(r) for r in rows]


def _row(r):
    d = dict(r)
    for k in ("categories", "tags", "skills"):
        d[k] = json.loads(d[k] or "[]")
    d["fresh"] = d["first_seen"] >= (utcnow() - timedelta(hours=1)).isoformat()
    d["age"] = _age(d["published_at"])
    return d


def _age(iso):
    try:
        delta = utcnow() - datetime.fromisoformat(iso)
    except (TypeError, ValueError):
        return ""
    m = int(delta.total_seconds() // 60)
    if m < 1:
        return "только что"
    if m < 60:
        return f"{m} мин"
    if m < 60 * 24:
        return f"{m // 60} ч"
    return f"{m // 1440} дн"


def _sidebar_counts():
    with db.connect() as c:
        rows = c.execute(
            "SELECT site, skills FROM orders WHERE status IN ('new','interesting')").fetchall()
        last_run = c.execute("SELECT * FROM runs ORDER BY id DESC LIMIT 1").fetchone()
    sites = {k: 0 for k in SITES}
    skills = {k: 0 for k in config.SKILLS}
    for r in rows:
        sites[r["site"]] = sites.get(r["site"], 0) + 1
        for s in json.loads(r["skills"] or "[]"):
            skills[s] = skills.get(s, 0) + 1
    run = None
    if last_run:
        run = dict(last_run)
        run["errors"] = json.loads(run["errors"] or "[]")
        run["age"] = _age(run["finished_at"] or run["started_at"])
    return sites, skills, run


@app.route("/")
def index():
    f = _filters()
    page = max(request.args.get("page", 1, type=int), 1)
    total, orders = _query(f, PAGE_SIZE, (page - 1) * PAGE_SIZE)
    site_counts, skill_counts, run = _sidebar_counts()
    return render_template(
        "index.html", f=f, orders=orders, total=total, page=page,
        pages=max((total + PAGE_SIZE - 1) // PAGE_SIZE, 1),
        sites=SITES, site_counts=site_counts,
        skills={k: v[0] for k, v in config.SKILLS.items()}, skill_counts=skill_counts,
        statuses=db.STATUSES, run=run, reply=config.REPLY_TEMPLATE,
    )


@app.post("/api/orders/<int:oid>/status")
def set_status(oid):
    status = (request.get_json(silent=True) or {}).get("status")
    if status not in db.STATUSES:
        abort(400)
    with db.connect() as c:
        if c.execute("UPDATE orders SET status=? WHERE id=?", (status, oid)).rowcount == 0:
            abort(404)
    return jsonify(ok=True, status=status)


@app.template_global()
def page_url(n):
    args = [(k, v) for k, v in request.args.items(multi=True) if k != "page"]
    return "?" + urlencode(args + [("page", n)])


@app.template_filter("plural")
def plural(n, one, few, many):
    n10, n100 = n % 10, n % 100
    word = one if n10 == 1 and n100 != 11 else few if 2 <= n10 <= 4 and not 12 <= n100 <= 14 else many
    return f"{n} {word}"


@app.template_filter("money")
def money(v):
    return f"{v:,}".replace(",", " ") if v else ""


if __name__ == "__main__":
    db.init()
    if config.DASHBOARD_HOST not in ("127.0.0.1", "localhost") and not config.DASHBOARD_PASSWORD:
        raise SystemExit("Дашборд открыт наружу без пароля. Задайте DASHBOARD_PASSWORD.")
    app.run(host=config.DASHBOARD_HOST, port=config.DASHBOARD_PORT)
