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
        "pro_max_processos": "0", "pro_max_storage_mb": "0"}
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
assert "Idêntico" in ok(r)
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
r = cli.get("/"); ok(r, 302); assert "/login" in r.headers["Location"]
print("compartilhamento e bloqueio ok")

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
