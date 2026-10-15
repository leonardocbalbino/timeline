"""Painel do administrador: clientes, planos (Free/Pro), configurações do Pix e pagamentos."""
import json

from flask import abort, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import generate_password_hash

from core import (FEATURES, PLAN_LABELS, admin_required, grant_pro, app, audit, db,
                  effective_plan, guess_mime, new_password, now, plans, serve_upload, set_setting,
                  setting, storage_used, today, unlink_upload)
import asaas
import billing
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
    subs = db().execute("SELECT * FROM subscriptions WHERE tenant_id=? ORDER BY id DESC", (tid,)).fetchall()
    return render_template("admin/client_form.html", t=old, user=user, editing=True, senha=senha,
                           pays=pays, procs=procs, used=storage_used(tid), subs=subs,
                           gateway=billing.gateway(), billing_types=asaas.BILLING_TYPES,
                           doc_ok=billing.valid_cpf_cnpj(old["document"]), default_due=billing.add_days(today(), 3))


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
    for sub in db().execute("SELECT * FROM subscriptions WHERE tenant_id=? AND status='ativa'", (tid,)).fetchall():
        try:
            billing.cancel_subscription(sub, g.user["email"])
        except billing.BillingError as e:
            flash(f"Não excluí o cliente: a assinatura no Asaas não foi cancelada ({e}).", "erro")
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
        set_setting("gateway", "asaas" if request.form.get("gateway") == "asaas" else "manual")
        set_setting("contato_email", request.form.get("contato_email", "").strip()[:200])
        if setting("pix_chave"):
            set_setting("pix_chave", pix.normalizar_chave(setting("pix_chave")))
        db().commit()
        audit("admin_planos", json.dumps(cfg, ensure_ascii=False))
        flash("Planos e pagamento salvos.", "ok")
        return redirect(url_for("admin_plans"))
    settings = {k: setting(k) for k in ("pix_chave", "pix_nome", "pix_cidade", "pro_preco", "pro_dias",
                                        "autocadastro", "contato_email")}
    settings["gateway"] = setting("gateway")
    hooks = [e for e in db().execute("SELECT * FROM webhook_events ORDER BY received_at DESC LIMIT 8")]
    return render_template("admin/plans.html", plans=plans(), s=settings, asaas_ok=asaas.configured(),
                           asaas_env=asaas.environment_label(), hook_token_ok=len(asaas.WEBHOOK_TOKEN) >= 32,
                           hook_url=url_for("asaas_webhook", _external=True), hooks=hooks,
                           admin_email=g.user["email"] if "@" in g.user["email"] else setting("contato_email"))


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
    if pay["provider"] != "manual":
        flash("Cobranças do Asaas são confirmadas automaticamente. Use “Atualizar”.", "erro")
        return redirect(request.referrer or url_for("admin_payments"))
    if pay["status"] not in ("pendente", "informado"):
        flash("Esse pagamento já foi decidido.", "erro")
        return redirect(request.referrer or url_for("admin_payments"))
    t = get_tenant(pay["tenant_id"])
    if acao == "confirmar":
        until = grant_pro(t["id"], pay["days"])
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


# ---------------------------------------------------------------- Asaas
@app.route("/admin/asaas/testar", methods=["POST"])
@admin_required
def admin_asaas_test():
    try:
        b = asaas.balance()
        flash(f"Conexão com o Asaas OK ({asaas.environment_label()}). Saldo: R$ {b.get('balance', 0):.2f}"
              .replace(".", ","), "ok")
    except asaas.AsaasError as e:
        flash(f"Falha ao conectar no Asaas: {e}", "erro")
    return redirect(url_for("admin_plans") + "#gateway")


@app.route("/admin/asaas/webhook", methods=["POST"])
@admin_required
def admin_asaas_webhook():
    email = request.form.get("email", "").strip()
    url = url_for("asaas_webhook", _external=True)
    if "@" not in email:
        flash("Informe um e-mail para o Asaas avisar se o webhook falhar.", "erro")
        return redirect(url_for("admin_plans") + "#gateway")
    if len(asaas.WEBHOOK_TOKEN) < 32:
        flash("Defina ASAAS_WEBHOOK_TOKEN (32 caracteres ou mais) no .env do servidor.", "erro")
        return redirect(url_for("admin_plans") + "#gateway")
    try:
        existing = next((w for w in asaas.list_webhooks() if w.get("url") == url), None)
        if existing:
            asaas.update_webhook(existing["id"], url, email, asaas.WEBHOOK_TOKEN)
        else:
            asaas.create_webhook(url, email, asaas.WEBHOOK_TOKEN)
        audit("admin_asaas_webhook", url)
        flash(f"Webhook {'atualizado' if existing else 'criado'} no Asaas: {url}", "ok")
    except asaas.AsaasError as e:
        flash(f"O Asaas recusou o webhook: {e}", "erro")
    return redirect(url_for("admin_plans") + "#gateway")


@app.route("/admin/clientes/<int:tid>/cobranca", methods=["POST"])
@admin_required
def admin_client_charge(tid):
    t = get_tenant(tid)
    if billing.gateway() != "asaas":
        flash("Ative o Asaas em Planos e Pix para gerar cobranças.", "erro")
        return redirect(url_for("admin_client", tid=tid))
    try:
        value = billing.parse_money_cents(request.form.get("valor", ""))
        days = max(0, int(request.form.get("dias", "0") or 0))
    except ValueError:
        flash("Valor ou dias de Pro inválidos.", "erro")
        return redirect(url_for("admin_client", tid=tid) + "#cobranca")
    desc = request.form.get("descricao", "").strip()[:500] or "Cobrança Íntegra"
    try:
        row = billing.create_charge(tid, value, days, "avulsa", desc, request.form.get("forma", "UNDEFINED"),
                                    request.form.get("vencimento") or None)
    except (billing.BillingError, asaas.AsaasError) as e:
        flash(str(e), "erro")
        return redirect(url_for("admin_client", tid=tid) + "#cobranca")
    audit("admin_cobranca_avulsa", f"pagamento #{row['id']} {row['external_id']} valor={value} dias={days} {desc}",
          tenant_id=tid)
    flash(f"Cobrança criada para {t['name']}. O Asaas envia a fatura ao cliente; o link também está na lista abaixo.",
          "ok")
    return redirect(url_for("admin_client", tid=tid) + "#pagamentos")


@app.route("/admin/assinaturas/<int:sid>/cancelar", methods=["POST"])
@admin_required
def admin_subscription_cancel(sid):
    sub = db().execute("SELECT * FROM subscriptions WHERE id=?", (sid,)).fetchone()
    if not sub:
        abort(404)
    if sub["status"] == "ativa":
        try:
            billing.cancel_subscription(sub, g.user["email"])
            flash("Assinatura cancelada no Asaas.", "ok")
        except billing.BillingError as e:
            flash(str(e), "erro")
    return redirect(url_for("admin_client", tid=sub["tenant_id"]))


@app.route("/admin/pagamentos/<int:pay_id>/sincronizar", methods=["POST"])
@admin_required
def admin_payment_sync(pay_id):
    pay = db().execute("SELECT * FROM payments WHERE id=?", (pay_id,)).fetchone()
    if not pay:
        abort(404)
    try:
        pay = billing.sync_payment(pay, force=True)
        flash(f"Status atualizado pelo Asaas: {pay['status']}.", "ok")
    except asaas.AsaasError as e:
        flash(f"Não foi possível consultar o Asaas: {e}", "erro")
    return redirect(request.referrer or url_for("admin_payments"))


@app.route("/admin/pagamentos/<int:pay_id>/cancelar", methods=["POST"])
@admin_required
def admin_payment_cancel(pay_id):
    pay = db().execute("SELECT * FROM payments WHERE id=?", (pay_id,)).fetchone()
    if not pay or pay["provider"] != "asaas":
        abort(404)
    if pay["status"] in ("pendente", "vencido"):
        try:
            billing.cancel_charge(pay, g.user["email"])
            flash("Cobrança cancelada no Asaas.", "ok")
        except billing.BillingError as e:
            flash(str(e), "erro")
    return redirect(request.referrer or url_for("admin_payments"))
