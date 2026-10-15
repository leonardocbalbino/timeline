"""Linha do Tempo de Provas - sistema multi-cliente para organizar prints, áudios e vídeos
em ordem cronológica por processo, com hash SHA-256 de cada arquivo e registro de auditoria."""
import csv
import hashlib
import io
import os
import re
import secrets
import tempfile
import time
import zipfile

from flask import (abort, flash, g, redirect, render_template, request,
                   send_file, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

from core import (DATA, UPLOADS, app, audit, client_ip, db, effective_plan, feature_required,
                  fmt_dt, guess_mime, has_feature, human_size, init_db, kind_for, login_required,
                  now, parse_dt, password_fingerprint, plan_cfg, plans, process_count, quota_left,
                  serve_upload, setting, slug, storage_used, store_upload, tenant_required, today,
                  unlink_upload)
import pix

# ---------------------------------------------------------------- login
_fails = {}


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        ip = client_ip()
        fails = [t for t in _fails.get(ip, []) if time.time() - t < 900]
        if len(fails) >= 8:
            flash("Muitas tentativas. Aguarde 15 minutos.", "erro")
            return render_template("login.html"), 429
        email = request.form.get("email", "").strip().lower()
        pwd = request.form.get("senha", "")
        u = db().execute("SELECT u.*, t.active AS t_active FROM users u "
                         "LEFT JOIN tenants t ON t.id = u.tenant_id WHERE u.email=?",
                         (email,)).fetchone()
        if u and u["active"] and check_password_hash(u["password_hash"], pwd):
            if u["role"] != "admin" and not u["t_active"]:
                flash("Sua conta está desativada. Fale com o administrador.", "erro")
                return render_template("login.html"), 403
            _fails.pop(ip, None)
            start_session(u)
            audit("login", tenant_id=u["tenant_id"])
            nxt = request.args.get("next", "")
            if nxt.startswith("/") and not nxt.startswith("//"):
                return redirect(nxt)
            return redirect(url_for("index"))
        fails.append(time.time())
        _fails[ip] = fails
        time.sleep(1)
        flash("E-mail ou senha incorretos.", "erro")
    return render_template("login.html", signup_open=signup_open())


def start_session(u):
    session.clear()
    session.permanent = True
    session["uid"] = u["id"]
    session["pwv"] = password_fingerprint(u)
    db().execute("UPDATE users SET last_login=? WHERE id=?", (now(), u["id"]))
    db().commit()
    g.user = u


@app.route("/sair")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------------------------------------------------------------- página inicial e autocadastro
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_signups = {}


def signup_open():
    return setting("autocadastro") == "1"


def landing():
    return render_template("landing.html", plans=plans(), price=_pro_price_cents(),
                           days=_pro_days(), signup_open=signup_open(),
                           contato=setting("contato_email"), now_year=today()[:4])


@app.route("/cadastro", methods=["GET", "POST"])
def signup():
    if g.user:
        return redirect(url_for("index"))
    if not signup_open():
        flash("O cadastro está fechado no momento. Fale com a gente para criar sua conta.", "erro")
        return redirect(url_for("index"))
    form = {"nome": "", "email": ""}
    if request.method == "POST":
        form = {"nome": request.form.get("nome", "").strip()[:200],
                "email": request.form.get("email", "").strip().lower()[:200]}
        senha = request.form.get("senha", "")
        ip = client_ip()
        recentes = [t for t in _signups.get(ip, []) if time.time() - t < 3600]
        erro = None
        if request.form.get("site"):  # campo isca: só robôs preenchem
            abort(400)
        if len(recentes) >= 5:
            erro = "Muitos cadastros a partir desta conexão. Tente novamente mais tarde."
        elif not form["nome"]:
            erro = "Informe seu nome."
        elif not EMAIL_RE.match(form["email"]):
            erro = "Informe um e-mail válido."
        elif len(senha) < 8:
            erro = "A senha precisa ter pelo menos 8 caracteres."
        elif senha != request.form.get("confirma", ""):
            erro = "A confirmação não confere com a senha."
        elif not request.form.get("termos"):
            erro = "É preciso aceitar as condições de uso."
        elif db().execute("SELECT 1 FROM users WHERE email=?", (form["email"],)).fetchone():
            erro = "Já existe uma conta com esse e-mail. Entre ou peça uma nova senha ao suporte."
        if erro:
            flash(erro, "erro")
            return render_template("signup.html", form=form), 400
        tid = db().execute("INSERT INTO tenants(name, plan, notes, created_at) VALUES (?, 'free', ?, ?)",
                           (form["nome"], "Autocadastro pela página inicial.", now())).lastrowid
        uid = db().execute("INSERT INTO users(tenant_id, email, name, password_hash, role, created_at) "
                           "VALUES (?,?,?,?, 'cliente', ?)",
                           (tid, form["email"], form["nome"], generate_password_hash(senha), now())).lastrowid
        db().commit()
        recentes.append(time.time())
        _signups[ip] = recentes
        start_session(db().execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone())
        g.tenant = db().execute("SELECT * FROM tenants WHERE id=?", (tid,)).fetchone()
        audit("autocadastro", f"#{tid} {form['nome']} {form['email']}")
        flash("Conta criada! Comece criando o seu primeiro processo.", "ok")
        return redirect(url_for("index"))
    return render_template("signup.html", form=form)


@app.route("/conta", methods=["GET", "POST"])
@login_required
def account():
    if request.method == "POST":
        atual = request.form.get("atual", "")
        nova = request.form.get("nova", "")
        if not check_password_hash(g.user["password_hash"], atual):
            flash("Senha atual incorreta.", "erro")
        elif len(nova) < 8:
            flash("A nova senha precisa ter pelo menos 8 caracteres.", "erro")
        elif nova != request.form.get("confirma", ""):
            flash("A confirmação não confere com a nova senha.", "erro")
        else:
            h = generate_password_hash(nova)
            db().execute("UPDATE users SET password_hash=? WHERE id=?", (h, g.user["id"]))
            db().commit()
            session["pwv"] = h[-16:]
            audit("trocar_senha", tenant_id=g.user["tenant_id"])
            flash("Senha alterada.", "ok")
            return redirect(url_for("index"))
    return render_template("account.html")


# ---------------------------------------------------------------- processos
@app.route("/")
def index():
    if not g.user:
        return landing()
    if g.user["role"] == "admin" and not g.impersonating:
        return redirect(url_for("admin_home"))
    tid = g.tenant["id"]
    procs = db().execute("""
        SELECT p.*,
               (SELECT COUNT(*) FROM evidences e WHERE e.process_id = p.id) AS n,
               (SELECT MIN(occurred_at) FROM evidences e WHERE e.process_id = p.id) AS a,
               (SELECT MAX(occurred_at) FROM evidences e WHERE e.process_id = p.id) AS b,
               (SELECT COALESCE(SUM(f.size), 0) FROM files f JOIN evidences e ON e.id = f.evidence_id
                 WHERE e.process_id = p.id) AS bytes
        FROM processes p WHERE p.tenant_id=? ORDER BY p.updated_at DESC""", (tid,)).fetchall()
    cfg = plan_cfg()
    return render_template("processes.html", procs=procs, cfg=cfg,
                           used=storage_used(tid), can_create=_can_create_process())


def _can_create_process():
    limit = int(plan_cfg()["max_processos"] or 0)
    return not limit or process_count(g.tenant["id"]) < limit


def get_process(pid):
    p = db().execute("SELECT * FROM processes WHERE id=? AND tenant_id=?",
                     (pid, g.tenant["id"])).fetchone()
    if not p:
        abort(404)
    return p


def read_process_form():
    return {"title": request.form.get("titulo", "").strip()[:200],
            "number": request.form.get("numero", "").strip()[:80],
            "description": request.form.get("descricao", "").strip()[:4000]}


@app.route("/processos/novo", methods=["GET", "POST"])
@tenant_required
def process_new():
    if not _can_create_process():
        flash("Seu plano atingiu o limite de processos. Assine o Pro para criar mais.", "erro")
        return redirect(url_for("plan"))
    if request.method == "POST":
        p = read_process_form()
        if not p["title"]:
            flash("Informe um nome para o processo.", "erro")
            return render_template("process_form.html", p=p)
        cur = db().execute("INSERT INTO processes(tenant_id, title, number, description, created_at, "
                           "updated_at) VALUES (?,?,?,?,?,?)",
                           (g.tenant["id"], p["title"], p["number"], p["description"], now(), now()))
        db().commit()
        audit("criar_processo", f"#{cur.lastrowid} {p['title']} {p['number']}")
        flash("Processo criado. Agora adicione as provas à linha do tempo.", "ok")
        return redirect(url_for("timeline", pid=cur.lastrowid))
    return render_template("process_form.html", p={})


@app.route("/processos/<int:pid>/editar", methods=["GET", "POST"])
@tenant_required
def process_edit(pid):
    proc = get_process(pid)
    if request.method == "POST":
        p = read_process_form()
        db().execute("UPDATE processes SET title=?, number=?, description=?, updated_at=? WHERE id=?",
                     (p["title"] or proc["title"], p["number"], p["description"], now(), pid))
        db().commit()
        audit("editar_processo", f"#{pid} {p}")
        flash("Processo atualizado.", "ok")
        return redirect(url_for("timeline", pid=pid))
    return render_template("process_form.html", p=proc, editing=True)


@app.route("/processos/<int:pid>/excluir", methods=["POST"])
@tenant_required
def process_delete(pid):
    proc = get_process(pid)
    if request.form.get("confirmar", "").strip() != proc["title"]:
        flash("Para excluir, digite o nome do processo exatamente como aparece.", "erro")
        return redirect(url_for("process_edit", pid=pid))
    files = db().execute("SELECT f.* FROM files f JOIN evidences e ON e.id = f.evidence_id "
                         "WHERE e.process_id=?", (pid,)).fetchall()
    db().execute("DELETE FROM processes WHERE id=?", (pid,))
    db().commit()
    for f in files:
        unlink_upload(f["stored_name"])
    audit("excluir_processo", f"#{pid} {proc['title']} | {len(files)} arquivo(s): " +
          "; ".join(f"{f['original_name']} sha256={f['sha256']}" for f in files))
    flash("Processo excluído.", "ok")
    return redirect(url_for("index"))


@app.route("/processos/<int:pid>/compartilhar", methods=["POST"])
@tenant_required
@feature_required("compartilhar")
def process_share(pid):
    get_process(pid)
    if request.form.get("acao") == "revogar":
        db().execute("UPDATE processes SET share_token=NULL WHERE id=?", (pid,))
        audit("revogar_link", f"#{pid}")
        flash("Link de acesso revogado. Quem tinha o link não consegue mais abrir.", "ok")
    else:
        db().execute("UPDATE processes SET share_token=? WHERE id=?", (secrets.token_urlsafe(24), pid))
        audit("gerar_link", f"#{pid}")
        flash("Novo link somente leitura gerado. O link anterior, se existia, deixou de funcionar.", "ok")
    db().commit()
    return redirect(url_for("process_edit", pid=pid) + "#compartilhar")


# ---------------------------------------------------------------- linha do tempo
def load_evidences(process_id, filters):
    sql = "SELECT * FROM evidences WHERE process_id=?"
    args = [process_id]
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


def view_mode():
    """Vertical é o padrão; a escolha do usuário fica guardada na sessão."""
    modo = request.args.get("modo")
    if modo in ("vertical", "horizontal"):
        session["modo"] = modo
    modo = session.get("modo", "vertical")
    if modo == "horizontal" and not has_feature("timeline_horizontal"):
        modo = "vertical"
    return modo


def render_timeline(proc, share=False):
    f = current_filters()
    evs = load_evidences(proc["id"], f)
    stats = db().execute("SELECT COUNT(*) n, MIN(occurred_at) a, MAX(occurred_at) b "
                         "FROM evidences WHERE process_id=?", (proc["id"],)).fetchone()
    kinds = dict(db().execute("SELECT f.kind, COUNT(*) FROM files f JOIN evidences e "
                              "ON e.id = f.evidence_id WHERE e.process_id=? GROUP BY f.kind",
                              (proc["id"],)).fetchall())
    return render_template("timeline.html", proc=proc, days=group_by_day(evs), total=len(evs),
                           stats=stats, kinds=kinds, f=f, modo=view_mode(), share=share)


@app.route("/processos/<int:pid>")
@tenant_required
def timeline(pid):
    return render_timeline(get_process(pid))


@app.route("/processos/<int:pid>/relatorio")
@tenant_required
@feature_required("relatorio")
def report(pid):
    proc = get_process(pid)
    return _render_report(proc)


def _render_report(proc):
    f = current_filters()
    evs = load_evidences(proc["id"], f)
    audit("relatorio", f"#{proc['id']} " + str({k: v for k, v in f.items() if v}),
          tenant_id=proc["tenant_id"])
    return render_template("report.html", proc=proc, days=group_by_day(evs), total=len(evs),
                           generated=fmt_dt(now()), f=f)


# ---------------------------------------------------------------- provas
def save_uploads(evidence_id, uploads):
    saved = []
    pos = db().execute("SELECT COALESCE(MAX(position), -1) + 1 FROM files WHERE evidence_id=?",
                       (evidence_id,)).fetchone()[0]
    for up in uploads:
        if not up or not up.filename:
            continue
        stored, original, mime, size, digest = store_upload(up)
        db().execute("INSERT INTO files(evidence_id, stored_name, original_name, mime, kind, "
                     "size, sha256, uploaded_at, position) VALUES (?,?,?,?,?,?,?,?,?)",
                     (evidence_id, stored, original, mime, kind_for(mime), size, digest,
                      now(), pos))
        pos += 1
        saved.append(f"{original} sha256={digest}")
    return saved


def quota_ok():
    left = quota_left()
    if left is None or not request.files:
        return True
    if (request.content_length or 0) > left:
        flash(f"Espaço insuficiente no seu plano (restam {human_size(max(left, 0))}). "
              "Remova arquivos ou assine o Pro.", "erro")
        return False
    return True


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


def touch_process(pid):
    db().execute("UPDATE processes SET updated_at=? WHERE id=?", (now(), pid))


@app.route("/processos/<int:pid>/provas/nova", methods=["GET", "POST"])
@tenant_required
def new(pid):
    proc = get_process(pid)
    if request.method == "POST":
        if not quota_ok():
            return redirect(url_for("new", pid=pid))
        try:
            ev = read_form()
        except ValueError:
            flash("Data ou hora inválida.", "erro")
            return render_template("form.html", proc=proc, ev=request.form, files=[]), 400
        if not ev["title"]:
            flash("Informe um título.", "erro")
            return render_template("form.html", proc=proc, ev=request.form, files=[]), 400
        cur = db().execute("INSERT INTO evidences(process_id, occurred_at, title, description, source, "
                           "people, important, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
                           (pid, ev["occurred_at"], ev["title"], ev["description"], ev["source"],
                            ev["people"], ev["important"], now(), now()))
        eid = cur.lastrowid
        saved = save_uploads(eid, request.files.getlist("arquivos"))
        touch_process(pid)
        db().commit()
        audit("criar", f"processo #{pid} prova #{eid} {ev['occurred_at']} {ev['title']} | " + "; ".join(saved))
        flash("Prova adicionada à linha do tempo.", "ok")
        if request.form.get("continuar"):
            return redirect(url_for("new", pid=pid, data=ev["occurred_at"][:10]))
        return redirect(url_for("timeline", pid=pid) + f"#e{eid}")
    return render_template("form.html", proc=proc, ev={"data": request.args.get("data", "")}, files=[])


def get_ev(pid, eid):
    ev = db().execute("SELECT * FROM evidences WHERE id=? AND process_id=?", (eid, pid)).fetchone()
    if not ev:
        abort(404)
    return ev


@app.route("/processos/<int:pid>/provas/<int:eid>/editar", methods=["GET", "POST"])
@tenant_required
def edit(pid, eid):
    proc = get_process(pid)
    ev = get_ev(pid, eid)
    files = db().execute("SELECT * FROM files WHERE evidence_id=? ORDER BY position, id",
                         (eid,)).fetchall()
    if request.method == "POST":
        if not quota_ok():
            return redirect(url_for("edit", pid=pid, eid=eid))
        try:
            new_ev = read_form()
        except ValueError:
            flash("Data ou hora inválida.", "erro")
            return redirect(url_for("edit", pid=pid, eid=eid))
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
                unlink_upload(f["stored_name"])
                removed.append(f"{f['original_name']} sha256={f['sha256']}")
        saved = save_uploads(eid, request.files.getlist("arquivos"))
        touch_process(pid)
        db().commit()
        changes = {k: (ev[k], v) for k, v in new_ev.items() if str(ev[k]) != str(v)}
        audit("editar", f"processo #{pid} prova #{eid} alterações={changes} "
                        f"adicionados={saved} removidos={removed}")
        flash("Alterações salvas.", "ok")
        return redirect(url_for("timeline", pid=pid) + f"#e{eid}")
    d = dict(ev)
    d["data"], d["hora"] = ev["occurred_at"][:10], ev["occurred_at"][11:19]
    return render_template("form.html", proc=proc, ev=d, files=files, editing=True)


@app.route("/processos/<int:pid>/provas/<int:eid>/excluir", methods=["POST"])
@tenant_required
def delete(pid, eid):
    get_process(pid)
    ev = get_ev(pid, eid)
    files = db().execute("SELECT * FROM files WHERE evidence_id=?", (eid,)).fetchall()
    db().execute("DELETE FROM evidences WHERE id=?", (eid,))
    touch_process(pid)
    db().commit()
    for f in files:
        unlink_upload(f["stored_name"])
    audit("excluir", f"processo #{pid} prova #{eid} {ev['occurred_at']} {ev['title']} | " +
          "; ".join(f"{f['original_name']} sha256={f['sha256']}" for f in files))
    flash("Prova excluída.", "ok")
    return redirect(url_for("timeline", pid=pid))


# ---------------------------------------------------------------- arquivos
@app.route("/arquivo/<int:fid>")
@tenant_required
def file(fid):
    f = db().execute("SELECT f.* FROM files f JOIN evidences e ON e.id = f.evidence_id "
                     "JOIN processes p ON p.id = e.process_id WHERE f.id=? AND p.tenant_id=?",
                     (fid, g.tenant["id"])).fetchone()
    if not f:
        abort(404)
    download = request.args.get("baixar") == "1"
    if download:
        audit("baixar", f"{f['original_name']} sha256={f['sha256']}")
    return serve_upload(f["stored_name"], f["mime"], f["original_name"], download)


@app.route("/verificar", methods=["GET", "POST"])
@tenant_required
@feature_required("verificar")
def verify():
    """Confere se um arquivo é idêntico (mesmo SHA-256) a algum arquivo registrado na conta."""
    result = None
    if request.method == "POST":
        up = request.files.get("arquivo")
        if up and up.filename:
            h = hashlib.sha256()
            for chunk in iter(lambda: up.stream.read(1024 * 1024), b""):
                h.update(chunk)
            digest = h.hexdigest()
            rows = db().execute("SELECT f.*, e.title, e.occurred_at, e.process_id, p.title AS proc_title "
                                "FROM files f JOIN evidences e ON e.id = f.evidence_id "
                                "JOIN processes p ON p.id = e.process_id "
                                "WHERE f.sha256=? AND p.tenant_id=?",
                                (digest, g.tenant["id"])).fetchall()
            result = {"name": up.filename, "sha256": digest, "matches": rows}
    return render_template("verify.html", result=result)


def build_export(proc):
    """Gera um ZIP com todos os arquivos, organizados por data, e um manifesto CSV."""
    evs = load_evidences(proc["id"], current_filters())
    audit("exportar", f"processo #{proc['id']} {len(evs)} provas", tenant_id=proc["tenant_id"])
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
                   f"Processo: {proc['title']} {proc['number']}\n"
                   "Pacote exportado da Linha do Tempo de Provas em " + fmt_dt(now()) + ".\n"
                   "O arquivo manifesto.csv lista cada prova em ordem cronológica e o hash\n"
                   "SHA-256 de cada arquivo, calculado no momento do envio ao sistema.\n"
                   "Para conferir a integridade de um arquivo:\n"
                   "  Windows:  certutil -hashfile <arquivo> SHA256\n"
                   "  Linux/Mac: sha256sum <arquivo>  /  shasum -a 256 <arquivo>\n")

    resp = send_file(tmp.name, mimetype="application/zip", as_attachment=True,
                     download_name=f"provas_{slug(proc['title'])}_{today()}.zip")
    resp.call_on_close(lambda: os.path.exists(tmp.name) and os.remove(tmp.name))
    return resp


@app.route("/processos/<int:pid>/exportar")
@tenant_required
@feature_required("exportar")
def export(pid):
    return build_export(get_process(pid))


@app.route("/auditoria")
@tenant_required
@feature_required("auditoria")
def audit_log():
    rows = db().execute("SELECT * FROM audit WHERE tenant_id=? ORDER BY id DESC LIMIT 1000",
                        (g.tenant["id"],)).fetchall()
    return render_template("audit.html", rows=rows)


# ---------------------------------------------------------------- link somente leitura
def share_context(token):
    p = db().execute("SELECT * FROM processes WHERE share_token=?", (token,)).fetchone()
    if not p:
        abort(404)
    t = db().execute("SELECT * FROM tenants WHERE id=?", (p["tenant_id"],)).fetchone()
    if not t or not t["active"] or not has_feature("compartilhar", t):
        abort(404)
    g.share_token = token
    g.tenant = t
    return p


@app.route("/p/<token>")
def share_view(token):
    proc = share_context(token)
    if not session.get(f"visto_{proc['id']}"):
        session[f"visto_{proc['id']}"] = 1
        audit("abrir_link", f"processo #{proc['id']}")
    return render_timeline(proc, share=True)


@app.route("/p/<token>/relatorio")
def share_report(token):
    proc = share_context(token)
    if not has_feature("relatorio"):
        abort(404)
    return _render_report(proc)


@app.route("/p/<token>/exportar")
def share_export(token):
    proc = share_context(token)
    if not has_feature("exportar"):
        abort(404)
    return build_export(proc)


@app.route("/p/<token>/arquivo/<int:fid>")
def share_file(token, fid):
    proc = share_context(token)
    f = db().execute("SELECT f.* FROM files f JOIN evidences e ON e.id = f.evidence_id "
                     "WHERE f.id=? AND e.process_id=?", (fid, proc["id"])).fetchone()
    if not f:
        abort(404)
    download = request.args.get("baixar") == "1"
    if download:
        audit("baixar", f"{f['original_name']} sha256={f['sha256']}")
    return serve_upload(f["stored_name"], f["mime"], f["original_name"], download)


# ---------------------------------------------------------------- plano e pagamento Pix
@app.route("/plano")
@tenant_required
def plan():
    pays = db().execute("SELECT * FROM payments WHERE tenant_id=? ORDER BY id DESC LIMIT 20",
                        (g.tenant["id"],)).fetchall()
    return render_template("plan.html", plans=plans(), current=effective_plan(g.tenant),
                           price=_pro_price_cents(), days=_pro_days(), pays=pays,
                           pix_ok=bool(setting("pix_chave")), used=storage_used(g.tenant["id"]),
                           nproc=process_count(g.tenant["id"]))


def _pro_price_cents():
    try:
        return round(float(setting("pro_preco").replace(",", ".")) * 100)
    except ValueError:
        return 0


def _pro_days():
    try:
        return max(1, int(setting("pro_dias")))
    except ValueError:
        return 30


PERIODOS = (1, 3, 6, 12)


@app.route("/plano/pix", methods=["POST"])
@tenant_required
def plan_pix():
    if not setting("pix_chave") or not _pro_price_cents():
        flash("Pagamento via Pix ainda não está configurado. Fale com o administrador.", "erro")
        return redirect(url_for("plan"))
    try:
        periodos = int(request.form.get("periodos", "1"))
    except ValueError:
        periodos = 1
    if periodos not in PERIODOS:
        periodos = 1
    txid = f"TL{g.tenant['id']}X{secrets.token_hex(8).upper()}"[:25]
    cur = db().execute("INSERT INTO payments(tenant_id, txid, amount_cents, days, created_at) "
                       "VALUES (?,?,?,?,?)",
                       (g.tenant["id"], txid, _pro_price_cents() * periodos,
                        _pro_days() * periodos, now()))
    db().commit()
    audit("gerar_pix", f"pagamento #{cur.lastrowid} txid={txid}")
    return redirect(url_for("payment", pay_id=cur.lastrowid))


def get_payment(pay_id):
    p = db().execute("SELECT * FROM payments WHERE id=? AND tenant_id=?",
                     (pay_id, g.tenant["id"])).fetchone()
    if not p:
        abort(404)
    return p


@app.route("/plano/pagamento/<int:pay_id>", methods=["GET", "POST"])
@tenant_required
def payment(pay_id):
    pay = get_payment(pay_id)
    if request.method == "POST" and pay["status"] in ("pendente", "informado"):
        if request.form.get("acao") == "cancelar":
            db().execute("UPDATE payments SET status='cancelado', decided_at=? WHERE id=?",
                         (now(), pay_id))
            db().commit()
            audit("cancelar_pix", f"pagamento #{pay_id}")
            flash("Cobrança cancelada.", "ok")
            return redirect(url_for("plan"))
        up = request.files.get("comprovante")
        stored = name = None
        if up and up.filename:
            stored, name, _mime, _size, _digest = store_upload(up)
            if pay["receipt_stored"]:
                unlink_upload(pay["receipt_stored"])
        db().execute("UPDATE payments SET status='informado', informed_at=?, "
                     "receipt_stored=COALESCE(?, receipt_stored), receipt_name=COALESCE(?, receipt_name), "
                     "note=? WHERE id=?",
                     (now(), stored, name, request.form.get("obs", "").strip()[:500], pay_id))
        db().commit()
        audit("informar_pix", f"pagamento #{pay_id} comprovante={name or '-'}")
        flash("Pagamento informado. Assim que o administrador confirmar, o plano Pro é liberado.", "ok")
        return redirect(url_for("payment", pay_id=pay_id))
    code = pix.brcode(setting("pix_chave"), setting("pix_nome"), setting("pix_cidade"),
                      pay["amount_cents"] / 100, pay["txid"], "Linha do Tempo Pro")
    return render_template("payment.html", pay=pay, code=code, qr=pix.qr_svg_data_uri(code),
                           pix_nome=setting("pix_nome"))


@app.route("/plano/pagamento/<int:pay_id>/comprovante")
@tenant_required
def payment_receipt(pay_id):
    pay = get_payment(pay_id)
    if not pay["receipt_stored"]:
        abort(404)
    return serve_upload(pay["receipt_stored"], guess_mime(pay["receipt_name"], None),
                        pay["receipt_name"], False)


@app.errorhandler(413)
def too_large(_e):
    return "Arquivo grande demais (limite 4 GB por envio).", 413


import admin  # noqa: E402,F401  (registra as rotas do painel do administrador)

init_db()

if __name__ == "__main__":
    app.run(debug=True, port=8410)
