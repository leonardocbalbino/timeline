"""API JSON do app (Android/iOS). Autenticação por token Bearer, criado no login do app.

As regras são as mesmas da web: isolamento por cliente, limites do plano, upload em partes
(rotas /uploads/... aceitam o mesmo token), hash SHA-256 e auditoria. O app não vende nem
leva para a assinatura do Pro: compra de plano só pelo site (regras da App Store e do Google Play).
"""
import secrets
import time
from functools import wraps

from flask import g, jsonify, request, url_for
from werkzeug.security import check_password_hash

import billing
import chunks
from core import (FEATURES, PLAN_LABELS, app, audit, client_ip, db, effective_plan, has_feature, now,
                  parse_dt, password_fingerprint, plan_cfg, process_count, serve_upload, storage_used,
                  token_hash, unlink_upload)

_fails = {}


def api_error(message, status=400, **extra):
    return jsonify(error=message, **extra), status


def api_auth(fn):
    @wraps(fn)
    def wrapper(*a, **kw):
        if not g.get("api_token"):
            return api_error("Sessão expirada. Entre de novo.", 401)
        return fn(*a, **kw)
    return wrapper


def body():
    return request.get_json(silent=True) or {}


# ---------------------------------------------------------------- serialização
def file_json(f):
    return {"id": f["id"], "name": f["original_name"], "kind": f["kind"], "mime": f["mime"], "size": f["size"],
            "sha256": f["sha256"], "uploaded_at": f["uploaded_at"],
            "url": url_for("api_file", fid=f["id"])}


def evidence_json(e, files):
    return {"id": e["id"], "occurred_at": e["occurred_at"], "title": e["title"], "description": e["description"],
            "source": e["source"], "people": e["people"], "important": bool(e["important"]),
            "files": [file_json(f) for f in files]}


def process_json(p, extra=None):
    d = {"id": p["id"], "title": p["title"], "number": p["number"], "description": p["description"],
         "updated_at": p["updated_at"], "shared": bool(p["share_token"])}
    if extra:
        d.update(extra)
    return d


def me_json():
    t = g.tenant
    cfg = plan_cfg()
    plan = effective_plan(t)
    return {
        "user": {"id": g.user["id"], "email": g.user["email"], "name": g.user["name"]},
        "account": {"id": t["id"], "name": t["name"], "plan": plan, "plan_label": PLAN_LABELS[plan],
                    "pro_until": t["pro_until"] if plan == "pro" else None},
        "features": {k: k in cfg["features"] for k, _ in FEATURES},
        "limits": {"processes": int(cfg["max_processos"] or 0), "storage_mb": int(cfg["max_storage_mb"] or 0)},
        "usage": {"processes": process_count(t["id"]), "storage_bytes": storage_used(t["id"])},
    }


def get_process(pid):
    return db().execute("SELECT * FROM processes WHERE id=? AND tenant_id=?", (pid, g.tenant["id"])).fetchone()


# ---------------------------------------------------------------- sessão
@app.route("/api/v1/login", methods=["POST"])
def api_login():
    ip = client_ip()
    fails = [t for t in _fails.get(ip, []) if time.time() - t < 900]
    if len(fails) >= 8:
        return api_error("Muitas tentativas. Aguarde 15 minutos.", 429)
    data = body()
    email = str(data.get("email", "")).strip().lower()
    u = db().execute("SELECT u.*, t.active AS t_active FROM users u LEFT JOIN tenants t ON t.id = u.tenant_id "
                     "WHERE u.email=?", (email,)).fetchone()
    if not u or not u["active"] or not check_password_hash(u["password_hash"], str(data.get("senha", ""))):
        fails.append(time.time())
        _fails[ip] = fails
        time.sleep(1)
        return api_error("E-mail ou senha incorretos.", 401)
    if u["role"] != "cliente":
        return api_error("O app é para clientes. O administrador usa o painel no site.", 403)
    if not u["t_active"]:
        return api_error("Sua conta está desativada. Fale com o suporte.", 403)
    _fails.pop(ip, None)
    token = secrets.token_urlsafe(32)
    db().execute("INSERT INTO api_tokens(user_id, token_hash, pwv, device, created_at, last_used_at) "
                 "VALUES (?,?,?,?,?,?)", (u["id"], token_hash(token), password_fingerprint(u),
                                          str(data.get("device", ""))[:120], now(), now()))
    db().execute("UPDATE users SET last_login=? WHERE id=?", (now(), u["id"]))
    db().commit()
    g.user = u
    audit("login_app", str(data.get("device", ""))[:120], tenant_id=u["tenant_id"])
    g.user, g.tenant = u, db().execute("SELECT * FROM tenants WHERE id=?", (u["tenant_id"],)).fetchone()
    return jsonify(token=token, **me_json())


@app.route("/api/v1/sessao", methods=["DELETE"])
@api_auth
def api_logout():
    db().execute("DELETE FROM api_tokens WHERE id=?", (g.api_token,))
    db().commit()
    return jsonify(ok=True)


@app.route("/api/v1/me")
@api_auth
def api_me():
    return jsonify(me_json())


@app.route("/api/v1/conta/excluir", methods=["POST"])
@api_auth
def api_delete_account():
    if not check_password_hash(g.user["password_hash"], str(body().get("senha", ""))):
        return api_error("Senha incorreta.", 403)
    tid, name, email = g.tenant["id"], g.tenant["name"], g.user["email"]
    try:
        n = billing.delete_tenant(tid, email)
    except billing.BillingError as e:
        return api_error(f"Não foi possível cancelar a assinatura agora ({e}). Tente de novo mais tarde.", 502)
    g.tenant = None
    audit("excluir_propria_conta", f"#{tid} {name} {email} | {n} arquivo(s) apagado(s) | app", tenant_id=tid)
    return jsonify(ok=True)


# ---------------------------------------------------------------- processos
@app.route("/api/v1/processos")
@api_auth
def api_processes():
    rows = db().execute("""
        SELECT p.*,
               (SELECT COUNT(*) FROM evidences e WHERE e.process_id = p.id) AS n,
               (SELECT MIN(occurred_at) FROM evidences e WHERE e.process_id = p.id) AS a,
               (SELECT MAX(occurred_at) FROM evidences e WHERE e.process_id = p.id) AS b
        FROM processes p WHERE p.tenant_id=? ORDER BY p.updated_at DESC""", (g.tenant["id"],)).fetchall()
    return jsonify(processes=[process_json(p, {"evidence_count": p["n"], "first_at": p["a"], "last_at": p["b"]})
                              for p in rows])


@app.route("/api/v1/processos", methods=["POST"])
@api_auth
def api_process_new():
    limit = int(plan_cfg()["max_processos"] or 0)
    if limit and process_count(g.tenant["id"]) >= limit:
        return api_error(f"Seu plano permite até {limit} processo(s).", 403, code="limite_processos")
    d = body()
    title = str(d.get("titulo", "")).strip()[:200]
    if not title:
        return api_error("Informe um nome para o processo.")
    cur = db().execute("INSERT INTO processes(tenant_id, title, number, description, created_at, updated_at) "
                       "VALUES (?,?,?,?,?,?)", (g.tenant["id"], title, str(d.get("numero", "")).strip()[:80],
                                                str(d.get("descricao", "")).strip()[:4000], now(), now()))
    db().commit()
    audit("criar_processo", f"#{cur.lastrowid} {title} (app)")
    return jsonify(process=process_json(get_process(cur.lastrowid), {"evidence_count": 0})), 201


@app.route("/api/v1/processos/<int:pid>")
@api_auth
def api_process(pid):
    p = get_process(pid)
    if not p:
        return api_error("Processo não encontrado.", 404)
    evs = db().execute("SELECT * FROM evidences WHERE process_id=? ORDER BY occurred_at, id", (pid,)).fetchall()
    files = {}
    if evs:
        ids = [e["id"] for e in evs]
        for f in db().execute(f"SELECT * FROM files WHERE evidence_id IN ({','.join('?' * len(ids))}) "
                              "ORDER BY position, id", ids):
            files.setdefault(f["evidence_id"], []).append(f)
    return jsonify(process=process_json(p), evidences=[evidence_json(e, files.get(e["id"], [])) for e in evs])


@app.route("/api/v1/processos/<int:pid>/link", methods=["POST", "DELETE"])
@api_auth
def api_process_link(pid):
    p = get_process(pid)
    if not p:
        return api_error("Processo não encontrado.", 404)
    if not has_feature("compartilhar"):
        return api_error("O link para advogado não está liberado no seu plano.", 403, code="recurso_bloqueado")
    if request.method == "DELETE":
        db().execute("UPDATE processes SET share_token=NULL WHERE id=?", (pid,))
        db().commit()
        audit("revogar_link", f"#{pid} (app)")
        return jsonify(url=None)
    token = p["share_token"]
    if not token or body().get("novo"):
        token = secrets.token_urlsafe(24)
        db().execute("UPDATE processes SET share_token=? WHERE id=?", (token, pid))
        db().commit()
        audit("gerar_link", f"#{pid} (app)")
    return jsonify(url=url_for("share_view", token=token, _external=True))


# ---------------------------------------------------------------- provas
def read_evidence(d, partial=False):
    out = {}
    if not partial or "data" in d or "hora" in d:
        data = str(d.get("data", ""))
        hora = str(d.get("hora", "") or "00:00")
        if len(hora) == 5:
            hora += ":00"
        out["occurred_at"] = f"{data}T{hora}"
        parse_dt(out["occurred_at"])  # ValueError se inválida
    for key, field, size in (("title", "titulo", 300), ("description", "descricao", 20000),
                             ("source", "origem", 120), ("people", "pessoas", 300)):
        if not partial or field in d:
            out[key] = str(d.get(field, "") or "").strip()[:size]
    if not partial or "destaque" in d:
        out["important"] = 1 if d.get("destaque") else 0
    return out


@app.route("/api/v1/processos/<int:pid>/provas", methods=["POST"])
@api_auth
def api_evidence_new(pid):
    if not get_process(pid):
        return api_error("Processo não encontrado.", 404)
    d = body()
    try:
        ev = read_evidence(d)
    except ValueError:
        return api_error("Data ou hora inválida.")
    if not ev["title"]:
        return api_error("Informe um título.")
    try:
        partes = chunks.claim([str(i) for i in d.get("upload_ids") or []])
    except chunks.UploadError as e:
        return api_error(str(e))
    cur = db().execute("INSERT INTO evidences(process_id, occurred_at, title, description, source, people, important, "
                       "created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
                       (pid, ev["occurred_at"], ev["title"], ev["description"], ev["source"], ev["people"],
                        ev["important"], now(), now()))
    eid = cur.lastrowid
    saved = chunks.finalize(eid, partes)
    db().execute("UPDATE processes SET updated_at=? WHERE id=?", (now(), pid))
    db().commit()
    audit("criar", f"processo #{pid} prova #{eid} {ev['occurred_at']} {ev['title']} (app) | " + "; ".join(saved))
    e = db().execute("SELECT * FROM evidences WHERE id=?", (eid,)).fetchone()
    files = db().execute("SELECT * FROM files WHERE evidence_id=? ORDER BY position, id", (eid,)).fetchall()
    return jsonify(evidence=evidence_json(e, files)), 201


def get_evidence(pid, eid):
    if not get_process(pid):
        return None
    return db().execute("SELECT * FROM evidences WHERE id=? AND process_id=?", (eid, pid)).fetchone()


@app.route("/api/v1/processos/<int:pid>/provas/<int:eid>", methods=["PATCH"])
@api_auth
def api_evidence_edit(pid, eid):
    e = get_evidence(pid, eid)
    if not e:
        return api_error("Prova não encontrada.", 404)
    try:
        changes = read_evidence(body(), partial=True)
    except ValueError:
        return api_error("Data ou hora inválida.")
    if "title" in changes and not changes["title"]:
        return api_error("Informe um título.")
    if changes:
        sets = ", ".join(f"{k}=?" for k in changes)
        db().execute(f"UPDATE evidences SET {sets}, updated_at=? WHERE id=?", (*changes.values(), now(), eid))
        db().execute("UPDATE processes SET updated_at=? WHERE id=?", (now(), pid))
        db().commit()
        diff = {k: (e[k], v) for k, v in changes.items() if str(e[k]) != str(v)}
        audit("editar", f"processo #{pid} prova #{eid} alterações={diff} (app)")
    e = db().execute("SELECT * FROM evidences WHERE id=?", (eid,)).fetchone()
    files = db().execute("SELECT * FROM files WHERE evidence_id=? ORDER BY position, id", (eid,)).fetchall()
    return jsonify(evidence=evidence_json(e, files))


@app.route("/api/v1/processos/<int:pid>/provas/<int:eid>", methods=["DELETE"])
@api_auth
def api_evidence_delete(pid, eid):
    e = get_evidence(pid, eid)
    if not e:
        return api_error("Prova não encontrada.", 404)
    files = db().execute("SELECT * FROM files WHERE evidence_id=?", (eid,)).fetchall()
    db().execute("DELETE FROM evidences WHERE id=?", (eid,))
    db().execute("UPDATE processes SET updated_at=? WHERE id=?", (now(), pid))
    db().commit()
    for f in files:
        unlink_upload(f["stored_name"])
    audit("excluir", f"processo #{pid} prova #{eid} {e['occurred_at']} {e['title']} (app) | " +
          "; ".join(f"{f['original_name']} sha256={f['sha256']}" for f in files))
    return jsonify(ok=True)


@app.route("/api/v1/arquivos/<int:fid>")
@api_auth
def api_file(fid):
    f = db().execute("SELECT f.* FROM files f JOIN evidences e ON e.id = f.evidence_id "
                     "JOIN processes p ON p.id = e.process_id WHERE f.id=? AND p.tenant_id=?",
                     (fid, g.tenant["id"])).fetchone()
    if not f:
        return api_error("Arquivo não encontrado.", 404)
    download = request.args.get("baixar") == "1"
    if download:
        audit("baixar", f"{f['original_name']} sha256={f['sha256']} (app)")
    return serve_upload(f["stored_name"], f["mime"], f["original_name"], download)


@app.route("/api/v1/verificar", methods=["POST"])
@api_auth
def api_verify():
    if not has_feature("verificar"):
        return api_error("A verificação não está liberada no seu plano.", 403, code="recurso_bloqueado")
    try:
        name, digest = chunks.hash_and_discard(str(body().get("upload_id", "")))
    except chunks.UploadError as e:
        return api_error(str(e))
    rows = db().execute("SELECT f.id, f.original_name, f.uploaded_at, e.id AS evidence_id, e.title, e.occurred_at, "
                        "e.process_id, p.title AS process_title FROM files f JOIN evidences e ON e.id = f.evidence_id "
                        "JOIN processes p ON p.id = e.process_id WHERE f.sha256=? AND p.tenant_id=?",
                        (digest, g.tenant["id"])).fetchall()
    return jsonify(name=name, sha256=digest, matches=[dict(r) for r in rows])
