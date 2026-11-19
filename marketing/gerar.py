"""Gera as imagens de divulgação do Íntegra (HTML com a identidade da marca → PNG).

Uso:  python marketing/gerar.py            (precisa de: pip install playwright; usa o Edge/Chrome instalado)
Saída: marketing/png/*.png  e  static/img/og.png (prévia de link do site)
"""
import os
import sys

from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "marketing", "png")
SITE = "processointegra.com.br"

FONTS = ('<link href="https://fonts.googleapis.com/css2?family=Schibsted+Grotesk:wght@600;700;800&'
         'family=Public+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">')

CSS = """
:root { --ink:#0E1A2B; --ink2:#1B2B44; --muted:#3B4B62; --subtle:#5A6B82; --bg:#F5F6F8; --surface:#fff; --s2:#EEF1F5;
  --border:#E2E6EC; --bs:#C9D1DC; --action:#2443B8; --ver:#0F766E; --verbg:#E3F4F1; --bright:#2DD4BF;
  --hl:#B45309; --hlt:#8A4006; --hlbg:#FDF0E1; --odm:#B7C4D6; --line:#24364F; }
* { box-sizing: border-box; margin: 0; padding: 0; }
html, body { width: 100%; height: 100%; }
body { font-family: 'Public Sans', sans-serif; color: var(--ink); -webkit-font-smoothing: antialiased; overflow: hidden; }
.frame { position: relative; width: 100%; height: 100%; display: flex; flex-direction: column; }
.light { background: var(--bg); } .white { background: #fff; } .dark { background: var(--ink); color: #fff; }
.logo { display: flex; align-items: center; gap: 14px; font: 800 34px/1 'Schibsted Grotesk'; letter-spacing: -.02em; }
.logo svg { width: 46px; height: 46px; }
.eyebrow { font: 500 22px/1.2 'IBM Plex Mono'; letter-spacing: .1em; text-transform: uppercase; color: var(--ver); }
.dark .eyebrow { color: var(--bright); }
h1 { font: 800 92px/1.02 'Schibsted Grotesk'; letter-spacing: -.035em; }
h2 { font: 700 64px/1.06 'Schibsted Grotesk'; letter-spacing: -.03em; }
.lead { font-size: 32px; line-height: 1.45; color: var(--muted); }
.dark .lead { color: var(--odm); }
.mono { font-family: 'IBM Plex Mono'; }
.chip { display: inline-flex; align-items: center; gap: 8px; border-radius: 999px; padding: 6px 16px; font: 600 22px/1.4 'Public Sans';
  background: var(--s2); color: var(--muted); white-space: nowrap; }
.chip.ver { background: var(--verbg); color: var(--ver); } .chip.hl { background: var(--hlbg); color: var(--hlt); }
.card { background: #fff; border: 2px solid var(--border); border-radius: 22px; }
.pop { box-shadow: 0 40px 80px -40px rgba(14,26,43,.35); }
.btn { display: inline-flex; align-items: center; justify-content: center; border-radius: 16px; padding: 26px 40px;
  font: 600 32px/1 'Public Sans'; background: var(--action); color: #fff; }
.foot { display: flex; justify-content: space-between; align-items: center; font-size: 24px; color: var(--subtle); }
.dark .foot { color: var(--odm); }
.pager { font: 500 22px 'IBM Plex Mono'; color: var(--subtle); }
.dark .pager { color: var(--odm); }
/* linha do tempo ilustrativa */
.tl { display: grid; gap: 20px; }
.tl-day { font: 700 28px 'Schibsted Grotesk'; letter-spacing: -.01em; }
.tl-day span { font: 400 22px 'Public Sans'; color: var(--subtle); margin-left: 10px; }
.tl-item { display: grid; grid-template-columns: 92px 40px 1fr; align-items: start; }
.tl-time { font: 500 22px 'IBM Plex Mono'; color: var(--muted); text-align: right; padding-top: 26px; }
.tl-rail { position: relative; align-self: stretch; }
.tl-rail::before { content: ""; position: absolute; left: 19px; top: 0; bottom: -20px; width: 3px; background: var(--bs); }
.tl-item:first-of-type .tl-rail::before { top: 30px; }
.tl-item:last-of-type .tl-rail::before { bottom: auto; height: 30px; }
.tl-rail::after { content: ""; position: absolute; left: 11px; top: 26px; width: 19px; height: 19px; border-radius: 50%;
  background: #fff; border: 3px solid var(--ink); }
.tl-item.hl .tl-rail::after { left: 8px; top: 23px; width: 25px; height: 25px; background: var(--hl); border-color: var(--hl); }
.ev { padding: 22px 26px; display: grid; gap: 14px; }
.ev.hl { box-shadow: 0 0 0 6px var(--hlbg); border-color: #F3D9B8; }
.ev-title { font: 600 27px/1.25 'Public Sans'; }
.ev-chips { display: flex; gap: 10px; flex-wrap: wrap; }
.ev .chip { font-size: 19px; padding: 4px 13px; }
.shots { display: flex; gap: 12px; }
.shots i { width: 92px; height: 120px; border-radius: 12px; background: linear-gradient(180deg, var(--s2), #E3E8EF); border: 2px solid var(--border); }
.player { display: flex; align-items: center; gap: 16px; background: var(--bg); border: 2px solid var(--border); border-radius: 14px; padding: 10px 18px 10px 10px; }
.player b { width: 50px; height: 50px; border-radius: 50%; background: var(--ink); display: grid; place-items: center; }
.player b::after { content: ""; border-left: 15px solid #fff; border-top: 9px solid transparent; border-bottom: 9px solid transparent; margin-left: 4px; }
.player .bar { flex: 1; height: 8px; border-radius: 4px; background: var(--border); position: relative; }
.player .bar::after { content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 38%; border-radius: 4px; background: var(--ink); }
.player .t { font: 500 19px 'IBM Plex Mono'; color: var(--muted); }
.integrity { display: flex; align-items: center; gap: 10px; font: 400 19px 'IBM Plex Mono'; color: var(--ver);
  border-top: 2px solid var(--s2); padding-top: 14px; }
.integrity svg { width: 24px; height: 24px; flex: none; }
"""

LOGO = ('<svg viewBox="0 0 40 40"><rect width="40" height="40" rx="10" fill="{bg}"/>'
        '<line x1="20" y1="9" x2="20" y2="31" stroke="#5B7192" stroke-width="2.4" stroke-linecap="round"/>'
        '<circle cx="20" cy="11" r="3.1" fill="{bg}" stroke="#FFFFFF" stroke-width="2.1"/><circle cx="20" cy="20" r="4.8" fill="#2DD4BF"/>'
        '<path d="M17.9 20.1l1.5 1.5 2.9-3" fill="none" stroke="#0E1A2B" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/>'
        '<circle cx="20" cy="29" r="3.1" fill="{bg}" stroke="#FFFFFF" stroke-width="2.1"/></svg>')
SHIELD = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
          '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/>'
          '<path d="m9 12 2 2 4-4"/></svg>')


def icon(paths, size=40, color="currentColor"):
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" '
            f'stroke-linecap="round" stroke-linejoin="round">{paths}</svg>')


I_CLOCK = '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>'
I_FILE = '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M16 13H8"/><path d="M16 17H8"/>'
I_DOWN = '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" x2="12" y1="15" y2="3"/>'
I_LINK = ('<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/>'
          '<path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>')
I_HASH = '<line x1="4" x2="20" y1="9" y2="9"/><line x1="4" x2="20" y1="15" y2="15"/><line x1="10" x2="8" y1="3" y2="21"/><line x1="16" x2="14" y1="3" y2="21"/>'
I_SHARE = '<circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><line x1="8.59" x2="15.42" y1="13.51" y2="17.49"/><line x1="15.41" x2="8.59" y1="6.51" y2="10.49"/>'


def logo(dark=False):
    return f'<div class="logo">{LOGO.format(bg="#1B2B44" if dark else "#0E1A2B")}<span>íntegra</span></div>'


def timeline(compact=False):
    shots = "<div class=shots><i></i><i></i></div>" if not compact else ""
    return f"""
<div class="tl">
  <div class="tl-day">Terça-feira, 12 de março <span>3 registros</span></div>
  <div>
    <div class="tl-item"><div class="tl-time">09:14</div><div class="tl-rail"></div>
      <div class="card ev"><div class="ev-title">Mensagem confirmando o horário</div>
        <div class="ev-chips"><span class="chip">WhatsApp</span><span class="chip">2 imagens</span></div>{shots}</div></div>
    <div style="height:20px"></div>
    <div class="tl-item hl"><div class="tl-time">14:02</div><div class="tl-rail"></div>
      <div class="card ev hl"><div class="ev-title">Áudio com a ameaça</div>
        <div class="ev-chips"><span class="chip hl">★ Destaque</span><span class="chip">0:48</span></div>
        <div class="player"><b></b><span class="bar"></span><span class="t">0:18 / 0:48</span></div></div></div>
    <div style="height:20px"></div>
    <div class="tl-item"><div class="tl-time">18:30</div><div class="tl-rail"></div>
      <div class="card ev"><div class="ev-title">Vídeo da câmera da portaria</div>
        <div class="ev-chips"><span class="chip">Câmera de segurança</span><span class="chip">1 vídeo</span></div>
        <div class="integrity">{SHIELD}Íntegro desde o envio · SHA-256 9f2c…e41a</div></div></div>
  </div>
</div>"""


def page(body, cls="light"):
    return f"<!doctype html><html lang=pt-BR><head><meta charset=utf-8>{FONTS}<style>{CSS}</style></head><body><div class='frame {cls}'>{body}</div></body></html>"


# ------------------------------------------------------------ peças
PIECES = []


def piece(name, w, h):
    def deco(fn):
        PIECES.append((name, w, h, fn))
        return fn
    return deco


@piece("og", 1200, 630)
def og():
    return page(f"""
<div style="display:grid;grid-template-columns:1.05fr .95fr;grid-template-rows:100%;gap:40px;padding:56px 64px 0;height:100%">
  <div style="display:flex;flex-direction:column;gap:24px">
    {logo()}
    <h1 style="font-size:58px">Provas em ordem, do fato ao processo.</h1>
    <p class="lead" style="font-size:24px">Prints, áudios e vídeos numa linha do tempo, com impressão digital SHA-256 de cada arquivo.</p>
    <span class="mono" style="font-size:24px;color:var(--action);margin-top:auto;margin-bottom:60px">{SITE}</span>
  </div>
  <div style="zoom:.72;width:640px;align-self:start"><div class="card pop" style="padding:30px;border-radius:30px">{timeline(compact=True)}</div></div>
</div>""")


def ig_slide(n, total, inner, cls="light"):
    return page(f"""
<div style="padding:84px 84px 72px;display:flex;flex-direction:column;gap:46px;height:100%">
  <div class="foot">{logo(cls == 'dark')}<span class="pager">{n:02d}/{total:02d}</span></div>
  {inner}
</div>""", cls)


@piece("instagram-1", 1080, 1350)
def ig1():
    return ig_slide(1, 5, f"""
  <h1>Prints, áudios e vídeos espalhados no celular?</h1>
  <p class="lead">Quando o caso chega ao advogado, a cronologia é o que convence. O Íntegra coloca tudo em ordem, com prova de que nada foi alterado.</p>
  <div style="margin-top:auto;zoom:.86" class="card pop"><div style="padding:30px">{timeline(compact=True)}</div></div>""")


@piece("instagram-2", 1080, 1350)
def ig2():
    return ig_slide(2, 5, f"""
  <span class="eyebrow">Linha do tempo</span>
  <h2>Cada prova no dia e na hora em que aconteceu.</h2>
  <p class="lead">Envie vários arquivos de uma vez. A data é sugerida pelo nome do arquivo do WhatsApp, do print ou da câmera.</p>
  <div style="margin-top:auto;zoom:.84">{timeline()}</div>""", "white")


@piece("instagram-3", 1080, 1350)
def ig3():
    return ig_slide(3, 5, f"""
  <span class="eyebrow">Integridade</span>
  <h2 style="font-size:72px">Uma impressão digital para cada arquivo.</h2>
  <p class="lead">No envio, o Íntegra calcula o código SHA-256 do arquivo. Se alguém mudar um único pixel, o código muda — e a verificação mostra na hora.</p>
  <div style="margin-top:auto;display:grid;gap:22px">
    <div class="card" style="padding:30px 34px;display:grid;gap:14px;border-color:#BFE3DC">
      <div style="display:flex;gap:14px;align-items:center;color:var(--ver);font:700 32px 'Schibsted Grotesk'">{SHIELD.replace('<svg ', '<svg width=40 height=40 ')}Arquivo íntegro</div>
      <div class="mono" style="font-size:24px;color:var(--ver);line-height:1.5">9f2c4a71d0b8e3f65a9c12e7d44b0f8a<br>3c6e19d57b2a80f4e3c1d96a7b05e41a</div>
      <div style="font-size:24px;color:var(--muted)">Idêntico ao registrado em 12/03 às 18:31</div>
    </div>
    <div class="card" style="padding:30px 34px;display:grid;gap:10px;border-color:#F5C9C4;background:#FFFBFA">
      <div style="font:700 30px 'Schibsted Grotesk';color:#B42318">Cópia alterada</div>
      <div style="font-size:24px;color:var(--muted)">Não corresponde a nenhuma prova registrada.</div>
    </div>
  </div>""")


@piece("instagram-4", 1080, 1350)
def ig4():
    row = lambda ic, t, d: (f'<div style="display:grid;grid-template-columns:72px 1fr;gap:26px;align-items:start;padding:34px 0;'
                            f'border-top:2px solid var(--line)"><div style="color:var(--bright)">{icon(ic, 56)}</div>'
                            f'<div style="display:grid;gap:8px"><div style="font:700 38px \'Schibsted Grotesk\'">{t}</div>'
                            f'<div class="lead" style="font-size:28px">{d}</div></div></div>')
    return ig_slide(4, 5, f"""
  <span class="eyebrow">Para o advogado</span>
  <h2>Pronto para entregar, do jeito que ele precisa.</h2>
  <div style="margin-top:auto">
    {row(I_FILE, 'Relatório em PDF', 'Data, hora, descrição e hash de cada prova, em ordem cronológica.')}
    {row(I_DOWN, 'Pacote ZIP', 'Todos os originais, organizados, com manifesto de hashes.')}
    {row(I_LINK, 'Link somente leitura', 'O advogado vê a linha do tempo sem criar conta. Você revoga quando quiser.')}
  </div>""", "dark")


@piece("instagram-5", 1080, 1350)
def ig5():
    return ig_slide(5, 5, f"""
  <span class="eyebrow">Comece hoje</span>
  <h1 style="font-size:100px">Quanto antes registrar, melhor.</h1>
  <p class="lead">A data de envio e o hash ficam guardados desde o primeiro dia. Plano Free sem cartão; Pro quando o caso crescer.</p>
  <div style="margin-top:auto;display:grid;gap:26px;justify-items:start">
    <span class="btn" style="font-size:36px;padding:30px 46px">Criar conta grátis</span>
    <span class="mono" style="font-size:34px;color:var(--action)">{SITE}</span>
    <span style="font-size:22px;color:var(--subtle)">Organiza e preserva provas. Não substitui orientação jurídica.</span>
  </div>""")


def story(inner, cls="light"):
    return page(f"""
<div style="padding:200px 84px 260px;display:flex;flex-direction:column;justify-content:center;gap:50px;height:100%">
  {logo(cls == 'dark')}
  {inner}
</div>""", cls)


@piece("story-1", 1080, 1920)
def st1():
    return story(f"""
  <h1 style="font-size:104px">As provas do seu caso, em ordem.</h1>
  <p class="lead" style="font-size:36px">Prints, áudios e vídeos numa linha do tempo, prontos para o advogado.</p>
  <div class="card pop" style="padding:36px;margin-top:20px;zoom:1.08">{timeline()}</div>""")


@piece("story-2", 1080, 1920)
def st2():
    return story(f"""
  <span class="eyebrow" style="font-size:26px">Integridade</span>
  <h1 style="font-size:96px">Cada arquivo com impressão digital SHA-256.</h1>
  <p class="lead" style="font-size:36px">Se o arquivo for alterado, por menor que seja a mudança, o código muda. Você confere em segundos.</p>
  <div style="display:grid;gap:26px;margin-top:30px">
    <div style="display:flex;align-items:center;gap:22px;color:var(--bright);font:700 46px 'Schibsted Grotesk'">{SHIELD.replace('<svg ', '<svg width=64 height=64 ')}Íntegro desde o envio</div>
    <div class="mono" style="font-size:32px;line-height:1.55;color:var(--odm)">9f2c4a71d0b8e3f65a9c12e7d44b0f8a<br>3c6e19d57b2a80f4e3c1d96a7b05e41a</div>
  </div>""", "dark")


@piece("story-3", 1080, 1920)
def st3():
    return story(f"""
  <span class="eyebrow" style="font-size:26px">Comece grátis</span>
  <h1 style="font-size:110px">Organize suas provas hoje.</h1>
  <p class="lead" style="font-size:36px">Plano Free sem cartão e sem prazo. Pro via Pix quando precisar.</p>
  <div style="display:grid;gap:22px;margin-top:10px">
    <div style="display:flex;gap:16px;align-items:center;font-size:34px">{icon(I_CLOCK, 44, '#0F766E')}Linha do tempo por dia e hora</div>
    <div style="display:flex;gap:16px;align-items:center;font-size:34px">{icon(I_HASH, 44, '#0F766E')}Hash SHA-256 de cada arquivo</div>
    <div style="display:flex;gap:16px;align-items:center;font-size:34px">{icon(I_SHARE, 44, '#0F766E')}Link para o advogado</div>
  </div>
  <!-- espaço livre para o adesivo de link do Instagram -->
  <div style="margin-top:120px;display:grid;gap:18px;justify-items:center;text-align:center">
    <span class="mono" style="font-size:40px;color:var(--action)">{SITE}</span>
    <span style="font-size:24px;color:var(--subtle)">Toque no link · Não substitui orientação jurídica.</span>
  </div>""")


def main(only=None):
    os.makedirs(OUT, exist_ok=True)
    with sync_playwright() as pw:
        browser = None
        for channel in ("msedge", "chrome", None):
            try:
                browser = pw.chromium.launch(channel=channel) if channel else pw.chromium.launch()
                break
            except Exception:  # noqa: BLE001 - tenta o próximo navegador
                continue
        for name, w, h, fn in PIECES:
            if only and name not in only:
                continue
            pg = browser.new_page(viewport={"width": w, "height": h}, device_scale_factor=1)
            pg.set_content(fn(), wait_until="networkidle")
            pg.evaluate("document.fonts.ready")
            pg.wait_for_timeout(300)
            dest = os.path.join(ROOT, "static", "img", "og.png") if name == "og" else os.path.join(OUT, f"{name}.png")
            pg.screenshot(path=dest)
            pg.close()
            print("ok", os.path.relpath(dest, ROOT))
        browser.close()


if __name__ == "__main__":
    main(set(sys.argv[1:]) or None)
