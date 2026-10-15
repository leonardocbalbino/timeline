"""Cliente mínimo da API v3 do Asaas (https://docs.asaas.com). Credenciais vêm do ambiente (.env)."""
import json
import os
import urllib.error
import urllib.parse
import urllib.request

API_KEY = os.environ.get("ASAAS_API_KEY", "").strip()
ENV = os.environ.get("ASAAS_ENV", "sandbox").strip().lower()
WEBHOOK_TOKEN = os.environ.get("ASAAS_WEBHOOK_TOKEN", "").strip()
USER_AGENT = "integra/1.0"
TIMEOUT = 20

BILLING_TYPES = {"PIX": "Pix", "BOLETO": "Boleto", "CREDIT_CARD": "Cartão de crédito", "UNDEFINED": "Cliente escolhe"}
CYCLES = {1: "MONTHLY", 3: "QUARTERLY", 6: "SEMIANNUALLY", 12: "YEARLY"}
CYCLE_MONTHS = {"MONTHLY": 1, "BIMONTHLY": 2, "QUARTERLY": 3, "SEMIANNUALLY": 6, "YEARLY": 12}
WEBHOOK_EVENTS = [
    "PAYMENT_CREATED", "PAYMENT_UPDATED", "PAYMENT_CONFIRMED", "PAYMENT_RECEIVED", "PAYMENT_OVERDUE",
    "PAYMENT_DELETED", "PAYMENT_RESTORED", "PAYMENT_REFUNDED", "PAYMENT_PARTIALLY_REFUNDED",
    "PAYMENT_RECEIVED_IN_CASH_UNDONE", "PAYMENT_CHARGEBACK_REQUESTED", "PAYMENT_CHARGEBACK_DISPUTE",
    "SUBSCRIPTION_CREATED", "SUBSCRIPTION_UPDATED", "SUBSCRIPTION_INACTIVATED", "SUBSCRIPTION_DELETED",
]


class AsaasError(Exception):
    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status


def configured():
    return bool(API_KEY)


def base_url():
    return "https://api.asaas.com/v3" if ENV in ("production", "producao", "prod") else "https://api-sandbox.asaas.com/v3"


def environment_label():
    return "Produção" if "sandbox" not in base_url() else "Sandbox (testes)"


def _request(method, path, body=None, params=None):
    if not API_KEY:
        raise AsaasError("Asaas não configurado: defina ASAAS_API_KEY no .env do servidor.")
    url = base_url() + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "access_token": API_KEY, "Content-Type": "application/json", "Accept": "application/json",
        "User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            errors = json.loads(raw).get("errors") or []
            msg = "; ".join(err.get("description", "") for err in errors) or f"HTTP {e.code}"
        except (ValueError, AttributeError):
            msg = f"HTTP {e.code}"
        if e.code == 401:
            msg = "Chave da API do Asaas inválida ou do ambiente errado (sandbox x produção)."
        raise AsaasError(msg, e.code) from None
    except (urllib.error.URLError, TimeoutError) as e:
        raise AsaasError(f"Não foi possível falar com o Asaas: {getattr(e, 'reason', e)}") from None
    return json.loads(raw) if raw else {}


# ---------------------------------------------------------------- recursos
def create_customer(name, cpf_cnpj, email="", mobile_phone="", external_reference=""):
    body = {"name": name, "cpfCnpj": cpf_cnpj, "externalReference": external_reference}
    if email:
        body["email"] = email
    if mobile_phone:
        body["mobilePhone"] = mobile_phone
    return _request("POST", "/customers", body)


def update_customer(customer_id, **fields):
    return _request("PUT", f"/customers/{customer_id}", fields)


def create_payment(customer, billing_type, value, due_date, description="", external_reference=""):
    return _request("POST", "/payments", {
        "customer": customer, "billingType": billing_type, "value": round(value, 2), "dueDate": due_date,
        "description": description[:500], "externalReference": external_reference})


def get_payment(payment_id):
    return _request("GET", f"/payments/{payment_id}")


def delete_payment(payment_id):
    return _request("DELETE", f"/payments/{payment_id}")


def pix_qr_code(payment_id):
    return _request("GET", f"/payments/{payment_id}/pixQrCode")


def create_subscription(customer, billing_type, value, next_due_date, cycle, description="", external_reference=""):
    return _request("POST", "/subscriptions", {
        "customer": customer, "billingType": billing_type, "value": round(value, 2),
        "nextDueDate": next_due_date, "cycle": cycle, "description": description[:500],
        "externalReference": external_reference})


def get_subscription(subscription_id):
    return _request("GET", f"/subscriptions/{subscription_id}")


def delete_subscription(subscription_id):
    return _request("DELETE", f"/subscriptions/{subscription_id}")


def subscription_payments(subscription_id):
    return _request("GET", f"/subscriptions/{subscription_id}/payments").get("data", [])


def balance():
    return _request("GET", "/finance/balance")


def list_webhooks():
    return _request("GET", "/webhooks").get("data", [])


def create_webhook(url, email, auth_token, name="Íntegra"):
    return _request("POST", "/webhooks", {
        "name": name, "url": url, "email": email, "enabled": True, "interrupted": False,
        "authToken": auth_token, "sendType": "SEQUENTIALLY", "events": WEBHOOK_EVENTS})


def update_webhook(webhook_id, url, email, auth_token):
    return _request("PUT", f"/webhooks/{webhook_id}", {
        "url": url, "email": email, "enabled": True, "interrupted": False,
        "authToken": auth_token, "sendType": "SEQUENTIALLY", "events": WEBHOOK_EVENTS})
