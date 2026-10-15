"""Íntegra — núcleo: configuração, banco de dados, migração, autenticação, planos e utilidades."""
import hashlib
import json
import os
import re
import secrets
import sqlite3
import uuid
from datetime import date, datetime, timedelta
from functools import wraps
from urllib.parse import quote
from zoneinfo import ZoneInfo

from icons import icon
from flask import (Flask, Response, abort, flash, g, redirect, request, send_file, session,
                   url_for)
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import generate_password_hash

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.environ.get("DATA_DIR", os.path.join(BASE, "data"))
UPLOADS = os.path.join(DATA, "uploads")
DB_PATH = os.path.join(DATA, "provas.db")
TZ = ZoneInfo(os.environ.get("TZ_NAME", "America/Sao_Paulo"))
USE_X_ACCEL = os.environ.get("USE_X_ACCEL", "1") == "1"
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin").strip().lower()
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")

os.makedirs(UPLOADS, exist_ok=True)

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1)  # nginx informa http/https
app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
app.config.update(
    MAX_CONTENT_LENGTH=4 * 1024 ** 3,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    PERMANENT_SESSION_LIFETIME=60 * 60 * 12,
)

MIME_FIX = {".opus": "audio/ogg", ".ogg": "audio/ogg", ".m4a": "audio/mp4",
            ".aac": "audio/aac", ".amr": "audio/amr", ".mp3": "audio/mpeg",
            ".wav": "audio/wav", ".mp4": "video/mp4", ".mov": "video/quicktime",
            ".webm": "video/webm", ".3gp": "video/3gpp", ".mkv": "video/x-matroska",
            ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
            ".webp": "image/webp", ".gif": "image/gif", ".heic": "image/heic",
            ".pdf": "application/pdf", ".txt": "text/plain"}

DIAS = ["Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira",
        "Sexta-feira", "Sábado", "Domingo"]
DIAS_CURTOS = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
         "agosto", "setembro", "outubro", "novembro", "dezembro"]

# ---------------------------------------------------------------- planos
# Funcionalidades que o admin libera por plano (tela Admin > Planos).
FEATURES = [
    ("timeline_horizontal", "Linha do tempo horizontal"),
    ("relatorio", "Relatório para imprimir / salvar em PDF"),
    ("exportar", "Pacote ZIP com originais e manifesto de hashes"),
    ("verificar", "Verificação de integridade de arquivos"),
    ("compartilhar", "Link somente leitura para advogado / terceiros"),
    ("auditoria", "Registro de auditoria da conta"),
]
FEATURE_NAMES = dict(FEATURES)
PLAN_LABELS = {"free": "Free", "pro": "Pro"}
DEFAULT_PLANS = {
    "free": {"features": ["relatorio", "verificar"], "max_processos": 1, "max_storage_mb": 1024},
    "pro": {"features": [k for k, _ in FEATURES], "max_processos": 0, "max_storage_mb": 51200},
}
DEFAULT_SETTINGS = {"pix_chave": "", "pix_nome": "", "pix_cidade": "",
                    "pro_preco": "49.90", "pro_dias": "30", "planos": "",
                    "autocadastro": "1", "contato_email": "", "gateway": "manual"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS tenants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    document TEXT NOT NULL DEFAULT '',
    phone TEXT NOT NULL DEFAULT '',
    plan TEXT NOT NULL DEFAULT 'free',  -- free | pro
    pro_until TEXT,                     -- YYYY-MM-DD; NULL = Pro sem vencimento
    active INTEGER NOT NULL DEFAULT 1,
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER REFERENCES tenants(id) ON DELETE CASCADE,  -- NULL para o admin
    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
    name TEXT NOT NULL DEFAULT '',
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL,                 -- admin | cliente
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    last_login TEXT
);
CREATE TABLE IF NOT EXISTS processes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    number TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    share_token TEXT UNIQUE,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS evidences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    occurred_at TEXT NOT NULL,          -- YYYY-MM-DDTHH:MM:SS (horário de Brasília)
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT '',
    people TEXT NOT NULL DEFAULT '',
    important INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    process_id INTEGER REFERENCES processes(id) ON DELETE CASCADE
);
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
CREATE TABLE IF NOT EXISTS audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    at TEXT NOT NULL,
    role TEXT NOT NULL,
    ip TEXT NOT NULL,
    action TEXT NOT NULL,
    detail TEXT NOT NULL DEFAULT '',
    tenant_id INTEGER,
    user_email TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    txid TEXT NOT NULL UNIQUE,
    amount_cents INTEGER NOT NULL,
    days INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pendente',  -- pendente | informado | confirmado | vencido | estornado | recusado | cancelado
    created_at TEXT NOT NULL,
    informed_at TEXT,
    decided_at TEXT,
    decided_by TEXT NOT NULL DEFAULT '',
    receipt_stored TEXT,
    receipt_name TEXT,
    note TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    provider TEXT NOT NULL DEFAULT 'asaas',
    external_id TEXT UNIQUE,
    status TEXT NOT NULL DEFAULT 'ativa',      -- ativa | inativa | cancelada
    months INTEGER NOT NULL,
    days INTEGER NOT NULL,                      -- dias de Pro liberados a cada cobrança paga
    value_cents INTEGER NOT NULL,
    billing_type TEXT NOT NULL,
    next_due_date TEXT,
    created_at TEXT NOT NULL,
    canceled_at TEXT,
    canceled_by TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS webhook_events (
    id TEXT PRIMARY KEY,                        -- id do evento no Asaas (idempotência)
    event TEXT NOT NULL,
    resource_id TEXT,
    received_at TEXT NOT NULL,
    error TEXT NOT NULL DEFAULT '',
    payload TEXT NOT NULL
);
"""

INDEXES = """
CREATE INDEX IF NOT EXISTS idx_ev_when ON evidences(occurred_at);
CREATE INDEX IF NOT EXISTS idx_ev_proc ON evidences(process_id, occurred_at);
CREATE INDEX IF NOT EXISTS idx_files_ev ON files(evidence_id);
CREATE INDEX IF NOT EXISTS idx_files_hash ON files(sha256);
CREATE INDEX IF NOT EXISTS idx_proc_tenant ON processes(tenant_id);
CREATE INDEX IF NOT EXISTS idx_audit_tenant ON audit(tenant_id, id);
CREATE INDEX IF NOT EXISTS idx_pay_tenant ON payments(tenant_id, id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_pay_external ON payments(external_id);
CREATE INDEX IF NOT EXISTS idx_sub_tenant ON subscriptions(tenant_id, id);
"""


# ---------------------------------------------------------------- utilidades
def now():
    return datetime.now(TZ).strftime("%Y-%m-%dT%H:%M:%S")


def today():
    return datetime.now(TZ).date().isoformat()


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
    """Cria as tabelas e migra a versão de usuário único para multi-cliente."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA)

    def cols(table):
        return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}

    if "process_id" not in cols("evidences"):
        conn.execute("ALTER TABLE evidences ADD COLUMN process_id INTEGER "
                     "REFERENCES processes(id) ON DELETE CASCADE")
    audit_cols = cols("audit")
    if "tenant_id" not in audit_cols:
        conn.execute("ALTER TABLE audit ADD COLUMN tenant_id INTEGER")
    if "user_email" not in audit_cols:
        conn.execute("ALTER TABLE audit ADD COLUMN user_email TEXT NOT NULL DEFAULT ''")
    pay_cols = cols("payments")
    for col, ddl in (("provider", "TEXT NOT NULL DEFAULT 'manual'"),   # manual | asaas
                     ("kind", "TEXT NOT NULL DEFAULT 'plano'"),       # plano | assinatura | avulsa
                     ("external_id", "TEXT"), ("subscription_id", "INTEGER"),
                     ("billing_type", "TEXT NOT NULL DEFAULT 'PIX'"), ("invoice_url", "TEXT"),
                     ("due_date", "TEXT"), ("description", "TEXT NOT NULL DEFAULT ''"),
                     ("paid_at", "TEXT"), ("synced_at", "TEXT")):
        if col not in pay_cols:
            conn.execute(f"ALTER TABLE payments ADD COLUMN {col} {ddl}")
    if "asaas_customer_id" not in cols("tenants"):
        conn.execute("ALTER TABLE tenants ADD COLUMN asaas_customer_id TEXT")
    conn.executescript(INDEXES)

    # Provas da versão anterior vão para uma conta "Conta principal" (Pro sem vencimento).
    if conn.execute("SELECT 1 FROM evidences WHERE process_id IS NULL LIMIT 1").fetchone():
        ts = now()
        tid = conn.execute("INSERT INTO tenants(name, plan, pro_until, notes, created_at) "
                           "VALUES ('Conta principal', 'pro', NULL, ?, ?)",
                           ("Criada automaticamente com as provas da versão anterior.", ts)).lastrowid
        pid = conn.execute("INSERT INTO processes(tenant_id, title, created_at, updated_at) "
                           "VALUES (?, 'Processo principal', ?, ?)", (tid, ts, ts)).lastrowid
        conn.execute("UPDATE evidences SET process_id=? WHERE process_id IS NULL", (pid,))
        conn.execute("UPDATE audit SET tenant_id=? WHERE tenant_id IS NULL", (tid,))

    if ADMIN_PASSWORD and not conn.execute("SELECT 1 FROM users WHERE role='admin'").fetchone():
        conn.execute("INSERT INTO users(tenant_id, email, name, password_hash, role, created_at) "
                     "VALUES (NULL, ?, 'Administrador', ?, 'admin', ?)",
                     (ADMIN_EMAIL, generate_password_hash(ADMIN_PASSWORD), now()))
    conn.commit()
    conn.close()


def client_ip():
    return request.headers.get("X-Real-IP") or request.remote_addr or "?"


def audit(action, detail="", tenant_id=None):
    u, t = g.get("user"), g.get("tenant")
    if u:
        role = "admin (suporte)" if g.get("impersonating") else u["role"]
    else:
        role = "link" if g.get("share_token") else "-"
    if tenant_id is None and t is not None:
        tenant_id = t["id"]
    db().execute("INSERT INTO audit(at, role, ip, action, detail, tenant_id, user_email) "
                 "VALUES (?,?,?,?,?,?,?)",
                 (now(), role, client_ip(), action, detail, tenant_id, u["email"] if u else ""))
    db().commit()


def new_password():
    return secrets.token_urlsafe(9)


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
    n = n or 0
    for unit in ["B", "KB", "MB", "GB"]:
        if n < 1024 or unit == "GB":
            if unit == "B" or n == int(n):
                return f"{n:.0f} {unit}"
            return f"{n:.1f} {unit}".replace(".", ",")
        n /= 1024


def parse_dt(s):
    try:
        return datetime.strptime(s[:19], "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return datetime.strptime(s[:16], "%Y-%m-%dT%H:%M")


def fmt_day(s):
    d = parse_dt(s)
    return f"{DIAS[d.weekday()]}, {d.day} de {MESES[d.month - 1]} de {d.year}"


def fmt_day_short(s):
    d = parse_dt(s)
    return f"{DIAS_CURTOS[d.weekday()]}, {d.day:02d} {MESES[d.month - 1][:3]} {d.year}"


def fmt_dt(s):
    return parse_dt(s).strftime("%d/%m/%Y %H:%M:%S") if s else ""


def fmt_date(s):
    return f"{s[8:10]}/{s[5:7]}/{s[:4]}" if s else ""


def brl(cents):
    return "R$ " + f"{(cents or 0) / 100:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def slug(s):
    s = re.sub(r"[^\w\-]+", "_", s, flags=re.UNICODE).strip("_")
    return s[:60] or "processo"


def add_days(iso_date, days):
    return (date.fromisoformat(iso_date) + timedelta(days=days)).isoformat()


app.jinja_env.filters.update(human_size=human_size, fmt_day=fmt_day, fmt_day_short=fmt_day_short,
                             fmt_dt=fmt_dt, fmt_date=fmt_date, brl=brl,
                             hora=lambda s: s[11:19] if s[17:19] != "00" else s[11:16])


# ---------------------------------------------------------------- arquivos enviados
def unlink_upload(stored):
    path = os.path.join(UPLOADS, stored)
    try:
        os.remove(path)
    except FileNotFoundError:
        pass
    except PermissionError:  # Windows não apaga arquivo somente leitura
        os.chmod(path, 0o640)
        os.remove(path)


def store_upload(up):
    """Grava o arquivo enviado em disco calculando o SHA-256. Retorna (nome, original, mime, tamanho, hash)."""
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
    return stored, original, guess_mime(original, up.mimetype), size, h.hexdigest()


def serve_upload(stored, mime, original, download):
    disp = "attachment" if download else "inline"
    cd = f"{disp}; filename*=UTF-8''{quote(original)}"
    if USE_X_ACCEL:
        r = Response(status=200)
        r.headers["X-Accel-Redirect"] = f"/_protegido/{stored}"
        r.headers["Content-Type"] = mime
        r.headers["Content-Disposition"] = cd
        r.headers["Cache-Control"] = "private, max-age=3600"
        return r
    r = send_file(os.path.join(UPLOADS, stored), mimetype=mime, conditional=True)
    r.headers["Content-Disposition"] = cd
    return r



# ---------------------------------------------------------------- configurações e planos
def setting(key):
    row = db().execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row[0] if row else DEFAULT_SETTINGS.get(key, "")


def set_setting(key, value):
    db().execute("INSERT INTO settings(key, value) VALUES (?, ?) "
                 "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, str(value)))


def plans():
    if "plans" not in g:
        saved = json.loads(setting("planos") or "{}")
        g.plans = {k: {**v, **saved.get(k, {})} for k, v in DEFAULT_PLANS.items()}
    return g.plans


def effective_plan(t):
    if t is None:
        return "free"
    if t["plan"] == "pro" and (not t["pro_until"] or t["pro_until"] >= today()):
        return "pro"
    return "free"


def plan_cfg(t=None):
    return plans()[effective_plan(t if t is not None else g.get("tenant"))]


def has_feature(name, t=None):
    t = t if t is not None else g.get("tenant")
    return t is not None and name in plan_cfg(t)["features"]


def grant_pro(tenant_id, days):
    """Soma dias de Pro a partir do vencimento atual (ou de hoje, se já venceu). Retorna o novo vencimento."""
    t = db().execute("SELECT * FROM tenants WHERE id=?", (tenant_id,)).fetchone()
    if not t or days <= 0:
        return t["pro_until"] if t else None
    if t["plan"] == "pro" and not t["pro_until"]:
        return None  # já é Pro sem vencimento
    base = t["pro_until"] if effective_plan(t) == "pro" and t["pro_until"] else today()
    until = add_days(base, days)
    db().execute("UPDATE tenants SET plan='pro', pro_until=? WHERE id=?", (until, tenant_id))
    return until


def revoke_pro(tenant_id, days):
    """Desfaz dias de Pro de um pagamento estornado (não mexe em Pro sem vencimento)."""
    t = db().execute("SELECT * FROM tenants WHERE id=?", (tenant_id,)).fetchone()
    if t and t["plan"] == "pro" and t["pro_until"] and days > 0:
        db().execute("UPDATE tenants SET pro_until=? WHERE id=?", (add_days(t["pro_until"], -days), tenant_id))


def storage_used(tenant_id):
    return db().execute("SELECT COALESCE(SUM(f.size), 0) FROM files f "
                        "JOIN evidences e ON e.id = f.evidence_id "
                        "JOIN processes p ON p.id = e.process_id WHERE p.tenant_id=?",
                        (tenant_id,)).fetchone()[0]


def process_count(tenant_id):
    return db().execute("SELECT COUNT(*) FROM processes WHERE tenant_id=?", (tenant_id,)).fetchone()[0]


def quota_left(t=None):
    """Bytes ainda disponíveis para o cliente (None = ilimitado)."""
    t = t if t is not None else g.tenant
    limit = int(plan_cfg(t)["max_storage_mb"] or 0)
    if not limit:
        return None
    return limit * 1024 ** 2 - storage_used(t["id"])


# ---------------------------------------------------------------- autenticação
def password_fingerprint(user):
    return user["password_hash"][-16:]


@app.before_request
def load_user():
    g.user = g.tenant = None
    g.impersonating = False
    uid = session.get("uid")
    if not uid or request.endpoint == "static":
        return
    u = db().execute("SELECT * FROM users WHERE id=? AND active=1", (uid,)).fetchone()
    if not u or session.get("pwv") != password_fingerprint(u):
        session.clear()
        return
    if u["role"] == "admin":
        tid = session.get("as_tenant")
        if tid:
            g.tenant = db().execute("SELECT * FROM tenants WHERE id=?", (tid,)).fetchone()
            g.impersonating = g.tenant is not None
            if not g.tenant:
                session.pop("as_tenant", None)
    else:
        g.tenant = db().execute("SELECT * FROM tenants WHERE id=?", (u["tenant_id"],)).fetchone()
        if not g.tenant or not g.tenant["active"]:
            session.clear()
            flash("Sua conta está desativada. Fale com o administrador.", "erro")
            return
    g.user = u


PUBLIC_PAGES = {"index", "signup", "static"}


@app.after_request
def robots(resp):
    """Só a página inicial e o cadastro podem aparecer em buscadores."""
    if request.endpoint not in PUBLIC_PAGES or g.get("user"):
        resp.headers["X-Robots-Tag"] = "noindex, nofollow"
    return resp


def csrf_token():
    if "csrf" not in session:
        session["csrf"] = secrets.token_hex(16)
    return session["csrf"]


@app.before_request
def check_csrf():
    if request.method == "POST" and request.endpoint not in ("login", "asaas_webhook"):
        if request.form.get("csrf") != session.get("csrf"):
            abort(400, "Token de segurança inválido. Recarregue a página.")


def _to_login():
    return redirect(url_for("login", next=request.full_path))


def login_required(fn):
    @wraps(fn)
    def wrapper(*a, **kw):
        if not g.user:
            return _to_login()
        return fn(*a, **kw)
    return wrapper


def admin_required(fn):
    @wraps(fn)
    def wrapper(*a, **kw):
        if not g.user:
            return _to_login()
        if g.user["role"] != "admin":
            abort(403)
        return fn(*a, **kw)
    return wrapper


def tenant_required(fn):
    """Área do cliente. O admin só entra aqui pelo "Acessar conta" de um cliente."""
    @wraps(fn)
    def wrapper(*a, **kw):
        if not g.user:
            return _to_login()
        if not g.tenant:
            if g.user["role"] == "admin":
                return redirect(url_for("admin_home"))
            abort(403)
        return fn(*a, **kw)
    return wrapper


def feature_required(name):
    def deco(fn):
        @wraps(fn)
        def wrapper(*a, **kw):
            if not has_feature(name):
                flash(f"“{FEATURE_NAMES[name]}” não está liberado no seu plano.", "erro")
                return redirect(url_for("plan"))
            return fn(*a, **kw)
        return wrapper
    return deco


def file_url(fid, download=False):
    args = {"baixar": 1} if download else {}
    if g.get("share_token"):
        return url_for("share_file", token=g.share_token, fid=fid, **args)
    return url_for("file", fid=fid, **args)


def self_url(**overrides):
    """URL da página atual trocando alguns parâmetros da query string."""
    args = request.args.to_dict()
    for k, v in overrides.items():
        if v in (None, ""):
            args.pop(k, None)
        else:
            args[k] = v
    return url_for(request.endpoint, **(request.view_args or {}), **args)


def short_hash(h):
    return f"{h[:4]}…{h[-4:]}" if h and len(h) > 8 else (h or "")


def initials(name):
    parts = [p for p in re.split(r"[\s@._-]+", name or "") if p]
    return ((parts[0][0] + (parts[1][0] if len(parts) > 1 else "")) if parts else "?").upper()


app.jinja_env.filters.update(short_hash=short_hash, initials=initials)
app.jinja_env.globals.update(csrf_token=csrf_token, has_feature=has_feature, file_url=file_url,
                             self_url=self_url, effective_plan=effective_plan, plan_cfg=plan_cfg,
                             icon=icon, PLAN_LABELS=PLAN_LABELS, FEATURES=FEATURES)
