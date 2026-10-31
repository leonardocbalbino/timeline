"""Upload em partes: o navegador envia cada arquivo em pedaços pequenos (o Cloudflare recusa
requisições acima de 100 MB) e o servidor monta o arquivo num temporário. Ao salvar a prova, o
arquivo vai para o armazenamento definitivo e o SHA-256 é calculado sobre o arquivo inteiro."""
import hashlib
import os
import secrets
import time
import uuid

from flask import abort, g, jsonify, request

from core import (DATA, UPLOADS, app, db, guess_mime, has_feature, human_size, kind_for, now,
                  quota_left, tenant_required, unlink_upload)

PARTS = os.path.join(DATA, "partes")
CHUNK_SIZE = 16 * 1024 ** 2         # tamanho sugerido ao navegador
CHUNK_MAX = 64 * 1024 ** 2          # maior pedaço aceito numa requisição
FILE_MAX = 4 * 1024 ** 3            # mesmo limite do envio direto
STALE_SECONDS = 24 * 3600           # temporários abandonados são apagados depois disso

os.makedirs(PARTS, exist_ok=True)


class UploadError(Exception):
    pass


def part_path(sid):
    return os.path.join(PARTS, f"{sid}.part")


def received(sid):
    try:
        return os.path.getsize(part_path(sid))
    except FileNotFoundError:
        return 0


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def cleanup():
    """Apaga envios abandonados (sessões e arquivos órfãos com mais de 24 h)."""
    limite = time.time() - STALE_SECONDS
    for name in os.listdir(PARTS):
        path = os.path.join(PARTS, name)
        try:
            if os.path.getmtime(path) < limite:
                os.remove(path)
        except OSError:
            pass
    for row in db().execute("SELECT id FROM upload_sessions").fetchall():
        if not os.path.exists(part_path(row["id"])):
            db().execute("DELETE FROM upload_sessions WHERE id=?", (row["id"],))
    db().commit()


def get_session(sid):
    s = db().execute("SELECT * FROM upload_sessions WHERE id=? AND tenant_id=? AND user_id=?",
                     (sid, g.tenant["id"], g.user["id"])).fetchone()
    if not s:
        abort(404)
    return s


@app.route("/uploads/iniciar", methods=["POST"])
@tenant_required
def upload_start():
    data = request.get_json(silent=True) or {}
    name = os.path.basename(str(data.get("name", "")).replace("\\", "/"))[:200]
    purpose = data.get("purpose", "prova")
    try:
        size = int(data.get("size", 0))
    except (TypeError, ValueError):
        size = 0
    if not name or size <= 0:
        return jsonify(error="Arquivo inválido."), 400
    if size > FILE_MAX:
        return jsonify(error=f"“{name}” passa do limite de 4 GB por arquivo."), 413
    if purpose == "verificar":
        if not has_feature("verificar"):
            abort(403)
    else:
        purpose = "prova"
        left = quota_left()
        pendente = db().execute("SELECT COALESCE(SUM(size), 0) FROM upload_sessions WHERE tenant_id=? "
                                "AND purpose='prova'", (g.tenant["id"],)).fetchone()[0]
        if left is not None and size + pendente > left:
            return jsonify(error=f"Espaço insuficiente no seu plano para “{name}” (restam "
                                 f"{human_size(max(left - pendente, 0))}). Remova arquivos ou assine o Pro."), 413
    cleanup()
    sid = secrets.token_hex(16)
    db().execute("INSERT INTO upload_sessions(id, tenant_id, user_id, purpose, original_name, mime, size, created_at) "
                 "VALUES (?,?,?,?,?,?,?,?)",
                 (sid, g.tenant["id"], g.user["id"], purpose, name, str(data.get("mime", ""))[:100], size, now()))
    db().commit()
    open(part_path(sid), "wb").close()
    return jsonify(id=sid, chunk_size=CHUNK_SIZE, received=0)


@app.route("/uploads/<sid>/parte", methods=["POST"])
@tenant_required
def upload_chunk(sid):
    s = get_session(sid)
    path = part_path(sid)
    current = received(sid)
    offset = request.args.get("offset", type=int, default=-1)
    length = request.content_length or 0
    # Pedaço fora de ordem: devolve até onde o servidor já tem, para o navegador continuar dali.
    if offset < 0 or offset > current:
        return jsonify(received=current), 409
    if length <= 0 or length > CHUNK_MAX or offset + length > s["size"]:
        return jsonify(error="Pedaço inválido.", received=current), 400
    written = 0
    with open(path, "r+b") as out:
        out.seek(offset)
        out.truncate()  # reenvio de um pedaço: descarta o que veio depois dele
        while True:
            block = request.stream.read(1024 * 1024)
            if not block:
                break
            out.write(block)
            written += len(block)
    return jsonify(received=offset + written), (200 if written == length else 409)


@app.route("/uploads/<sid>", methods=["DELETE", "POST"])
@tenant_required
def upload_cancel(sid):
    get_session(sid)
    discard(sid)
    return jsonify(ok=True)


def discard(sid):
    try:
        os.remove(part_path(sid))
    except FileNotFoundError:
        pass
    db().execute("DELETE FROM upload_sessions WHERE id=?", (sid,))
    db().commit()


def claim(ids, purpose="prova"):
    """Confere que os envios são deste usuário e chegaram completos. Não altera nada."""
    rows = []
    for sid in dict.fromkeys(i for i in ids if i):
        s = db().execute("SELECT * FROM upload_sessions WHERE id=? AND tenant_id=? AND user_id=? AND purpose=?",
                         (sid, g.tenant["id"], g.user["id"], purpose)).fetchone()
        if not s:
            raise UploadError("Um dos arquivos enviados expirou. Envie de novo.")
        if received(sid) != s["size"]:
            raise UploadError(f"O envio de “{s['original_name']}” não terminou. Envie de novo.")
        rows.append(s)
    return rows


def finalize(evidence_id, rows):
    """Move os temporários para o armazenamento definitivo, calcula o hash e registra os arquivos."""
    saved = []
    pos = db().execute("SELECT COALESCE(MAX(position), -1) + 1 FROM files WHERE evidence_id=?",
                       (evidence_id,)).fetchone()[0]
    for s in rows:
        ext = os.path.splitext(s["original_name"])[1].lower()[:10]
        stored = f"{uuid.uuid4().hex}{ext}"
        dest = os.path.join(UPLOADS, stored)
        os.replace(part_path(s["id"]), dest)
        try:
            digest = sha256_file(dest)
            size = os.path.getsize(dest)
            os.chmod(dest, 0o440)
        except OSError:
            unlink_upload(stored)
            raise
        mime = guess_mime(s["original_name"], s["mime"])
        db().execute("INSERT INTO files(evidence_id, stored_name, original_name, mime, kind, size, sha256, "
                     "uploaded_at, position) VALUES (?,?,?,?,?,?,?,?,?)",
                     (evidence_id, stored, s["original_name"], mime, kind_for(mime), size, digest, now(), pos))
        db().execute("DELETE FROM upload_sessions WHERE id=?", (s["id"],))
        pos += 1
        saved.append(f"{s['original_name']} sha256={digest}")
    return saved


def hash_and_discard(sid):
    """Para a verificação de integridade: calcula o hash do envio e apaga o temporário."""
    s = claim([sid], purpose="verificar")[0]
    digest = sha256_file(part_path(sid))
    discard(sid)
    return s["original_name"], digest
