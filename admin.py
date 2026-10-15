"""Painel do administrador: clientes, planos (Free/Pro), configurações do Pix e pagamentos."""
import json

from flask import abort, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import generate_password_hash

from core import (FEATURES, PLAN_LABELS, add_days, admin_required, app, audit, db,
                  effective_plan, guess_mime, new_password, now, plans, serve_upload, set_setting,
                  setting, storage_used, today, unlink_upload)
import pix


def get_tenant(tid):
    t = db().execute("SELECT * FROM tenants WHERE id=?", (tid,)).fetchone()
    if not t:
        abort(404)
    return t


@app.route("/admin")
@admin_required
def admin_home():
    q = request.args.get("q", "").strip()
    sql = """
        SELECT t.*,
               (SELECT email FROM users u WHERE u.tenant_id = t.id ORDER BY u.id LIMIT 1) AS email,
               (SELECT last_login FROM users u WHERE u.tenant_id = t.id ORDER BY u.id LIMIT 1) AS last_login,
               (SELECT COUNT(*) FROM processes p WHERE p.tenant_id = t.id) AS nproc,
               (SELECT COALESCE(SUM(f.size), 0) FROM files f JOIN evidences e ON e.id = f.evidence_id
                  JOIN processes p ON p.id = e.process_id WHERE p.tenant_id = t.id) AS bytes
        FROM tenants t"""
    args = []
    if q:
        sql += (" WHERE t.name LIKE ? OR t.document LIKE ? OR EXISTS (SELECT 1 FROM users u "
                "WHERE u.tenant_id = t.id AND u.email LIKE ?)")
        args = [f"%{q}%"] * 3
    tenants = db().execute(sql + " ORDER BY t.name COLLATE NOCASE", args).fetchall()
    pending = db().execute("SELECT COUNT(*) FROM payments WHERE status='informado'").fetchone()[0]
    counts = {"total": len(tenants), "pro": sum(effective_plan(t) == "pro" for t in tenants)}
    return render_template("admin/dashboard.html", tenants=tenants, pending=pending,
                           counts=counts, q=q, pix_ok=bool(setting("pix_chave")))


def read_tenant_form():
    plan = request.form.get("plano", "free")
    return {
        "name": request.form.get("nome", "").strip()[:200],
        "document": request.form.get("documento", "").strip()[:30],
        "phone": request.form.get("telefone", "").strip()[:30],
        "plan": plan if plan in PLAN_LABELS else "free",
        "pro_until": request.form.get("pro_ate", "").strip() or None,
        "active": 1 if request.form.get("ativo") else 0,
        "notes": request.form.get("obs", "").strip()[:2000],
        "email": request.form.get("email", "").strip().lower()[:200],
    }


def email_taken(email, except_tenant=None):
    row = db().execute("SELECT tenant_id FROM users WHERE email=?", (email,)).fetchone()
    return row is not None and (except_tenant is None or row["tenant_id"] != except_tenant)


@app.route("/admin/clientes/novo", methods=["GET", "POST"])
@admin_required
def admin_client_new():
    if request.method == "POST":
        t = read_tenant_form()
        if not t["name"] or "@" not in t["email"]:
            flash("Informe o nome e um e-mail válido para o login do cliente.", "erro")
            return render_template("admin/client_form.html", t=t)
        if email_taken(t["email"]):
            flash("Já existe um usuário com esse e-mail.", "erro")
            return render_template("admin/client_form.html", t=t)
        senha = request.form.get("senha", "").strip() or new_password()
        cur = db().execute("INSERT INTO tenants(name, document, phone, plan, pro_until, active, notes, "
                           "created_at) VALUES (?,?,?,?,?,?,?,?)",
                           (t["name"], t["document"], t["phone"], t["plan"], t["pro_until"],
                            t["active"], t["notes"], now()))
        tid = cur.lastrowid
        db().execute("INSERT INTO users(tenant_id, email, name, password_hash, role, created_at) "
                     "VALUES (?,?,?,?, 'cliente', ?)",
                     (tid, t["email"], t["name"], generate_password_hash(senha), now()))
        db().commit()
        audit("admin_criar_cliente", f"#{tid} {t['name']} {t['email']} plano={t['plan']}", tenant_id=tid)
        session["senha_gerada"] = {"tid": tid, "email": t["email"], "senha": senha}
        return redirect(url_for("admin_client", tid=tid))
    return render_template("admin/client_form.html", t={"active": 1, "plan": "free"})


@app.route("/admin/clientes/<int:tid>", methods=["GET", "POST"])
@admin_required
def admin_client(tid):
    old = get_tenant(tid)
    user = db().execute("SELECT * FROM users WHERE tenant_id=? ORDER BY id LIMIT 1", (tid,)).fetchone()
    if request.method == "POST":
        t = read_tenant_form()
        if not t["name"]:
            t["name"] = old["name"]
        if t["email"] and user and t["email"] != user["email"]:
            if email_taken(t["email"], except_tenant=tid):
                flash("Já existe um usuário com esse e-mail.", "erro")
                return redirect(url_for("admin_client", tid=tid))
            db().execute("UPDATE users SET email=? WHERE id=?", (t["email"], user["id"]))
        db().execute("UPDATE tenants SET name=?, document=?, phone=?, plan=?, pro_until=?, active=?, "
                     "notes=? WHERE id=?",
                     (t["name"], t["document"], t["phone"], t["plan"], t["pro_until"], t["active"],
                      t["notes"], tid))
        db().commit()
        changes = {k: (old[k], t[k]) for k in ("name", "document", "phone", "plan", "pro_until", "active")
                   if str(old[k]) != str(t[k])}
        audit("admin_editar_cliente", f"#{tid} {changes}", tenant_id=tid)
        flash("Cliente atualizado.", "ok")
        return redirect(url_for("admin_client", tid=tid))
    senha = session.pop("senha_gerada", None)
    if senha and senha.get("tid") != tid:
        senha = None
    pays = db().execute("SELECT * FROM payments WHERE tenant_id=? ORDER BY id DESC LIMIT 20",
                        (tid,)).fetchall()
    procs = db().execute("SELECT p.*, (SELECT COUNT(*) FROM evidences e WHERE e.process_id = p.id) n "
                         "FROM processes p WHERE tenant_id=? ORDER BY updated_at DESC", (tid,)).fetchall()
    return render_template("admin/client_form.html", t=old, user=user, editing=True, senha=senha,
                           pays=pays, procs=procs, used=storage_used(tid))


@app.route("/admin/clientes/<int:tid>/senha", methods=["POST"])
@admin_required
def admin_client_password(tid):
    get_tenant(tid)
    user = db().execute("SELECT * FROM users WHERE tenant_id=? ORDER BY id LIMIT 1", (tid,)).fetchone()
    if not user:
        abort(404)
    senha = new_password()
    db().execute("UPDATE users SET password_hash=? WHERE id=?", (generate_password_hash(senha), user["id"]))
    db().commit()
    audit("admin_redefinir_senha", f"#{tid} {user['email']}", tenant_id=tid)
    session["senha_gerada"] = {"tid": tid, "email": user["email"], "senha": senha}
    return redirect(url_for("admin_client", tid=tid))


@app.route("/admin/clientes/<int:tid>/acessar", methods=["POST"])
@admin_required
def admin_client_enter(tid):
    t = get_tenant(tid)
    session["as_tenant"] = tid
    audit("admin_acessar_conta", f"#{tid} {t['name']}", tenant_id=tid)
    flash(f"Você está acessando a conta de {t['name']} como administrador.", "ok")
    return redirect(url_for("index"))


@app.route("/admin/sair-da-conta", methods=["POST"])
@admin_required
def admin_client_leave():
    tid = session.pop("as_tenant", None)
    return redirect(url_for("admin_client", tid=tid) if tid else url_for("admin_home"))


@app.route("/admin/clientes/<int:tid>/excluir", methods=["POST"])
@admin_required
def admin_client_delete(tid):
    t = get_tenant(tid)
    if request.form.get("confirmar", "").strip() != t["name"]:
        flash("Para excluir, digite o nome do cliente exatamente como aparece.", "erro")
        return redirect(url_for("admin_client", tid=tid))
    stored = [r[0] for r in db().execute(
        "SELECT f.stored_name FROM files f JOIN evidences e ON e.id = f.evidence_id "
        "JOIN processes p ON p.id = e.process_id WHERE p.tenant_id=?", (tid,))]
    stored += [r[0] for r in db().execute(
        "SELECT receipt_stored FROM payments WHERE tenant_id=? AND receipt_stored IS NOT NULL", (tid,))]
    db().execute("DELETE FROM tenants WHERE id=?", (tid,))
    db().commit()
    for s in stored:
        unlink_upload(s)
    if session.get("as_tenant") == tid:
        session.pop("as_tenant")
    audit("admin_excluir_cliente", f"#{tid} {t['name']} | {len(stored)} arquivo(s) apagado(s)", tenant_id=tid)
    flash("Cliente e todos os seus dados foram excluídos.", "ok")
    return redirect(url_for("admin_home"))


# ---------------------------------------------------------------- planos e Pix
@app.route("/admin/planos", methods=["GET", "POST"])
@admin_required
def admin_plans():
    if request.method == "POST":
        cfg = {}
        for plan in PLAN_LABELS:
            def num(field):
                try:
                    return max(0, int(request.form.get(f"{plan}_{field}", "0") or 0))
                except ValueError:
                    return 0
            cfg[plan] = {
                "features": [k for k, _ in FEATURES if request.form.get(f"{plan}_{k}")],
                "max_processos": num("max_processos"),
                "max_storage_mb": num("max_storage_mb"),
            }
        set_setting("planos", json.dumps(cfg))
        for key in ("pix_chave", "pix_nome", "pix_cidade", "pro_preco", "pro_dias"):
            set_setting(key, request.form.get(key, "").strip())
        set_setting("autocadastro", "1" if request.form.get("autocadastro") else "0")
        set_setting("contato_email", request.form.get("contato_email", "").strip()[:200])
        if setting("pix_chave"):
            set_setting("pix_chave", pix.normalizar_chave(setting("pix_chave")))
        db().commit()
        audit("admin_planos", json.dumps(cfg, ensure_ascii=False))
        flash("Planos e pagamento salvos.", "ok")
        return redirect(url_for("admin_plans"))
    settings = {k: setting(k) for k in ("pix_chave", "pix_nome", "pix_cidade", "pro_preco", "pro_dias",
                                        "autocadastro", "contato_email")}
    return render_template("admin/plans.html", plans=plans(), s=settings)


@app.route("/admin/pagamentos")
@admin_required
def admin_payments():
    status = request.args.get("status", "informado")
    sql = ("SELECT p.*, t.name AS tenant_name, t.plan, t.pro_until FROM payments p "
           "JOIN tenants t ON t.id = p.tenant_id")
    args = []
    if status != "todos":
        sql += " WHERE p.status=?"
        args.append(status)
    pays = db().execute(sql + " ORDER BY p.id DESC LIMIT 500", args).fetchall()
    counts = dict(db().execute("SELECT status, COUNT(*) FROM payments GROUP BY status").fetchall())
    counts["todos"] = sum(counts.values())
    return render_template("admin/payments.html", pays=pays, status=status, counts=counts)


@app.route("/admin/pagamentos/<int:pay_id>/<acao>", methods=["POST"])
@admin_required
def admin_payment_decide(pay_id, acao):
    pay = db().execute("SELECT * FROM payments WHERE id=?", (pay_id,)).fetchone()
    if not pay or acao not in ("confirmar", "recusar"):
        abort(404)
    if pay["status"] not in ("pendente", "informado"):
        flash("Esse pagamento já foi decidido.", "erro")
        return redirect(request.referrer or url_for("admin_payments"))
    t = get_tenant(pay["tenant_id"])
    if acao == "confirmar":
        if t["plan"] == "pro" and not t["pro_until"]:
            until = None  # já é Pro sem vencimento
        else:
            base = t["pro_until"] if effective_plan(t) == "pro" and t["pro_until"] else today()
            until = add_days(base, pay["days"])
        db().execute("UPDATE tenants SET plan='pro', pro_until=? WHERE id=?", (until, t["id"]))
        status = "confirmado"
        msg = f"Pagamento confirmado. {t['name']} é Pro" + (f" até {until[8:]}/{until[5:7]}/{until[:4]}." if until else ".")
    else:
        status, msg = "recusado", "Pagamento recusado."
    db().execute("UPDATE payments SET status=?, decided_at=?, decided_by=? WHERE id=?",
                 (status, now(), g.user["email"], pay_id))
    db().commit()
    audit(f"admin_pix_{status}", f"pagamento #{pay_id} txid={pay['txid']} valor={pay['amount_cents']}",
          tenant_id=t["id"])
    flash(msg, "ok")
    return redirect(request.referrer or url_for("admin_payments"))


@app.route("/admin/pagamentos/<int:pay_id>/comprovante")
@admin_required
def admin_payment_receipt(pay_id):
    pay = db().execute("SELECT * FROM payments WHERE id=?", (pay_id,)).fetchone()
    if not pay or not pay["receipt_stored"]:
        abort(404)
    return serve_upload(pay["receipt_stored"], guess_mime(pay["receipt_name"], None),
                        pay["receipt_name"], False)


@app.route("/admin/auditoria")
@admin_required
def admin_audit():
    tid = request.args.get("cliente", type=int)
    sql = "SELECT a.*, t.name AS tenant_name FROM audit a LEFT JOIN tenants t ON t.id = a.tenant_id"
    args = []
    if tid:
        sql += " WHERE a.tenant_id=?"
        args.append(tid)
    rows = db().execute(sql + " ORDER BY a.id DESC LIMIT 1000", args).fetchall()
    tenants = db().execute("SELECT id, name FROM tenants ORDER BY name COLLATE NOCASE").fetchall()
    return render_template("audit.html", rows=rows, admin_view=True, tenants=tenants, tid=tid)
