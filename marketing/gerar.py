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


# ------------------------------------------------------------ divulgação do site + app
# Troque para True quando o app estiver publicado nas lojas e gere de novo.
APP_NAS_LOJAS = False
APP_LINHA = "Baixe para Android e iPhone" if APP_NAS_LOJAS else "App para Android e iPhone em breve"

DEVICE_CSS = """
.phone { background:#0B1422; border-radius:62px; padding:15px; box-shadow:0 50px 90px -40px rgba(14,26,43,.55); flex:none; }
.phone-screen { background:var(--bg); color:var(--ink); border-radius:48px; overflow:hidden; display:flex; flex-direction:column; }
.phone-status { display:flex; justify-content:space-between; padding:22px 34px 8px; font:600 20px 'Public Sans'; }
.phone-status i { width:120px; height:30px; background:#0B1422; border-radius:20px; }
.phone-bar { display:flex; align-items:center; justify-content:space-between; padding:14px 26px 16px; background:#fff;
  border-bottom:2px solid var(--border); }
.phone-bar .logo { font-size:26px; gap:10px; } .phone-bar .logo svg { width:34px; height:34px; }
.phone-bar .ic { display:flex; gap:18px; color:var(--ink); }
.phone-body { padding:22px 20px; display:grid; gap:16px; align-content:start; flex:1; }
.phone-title { font:700 30px/1.15 'Schibsted Grotesk'; letter-spacing:-.02em; }
.phone-meta { font:400 18px 'Public Sans'; color:var(--subtle); }
.fab { margin:0 20px 26px; background:var(--action); color:#fff; border-radius:16px; text-align:center; padding:20px; font:600 22px 'Public Sans'; }
.laptop { flex:none; }
.laptop-screen { background:#fff; border:14px solid #0B1422; border-bottom-width:18px; border-radius:22px 22px 0 0; overflow:hidden; }
.laptop-base { height:22px; background:linear-gradient(#C9D1DC,#AEB8C6); border-radius:0 0 18px 18px; margin:0 -40px; }
.browser { display:flex; align-items:center; gap:12px; padding:12px 16px; background:var(--s2); border-bottom:2px solid var(--border); }
.browser b { width:12px; height:12px; border-radius:50%; background:#C9D1DC; }
.browser .url { flex:1; background:#fff; border-radius:999px; padding:6px 16px; font:400 15px 'IBM Plex Mono'; color:var(--muted); }
.web-head { display:flex; align-items:center; gap:22px; padding:14px 22px; border-bottom:2px solid var(--border); font:500 15px 'Public Sans'; color:var(--muted); }
.web-head .logo { font-size:20px; gap:8px; } .web-head .logo svg { width:26px; height:26px; }
.web-head .act { background:var(--s2); color:var(--ink); padding:5px 10px; border-radius:8px; font-weight:600; }
.web-body { display:grid; grid-template-columns:150px 1fr; gap:22px; padding:20px 22px; background:var(--bg); }
.web-index { display:grid; gap:6px; align-content:start; font:400 14px 'Public Sans'; color:var(--muted); }
.web-index .on { background:#fff; border:2px solid var(--border); border-radius:10px; padding:7px 10px; color:var(--ink); font-weight:600; }
.web-index span { padding:7px 10px; }
.sheet { background:#fff; border-radius:30px 30px 0 0; padding:26px 24px 34px; display:grid; gap:22px; box-shadow:0 -10px 40px rgba(14,26,43,.18); }
.sheet-apps { display:grid; grid-template-columns:repeat(4,1fr); gap:16px; text-align:center; font:500 17px 'Public Sans'; color:var(--muted); }
.sheet-apps i { display:block; width:76px; height:76px; border-radius:22px; background:var(--s2); margin:0 auto 10px; }
.sheet-apps .me i { background:none; outline:5px solid var(--bright); outline-offset:4px; }
.sheet-apps .me { color:var(--ink); font-weight:700; }
.shot-chat { display:grid; gap:12px; padding:22px 20px; }
.bubble { max-width:78%; padding:14px 18px; border-radius:20px; font:400 19px/1.35 'Public Sans'; background:#fff; border:2px solid var(--border); }
.bubble.me { justify-self:end; background:#E7F6EC; border-color:#CDEBD6; }
.bubble.media { padding:8px; } .bubble.media i { display:block; width:240px; height:150px; border-radius:14px; background:linear-gradient(180deg,#DCE3EC,#C9D1DC); }
.arrow { font:700 64px 'Schibsted Grotesk'; color:var(--bright); }
.stores { display:inline-flex; align-items:center; gap:14px; font:600 26px 'Public Sans'; }
.stores .tag { font:500 18px 'IBM Plex Mono'; letter-spacing:.06em; text-transform:uppercase; padding:6px 12px; border-radius:999px;
  background:var(--s2); color:var(--muted); }
.dark .stores .tag { background:var(--ink2); color:var(--odm); }
"""

I_SHIELD = ('<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/>'
            '<path d="m9 12 2 2 4-4"/>')
I_USER = '<path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>'
I_PHONE = '<rect width="14" height="20" x="5" y="2" rx="2" ry="2"/><path d="M12 18h.01"/>'
I_LAPTOP = '<path d="M20 16V7a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v9m16 0H4m16 0 1.28 2.55a1 1 0 0 1-.9 1.45H3.62a1 1 0 0 1-.9-1.45L4 16"/>'
I_CHECK = '<path d="M20 6 9 17l-5-5"/>'


def page2(body, cls="light"):
    return page(body, cls).replace("</style>", DEVICE_CSS + "</style>", 1)


def phone(body, w=430, h=880, bar=True, fab=None, overlay=""):
    head = (f'<div class="phone-bar">{logo()}<span class="ic">{icon(I_SHIELD, 26)}{icon(I_USER, 26)}</span></div>' if bar else "")
    return (f'<div class="phone" style="width:{w}px"><div class="phone-screen" style="height:{h}px;position:relative">'
            f'<div class="phone-status"><span>9:41</span><i></i><span>100%</span></div>{head}'
            f'<div class="phone-body">{body}</div>{f"<div class=fab>{fab}</div>" if fab else ""}{overlay}</div></div>')


def app_timeline():
    return (f'<div><div class="phone-title">Ação trabalhista — Empresa X</div>'
            f'<div class="phone-meta" style="margin-top:6px"><b style="color:var(--ink)">5</b> registros · 8 arquivos</div></div>'
            f'<div style="zoom:.62">{timeline(compact=True)}</div>')


def app_share_save():
    files = "".join(f'<div style="display:flex;gap:10px;align-items:center;font-size:17px;color:var(--muted)">{icon(I_FILE, 20, "#5A6B82")}{n}</div>'
                    for n in ("IMG-20250312-WA0014.jpg", "PTT-20250312-WA0021.opus", "IMG-20250312-WA0015.jpg"))
    proc = lambda t, n: (f'<div class="card" style="padding:18px 20px;display:flex;justify-content:space-between;align-items:center">'
                         f'<div><div style="font:600 21px \'Public Sans\'">{t}</div><div style="font-size:16px;color:var(--subtle)">{n}</div></div>'
                         f'<span style="font:700 26px \'Schibsted Grotesk\';color:var(--subtle)">›</span></div>')
    return (f'<div class="card" style="padding:18px 20px;display:grid;gap:10px">'
            f'<div style="font:600 19px \'Public Sans\'">3 arquivos recebidos · 4,2 MB</div>{files}</div>'
            f'<div class="phone-title" style="font-size:26px">Em qual processo salvar?</div>'
            f'{proc("Ação trabalhista — Empresa X", "5 provas")}{proc("Condomínio — barulho", "2 provas")}')


def chat_with_sheet():
    chat = ('<div class="shot-chat"><div class="bubble">Te mando o print da conversa de ontem</div>'
            '<div class="bubble media"><i></i></div><div class="bubble me">Recebi, obrigado!</div></div>')
    sheet = (f'<div class="sheet" style="position:absolute;left:0;right:0;bottom:0">'
             f'<div style="font:600 22px \'Public Sans\'">Compartilhar com</div>'
             f'<div class="sheet-apps"><span><i></i>E-mail</span><span><i></i>Drive</span>'
             f'<span class="me">{LOGO.format(bg="#0E1A2B").replace("<svg ", "<svg style=\"display:block;width:76px;height:76px;margin:0 auto 10px;border-radius:22px;outline:5px solid #2DD4BF;outline-offset:4px\" ")}Íntegra</span>'
             f'<span><i></i>Mensagens</span></div></div>')
    return phone(chat, bar=False, overlay=sheet)


def laptop(w=900):
    return (f'<div class="laptop" style="width:{w}px"><div class="laptop-screen">'
            f'<div class="browser"><b></b><b></b><b></b><span class="url">🔒 {SITE}</span></div>'
            f'<div class="web-head">{logo()}<span class="act">Processos</span><span>Verificar arquivo</span><span>Plano</span></div>'
            f'<div class="web-body"><div class="web-index"><span style="font:500 12px \'IBM Plex Mono\';letter-spacing:.08em">DATAS</span>'
            f'<span class="on">ter, 12 mar · 3</span><span>qua, 13 mar · 1</span><span>sex, 15 mar · 1</span></div>'
            f'<div style="zoom:.6">{timeline()}</div></div></div><div class="laptop-base"></div></div>')


def stores_line(dark=False):
    return f'<div class="stores">{icon(I_PHONE, 30)}<span>{APP_LINHA}</span></div>'


@piece("divulga-post-1", 1080, 1350)
def dp1():
    return page2(f"""
<div style="padding:84px 84px 0;display:flex;flex-direction:column;gap:36px;height:100%">
  <div class="foot">{logo()}<span class="pager">01/03</span></div>
  <span class="eyebrow">No computador e no celular</span>
  <h2>Suas provas em ordem, onde você estiver.</h2>
  <p class="lead">Organize no site. Registre na hora pelo app. Tudo na mesma linha do tempo, com o hash de cada arquivo.</p>
  <div style="position:relative;margin-top:auto;height:640px">
    <div style="position:absolute;left:-10px;top:40px;zoom:.92">{laptop()}</div>
    <div style="position:absolute;right:-20px;top:0;zoom:.78">{phone(app_timeline(), fab='+ Nova prova')}</div>
  </div>
</div>""")


@piece("divulga-post-2", 1080, 1350)
def dp2():
    return page2(f"""
<div style="padding:84px 84px 0;display:flex;flex-direction:column;gap:34px;height:100%">
  <div class="foot">{logo(True)}<span class="pager">02/03</span></div>
  <span class="eyebrow">Do WhatsApp para o processo</span>
  <h2>Recebeu um print ou um áudio? Mande direto para o Íntegra.</h2>
  <p class="lead">Toque em Compartilhar, escolha o Íntegra e o processo. A data sai do nome do arquivo e o hash é registrado no envio.</p>
  <div style="display:flex;align-items:center;justify-content:center;gap:22px;margin-top:auto;margin-bottom:70px">
    <div style="zoom:.58">{chat_with_sheet()}</div>
    <div class="arrow">→</div>
    <div style="zoom:.58">{phone(app_share_save(), bar=False)}</div>
  </div>
</div>""", "dark")


@piece("divulga-post-3", 1080, 1350)
def dp3():
    item = lambda t: f'<div style="display:flex;gap:16px;align-items:center;font-size:30px">{icon(I_CHECK, 34, "#0F766E")}{t}</div>'
    return page2(f"""
<div style="padding:84px;display:grid;grid-template-columns:1fr 360px;grid-template-rows:auto 1fr;gap:40px 30px;height:100%">
  <div class="foot" style="grid-column:1/-1">{logo()}<span class="pager">03/03</span></div>
  <div style="display:flex;flex-direction:column;gap:34px">
    <span class="eyebrow">Comece hoje</span>
    <h2 style="font-size:70px">Grátis no site. No bolso com o app.</h2>
    <div style="display:grid;gap:18px">{item('Linha do tempo por dia e hora')}{item('Hash SHA-256 de cada arquivo')}{item('Relatório e link para o advogado')}</div>
    <div style="margin-top:auto;display:grid;gap:22px;justify-items:start">
      <span class="btn" style="font-size:32px">Criar conta grátis</span>
      <span class="mono" style="font-size:32px;color:var(--action)">{SITE}</span>
      {stores_line()}
      <span style="font-size:20px;color:var(--subtle)">Organiza e preserva provas. Não substitui orientação jurídica.</span>
    </div>
  </div>
  <div style="zoom:.82;align-self:center">{phone(app_timeline(), fab='+ Nova prova')}</div>
</div>""", "white")


def story2(inner, cls="light"):
    return page2(f"""
<div style="padding:190px 84px 250px;display:flex;flex-direction:column;justify-content:center;gap:44px;height:100%">
  {logo(cls == 'dark')}
  {inner}
</div>""", cls)


@piece("divulga-story-1", 1080, 1920)
def ds1():
    return story2(f"""
  <span class="eyebrow" style="font-size:26px">No computador e no celular</span>
  <h1 style="font-size:96px">Suas provas em ordem, onde você estiver.</h1>
  <div style="position:relative;height:760px;margin-top:10px">
    <div style="position:absolute;left:-40px;top:60px;zoom:1">{laptop(880)}</div>
    <div style="position:absolute;right:-30px;top:0;zoom:.86">{phone(app_timeline(), fab='+ Nova prova')}</div>
  </div>""")


@piece("divulga-story-2", 1080, 1920)
def ds2():
    return story2(f"""
  <span class="eyebrow" style="font-size:26px">Do WhatsApp para o processo</span>
  <h1 style="font-size:92px">Compartilhe direto para o Íntegra.</h1>
  <p class="lead" style="font-size:34px">Print, áudio ou vídeo: escolha o processo e pronto. Data sugerida e hash registrado.</p>
  <div style="display:flex;align-items:center;justify-content:center;gap:18px">
    <div style="zoom:.8">{chat_with_sheet()}</div>
    <div style="zoom:.8">{phone(app_share_save(), bar=False)}</div>
  </div>""", "dark")


@piece("divulga-story-3", 1080, 1920)
def ds3():
    return story2(f"""
  <span class="eyebrow" style="font-size:26px">Comece grátis</span>
  <h1 style="font-size:104px">Organize suas provas hoje.</h1>
  <div style="display:flex;gap:40px;align-items:center">
    <div style="zoom:.92">{phone(app_timeline(), fab='+ Nova prova')}</div>
    <div style="display:grid;gap:26px">
      <div style="display:flex;gap:14px;align-items:center;font-size:30px">{icon(I_LAPTOP, 40, '#0F766E')}No site, grátis</div>
      <div style="display:flex;gap:14px;align-items:center;font-size:30px">{icon(I_PHONE, 40, '#0F766E')}{'No Android e iPhone' if APP_NAS_LOJAS else 'App chegando'}</div>
      <div style="display:flex;gap:14px;align-items:center;font-size:30px">{icon(I_HASH, 40, '#0F766E')}Hash de cada arquivo</div>
    </div>
  </div>
  <div style="display:grid;gap:16px;justify-items:center;text-align:center;margin-top:20px">
    <span class="mono" style="font-size:42px;color:var(--action)">{SITE}</span>
    {stores_line()}
    <span style="font-size:22px;color:var(--subtle)">Não substitui orientação jurídica.</span>
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
