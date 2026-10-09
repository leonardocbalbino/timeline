"""Linha do Tempo de Provas - sistema leve para organizar prints, áudios e vídeos
em ordem cronológica, com hash SHA-256 de cada arquivo e registro de auditoria."""
import csv
import hashlib
import io
import os
import secrets
import sqlite3
import tempfile
import time
import uuid
import zipfile
from datetime import datetime
from functools import wraps
from urllib.parse import quote
from zoneinfo import ZoneInfo

from flask import (Flask, abort, flash, g, redirect, render_template, request,
                   send_file, session, url_for, Response)

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.environ.get("DATA_DIR", os.path.join(BASE, "data"))
UPLOADS = os.path.join(DATA, "uploads")
DB_PATH = os.path.join(DATA, "provas.db")
TZ = ZoneInfo(os.environ.get("TZ_NAME", "America/Sao_Paulo"))
USE_X_ACCEL = os.environ.get("USE_X_ACCEL", "1") == "1"

os.makedirs(UPLOADS, exist_ok=True)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
app.config.update(
    MAX_CONTENT_LENGTH=4 * 1024 ** 3,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    PERMANENT_SESSION_LIFETIME=60 * 60 * 12,
)

PASSWORDS = {
    "admin": os.environ.get("ADMIN_PASSWORD", ""),
    "leitor": os.environ.get("VIEWER_PASSWORD", ""),
}

MIME_FIX = {".opus": "audio/ogg", ".ogg": "audio/ogg", ".m4a": "audio/mp4",
            ".aac": "audio/aac", ".amr": "audio/amr", ".mp3": "audio/mpeg",
            ".wav": "audio/wav", ".mp4": "video/mp4", ".mov": "video/quicktime",
            ".webm": "video/webm", ".3gp": "video/3gpp", ".mkv": "video/x-matroska",
            ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
            ".webp": "image/webp", ".gif": "image/gif", ".heic": "image/heic",
            ".pdf": "application/pdf", ".txt": "text/plain"}

DIAS = ["Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira",
        "Sexta-feira", "Sábado", "Domingo"]
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
         "agosto", "setembro", "outubro", "novembro", "dezembro"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS evidences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    occurred_at TEXT NOT NULL,          -- YYYY-MM-DDTHH:MM:SS (horário de Brasília)
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT '',
    people TEXT NOT NULL DEFAULT '',
    important INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ev_when ON evidences(occurred_at);
CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    evidence_id INTEGER NOT NULL REFERENCES evidences(id) ON DELETE CASCADE,
    stored_name TEXT NOT NULL,
    original_name TEXT NOT NULL,
    mime TEXT NOT NULL,
    kind TEXT NOT NULL,                 -- imagem | audio | video | documento
    size INTEGER NOT NULL,
    sha256 TEXT NOT NULL,
    uploaded_at TEXT NOT NULL,
    position INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_files_ev ON files(evidence_id);
CREATE TABLE IF NOT EXISTS audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    at TEXT NOT NULL,
    role TEXT NOT NULL,
    ip TEXT NOT NULL,
    action TEXT NOT NULL,
    detail TEXT NOT NULL DEFAULT ''
);
"""


# ---------------------------------------------------------------- utilidades
def now():
    return datetime.now(TZ).strftime("%Y-%m-%dT%H:%M:%S")


def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys=ON")
        g.db.execute("PRAGMA journal_mode=WAL")
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    conn.close()


def client_ip():
    return request.headers.get("X-Real-IP") or request.remote_addr or "?"


def audit(action, detail=""):
    db().execute("INSERT INTO audit(at, role, ip, action, detail) VALUES (?,?,?,?,?)",
                 (now(), session.get("role", "-"), client_ip(), action, detail))
    db().commit()


def kind_for(mime):
    if mime.startswith("image/"):
        return "imagem"
    if mime.startswith("audio/"):
        return "audio"
    if mime.startswith("video/"):
        return "video"
    return "documento"


def guess_mime(filename, fallback):
    ext = os.path.splitext(filename)[1].lower()
    return MIME_FIX.get(ext) or fallback or "application/octet-stream"


def human_size(n):
    for unit in ["B", "KB", "MB", "GB"]:
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024


def parse_dt(s):
    try:
        return datetime.strptime(s[:19], "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return datetime.strptime(s[:16], "%Y-%m-%dT%H:%M")


def fmt_day(s):
    d = parse_dt(s)
    return f"{DIAS[d.weekday()]}, {d.day} de {MESES[d.month - 1]} de {d.year}"


def fmt_dt(s):
    d = parse_dt(s)
    return d.strftime("%d/%m/%Y %H:%M:%S")


app.jinja_env.filters.update(human_size=human_size, fmt_day=fmt_day, fmt_dt=fmt_dt,
                             hora=lambda s: s[11:19] if s[17:19] != "00" else s[11:16])


# ---------------------------------------------------------------- autenticação
_fails = {}


def login_required(role=None):
    def deco(fn):
        @wraps(fn)
        def wrapper(*a, **kw):
            if "role" not in session:
                return redirect(url_for("login", next=request.full_path))
            if role == "admin" and session["role"] != "admin":
                abort(403)
            return fn(*a, **kw)
        return wrapper
    return deco


def csrf_token():
    if "csrf" not in session:
        session["csrf"] = secrets.token_hex(16)
    return session["csrf"]


app.jinja_env.globals["csrf_token"] = csrf_token


@app.before_request
def check_csrf():
    if request.method == "POST" and request.endpoint != "login":
        if request.form.get("csrf") != session.get("csrf"):
            abort(400, "Token de segurança inválido. Recarregue a página.")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        ip = client_ip()
        fails = [t for t in _fails.get(ip, []) if time.time() - t < 900]
        if len(fails) >= 8:
            flash("Muitas tentativas. Aguarde 15 minutos.", "erro")
            return render_template("login.html"), 429
        pwd = request.form.get("senha", "")
        role = next((r for r, p in PASSWORDS.items()
                     if p and secrets.compare_digest(p, pwd)), None)
        if role:
            _fails.pop(ip, None)
            session.clear()
            session.permanent = True
            session["role"] = role
            audit("login")
            nxt = request.args.get("next", "")
            return redirect(nxt if nxt.startswith("/") and not nxt.startswith("//") else url_for("timeline"))
        fails.append(time.time())
        _fails[ip] = fails
        time.sleep(1)
        flash("Senha incorreta.", "erro")
    return render_template("login.html")


@app.route("/sair")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------------------------------------------------------------- consultas
def load_evidences(filters):
    sql = "SELECT * FROM evidences WHERE 1=1"
    args = []
    if filters.get("de"):
        sql += " AND occurred_at >= ?"
        args.append(filters["de"])
    if filters.get("ate"):
        sql += " AND occurred_at <= ?"
        args.append(filters["ate"] + "T23:59:59")
    if filters.get("q"):
        sql += " AND (title LIKE ? OR description LIKE ? OR source LIKE ? OR people LIKE ?)"
        args += [f"%{filters['q']}%"] * 4
    if filters.get("destaque"):
        sql += " AND important = 1"
    if filters.get("tipo"):
        sql += " AND id IN (SELECT evidence_id FROM files WHERE kind = ?)"
        args.append(filters["tipo"])
    sql += " ORDER BY occurred_at ASC, id ASC"
    evs = [dict(r) for r in db().execute(sql, args)]
    if evs:
        ids = [e["id"] for e in evs]
        marks = ",".join("?" * len(ids))
        files = {}
        for f in db().execute(f"SELECT * FROM files WHERE evidence_id IN ({marks}) "
                              "ORDER BY position, id", ids):
            files.setdefault(f["evidence_id"], []).append(dict(f))
        for e in evs:
            e["files"] = files.get(e["id"], [])
    return evs


def group_by_day(evs):
    days = []
    for e in evs:
        key = e["occurred_at"][:10]
        if not days or days[-1][0] != key:
            days.append((key, []))
        days[-1][1].append(e)
    return days


def current_filters():
    return {k: request.args.get(k, "").strip() for k in ("q", "de", "ate", "tipo", "destaque")}


@app.route("/")
@login_required()
def timeline():
    f = current_filters()
    evs = load_evidences(f)
    stats = db().execute("SELECT COUNT(*) n, MIN(occurred_at) a, MAX(occurred_at) b "
                         "FROM evidences").fetchone()
    kinds = dict(db().execute("SELECT kind, COUNT(*) FROM files GROUP BY kind").fetchall())
    return render_template("timeline.html", days=group_by_day(evs), total=len(evs),
                           stats=stats, kinds=kinds, f=f)


@app.route("/relatorio")
@login_required()
def report():
    f = current_filters()
    evs = load_evidences(f)
    audit("relatorio", str({k: v for k, v in f.items() if v}))
    return render_template("report.html", days=group_by_day(evs), total=len(evs),
                           generated=fmt_dt(now()), f=f)


# ---------------------------------------------------------------- arquivos
def save_uploads(evidence_id, uploads):
    saved = []
    pos = db().execute("SELECT COALESCE(MAX(position), -1) + 1 FROM files WHERE evidence_id=?",
                       (evidence_id,)).fetchone()[0]
    for up in uploads:
        if not up or not up.filename:
            continue
        original = os.path.basename(up.filename.replace("\\", "/"))[:200]
        ext = os.path.splitext(original)[1].lower()[:10]
        stored = f"{uuid.uuid4().hex}{ext}"
        path = os.path.join(UPLOADS, stored)
        h = hashlib.sha256()
        size = 0
        with open(path, "wb") as out:
            while True:
                chunk = up.stream.read(1024 * 1024)
                if not chunk:
                    break
                h.update(chunk)
                size += len(chunk)
                out.write(chunk)
        os.chmod(path, 0o440)
        mime = guess_mime(original, up.mimetype)
        digest = h.hexdigest()
        db().execute("INSERT INTO files(evidence_id, stored_name, original_name, mime, kind, "
                     "size, sha256, uploaded_at, position) VALUES (?,?,?,?,?,?,?,?,?)",
                     (evidence_id, stored, original, mime, kind_for(mime), size, digest,
                      now(), pos))
        pos += 1
        saved.append(f"{original} sha256={digest}")
    return saved


def read_form():
    data = request.form.get("data", "")
    hora = request.form.get("hora", "") or "00:00"
    if len(hora) == 5:
        hora += ":00"
    occurred = f"{data}T{hora}"
    parse_dt(occurred)  # valida
    return {
        "occurred_at": occurred,
        "title": request.form.get("titulo", "").strip()[:300],
        "description": request.form.get("descricao", "").strip(),
        "source": request.form.get("origem", "").strip()[:120],
        "people": request.form.get("pessoas", "").strip()[:300],
        "important": 1 if request.form.get("destaque") else 0,
    }


@app.route("/novo", methods=["GET", "POST"])
@login_required("admin")
def new():
    if request.method == "POST":
        try:
            ev = read_form()
        except ValueError:
            flash("Data ou hora inválida.", "erro")
            return render_template("form.html", ev=request.form, files=[]), 400
        if not ev["title"]:
            flash("Informe um título.", "erro")
            return render_template("form.html", ev=request.form, files=[]), 400
        cur = db().execute("INSERT INTO evidences(occurred_at, title, description, source, "
                           "people, important, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?)",
                           (ev["occurred_at"], ev["title"], ev["description"], ev["source"],
                            ev["people"], ev["important"], now(), now()))
        eid = cur.lastrowid
        saved = save_uploads(eid, request.files.getlist("arquivos"))
        db().commit()
        audit("criar", f"#{eid} {ev['occurred_at']} {ev['title']} | " + "; ".join(saved))
        flash("Prova adicionada à linha do tempo.", "ok")
        if request.form.get("continuar"):
            return redirect(url_for("new", data=ev["occurred_at"][:10]))
        return redirect(url_for("timeline") + f"#e{eid}")
    return render_template("form.html", ev={"data": request.args.get("data", "")}, files=[])


def get_ev(eid):
    ev = db().execute("SELECT * FROM evidences WHERE id=?", (eid,)).fetchone()
    if not ev:
        abort(404)
    return ev


@app.route("/prova/<int:eid>/editar", methods=["GET", "POST"])
@login_required("admin")
def edit(eid):
    ev = get_ev(eid)
    files = db().execute("SELECT * FROM files WHERE evidence_id=? ORDER BY position, id",
                         (eid,)).fetchall()
    if request.method == "POST":
        try:
            new_ev = read_form()
        except ValueError:
            flash("Data ou hora inválida.", "erro")
            return redirect(url_for("edit", eid=eid))
        db().execute("UPDATE evidences SET occurred_at=?, title=?, description=?, source=?, "
                     "people=?, important=?, updated_at=? WHERE id=?",
                     (new_ev["occurred_at"], new_ev["title"] or ev["title"],
                      new_ev["description"], new_ev["source"], new_ev["people"],
                      new_ev["important"], now(), eid))
        removed = []
        for fid in request.form.getlist("remover"):
            f = db().execute("SELECT * FROM files WHERE id=? AND evidence_id=?",
                             (fid, eid)).fetchone()
            if f:
                db().execute("DELETE FROM files WHERE id=?", (fid,))
                _unlink(f["stored_name"])
                removed.append(f"{f['original_name']} sha256={f['sha256']}")
        saved = save_uploads(eid, request.files.getlist("arquivos"))
        db().commit()
        changes = {k: (ev[k], v) for k, v in new_ev.items() if str(ev[k]) != str(v)}
        audit("editar", f"#{eid} alterações={changes} adicionados={saved} removidos={removed}")
        flash("Alterações salvas.", "ok")
        return redirect(url_for("timeline") + f"#e{eid}")
    d = dict(ev)
    d["data"], d["hora"] = ev["occurred_at"][:10], ev["occurred_at"][11:19]
    return render_template("form.html", ev=d, files=files, editing=True)


def _unlink(stored):
    try:
        os.remove(os.path.join(UPLOADS, stored))
    except FileNotFoundError:
        pass


@app.route("/prova/<int:eid>/excluir", methods=["POST"])
@login_required("admin")
def delete(eid):
    ev = get_ev(eid)
    files = db().execute("SELECT * FROM files WHERE evidence_id=?", (eid,)).fetchall()
    db().execute("DELETE FROM evidences WHERE id=?", (eid,))
    db().commit()
    for f in files:
        _unlink(f["stored_name"])
    audit("excluir", f"#{eid} {ev['occurred_at']} {ev['title']} | " +
          "; ".join(f"{f['original_name']} sha256={f['sha256']}" for f in files))
    flash("Prova excluída.", "ok")
    return redirect(url_for("timeline"))


@app.route("/arquivo/<int:fid>")
@login_required()
def file(fid):
    f = db().execute("SELECT * FROM files WHERE id=?", (fid,)).fetchone()
    if not f:
        abort(404)
    download = request.args.get("baixar") == "1"
    if download:
        audit("baixar", f"{f['original_name']} sha256={f['sha256']}")
    disp = "attachment" if download else "inline"
    cd = f"{disp}; filename*=UTF-8''{quote(f['original_name'])}"
    if USE_X_ACCEL:
        r = Response(status=200)
        r.headers["X-Accel-Redirect"] = f"/_protegido/{f['stored_name']}"
        r.headers["Content-Type"] = f["mime"]
        r.headers["Content-Disposition"] = cd
        r.headers["Cache-Control"] = "private, max-age=3600"
        return r
    r = send_file(os.path.join(UPLOADS, f["stored_name"]), mimetype=f["mime"], conditional=True)
    r.headers["Content-Disposition"] = cd
    return r


@app.route("/verificar", methods=["GET", "POST"])
@login_required()
def verify():
    """Confere se um arquivo é idêntico (mesmo SHA-256) a algum arquivo registrado."""
    result = None
    if request.method == "POST":
        up = request.files.get("arquivo")
        if up and up.filename:
            h = hashlib.sha256()
            for chunk in iter(lambda: up.stream.read(1024 * 1024), b""):
                h.update(chunk)
            digest = h.hexdigest()
            rows = db().execute("SELECT f.*, e.title, e.occurred_at FROM files f JOIN evidences e "
                                "ON e.id = f.evidence_id WHERE f.sha256=?", (digest,)).fetchall()
            result = {"name": up.filename, "sha256": digest, "matches": rows}
    return render_template("verify.html", result=result)


@app.route("/exportar")
@login_required()
def export():
    """Gera um ZIP com todos os arquivos, organizados por data, e um manifesto CSV."""
    evs = load_evidences(current_filters())
    audit("exportar", f"{len(evs)} provas")
    tmp = tempfile.NamedTemporaryFile(prefix="export-", suffix=".zip", dir=DATA, delete=False)
    tmp.close()
    manifest = io.StringIO()
    w = csv.writer(manifest, delimiter=";")
    w.writerow(["n", "data_hora", "titulo", "descricao", "origem", "pessoas", "destaque",
                "arquivo_no_zip", "nome_original", "tipo", "tamanho_bytes", "sha256",
                "enviado_ao_sistema_em"])
    with zipfile.ZipFile(tmp.name, "w", zipfile.ZIP_STORED, allowZip64=True) as z:
        for i, e in enumerate(evs, 1):
            prefix = f"{i:03d}_{e['occurred_at'][:16].replace(':', 'h').replace('T', '_')}"
            if not e["files"]:
                w.writerow([i, fmt_dt(e["occurred_at"]), e["title"], e["description"],
                            e["source"], e["people"], e["important"], "", "", "", "", "", ""])
            for j, f in enumerate(e["files"], 1):
                arc = f"arquivos/{prefix}_{j}_{f['original_name']}"
                z.write(os.path.join(UPLOADS, f["stored_name"]), arc)
                w.writerow([i, fmt_dt(e["occurred_at"]), e["title"], e["description"],
                            e["source"], e["people"], e["important"], arc, f["original_name"],
                            f["kind"], f["size"], f["sha256"], fmt_dt(f["uploaded_at"])])
        z.writestr("manifesto.csv", "﻿" + manifest.getvalue())
        z.writestr("LEIA-ME.txt",
                   "Pacote exportado da Linha do Tempo de Provas em " + fmt_dt(now()) + ".\n"
                   "O arquivo manifesto.csv lista cada prova em ordem cronológica e o hash\n"
                   "SHA-256 de cada arquivo, calculado no momento do envio ao sistema.\n"
                   "Para conferir a integridade de um arquivo:\n"
                   "  Windows:  certutil -hashfile <arquivo> SHA256\n"
                   "  Linux/Mac: sha256sum <arquivo>  /  shasum -a 256 <arquivo>\n")

    resp = send_file(tmp.name, mimetype="application/zip", as_attachment=True,
                     download_name=f"provas_{now()[:10]}.zip")
    resp.call_on_close(lambda: os.path.exists(tmp.name) and os.remove(tmp.name))
    return resp


@app.route("/auditoria")
@login_required("admin")
def audit_log():
    rows = db().execute("SELECT * FROM audit ORDER BY id DESC LIMIT 1000").fetchall()
    return render_template("audit.html", rows=rows)


@app.errorhandler(413)
def too_large(_e):
    return "Arquivo grande demais (limite 4 GB por envio).", 413


init_db()

if __name__ == "__main__":
    app.run(debug=True, port=8410)
