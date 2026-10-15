"""Teste de ponta a ponta: migração da versão antiga, admin, cliente, Pix e link.
Uso: python tests/smoke_test.py"""
import io
import os
import re
import shutil
import sqlite3
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
data = tempfile.mkdtemp(prefix="tl-")
os.makedirs(os.path.join(data, "uploads"))

# --- banco no formato antigo (versão de usuário único)
old = sqlite3.connect(os.path.join(data, "provas.db"))
old.executescript("""
CREATE TABLE evidences (id INTEGER PRIMARY KEY AUTOINCREMENT, occurred_at TEXT NOT NULL, title TEXT NOT NULL,
 description TEXT NOT NULL DEFAULT '', source TEXT NOT NULL DEFAULT '', people TEXT NOT NULL DEFAULT '',
 important INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE INDEX idx_ev_when ON evidences(occurred_at);
CREATE TABLE files (id INTEGER PRIMARY KEY AUTOINCREMENT, evidence_id INTEGER NOT NULL REFERENCES evidences(id) ON DELETE CASCADE,
 stored_name TEXT NOT NULL, original_name TEXT NOT NULL, mime TEXT NOT NULL, kind TEXT NOT NULL, size INTEGER NOT NULL,
 sha256 TEXT NOT NULL, uploaded_at TEXT NOT NULL, position INTEGER NOT NULL DEFAULT 0);
CREATE INDEX idx_files_ev ON files(evidence_id);
CREATE TABLE audit (id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL, role TEXT NOT NULL, ip TEXT NOT NULL,
 action TEXT NOT NULL, detail TEXT NOT NULL DEFAULT '');
INSERT INTO evidences VALUES (1,'2024-05-12T14:33:21','Print antigo','desc','WhatsApp','',1,'2024-05-13T10:00:00','2024-05-13T10:00:00');
INSERT INTO evidences VALUES (2,'2024-05-13T09:00:00','Áudio antigo','','WhatsApp','',0,'2024-05-13T10:00:00','2024-05-13T10:00:00');
INSERT INTO files VALUES (1,1,'legacy.png','print.png','image/png','imagem',3,'abc','2024-05-13T10:00:00',0);
INSERT INTO audit VALUES (1,'2024-05-13T10:00:00','admin','1.2.3.4','login','');
""")
old.commit(); old.close()
with open(os.path.join(data, "uploads", "legacy.png"), "wb") as fh:
    fh.write(b"PNG")

os.environ.update(DATA_DIR=data, USE_X_ACCEL="0", ADMIN_PASSWORD="senha-admin-123", SECRET_KEY="x")
sys.path.insert(0, ROOT)
os.chdir(ROOT)
import pix  # noqa
from app import app  # noqa

# --- Pix: exemplo oficial do manual do BR Code (CRC 1D3D)
ex = pix.brcode("123e4567-e12b-12d1-a456-426655440000", "Fulano de Tal", "BRASILIA", 0, "***")
assert ex == ("00020126580014br.gov.bcb.pix0136123e4567-e12b-12d1-a456-426655440000"
              "5204000053039865802BR5913Fulano de Tal6008BRASILIA62070503***63041D3D"), ex
print("pix ok")

conn = sqlite3.connect(os.path.join(data, "provas.db"))
assert conn.execute("SELECT COUNT(*) FROM evidences WHERE process_id IS NULL").fetchone()[0] == 0
t = conn.execute("SELECT * FROM tenants").fetchall()
assert len(t) == 1 and t[0][1] == "Conta principal", t
assert conn.execute("SELECT tenant_id FROM audit WHERE id=1").fetchone()[0] == t[0][0]
print("migração ok")

app.config["TESTING"] = True


def csrf(c):
    with c.session_transaction() as s:
        s.setdefault("csrf", "tok")
        return s["csrf"]


def ok(r, code=200):
    assert r.status_code == code, (r.status_code, r.request.path, r.get_data(as_text=True)[:2000])
    return r.get_data(as_text=True)


def login(c, email, pwd):
    r = c.post("/login", data={"email": email, "senha": pwd}, follow_redirects=True)
    return ok(r)


adm = app.test_client()
html = login(adm, "admin", "senha-admin-123")
assert "Clientes" in html and "Conta principal" in html
tok = csrf(adm)

# admin acessa a conta legada
ok(adm.post(f"/admin/clientes/{t[0][0]}/acessar", data={"csrf": tok}), 302)
html = ok(adm.get("/"))
assert "Processo principal" in html and "Modo suporte" in html
pid_legacy = conn.execute("SELECT id FROM processes").fetchone()[0]
html = ok(adm.get(f"/processos/{pid_legacy}"))
assert "Print antigo" in html and "Áudio antigo" in html
html = ok(adm.get(f"/processos/{pid_legacy}?modo=horizontal"))
assert "htl-trilho" in html
ok(adm.get(f"/processos/{pid_legacy}/relatorio"))
r = adm.get(f"/processos/{pid_legacy}/exportar"); assert r.status_code == 200 and r.data[:2] == b"PK", r.status_code; r.close()
assert ok(adm.get("/arquivo/1")) == "PNG"
ok(adm.post("/admin/sair-da-conta", data={"csrf": tok}), 302)
print("conta legada ok")

# configura planos e pix
form = {"csrf": tok, "pix_chave": "123.456.789-09", "pix_nome": "Leonardo Balbino", "pix_cidade": "São Paulo",
        "pro_preco": "49,90", "pro_dias": "30",
        "free_max_processos": "1", "free_max_storage_mb": "1", "free_relatorio": "1", "free_verificar": "1",
        "pro_max_processos": "0", "pro_max_storage_mb": "0", "autocadastro": "1"}
for k in ["timeline_horizontal", "relatorio", "exportar", "verificar", "compartilhar", "auditoria"]:
    form[f"pro_{k}"] = "1"
ok(adm.post("/admin/planos", data=form), 302)
assert "12345678909" in ok(adm.get("/admin/planos"))

# cria cliente
r = adm.post("/admin/clientes/novo", data={"csrf": tok, "nome": "Maria Silva", "email": "maria@ex.com",
                                           "plano": "free", "ativo": "1"}, follow_redirects=True)
html = ok(r)
senha = re.search(r'id="senha-nova">([^<]+)<', html).group(1)
tid = conn.execute("SELECT id FROM tenants WHERE name='Maria Silva'").fetchone()[0]
print("cliente criado, senha", senha)

cli = app.test_client()
html = login(cli, "maria@ex.com", senha)
assert "Nenhum processo ainda" in html, html[:3000]
ct = csrf(cli)
assert ok(cli.get("/admin"), 403) is not None
r = cli.post("/processos/novo", data={"csrf": ct, "titulo": "Caso Maria", "numero": "123"})
ok(r, 302)
pid = int(r.headers["Location"].rsplit("/", 1)[1])
# limite de 1 processo no Free
r = cli.get("/processos/novo"); ok(r, 302); assert "/plano" in r.headers["Location"]
# nova prova com arquivo
r = cli.post(f"/processos/{pid}/provas/nova", data={
    "csrf": ct, "data": "2024-06-01", "hora": "10:20", "titulo": "Mensagem", "descricao": "x",
    "arquivos": (io.BytesIO(b"hello world"), "IMG-20240601-WA0001.jpg")}, content_type="multipart/form-data")
ok(r, 302)
html = ok(cli.get(f"/processos/{pid}"))
assert "Mensagem" in html and "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9" in html
# horizontal bloqueado no Free -> cai para vertical
html = ok(cli.get(f"/processos/{pid}?modo=horizontal"))
assert "htl-trilho" not in html and "bloqueado" in html
assert ok(cli.get(f"/processos/{pid}/exportar"), 302) is not None  # exportar só no Pro
# isolamento: cliente não vê arquivo nem processo do outro
ok(cli.get("/arquivo/1"), 404)
ok(cli.get(f"/processos/{pid_legacy}"), 404)
# cota de 1 MB
r = cli.post(f"/processos/{pid}/provas/nova", data={
    "csrf": ct, "data": "2024-06-01", "titulo": "Grande",
    "arquivos": (io.BytesIO(b"0" * (2 * 1024 * 1024)), "video.mp4")}, content_type="multipart/form-data",
    follow_redirects=True)
assert "Espaço insuficiente" in ok(r)
# verificar
r = cli.post("/verificar", data={"csrf": ct, "arquivo": (io.BytesIO(b"hello world"), "a.jpg")},
             content_type="multipart/form-data")
assert "Arquivo íntegro" in ok(r)
print("cliente free ok")

# pagamento Pix
html = ok(cli.get("/plano"))
assert "Assinar com Pix" in html
r = cli.post("/plano/pix", data={"csrf": ct, "periodos": "3"}); ok(r, 302)
pay_url = r.headers["Location"]
html = ok(cli.get(pay_url))
code = re.search(r'value="(000201[^"]+)"', html).group(1)
assert "5406149.70" in code and "12345678909" in code and "LEONARDO" not in code
assert pix._crc16(code[:-4]) == code[-4:]
assert "data:image/svg+xml" in html
r = cli.post(pay_url, data={"csrf": ct, "acao": "informar", "obs": "pago",
                            "comprovante": (io.BytesIO(b"%PDF"), "comp.pdf")}, content_type="multipart/form-data")
ok(r, 302)
assert "Aguardando confirmação" in ok(cli.get(pay_url))
html = ok(adm.get("/admin/pagamentos"))
assert "Maria Silva" in html and "comp.pdf" in html
pay_id = conn.execute("SELECT id FROM payments").fetchone()[0]
assert ok(adm.get(f"/admin/pagamentos/{pay_id}/comprovante")) == "%PDF"
ok(adm.post(f"/admin/pagamentos/{pay_id}/confirmar", data={"csrf": tok}), 302)
row = conn.execute("SELECT plan, pro_until FROM tenants WHERE id=?", (tid,)).fetchone()
assert row[0] == "pro" and row[1], row
print("pix confirmado, pro até", row[1])

# agora é Pro
html = ok(cli.get(f"/processos/{pid}?modo=horizontal"))
assert "htl-trilho" in html
html = ok(cli.get(f"/processos/{pid}"))
assert "htl-trilho" in html  # preferência guardada na sessão
ok(cli.get("/processos/novo"))
r = cli.get(f"/processos/{pid}/exportar"); assert r.status_code == 200 and r.data[:2] == b"PK", r.status_code; r.close()
ok(cli.get("/auditoria"))
# link de compartilhamento
ok(cli.post(f"/processos/{pid}/compartilhar", data={"csrf": ct, "acao": "gerar"}), 302)
token = conn.execute("SELECT share_token FROM processes WHERE id=?", (pid,)).fetchone()[0]
anon = app.test_client()
html = ok(anon.get(f"/p/{token}"))
assert "Somente leitura" in html and "Mensagem" in html and "Editar" not in html
fid = conn.execute("SELECT f.id FROM files f JOIN evidences e ON e.id=f.evidence_id WHERE e.process_id=?", (pid,)).fetchone()[0]
assert ok(anon.get(f"/p/{token}/arquivo/{fid}")) == "hello world"
ok(anon.get(f"/p/{token}/arquivo/1"), 404)
ok(anon.get(f"/p/{token}/relatorio"))
ok(anon.get(f"/arquivo/{fid}"), 302)
# rebaixa para free -> link para de funcionar
ok(adm.post(f"/admin/clientes/{tid}", data={"csrf": tok, "nome": "Maria Silva", "email": "maria@ex.com",
                                            "plano": "free", "ativo": "1"}), 302)
ok(anon.get(f"/p/{token}"), 404)
# desativa -> cliente é desconectado
ok(adm.post(f"/admin/clientes/{tid}", data={"csrf": tok, "nome": "Maria Silva", "email": "maria@ex.com",
                                            "plano": "free"}), 302)
html = ok(cli.get("/")); assert "Preços simples" in html  # desconectado -> landing
print("compartilhamento e bloqueio ok")

# landing e autocadastro
anon2 = app.test_client()
html = ok(anon2.get("/"))
assert "R$ 49,90" in html and "Criar conta grátis" in html and 'content="index, follow"' in html
r = anon2.get("/")
assert "X-Robots-Tag" not in r.headers
assert anon2.get("/login").headers["X-Robots-Tag"].startswith("noindex")
ok(anon2.get("/cadastro"))
c2 = csrf(anon2)
base = {"csrf": c2, "nome": "João Souza", "email": "joao@ex.com", "senha": "segredo-123",
        "confirma": "segredo-123", "termos": "1"}
assert "e-mail válido" in ok(anon2.post("/cadastro", data={**base, "email": "x"}), 400)
assert "condições de uso" in ok(anon2.post("/cadastro", data={k: v for k, v in base.items() if k != "termos"}), 400)
ok(anon2.post("/cadastro", data={**base, "site": "spam"}), 400)
r = anon2.post("/cadastro", data=base); ok(r, 302)
html = ok(anon2.get("/"))
assert "Conta criada" in html and "Nenhum processo ainda" in html
row = conn.execute("SELECT t.plan, u.role FROM users u JOIN tenants t ON t.id=u.tenant_id WHERE u.email='joao@ex.com'").fetchone()
assert row == ("free", "cliente"), row
anon3 = app.test_client(); csrf(anon3)
assert "Já existe uma conta" in ok(anon3.post("/cadastro", data={**base, "csrf": csrf(anon3)}), 400)
# admin fecha o cadastro
form["autocadastro"] = ""
form["contato_email"] = "contato@ex.com"
ok(adm.post("/admin/planos", data=form), 302)
html = ok(anon3.get("/"))
assert "Criar conta grátis" not in html and "contato@ex.com" in html
ok(anon3.get("/cadastro"), 302)
print("landing e autocadastro ok")

# ---------------------------------------------------------------- Asaas (API simulada em memória)
import asaas  # noqa: E402

FAKE = {"customers": {}, "payments": {}, "subscriptions": {}, "webhooks": {}, "n": 0}


def _fake_request(method, path, body=None, params=None):
    FAKE["n"] += 1
    n = FAKE["n"]
    parts = path.strip("/").split("/")
    if path == "/customers" and method == "POST":
        if not body.get("cpfCnpj"):
            raise asaas.AsaasError("O CPF/CNPJ é obrigatório.", 400)
        c = {"id": f"cus_{n}", **body}
        FAKE["customers"][c["id"]] = c
        return c
    if path == "/payments" and method == "POST":
        p = {"id": f"pay_{n}", "status": "PENDING", "invoiceUrl": f"https://sandbox.asaas.com/i/{n}",
             "deleted": False, **body}
        FAKE["payments"][p["id"]] = p
        return p
    if parts[0] == "payments" and len(parts) == 2:
        p = FAKE["payments"][parts[1]]
        if method == "DELETE":
            p["deleted"] = True
            return {"deleted": True, "id": p["id"]}
        return dict(p)
    if parts[0] == "payments" and parts[2] == "pixQrCode":
        return {"encodedImage": "iVBORw0KGgo=", "payload": "00020126PIXFAKE" + parts[1], "expirationDate": "2030-01-01"}
    if path == "/subscriptions" and method == "POST":
        s = {"id": f"sub_{n}", "status": "ACTIVE", **body}
        FAKE["subscriptions"][s["id"]] = s
        p = {"id": f"pay_{n}a", "status": "PENDING", "subscription": s["id"], "customer": body["customer"],
             "value": body["value"], "billingType": body["billingType"], "dueDate": body["nextDueDate"],
             "invoiceUrl": f"https://sandbox.asaas.com/i/{n}a", "description": body["description"], "deleted": False}
        FAKE["payments"][p["id"]] = p
        return s
    if parts[0] == "subscriptions" and len(parts) == 3:
        return {"data": [p for p in FAKE["payments"].values() if p.get("subscription") == parts[1]]}
    if parts[0] == "subscriptions" and len(parts) == 2:
        if method == "DELETE":
            FAKE["subscriptions"][parts[1]]["status"] = "INACTIVE"
            return {"deleted": True}
        return FAKE["subscriptions"][parts[1]]
    if path == "/finance/balance":
        return {"balance": 1234.5}
    if path == "/webhooks":
        if method == "GET":
            return {"data": list(FAKE["webhooks"].values())}
        w = {"id": f"wh_{n}", **body}
        FAKE["webhooks"][w["id"]] = w
        return w
    raise AssertionError(f"chamada inesperada {method} {path}")


asaas._request = _fake_request
asaas.API_KEY = "teste"
asaas.WEBHOOK_TOKEN = "t" * 40


def rowd(sql, args=()):
    cur = conn.execute(sql, args)
    r = cur.fetchone()
    return dict(zip([c[0] for c in cur.description], r)) if r else None


def hook(event, payload, token="t" * 40, eid=None):
    FAKE["n"] += 1
    return anon.post("/webhooks/asaas", json={"id": eid or f"evt_{FAKE['n']}", "event": event, **payload},
                     headers={"asaas-access-token": token})


# admin ativa o Asaas e configura o webhook
form["gateway"] = "asaas"
form["autocadastro"] = "1"
ok(adm.post("/admin/planos", data=form), 302)
html = ok(adm.get("/admin/planos"))
assert "Chave configurada" in html and "/webhooks/asaas" in html
assert "Conexão com o Asaas OK" in ok(adm.post("/admin/asaas/testar", data={"csrf": tok}, follow_redirects=True))
assert "Webhook criado" in ok(adm.post("/admin/asaas/webhook", data={"csrf": tok, "email": "eu@ex.com"},
                                        follow_redirects=True))
assert list(FAKE["webhooks"].values())[0]["authToken"] == "t" * 40
assert "Webhook atualizado" not in ok(adm.get("/admin/planos"))

# cliente novo (Free) assina o Pro: exige CPF válido
r = adm.post("/admin/clientes/novo", data={"csrf": tok, "nome": "Ana Lima", "email": "ana@ex.com",
                                           "senha": "senha-ana-123", "plano": "free", "ativo": "1"})
tid_ana = conn.execute("SELECT id FROM tenants WHERE name='Ana Lima'").fetchone()[0]
ana = app.test_client()
login(ana, "ana@ex.com", "senha-ana-123")
ca = csrf(ana)
html = ok(ana.get("/plano"))
assert "Assinatura recorrente" in html and "CPF ou CNPJ" in html
assert "CPF ou CNPJ inválido" in ok(ana.post("/plano/asaas", data={"csrf": ca, "modalidade": "assinatura", "periodos": "1",
                                                                     "forma": "PIX", "documento": "111.111.111-11"},
                                             follow_redirects=True))
r = ana.post("/plano/asaas", data={"csrf": ca, "modalidade": "assinatura", "periodos": "1", "forma": "PIX",
                                   "documento": "529.982.247-25"})
ok(r, 302)
assert "/plano/pagamento/" in r.headers["Location"], r.headers["Location"]
html = ok(ana.get(r.headers["Location"]))
assert "00020126PIXFAKE" in html and "data:image/png;base64" in html and "data-status-url" in html
sub_ext = conn.execute("SELECT external_id FROM subscriptions WHERE tenant_id=?", (tid_ana,)).fetchone()[0]
pay_ext = conn.execute("SELECT external_id FROM payments WHERE tenant_id=? AND kind='assinatura'", (tid_ana,)).fetchone()[0]
assert conn.execute("SELECT document FROM tenants WHERE id=?", (tid_ana,)).fetchone()[0] == "52998224725"
# segunda assinatura é recusada
assert "Já existe uma assinatura ativa" in ok(ana.post("/plano/asaas", data={"csrf": ca, "modalidade": "assinatura",
                                                                              "periodos": "1", "forma": "PIX"},
                                                       follow_redirects=True))

# webhook: token inválido é recusado; pagamento recebido libera o Pro uma única vez
assert hook("PAYMENT_RECEIVED", {"payment": {"id": pay_ext}}, token="errado").status_code == 401
paid = dict(FAKE["payments"][pay_ext], status="RECEIVED")
FAKE["payments"][pay_ext] = paid
assert hook("PAYMENT_RECEIVED", {"payment": paid}, eid="evt_pago").status_code == 200
row = conn.execute("SELECT plan, pro_until FROM tenants WHERE id=?", (tid_ana,)).fetchone()
assert row[0] == "pro" and row[1], row
until1 = row[1]
hook("PAYMENT_RECEIVED", {"payment": paid}, eid="evt_pago")       # mesmo evento repetido
hook("PAYMENT_CONFIRMED", {"payment": paid})                       # outro evento, mesmo pagamento
ok(ana.get(f"/plano/pagamento/{conn.execute('SELECT id FROM payments WHERE external_id=?', (pay_ext,)).fetchone()[0]}/status"))
assert conn.execute("SELECT pro_until FROM tenants WHERE id=?", (tid_ana,)).fetchone()[0] == until1
assert conn.execute("SELECT COUNT(*) FROM audit WHERE action='asaas_pagamento_confirmado' AND tenant_id=?",
                    (tid_ana,)).fetchone()[0] == 1

# renovação: nova cobrança da assinatura chega só pelo webhook e soma mais 30 dias
renov = {"id": "pay_renov", "status": "PENDING", "subscription": sub_ext, "customer": paid["customer"], "value": 49.9,
         "billingType": "PIX", "dueDate": "2030-01-01", "invoiceUrl": "https://x/i/renov"}
FAKE["payments"]["pay_renov"] = renov
hook("PAYMENT_CREATED", {"payment": renov})
assert conn.execute("SELECT status, days FROM payments WHERE external_id='pay_renov'").fetchone() == ("pendente", 30)
hook("PAYMENT_RECEIVED", {"payment": dict(renov, status="RECEIVED")})
until2 = conn.execute("SELECT pro_until FROM tenants WHERE id=?", (tid_ana,)).fetchone()[0]
from datetime import date  # noqa: E402
assert (date.fromisoformat(until2) - date.fromisoformat(until1)).days == 30, (until1, until2)
# estorno devolve os dias
hook("PAYMENT_REFUNDED", {"payment": dict(renov, status="REFUNDED")})
assert conn.execute("SELECT pro_until FROM tenants WHERE id=?", (tid_ana,)).fetchone()[0] == until1
assert conn.execute("SELECT status FROM payments WHERE external_id='pay_renov'").fetchone()[0] == "estornado"
# evento de cliente desconhecido fica registrado sem erro
assert hook("PAYMENT_RECEIVED", {"payment": {"id": "pay_x", "customer": "cus_x", "status": "RECEIVED"}}).status_code == 200

# cliente cancela a assinatura
html = ok(ana.get("/plano"))
assert "Assinatura ativa" in html
ok(ana.post("/plano/assinatura/cancelar", data={"csrf": ca}), 302)
assert conn.execute("SELECT status FROM subscriptions WHERE external_id=?", (sub_ext,)).fetchone()[0] == "cancelada"
assert FAKE["subscriptions"][sub_ext]["status"] == "INACTIVE"
assert "Assinatura recorrente" in ok(ana.get("/plano"))

# pagamento único por boleto, confirmado pela sincronização (sem webhook)
r = ana.post("/plano/asaas", data={"csrf": ca, "modalidade": "unico", "periodos": "3", "forma": "BOLETO"})
ok(r, 302)
html = ok(ana.get(r.headers["Location"]))
assert "Abrir fatura" in html and "PIXFAKE" not in html
one = rowd("SELECT * FROM payments WHERE tenant_id=? AND kind='plano' AND provider='asaas'", (tid_ana,))
assert one["days"] == 90 and one["amount_cents"] == 14970, dict(one)
FAKE["payments"][one["external_id"]]["status"] = "CONFIRMED"
assert "Pagamento confirmado" in ok(ana.post(r.headers["Location"], data={"csrf": ca, "acao": "verificar"},
                                             follow_redirects=True))
until3 = conn.execute("SELECT pro_until FROM tenants WHERE id=?", (tid_ana,)).fetchone()[0]
assert (date.fromisoformat(until3) - date.fromisoformat(until1)).days == 90

# admin gera cobrança avulsa sem dias de Pro, depois cancela
html = ok(adm.get(f"/admin/clientes/{tid_ana}"))
assert "Nova cobrança avulsa" in html and "Assinaturas" in html
r = adm.post(f"/admin/clientes/{tid_ana}/cobranca", data={"csrf": tok, "valor": "1.250,00", "descricao": "Consultoria",
                                                          "vencimento": "2030-01-10", "forma": "UNDEFINED", "dias": "0"},
             follow_redirects=True)
assert "Cobrança criada" in ok(r)
av = rowd("SELECT * FROM payments WHERE tenant_id=? AND kind='avulsa' AND description='Consultoria'", (tid_ana,))
assert av["amount_cents"] == 125000 and av["due_date"] == "2030-01-10" and av["days"] == 0
assert "Fatura" in ok(adm.get("/admin/pagamentos?status=pendente"))
assert "pelo menos R$ 5,00" in ok(adm.post(f"/admin/clientes/{tid_ana}/cobranca", data={"csrf": tok, "valor": "2", "forma": "PIX"},
                                           follow_redirects=True))
ok(adm.post(f"/admin/pagamentos/{av['id']}/cancelar", data={"csrf": tok}), 302)
assert conn.execute("SELECT status FROM payments WHERE id=?", (av["id"],)).fetchone()[0] == "cancelado"
# confirmar manualmente não vale para o Asaas
ok(adm.post(f"/admin/pagamentos/{one['id']}/confirmar", data={"csrf": tok}), 302)
html = ok(adm.get("/admin/planos"))
assert "PAYMENT_RECEIVED" in html
print("asaas ok")

# trocar senha do admin
ok(adm.post("/conta", data={"csrf": tok, "atual": "senha-admin-123", "nova": "nova-senha-1", "confirma": "nova-senha-1"}), 302)
ok(adm.get("/admin"))
assert "Auditoria" in ok(adm.get("/admin/auditoria"))
# excluir cliente
ok(adm.post(f"/admin/clientes/{tid}/excluir", data={"csrf": tok, "confirmar": "Maria Silva"}), 302)
assert conn.execute("SELECT COUNT(*) FROM processes WHERE tenant_id=?", (tid,)).fetchone()[0] == 0
left = sorted(os.listdir(os.path.join(data, "uploads")))
assert left == ["legacy.png"], left
print("exclusão ok")

conn.close()
shutil.rmtree(data, ignore_errors=True)
print("TUDO OK")
