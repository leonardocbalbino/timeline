"""Cobranças pelo Asaas: assinaturas recorrentes, cobranças avulsas, sincronização de status e webhook.

Regra central: um pagamento só libera dias de Pro na transição para "confirmado" (uma única vez),
seja pelo webhook, pela sincronização manual ou pela consulta automática da tela de pagamento.
"""
import json
import re
import secrets
import sqlite3
from datetime import datetime

from flask import abort, g, jsonify, request

import asaas
from core import add_days, app, audit, db, grant_pro, now, revoke_pro, setting, today

PAID = {"RECEIVED", "CONFIRMED", "RECEIVED_IN_CASH", "DUNNING_RECEIVED"}
REVERSED = {"REFUNDED", "REFUND_REQUESTED", "REFUND_IN_PROGRESS", "CHARGEBACK_REQUESTED",
            "CHARGEBACK_DISPUTE", "AWAITING_CHARGEBACK_REVERSAL"}
SYNC_INTERVAL = 8  # segundos entre consultas ao Asaas para o mesmo pagamento


class BillingError(Exception):
    pass


def gateway():
    """'asaas' quando escolhido no admin e com chave configurada; senão o Pix manual."""
    return "asaas" if setting("gateway") == "asaas" and asaas.configured() else "manual"


def asaas_status(p):
    if p.get("deleted"):
        return "cancelado"
    s = p.get("status", "")
    if s in PAID:
        return "confirmado"
    if s == "OVERDUE":
        return "vencido"
    if s in REVERSED:
        return "estornado"
    return "pendente"


# ---------------------------------------------------------------- CPF / CNPJ
def only_digits(s):
    return re.sub(r"\D", "", s or "")


def valid_cpf_cnpj(doc):
    d = only_digits(doc)
    if len(d) == 11 and len(set(d)) > 1:
        for n in (9, 10):
            total = sum(int(d[i]) * (n + 1 - i) for i in range(n))
            if (total * 10 % 11) % 10 != int(d[n]):
                return False
        return True
    if len(d) == 14 and len(set(d)) > 1:
        for n in (12, 13):
            weights = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2][13 - n:]
            r = sum(int(d[i]) * weights[i] for i in range(n)) % 11
            if (0 if r < 2 else 11 - r) != int(d[n]):
                return False
        return True
    return False


# ---------------------------------------------------------------- cliente no Asaas
def ensure_customer(tenant_id):
    t = db().execute("SELECT * FROM tenants WHERE id=?", (tenant_id,)).fetchone()
    doc = only_digits(t["document"])
    if not valid_cpf_cnpj(doc):
        raise BillingError("Informe um CPF ou CNPJ válido para gerar cobranças.")
    if t["asaas_customer_id"]:
        return t["asaas_customer_id"]
    user = db().execute("SELECT email FROM users WHERE tenant_id=? ORDER BY id LIMIT 1", (tenant_id,)).fetchone()
    phone = only_digits(t["phone"])
    try:
        c = asaas.create_customer(t["name"], doc, email=user["email"] if user else "",
                                  mobile_phone=phone if len(phone) in (10, 11) else "",
                                  external_reference=f"integra:t{tenant_id}")
    except asaas.AsaasError as e:
        raise BillingError(f"Asaas recusou o cadastro do cliente: {e}") from None
    db().execute("UPDATE tenants SET asaas_customer_id=? WHERE id=?", (c["id"], tenant_id))
    db().commit()
    return c["id"]


# ---------------------------------------------------------------- registro local dos pagamentos
def upsert_payment(p, tenant_id, kind, days, subscription_id=None):
    """Grava/atualiza o pagamento do Asaas na tabela local e aplica a mudança de status."""
    row = db().execute("SELECT * FROM payments WHERE external_id=?", (p["id"],)).fetchone()
    if not row:
        db().execute(
            "INSERT OR IGNORE INTO payments(tenant_id, txid, amount_cents, days, status, created_at, provider, kind, "
            "external_id, subscription_id, billing_type, invoice_url, due_date, description) "
            "VALUES (?,?,?,?, 'pendente', ?, 'asaas', ?,?,?,?,?,?,?)",
            (tenant_id, p["id"], round(float(p.get("value", 0)) * 100), days, now(), kind, p["id"],
             subscription_id, p.get("billingType", "UNDEFINED"), p.get("invoiceUrl"), p.get("dueDate"),
             (p.get("description") or "")[:500]))
        row = db().execute("SELECT * FROM payments WHERE external_id=?", (p["id"],)).fetchone()
    db().execute("UPDATE payments SET invoice_url=COALESCE(?, invoice_url), due_date=COALESCE(?, due_date), "
                 "amount_cents=?, billing_type=?, synced_at=?, subscription_id=COALESCE(subscription_id, ?) WHERE id=?",
                 (p.get("invoiceUrl"), p.get("dueDate"), round(float(p.get("value", 0)) * 100),
                  p.get("billingType", row["billing_type"]), now(), subscription_id, row["id"]))
    apply_status(row, asaas_status(p))
    db().commit()
    return db().execute("SELECT * FROM payments WHERE id=?", (row["id"],)).fetchone()


def apply_status(row, new):
    """Transição de status com efeito no plano. Idempotente: o UPDATE condicional garante uma única liberação."""
    old = row["status"]
    if new == old:
        return
    if new == "confirmado":
        cur = db().execute("UPDATE payments SET status='confirmado', paid_at=?, decided_at=?, decided_by='asaas' "
                           "WHERE id=? AND status!='confirmado'", (now(), now(), row["id"]))
        if cur.rowcount == 1:
            until = grant_pro(row["tenant_id"], row["days"])
            audit("asaas_pagamento_confirmado", f"pagamento #{row['id']} {row['external_id']} "
                  f"valor={row['amount_cents']} dias={row['days']} pro_ate={until or '-'}", tenant_id=row["tenant_id"])
        return
    cur = db().execute("UPDATE payments SET status=? WHERE id=? AND status=?", (new, row["id"], old))
    if cur.rowcount == 1:
        if old == "confirmado" and new == "estornado":
            revoke_pro(row["tenant_id"], row["days"])
        audit(f"asaas_pagamento_{new}", f"pagamento #{row['id']} {row['external_id']} ({old} → {new})",
              tenant_id=row["tenant_id"])


def days_for(months):
    try:
        per = max(1, int(setting("pro_dias")))
    except ValueError:
        per = 30
    return per * months


def parse_money_cents(text):
    """Aceita 49,90 / 1.234,56 / 49.90 / R$ 49,90."""
    t = (text or "").replace("R$", "").replace(" ", "")
    if "," in t:
        t = t.replace(".", "").replace(",", ".")
    return round(float(t or 0) * 100)


def pro_price_cents():
    try:
        return parse_money_cents(setting("pro_preco"))
    except ValueError:
        return 0


def due_date_for(billing_type):
    # Boleto precisa de alguns dias para ser pago; Pix e cartão vencem hoje.
    return add_days(today(), 3) if billing_type in ("BOLETO", "UNDEFINED") else today()


# ---------------------------------------------------------------- operações
def create_charge(tenant_id, value_cents, days, kind, description, billing_type, due_date=None):
    if billing_type not in asaas.BILLING_TYPES:
        raise BillingError("Forma de pagamento inválida.")
    if value_cents < 500:
        raise BillingError("O Asaas exige cobranças de pelo menos R$ 5,00.")
    customer = ensure_customer(tenant_id)
    try:
        p = asaas.create_payment(customer, billing_type, value_cents / 100, due_date or due_date_for(billing_type),
                                 description, external_reference=f"integra:t{tenant_id}:{kind}")
    except asaas.AsaasError as e:
        raise BillingError(f"Asaas recusou a cobrança: {e}") from None
    return upsert_payment(p, tenant_id, kind, days)


def create_subscription(tenant_id, months, billing_type):
    if months not in asaas.CYCLES:
        raise BillingError("Período de assinatura inválido.")
    if billing_type not in asaas.BILLING_TYPES:
        raise BillingError("Forma de pagamento inválida.")
    if active_subscription(tenant_id):
        raise BillingError("Já existe uma assinatura ativa. Cancele-a antes de criar outra.")
    value = pro_price_cents() * months
    if value < 500:
        raise BillingError("Configure o preço do Pro (mínimo de R$ 5,00 por cobrança).")
    customer = ensure_customer(tenant_id)
    try:
        s = asaas.create_subscription(customer, billing_type, value / 100, due_date_for(billing_type),
                                      asaas.CYCLES[months], description="Íntegra Pro",
                                      external_reference=f"integra:t{tenant_id}:assinatura")
    except asaas.AsaasError as e:
        raise BillingError(f"Asaas recusou a assinatura: {e}") from None
    sid = db().execute("INSERT INTO subscriptions(tenant_id, external_id, months, days, value_cents, billing_type, "
                       "next_due_date, created_at) VALUES (?,?,?,?,?,?,?,?)",
                       (tenant_id, s["id"], months, days_for(months), value, billing_type,
                        s.get("nextDueDate"), now())).lastrowid
    db().commit()
    audit("asaas_assinatura_criada", f"assinatura #{sid} {s['id']} {asaas.CYCLES[months]} valor={value}",
          tenant_id=tenant_id)
    first = None
    try:
        for p in asaas.subscription_payments(s["id"]):
            row = upsert_payment(p, tenant_id, "assinatura", days_for(months), sid)
            if row["status"] in ("pendente", "vencido") and (first is None or row["due_date"] < first["due_date"]):
                first = row
    except asaas.AsaasError:
        pass  # a primeira cobrança chega pelo webhook PAYMENT_CREATED
    return sid, first


def active_subscription(tenant_id):
    return db().execute("SELECT * FROM subscriptions WHERE tenant_id=? AND status='ativa' ORDER BY id DESC LIMIT 1",
                        (tenant_id,)).fetchone()


def cancel_subscription(sub, by):
    if sub["external_id"]:
        try:
            asaas.delete_subscription(sub["external_id"])
        except asaas.AsaasError as e:
            if e.status != 404:
                raise BillingError(f"Asaas não cancelou a assinatura: {e}") from None
    db().execute("UPDATE subscriptions SET status='cancelada', canceled_at=?, canceled_by=? WHERE id=?",
                 (now(), by, sub["id"]))
    # cobranças em aberto da assinatura deixam de valer
    for row in db().execute("SELECT * FROM payments WHERE subscription_id=? AND status IN ('pendente', 'vencido')",
                            (sub["id"],)).fetchall():
        try:
            asaas.delete_payment(row["external_id"])
        except asaas.AsaasError:
            pass
        apply_status(row, "cancelado")
    db().commit()
    audit("asaas_assinatura_cancelada", f"assinatura #{sub['id']} {sub['external_id']} por {by}",
          tenant_id=sub["tenant_id"])


def cancel_charge(row, by):
    if row["external_id"]:
        try:
            asaas.delete_payment(row["external_id"])
        except asaas.AsaasError as e:
            if e.status != 404:
                raise BillingError(f"Asaas não cancelou a cobrança: {e}") from None
    apply_status(row, "cancelado")
    db().commit()


def sync_payment(row, force=False):
    """Consulta o Asaas e atualiza o pagamento local (no máximo a cada SYNC_INTERVAL segundos)."""
    if row["provider"] != "asaas" or not row["external_id"] or not asaas.configured():
        return row
    if not force and row["synced_at"]:
        age = (datetime.fromisoformat(now()) - datetime.fromisoformat(row["synced_at"])).total_seconds()
        if age < SYNC_INTERVAL:
            return row
    p = asaas.get_payment(row["external_id"])
    return upsert_payment(p, row["tenant_id"], row["kind"], row["days"], row["subscription_id"])


def pix_qr(row):
    try:
        return asaas.pix_qr_code(row["external_id"])
    except asaas.AsaasError:
        return None


# ---------------------------------------------------------------- webhook
def _tenant_for(p):
    if p.get("subscription"):
        sub = db().execute("SELECT * FROM subscriptions WHERE external_id=?", (p["subscription"],)).fetchone()
        if sub:
            return sub["tenant_id"], sub
    t = db().execute("SELECT id FROM tenants WHERE asaas_customer_id=?", (p.get("customer"),)).fetchone()
    if t:
        return t["id"], None
    m = re.match(r"integra:t(\d+)", p.get("externalReference") or "")
    if m and db().execute("SELECT 1 FROM tenants WHERE id=?", (int(m.group(1)),)).fetchone():
        return int(m.group(1)), None
    return None, None


def handle_payment_event(p):
    tenant_id, sub = _tenant_for(p)
    if tenant_id is None:
        return "pagamento de cliente desconhecido (ignorado)"
    row = db().execute("SELECT * FROM payments WHERE external_id=?", (p["id"],)).fetchone()
    if row:
        upsert_payment(p, row["tenant_id"], row["kind"], row["days"], row["subscription_id"])
        return ""
    if p.get("subscription"):
        if sub:
            days, sid = sub["days"], sub["id"]
        else:  # assinatura criada e ainda não gravada localmente: descobre o ciclo no Asaas
            months = asaas.CYCLE_MONTHS.get(asaas.get_subscription(p["subscription"]).get("cycle"), 1)
            days, sid = days_for(months), None
        upsert_payment(p, tenant_id, "assinatura", days, sid)
    else:
        upsert_payment(p, tenant_id, "avulsa", 0)
    return ""


def handle_subscription_event(event, s):
    sub = db().execute("SELECT * FROM subscriptions WHERE external_id=?", (s.get("id"),)).fetchone()
    if not sub:
        return "assinatura desconhecida (ignorada)"
    if event in ("SUBSCRIPTION_DELETED", "SUBSCRIPTION_INACTIVATED") or s.get("deleted") or s.get("status") == "INACTIVE":
        if sub["status"] == "ativa":
            db().execute("UPDATE subscriptions SET status=?, canceled_at=?, canceled_by='asaas' WHERE id=?",
                         ("cancelada" if event == "SUBSCRIPTION_DELETED" else "inativa", now(), sub["id"]))
            audit("asaas_assinatura_encerrada", f"assinatura #{sub['id']} {sub['external_id']} ({event})",
                  tenant_id=sub["tenant_id"])
    elif s.get("nextDueDate"):
        db().execute("UPDATE subscriptions SET next_due_date=? WHERE id=?", (s["nextDueDate"], sub["id"]))
    db().commit()
    return ""


@app.route("/webhooks/asaas", methods=["POST"])
def asaas_webhook():
    token = request.headers.get("asaas-access-token", "")
    if not asaas.WEBHOOK_TOKEN or not secrets.compare_digest(token, asaas.WEBHOOK_TOKEN):
        abort(401)
    body = request.get_json(silent=True) or {}
    event_id, event = str(body.get("id") or ""), body.get("event", "")
    if not event_id or not event:
        return jsonify(received=True)
    resource = body.get("payment") or body.get("subscription") or {}
    try:
        db().execute("INSERT INTO webhook_events(id, event, resource_id, received_at, payload) VALUES (?,?,?,?,?)",
                     (event_id, event, resource.get("id"), now(), json.dumps(body)[:20000]))
        db().commit()
    except sqlite3.IntegrityError:  # id repetido: evento já recebido
        db().rollback()
        return jsonify(received=True, duplicate=True)
    g.webhook = True
    try:
        if event.startswith("PAYMENT_") and body.get("payment"):
            err = handle_payment_event(body["payment"])
        elif event.startswith("SUBSCRIPTION_") and body.get("subscription"):
            err = handle_subscription_event(event, body["subscription"])
        else:
            err = ""
    except Exception as e:  # noqa: BLE001 - nunca devolve erro ao Asaas (a fila pausaria); fica registrado
        db().rollback()
        err = f"{type(e).__name__}: {e}"
    if err:
        db().execute("UPDATE webhook_events SET error=? WHERE id=?", (err[:1000], event_id))
        db().commit()
    return jsonify(received=True)
