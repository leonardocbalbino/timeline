(function () {
  // Ampliar imagens
  var lb = document.getElementById('lightbox');
  document.addEventListener('click', function (e) {
    if (e.target.classList.contains('zoom')) {
      lb.querySelector('img').src = e.target.src;
      lb.hidden = false;
    } else if (!lb.hidden && lb.contains(e.target)) {
      lb.hidden = true;
    }
  });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape') lb.hidden = true; });

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

  function pad(n) { return String(n).padStart(2, '0'); }

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

  function update() {
    lista.innerHTML = '';
    var files = Array.prototype.slice.call(input.files);
    files.forEach(function (f) {
      var li = document.createElement('li');
      li.textContent = f.name + ' (' + (f.size / 1048576).toFixed(1) + ' MB)';
      lista.appendChild(li);
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
      var t = f.type.indexOf('image') === 0 ? 'Print/Imagem' : f.type.indexOf('audio') === 0 || /\.(opus|amr)$/i.test(f.name) ? 'Áudio'
        : f.type.indexOf('video') === 0 ? 'Vídeo' : 'Documento';
      titulo.placeholder = t + ' — descreva em poucas palavras';
    }
  }

  input.addEventListener('change', update);
  ['dragenter', 'dragover'].forEach(function (ev) {
    drop.addEventListener(ev, function (e) { e.preventDefault(); drop.classList.add('sobre'); });
  });
  ['dragleave', 'drop'].forEach(function (ev) {
    drop.addEventListener(ev, function (e) { e.preventDefault(); drop.classList.remove('sobre'); });
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
