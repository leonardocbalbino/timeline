(function () {
  'use strict';

  var SVG = function (paths, size) {
    size = size || 16;
    return '<svg class="icon" width="' + size + '" height="' + size + '" viewBox="0 0 24 24" fill="none" stroke="currentColor" ' +
      'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + paths + '</svg>';
  };
  var ICON = {
    play: '<polygon points="6 3 20 12 6 21 6 3"/>',
    pause: '<rect x="14" y="4" width="4" height="16" rx="1"/><rect x="6" y="4" width="4" height="16" rx="1"/>',
    check: '<path d="M20 6 9 17l-5-5"/>',
    eye: '<path d="M2.062 12.348a1 1 0 0 1 0-.696 10.75 10.75 0 0 1 19.876 0 1 1 0 0 1 0 .696 10.75 10.75 0 0 1-19.876 0"/><circle cx="12" cy="12" r="3"/>',
    eyeOff: '<path d="M10.733 5.076a10.744 10.744 0 0 1 11.205 6.575 1 1 0 0 1 0 .696 10.747 10.747 0 0 1-1.444 2.49"/><path d="M14.084 14.158a3 3 0 0 1-4.242-4.242"/><path d="M17.479 17.499a10.75 10.75 0 0 1-15.417-5.151 1 1 0 0 1 0-.696 10.75 10.75 0 0 1 4.446-5.143"/><path d="m2 2 20 20"/>',
    file: '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/>',
    mic: '<path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" x2="12" y1="19" y2="22"/>',
    video: '<path d="m16 13 5.223 3.482a.5.5 0 0 0 .777-.416V7.87a.5.5 0 0 0-.752-.432L16 10.5"/><rect x="2" y="6" width="14" height="12" rx="2"/>',
    shield: '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/><path d="m9 12 2 2 4-4"/>'
  };
  var $$ = function (sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); };
  function pad(n) { return String(n).padStart(2, '0'); }
  function mmss(s) { s = Math.max(0, Math.floor(s || 0)); return Math.floor(s / 60) + ':' + pad(s % 60); }
  function humanSize(n) {
    var u = ['B', 'KB', 'MB', 'GB'], i = 0;
    while (n >= 1024 && i < u.length - 1) { n /= 1024; i++; }
    return (i ? n.toFixed(1) : n) + ' ' + u[i];
  }

  // ------------------------------------------------------------ lightbox com galeria por prova
  var lb = document.getElementById('lightbox');
  var galeria = [], atual = 0;
  function mostrar(i) {
    atual = (i + galeria.length) % galeria.length;
    var t = galeria[atual];
    lb.querySelector('img').src = t.getAttribute('data-src');
    lb.querySelector('img').alt = t.getAttribute('data-caption') || '';
    lb.querySelector('.lb-caption').textContent = (galeria.length > 1 ? (atual + 1) + ' / ' + galeria.length + ' · ' : '') + (t.getAttribute('data-caption') || '');
    lb.querySelector('.lb-prev').hidden = lb.querySelector('.lb-next').hidden = galeria.length < 2;
  }
  function fecharLb() { lb.hidden = true; lb.querySelector('img').src = ''; if (galeria[atual]) galeria[atual].focus(); }
  document.addEventListener('click', function (e) {
    var t = e.target.closest('.thumb[data-src]');
    if (t) {
      galeria = $$('.thumb[data-gal="' + t.getAttribute('data-gal') + '"]');
      lb.hidden = false;
      mostrar(galeria.indexOf(t));
      lb.querySelector('.lb-close').focus();
      return;
    }
    if (lb && !lb.hidden) {
      if (e.target.closest('.lb-prev')) mostrar(atual - 1);
      else if (e.target.closest('.lb-next')) mostrar(atual + 1);
      else if (e.target.closest('.lb-close') || e.target === lb) fecharLb();
    }
  });
  document.addEventListener('keydown', function (e) {
    if (lb && !lb.hidden) {
      if (e.key === 'Escape') fecharLb();
      if (e.key === 'ArrowLeft') mostrar(atual - 1);
      if (e.key === 'ArrowRight') mostrar(atual + 1);
    } else if (e.key === 'Escape') {
      $$('details.menu[open], details.popover[open]').forEach(function (d) { d.open = false; });
    }
  });

  // ------------------------------------------------------------ menus e popovers fecham ao clicar fora
  document.addEventListener('click', function (e) {
    $$('details.menu[open], details.popover[open]').forEach(function (d) { if (!d.contains(e.target)) d.open = false; });
  });

  // ------------------------------------------------------------ confirmação, impressão
  document.addEventListener('click', function (e) {
    var b = e.target.closest('[data-confirmar]');
    if (b && !confirm(b.getAttribute('data-confirmar'))) e.preventDefault();
    if (e.target.closest('[data-imprimir]')) window.print();
  });

  // ------------------------------------------------------------ copiar (link, Pix, hash, mensagem)
  function copiado(botao) {
    var orig = botao.innerHTML, label = botao.getAttribute('aria-label');
    var temTexto = botao.textContent.trim().length > 0;
    botao.innerHTML = SVG(ICON.check, 16) + (temTexto ? 'Copiado' : '');
    if (label) botao.setAttribute('aria-label', 'Copiado');
    setTimeout(function () { botao.innerHTML = orig; if (label) botao.setAttribute('aria-label', label); }, 1600);
  }
  function copiar(texto, botao) {
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(texto).then(function () { copiado(botao); });
      return;
    }
    var t = document.createElement('textarea');
    t.value = texto; t.setAttribute('readonly', ''); t.style.position = 'fixed'; t.style.opacity = '0';
    document.body.appendChild(t); t.select();
    try { document.execCommand('copy'); copiado(botao); } catch (err) { /* sem suporte */ }
    document.body.removeChild(t);
  }
  document.addEventListener('click', function (e) {
    var b = e.target.closest('[data-copiar], [data-copiar-texto]');
    if (!b) return;
    var alvo = b.getAttribute('data-copiar');
    copiar(alvo ? document.getElementById(alvo).value : b.getAttribute('data-copiar-texto'), b);
  });

  // ------------------------------------------------------------ mostrar / ocultar senha
  $$('.password').forEach(function (box) {
    var input = box.querySelector('input');
    var b = document.createElement('button');
    b.type = 'button';
    b.setAttribute('aria-label', 'Mostrar senha');
    b.innerHTML = SVG(ICON.eye, 18);
    b.addEventListener('click', function (e) {
      e.preventDefault();
      var ver = input.type === 'password';
      input.type = ver ? 'text' : 'password';
      b.setAttribute('aria-label', ver ? 'Ocultar senha' : 'Mostrar senha');
      b.innerHTML = SVG(ver ? ICON.eyeOff : ICON.eye, 18);
    });
    box.appendChild(b);
  });

  // ------------------------------------------------------------ filtros automáticos
  $$('form[data-autofiltro]').forEach(function (f) {
    f.addEventListener('change', function (e) {
      var el = e.target;
      if (el.type === 'date') return; // o período é aplicado pelo botão do popover
      if (el.tagName === 'SELECT' || el.type === 'checkbox') f.submit();
    });
    var busca = f.querySelector('input[type=search]');
    if (busca) busca.addEventListener('search', function () { if (!busca.value) f.submit(); });
  });
  $$('select[data-autoenvio]').forEach(function (s) { s.addEventListener('change', function () { s.form.submit(); }); });

  // ------------------------------------------------------------ índice de datas (destaca o dia visível)
  var secoes = $$('[data-dia-secao]');
  if (secoes.length && 'IntersectionObserver' in window) {
    var links = $$('.tl-index a[data-dia], .tl-chips a[data-dia]');
    var chips = document.querySelector('.tl-chips');
    var visiveis = {};
    var marcar = function (id) {
      links.forEach(function (a) {
        var on = a.getAttribute('data-dia') === id;
        a.classList.toggle('active', on);
        if (on) a.setAttribute('aria-current', 'true'); else a.removeAttribute('aria-current');
        if (on && chips && chips.contains(a)) chips.scrollLeft = a.offsetLeft - chips.offsetLeft - 16;
      });
    };
    var obs = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) { visiveis[en.target.id] = en.isIntersecting ? en.boundingClientRect.top : undefined; });
      var primeiro = secoes.filter(function (s) { return visiveis[s.id] !== undefined; })[0];
      if (primeiro) marcar(primeiro.id);
    }, { rootMargin: '-80px 0px -55% 0px' });
    secoes.forEach(function (s) { obs.observe(s); });
    marcar(secoes[0].id);
  }

  // ------------------------------------------------------------ linha do tempo horizontal
  var htl = document.querySelector('[data-htl]');
  if (htl) {
    var trilho = htl.querySelector('.htl-track');
    var ant = htl.querySelector('.htl-nav.prev'), prox = htl.querySelector('.htl-nav.next');
    var regua = htl.querySelector('input[type=range]');
    var arrastando = false;
    var atualizar = function () {
      var max = trilho.scrollWidth - trilho.clientWidth;
      ant.disabled = trilho.scrollLeft <= 2;
      prox.disabled = trilho.scrollLeft >= max - 2;
      if (regua) {
        regua.parentNode.hidden = max <= 0;
        if (!arrastando) regua.value = max > 0 ? Math.round(trilho.scrollLeft / max * 1000) : 0;
      }
    };
    var passo = function (dir) { trilho.scrollBy({ left: dir * trilho.clientWidth * 0.8, behavior: 'smooth' }); };
    ant.addEventListener('click', function () { passo(-1); });
    prox.addEventListener('click', function () { passo(1); });
    trilho.addEventListener('scroll', atualizar, { passive: true });
    window.addEventListener('resize', atualizar);
    trilho.addEventListener('keydown', function (e) {
      if (e.target !== trilho) return;
      if (e.key === 'ArrowRight') { passo(1); e.preventDefault(); }
      if (e.key === 'ArrowLeft') { passo(-1); e.preventDefault(); }
    });
    if (regua) {
      regua.addEventListener('input', function () {
        arrastando = true;
        trilho.style.scrollBehavior = 'auto';
        trilho.scrollLeft = regua.value / 1000 * (trilho.scrollWidth - trilho.clientWidth);
        trilho.style.scrollBehavior = '';
      });
      regua.addEventListener('change', function () { arrastando = false; });
    }
    var irPara = function (id) {
      var el = document.getElementById(id);
      if (!el || !trilho.contains(el)) return false;
      trilho.scrollTo({ left: el.offsetLeft - trilho.offsetLeft - 8, behavior: 'smooth' });
      $$('.tl-chips a[data-dia]').forEach(function (a) { a.classList.toggle('active', a.getAttribute('data-dia') === id); });
      return true;
    };
    $$('.tl-chips a[data-dia]').forEach(function (a) {
      a.addEventListener('click', function (e) { if (irPara(a.getAttribute('data-dia'))) e.preventDefault(); });
    });
    if (location.hash) {
      var alvo = document.getElementById(location.hash.slice(1));
      if (alvo && trilho.contains(alvo)) {
        var item = alvo.closest('.htl-item') || alvo;
        trilho.scrollLeft = item.offsetLeft - trilho.offsetLeft - 8;
      }
    }
    atualizar();
  }

  // ------------------------------------------------------------ player de áudio
  $$('[data-player]').forEach(function (box) {
    var audio = box.querySelector('audio');
    if (!audio) return;
    audio.controls = false;
    audio.hidden = true;
    var nome = box.querySelector('.player-name');
    var btn = document.createElement('button');
    btn.type = 'button'; btn.className = 'player-btn';
    btn.setAttribute('aria-label', 'Reproduzir' + (nome ? ' ' + nome.textContent : ''));
    btn.innerHTML = SVG(ICON.play, 16);
    var bar = document.createElement('span');
    bar.className = 'player-bar'; bar.tabIndex = 0;
    bar.setAttribute('role', 'slider'); bar.setAttribute('aria-label', 'Posição do áudio');
    bar.setAttribute('aria-valuemin', '0'); bar.setAttribute('aria-valuemax', '100'); bar.setAttribute('aria-valuenow', '0');
    var fill = document.createElement('i'); bar.appendChild(fill);
    var tempo = document.createElement('span'); tempo.className = 'player-time'; tempo.textContent = '0:00';
    box.insertBefore(tempo, nome); box.insertBefore(bar, tempo); box.insertBefore(btn, bar);
    var render = function () {
      var d = audio.duration, pc = d ? audio.currentTime / d * 100 : 0;
      fill.style.width = pc + '%';
      bar.setAttribute('aria-valuenow', String(Math.round(pc)));
      bar.setAttribute('aria-valuetext', mmss(audio.currentTime) + ' de ' + mmss(d));
      tempo.textContent = mmss(audio.currentTime) + (isFinite(d) && d ? ' / ' + mmss(d) : '');
    };
    btn.addEventListener('click', function () {
      if (audio.paused) {
        $$('[data-player] audio').forEach(function (a) { if (a !== audio) a.pause(); });
        audio.play();
      } else audio.pause();
    });
    audio.addEventListener('play', function () { btn.innerHTML = SVG(ICON.pause, 16); btn.setAttribute('aria-label', 'Pausar'); });
    audio.addEventListener('pause', function () { btn.innerHTML = SVG(ICON.play, 16); btn.setAttribute('aria-label', 'Reproduzir'); });
    audio.addEventListener('timeupdate', render);
    audio.addEventListener('loadedmetadata', render);
    audio.addEventListener('ended', function () { audio.currentTime = 0; render(); });
    var seek = function (frac) { if (audio.duration) { audio.currentTime = Math.min(1, Math.max(0, frac)) * audio.duration; render(); } };
    bar.addEventListener('click', function (e) { var r = bar.getBoundingClientRect(); seek((e.clientX - r.left) / r.width); });
    bar.addEventListener('keydown', function (e) {
      if (!audio.duration) return;
      if (e.key === 'ArrowRight') { audio.currentTime = Math.min(audio.duration, audio.currentTime + 5); e.preventDefault(); }
      if (e.key === 'ArrowLeft') { audio.currentTime = Math.max(0, audio.currentTime - 5); e.preventDefault(); }
      render();
    });
  });

  // ------------------------------------------------------------ dropzone simples (verificar arquivo)
  $$('[data-dropzone]').forEach(function (dz) {
    var input = dz.querySelector('input[type=file]');
    var nome = dz.querySelector('[data-dropzone-nome]');
    ['dragenter', 'dragover'].forEach(function (ev) { dz.addEventListener(ev, function (e) { e.preventDefault(); dz.classList.add('over'); }); });
    ['dragleave', 'drop'].forEach(function (ev) { dz.addEventListener(ev, function (e) { e.preventDefault(); dz.classList.remove('over'); }); });
    dz.addEventListener('drop', function (e) { input.files = e.dataTransfer.files; input.dispatchEvent(new Event('change')); });
    input.addEventListener('change', function () {
      if (input.files[0] && nome) nome.textContent = input.files[0].name + ' · ' + humanSize(input.files[0].size);
    });
  });

  // ------------------------------------------------------------ formulário de prova
  var form = document.getElementById('form-prova');
  if (!form) return;
  var input = document.getElementById('arquivos');
  var drop = document.getElementById('arrastar');
  var lista = document.getElementById('lista-arquivos');
  var sugestao = document.getElementById('sugestao');
  var data = form.querySelector('[name=data]');
  var hora = form.querySelector('[name=hora]');
  var titulo = form.querySelector('[name=titulo]');
  var origem = form.querySelector('[name=origem]');

  // Tenta extrair data/hora do nome do arquivo (WhatsApp, prints, câmeras, gravadores)
  function dateFromName(name) {
    var m;
    // "WhatsApp Image 2024-05-12 at 14.33.21" / "2024-05-12 14-33-21" / "2024-05-12_14.33.21"
    if ((m = name.match(/(20\d\d)[-_.](\d\d)[-_.](\d\d)(?:\D{1,4}(\d\d)[.\-_:h](\d\d)(?:[.\-_:m](\d\d))?)?/)))
      return { d: m[1] + '-' + m[2] + '-' + m[3], t: m[4] ? m[4] + ':' + m[5] + ':' + (m[6] || '00') : '' };
    // "Screenshot_20240512-143321" / "IMG_20240512_143321" / "VID_20240512_143321" / "PXL_20240512_143321"
    if ((m = name.match(/(20\d\d)(\d\d)(\d\d)[-_ T]?(\d\d)(\d\d)(\d\d)/)))
      return { d: m[1] + '-' + m[2] + '-' + m[3], t: m[4] + ':' + m[5] + ':' + m[6] };
    // "IMG-20240512-WA0003" / "PTT-20240512-WA0001" (WhatsApp sem hora)
    if ((m = name.match(/(20\d\d)(\d\d)(\d\d)/)))
      return { d: m[1] + '-' + m[2] + '-' + m[3], t: '' };
    return null;
  }

  function fromModified(file) {
    var d = new Date(file.lastModified);
    return { d: d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate()),
             t: pad(d.getHours()) + ':' + pad(d.getMinutes()) + ':' + pad(d.getSeconds()) };
  }

  function tipo(f) {
    if (f.type.indexOf('image') === 0) return 'imagem';
    if (f.type.indexOf('audio') === 0 || /\.(opus|amr|m4a)$/i.test(f.name)) return 'audio';
    if (f.type.indexOf('video') === 0) return 'video';
    return 'documento';
  }

  // Hash calculado no navegador (só em HTTPS e para arquivos até 100 MB): é o mesmo que o servidor vai registrar.
  function hashLocal(f, alvo) {
    if (!window.crypto || !crypto.subtle || !window.isSecureContext || f.size > 100 * 1048576) return;
    f.arrayBuffer().then(function (buf) { return crypto.subtle.digest('SHA-256', buf); }).then(function (d) {
      var h = Array.prototype.map.call(new Uint8Array(d), function (b) { return b.toString(16).padStart(2, '0'); }).join('');
      alvo.innerHTML = SVG(ICON.shield, 14) + h.slice(0, 4) + '…' + h.slice(-4);
      alvo.title = 'SHA-256: ' + h;
    }).catch(function () { /* ignora */ });
  }

  function update() {
    lista.innerHTML = '';
    var files = Array.prototype.slice.call(input.files);
    files.forEach(function (f) {
      var li = document.createElement('li');
      var ft = document.createElement('span'); ft.className = 'ft';
      var k = tipo(f);
      if (k === 'imagem') {
        var img = document.createElement('img'); img.alt = ''; img.src = URL.createObjectURL(f);
        img.onload = function () { URL.revokeObjectURL(img.src); };
        ft.appendChild(img);
      } else ft.innerHTML = SVG(k === 'audio' ? ICON.mic : k === 'video' ? ICON.video : ICON.file, 18);
      var fn = document.createElement('span'); fn.className = 'fn'; fn.textContent = f.name; fn.title = f.name;
      var fs = document.createElement('span'); fs.className = 'fs'; fs.textContent = humanSize(f.size);
      var fh = document.createElement('span'); fh.className = 'fh';
      li.appendChild(ft); li.appendChild(fn); li.appendChild(fs); li.appendChild(fh);
      lista.appendChild(li);
      hashLocal(f, fh);
    });
    if (!files.length) return;
    var f = files[0];
    var s = dateFromName(f.name);
    var origemTxt = 'pelo nome do arquivo';
    if (!s || !s.t) {
      var mod = fromModified(f);
      if (!s) { s = mod; origemTxt = 'pela data de modificação do arquivo (confira!)'; }
      else { s.t = ''; }
    }
    if (!data.value) data.value = s.d;
    if (!hora.value && s.t) hora.value = s.t;
    sugestao.textContent = 'Data sugerida ' + origemTxt + ': ' + s.d.split('-').reverse().join('/') +
      (s.t ? ' ' + s.t : '') + '. Ajuste se o fato ocorreu em outro horário.';
    if (!origem.value && /whatsapp|-WA\d|PTT-/i.test(f.name)) origem.value = 'WhatsApp';
    if (!titulo.value) {
      var nomes = { imagem: 'Print/Imagem', audio: 'Áudio', video: 'Vídeo', documento: 'Documento' };
      titulo.placeholder = nomes[tipo(f)] + ' — descreva em poucas palavras';
    }
  }

  input.addEventListener('change', update);
  ['dragenter', 'dragover'].forEach(function (ev) {
    drop.addEventListener(ev, function (e) { e.preventDefault(); drop.classList.add('over'); });
  });
  ['dragleave', 'drop'].forEach(function (ev) {
    drop.addEventListener(ev, function (e) { e.preventDefault(); drop.classList.remove('over'); });
  });
  drop.addEventListener('drop', function (e) { input.files = e.dataTransfer.files; update(); });

  // Envio com barra de progresso (arquivos grandes)
  form.addEventListener('submit', function (e) {
    if (!input.files.length || !window.FormData) return;
    e.preventDefault();
    var fd = new FormData(form);
    if (e.submitter && e.submitter.name) fd.append(e.submitter.name, e.submitter.value);
    var box = document.getElementById('progresso');
    var bar = box.querySelector('div'), label = box.querySelector('span');
    box.hidden = false;
    form.querySelectorAll('button').forEach(function (b) { b.disabled = true; });
    var xhr = new XMLHttpRequest();
    xhr.open('POST', form.action || location.href);
    xhr.upload.onprogress = function (p) {
      if (!p.lengthComputable) return;
      var pc = Math.round(p.loaded / p.total * 100);
      bar.style.width = pc + '%';
      label.textContent = pc < 100 ? 'Enviando… ' + pc + '%' : 'Calculando hash e salvando…';
    };
    xhr.onload = function () {
      if (xhr.status < 400) { location.href = xhr.responseURL; }
      else { alert('Erro ao enviar (' + xhr.status + '): ' + xhr.responseText.slice(0, 300)); location.reload(); }
    };
    xhr.onerror = function () { alert('Falha de conexão durante o envio. Tente novamente.'); location.reload(); };
    xhr.send(fd);
  });
})();
