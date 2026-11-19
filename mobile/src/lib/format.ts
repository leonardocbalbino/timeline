const DIAS = ['Domingo', 'Segunda-feira', 'Terça-feira', 'Quarta-feira', 'Quinta-feira', 'Sexta-feira', 'Sábado'];
const DIAS_CURTOS = ['dom', 'seg', 'ter', 'qua', 'qui', 'sex', 'sáb'];
const MESES = ['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho', 'julho', 'agosto', 'setembro',
  'outubro', 'novembro', 'dezembro'];

const pad = (n: number) => String(n).padStart(2, '0');

/** "2025-12-24T10:00:00" (horário de Brasília, como o servidor guarda) → Date local sem fuso. */
function parts(iso: string) {
  const [d, t = '00:00:00'] = iso.split('T');
  const [y, m, day] = d.split('-').map(Number);
  const [hh, mm, ss = 0] = t.split(':').map(Number);
  return { y, m, day, hh, mm, ss, weekday: new Date(y, m - 1, day).getDay() };
}

export function fmtDay(iso: string) {
  const p = parts(iso);
  return `${DIAS[p.weekday]}, ${p.day} de ${MESES[p.m - 1]} de ${p.y}`;
}
export function fmtDayShort(iso: string) {
  const p = parts(iso);
  return `${DIAS_CURTOS[p.weekday]}, ${pad(p.day)} ${MESES[p.m - 1].slice(0, 3)}`;
}
export function fmtDate(iso?: string | null) {
  if (!iso) return '';
  const p = parts(iso);
  return `${pad(p.day)}/${pad(p.m)}/${p.y}`;
}
export function fmtDateTime(iso?: string | null) {
  if (!iso) return '';
  const p = parts(iso);
  return `${pad(p.day)}/${pad(p.m)}/${p.y} ${pad(p.hh)}:${pad(p.mm)}`;
}
export function fmtTime(iso: string) {
  const p = parts(iso);
  return p.ss ? `${pad(p.hh)}:${pad(p.mm)}:${pad(p.ss)}` : `${pad(p.hh)}:${pad(p.mm)}`;
}
export function humanSize(n: number) {
  const units = ['B', 'KB', 'MB', 'GB'];
  let i = 0;
  let v = n;
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024;
    i += 1;
  }
  return i === 0 || v === Math.floor(v) ? `${Math.round(v)} ${units[i]}` : `${v.toFixed(1).replace('.', ',')} ${units[i]}`;
}
export const shortHash = (h: string) => (h.length > 8 ? `${h.slice(0, 4)}…${h.slice(-4)}` : h);

export function toDateInput(d: Date) {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}
export function toTimeInput(d: Date) {
  return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

/** Data e hora sugeridas pelo nome do arquivo (WhatsApp, prints, câmeras) — mesma regra do site. */
export function dateFromName(name: string): { d: string; t: string } | null {
  let m = name.match(/(20\d\d)[-_.](\d\d)[-_.](\d\d)(?:\D{1,4}(\d\d)[.\-_:h](\d\d)(?:[.\-_:m](\d\d))?)?/);
  if (m) return { d: `${m[1]}-${m[2]}-${m[3]}`, t: m[4] ? `${m[4]}:${m[5]}:${m[6] || '00'}` : '' };
  m = name.match(/(20\d\d)(\d\d)(\d\d)[-_ T]?(\d\d)(\d\d)(\d\d)/);
  if (m) return { d: `${m[1]}-${m[2]}-${m[3]}`, t: `${m[4]}:${m[5]}:${m[6]}` };
  m = name.match(/(20\d\d)(\d\d)(\d\d)/);
  if (m) return { d: `${m[1]}-${m[2]}-${m[3]}`, t: '' };
  return null;
}

export function kindOf(mime: string, name: string): 'imagem' | 'audio' | 'video' | 'documento' {
  if (mime.startsWith('image/')) return 'imagem';
  if (mime.startsWith('audio/') || /\.(opus|amr|m4a|ogg)$/i.test(name)) return 'audio';
  if (mime.startsWith('video/')) return 'video';
  return 'documento';
}
