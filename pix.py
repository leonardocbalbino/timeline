"""Geração do BR Code Pix (copia e cola) estático, conforme o manual do Banco Central."""
import re
import unicodedata


def _campo(ident, valor):
    return f"{ident}{len(valor):02d}{valor}"


def _ascii(texto, limite):
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    texto = re.sub(r"[^A-Za-z0-9 .\-]", "", texto).strip()
    return texto[:limite]


def _crc16(dados):
    crc = 0xFFFF
    for byte in dados.encode("utf-8"):
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) if crc & 0x8000 else crc << 1
            crc &= 0xFFFF
    return f"{crc:04X}"


def normalizar_chave(chave):
    """CPF/CNPJ só com dígitos; telefone no formato +55...; e-mail e chave aleatória como vieram."""
    chave = chave.strip().replace(" ", "")
    if chave.startswith("+"):
        return "+" + re.sub(r"\D", "", chave)
    if re.fullmatch(r"[\d.\-/]+", chave):
        return re.sub(r"\D", "", chave)
    return chave


def brcode(chave, nome, cidade, valor, txid, descricao=""):
    chave = normalizar_chave(chave)
    conta = _campo("00", "br.gov.bcb.pix") + _campo("01", chave)
    espaco = 99 - len(conta) - 4
    descricao = _ascii(descricao, espaco) if espaco > 0 else ""
    if descricao:
        conta += _campo("02", descricao)
    txid = re.sub(r"[^A-Za-z0-9]", "", txid)[:25] or "***"
    payload = (_campo("00", "01")
               + _campo("26", conta)
               + _campo("52", "0000")
               + _campo("53", "986")
               + (_campo("54", f"{valor:.2f}") if valor else "")
               + _campo("58", "BR")
               + _campo("59", _ascii(nome, 25) or "RECEBEDOR")
               + _campo("60", _ascii(cidade, 15) or "BRASIL")
               + _campo("62", _campo("05", txid))
               + "6304")
    return payload + _crc16(payload)


def qr_svg_data_uri(payload):
    import segno
    return segno.make(payload, error="m", micro=False).svg_data_uri(scale=6, border=2)
