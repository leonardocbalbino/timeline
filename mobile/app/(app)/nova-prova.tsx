import DateTimePicker, { DateTimePickerAndroid } from '@react-native-community/datetimepicker';
import {
  AudioModule, RecordingPresets, setAudioModeAsync, useAudioRecorder, useAudioRecorderState,
} from 'expo-audio';
import * as DocumentPicker from 'expo-document-picker';
import { File } from 'expo-file-system';
import { Image } from 'expo-image';
import * as ImagePicker from 'expo-image-picker';
import { router, Stack, useLocalSearchParams } from 'expo-router';
import { Camera, FileText, Images, Mic, Square, Star, Trash2, Video, X } from 'lucide-react-native';
import { useEffect, useState } from 'react';
import { Alert, KeyboardAvoidingView, Platform, Pressable, ScrollView, Switch, View } from 'react-native';

import { Button, Card, Chip, Field, Notice, Text } from '@/components/ui';
import { api, uploadInParts, type LocalFile } from '@/lib/api';
import { useDraft } from '@/lib/draft';
import { dateFromName, humanSize, kindOf, toDateInput, toTimeInput } from '@/lib/format';
import { colors, fonts, radius, space } from '@/theme';

const ORIGENS = ['WhatsApp', 'Instagram', 'E-mail', 'SMS', 'Ligação gravada', 'Câmera de segurança', 'Celular (galeria)', 'Documento'];
const pad = (n: number) => String(n).padStart(2, '0');

function sizeOf(uri: string, known?: number | null) {
  if (known) return known;
  try {
    return new File(uri).size ?? 0;
  } catch {
    return 0;
  }
}

/** "2025:01:05 10:15:00" (EXIF) → { d, t } */
function exifDate(exif?: Record<string, any> | null) {
  const raw = exif?.DateTimeOriginal || exif?.DateTimeDigitized || exif?.DateTime;
  const m = typeof raw === 'string' && raw.match(/(\d{4}):(\d\d):(\d\d)[ T](\d\d):(\d\d):(\d\d)/);
  return m ? { d: `${m[1]}-${m[2]}-${m[3]}`, t: `${m[4]}:${m[5]}:${m[6]}` } : null;
}

export default function EvidenceForm() {
  const { pid: pidParam, eid: eidParam } = useLocalSearchParams<{ pid: string; eid?: string }>();
  const pid = Number(pidParam);
  const eid = eidParam ? Number(eidParam) : null;
  const editing = eid !== null;
  const draft = useDraft();

  const now = new Date();
  const [data, setData] = useState(toDateInput(now));
  const [hora, setHora] = useState(toTimeInput(now).slice(0, 5) + ':00');
  const [touchedDate, setTouchedDate] = useState(false);
  const [hint, setHint] = useState('');
  const [titulo, setTitulo] = useState('');
  const [descricao, setDescricao] = useState('');
  const [origem, setOrigem] = useState('');
  const [pessoas, setPessoas] = useState('');
  const [destaque, setDestaque] = useState(false);
  const [existing, setExisting] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState<{ sent: number; total: number; name: string } | null>(null);
  const [error, setError] = useState('');

  const recorder = useAudioRecorder(RecordingPresets.HIGH_QUALITY);
  const recState = useAudioRecorderState(recorder);

  // Edição: carrega a prova
  useEffect(() => {
    if (!editing) return;
    api.process(pid).then(({ evidences }) => {
      const e = evidences.find((x) => x.id === eid);
      if (!e) return;
      setData(e.occurred_at.slice(0, 10));
      setHora(e.occurred_at.slice(11, 19));
      setTitulo(e.title);
      setDescricao(e.description);
      setOrigem(e.source);
      setPessoas(e.people);
      setDestaque(e.important);
      setExisting(e.files.map((f) => f.name));
      setTouchedDate(true);
    }).catch((e) => setError(e?.message || 'Não foi possível carregar a prova.'));
  }, [editing, pid, eid]);

  // Sugestão de data/hora e origem a partir do primeiro arquivo (mesma regra do site)
  const suggest = (file: LocalFile, exif?: { d: string; t: string } | null) => {
    if (touchedDate) return;
    const s = exif || dateFromName(file.name);
    if (!s) return;
    setData(s.d);
    if (s.t) setHora(s.t);
    setHint(`Data sugerida ${exif ? 'pelos dados da foto' : 'pelo nome do arquivo'}: ${s.d.split('-').reverse().join('/')}${s.t ? ` ${s.t}` : ''}. Ajuste se o fato ocorreu em outro horário.`);
    if (!origem && /whatsapp|-WA\d|PTT-/i.test(file.name)) setOrigem('WhatsApp');
  };
  useEffect(() => {
    if (!editing && draft.files[0]) suggest(draft.files[0]);
    // só quando o primeiro arquivo muda
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [draft.files[0]?.uri]);

  const fromPicker = (assets: ImagePicker.ImagePickerAsset[]) => {
    const files = assets.map((a) => ({
      uri: a.uri,
      name: a.fileName || `${a.type === 'video' ? 'VID' : 'IMG'}-${Date.now()}.${a.type === 'video' ? 'mp4' : 'jpg'}`,
      size: sizeOf(a.uri, a.fileSize),
      mimeType: a.mimeType || (a.type === 'video' ? 'video/mp4' : 'image/jpeg'),
    }));
    if (files[0] && !draft.files.length) suggest(files[0], exifDate(assets[0].exif));
    draft.add(files);
  };

  const camera = async () => {
    const perm = await ImagePicker.requestCameraPermissionsAsync();
    if (!perm.granted) return Alert.alert('Câmera', 'Permita o acesso à câmera nas configurações do celular.');
    const r = await ImagePicker.launchCameraAsync({ mediaTypes: ['images', 'videos'], quality: 1, exif: true });
    if (!r.canceled) fromPicker(r.assets);
  };
  const gallery = async () => {
    const r = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ['images', 'videos'], allowsMultipleSelection: true, selectionLimit: 0, quality: 1, exif: true,
    });
    if (!r.canceled) fromPicker(r.assets);
  };
  const documents = async () => {
    const r = await DocumentPicker.getDocumentAsync({ multiple: true, copyToCacheDirectory: true, type: '*/*' });
    if (r.canceled) return;
    const files = r.assets.map((a) => ({ uri: a.uri, name: a.name, size: sizeOf(a.uri, a.size), mimeType: a.mimeType || 'application/octet-stream' }));
    if (files[0] && !draft.files.length) suggest(files[0]);
    draft.add(files);
  };
  const toggleRecording = async () => {
    if (recState.isRecording) {
      await recorder.stop();
      await setAudioModeAsync({ allowsRecording: false, playsInSilentMode: true });
      if (recorder.uri) {
        const d = new Date();
        const name = `Gravacao-${toDateInput(d).replace(/-/g, '')}-${pad(d.getHours())}${pad(d.getMinutes())}${pad(d.getSeconds())}.m4a`;
        draft.add([{ uri: recorder.uri, name, size: sizeOf(recorder.uri), mimeType: 'audio/mp4' }]);
      }
      return;
    }
    const perm = await AudioModule.requestRecordingPermissionsAsync();
    if (!perm.granted) return Alert.alert('Microfone', 'Permita o acesso ao microfone nas configurações do celular.');
    await setAudioModeAsync({ allowsRecording: true, playsInSilentMode: true });
    await recorder.prepareToRecordAsync();
    recorder.record();
  };

  const pickDate = (mode: 'date' | 'time') => {
    const current = new Date(`${data}T${hora}`);
    DateTimePickerAndroid.open({
      value: isNaN(current.getTime()) ? new Date() : current, mode, is24Hour: true,
      onChange: (ev, d) => {
        if (ev.type !== 'set' || !d) return;
        setTouchedDate(true);
        if (mode === 'date') setData(toDateInput(d));
        else setHora(`${pad(d.getHours())}:${pad(d.getMinutes())}:00`);
      },
    });
  };

  const save = async () => {
    setError('');
    if (!titulo.trim()) return setError('Informe um título.');
    setBusy(true);
    try {
      if (editing) {
        await api.updateEvidence(pid, eid!, { data, hora, titulo, descricao, origem, pessoas, destaque });
      } else {
        const total = draft.files.reduce((t, f) => t + f.size, 0) || 1;
        let done = 0;
        const ids: string[] = [];
        for (const f of draft.files) {
          setProgress({ sent: done, total, name: f.name });
          ids.push(await uploadInParts(f, 'prova', (b) => setProgress({ sent: done + b, total, name: f.name })));
          done += f.size;
        }
        setProgress({ sent: total, total, name: '' });
        await api.createEvidence(pid, { data, hora, titulo, descricao, origem, pessoas, destaque, upload_ids: ids });
        draft.clear();
      }
      router.back();
    } catch (e: any) {
      setError(e?.message || 'Não foi possível salvar.');
    } finally {
      setBusy(false);
      setProgress(null);
    }
  };

  const remove = () => Alert.alert('Excluir prova', 'A prova e os arquivos serão apagados. A exclusão fica registrada na auditoria.', [
    { text: 'Cancelar', style: 'cancel' },
    { text: 'Excluir', style: 'destructive', onPress: async () => {
      try {
        await api.deleteEvidence(pid, eid!);
        router.back();
      } catch (e: any) {
        setError(e?.message || 'Não foi possível excluir.');
      }
    } },
  ]);

  const dateLabel = data.split('-').reverse().join('/');
  const pct = progress ? Math.min(100, Math.floor((progress.sent / progress.total) * 100)) : 0;

  return (
    <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={{ flex: 1 }}>
      <Stack.Screen options={{ title: editing ? 'Editar prova' : 'Nova prova' }} />
      <ScrollView contentContainerStyle={{ padding: space[4], gap: space[5], paddingBottom: 60 }} keyboardShouldPersistTaps="handled">
        {!editing ? (
          <Card style={{ gap: space[3] }}>
            <Text variant="label">Arquivos da prova</Text>
            <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
              <Button small kind="secondary" icon={Camera} title="Câmera" onPress={camera} />
              <Button small kind="secondary" icon={Images} title="Galeria" onPress={gallery} />
              <Button small kind="secondary" icon={FileText} title="Arquivo" onPress={documents} />
              <Button small kind={recState.isRecording ? 'danger' : 'secondary'} icon={recState.isRecording ? Square : Mic}
                title={recState.isRecording ? `Parar ${Math.floor(recState.durationMillis / 60000)}:${pad(Math.floor(recState.durationMillis / 1000) % 60)}` : 'Gravar áudio'}
                onPress={toggleRecording} />
            </View>
            {draft.files.map((f) => {
              const k = kindOf(f.mimeType, f.name);
              return (
                <View key={f.uri} style={{ flexDirection: 'row', alignItems: 'center', gap: 10, borderWidth: 1, borderColor: colors.border,
                  borderRadius: radius.md, padding: 8 }}>
                  <View style={{ width: 40, height: 40, borderRadius: radius.sm, backgroundColor: colors.surface2, overflow: 'hidden',
                    alignItems: 'center', justifyContent: 'center' }}>
                    {k === 'imagem' ? <Image source={{ uri: f.uri }} style={{ width: 40, height: 40 }} contentFit="cover" />
                      : k === 'video' ? <Video size={18} color={colors.textSubtle} />
                        : k === 'audio' ? <Mic size={18} color={colors.textSubtle} /> : <FileText size={18} color={colors.textSubtle} />}
                  </View>
                  <View style={{ flex: 1 }}>
                    <Text variant="body" numberOfLines={1} style={{ fontSize: 14 }}>{f.name}</Text>
                    <Text variant="mono" style={{ fontSize: 12 }}>{humanSize(f.size)}</Text>
                  </View>
                  <Pressable onPress={() => draft.remove(f.uri)} hitSlop={10} accessibilityRole="button" accessibilityLabel={`Remover ${f.name}`}>
                    <X size={18} color={colors.textSubtle} />
                  </Pressable>
                </View>
              );
            })}
            {!draft.files.length ? <Text variant="small">Pode juntar vários arquivos do mesmo momento. O hash SHA-256 de cada um é registrado no envio.</Text> : null}
          </Card>
        ) : existing.length ? (
          <Card style={{ gap: 6 }}>
            <Text variant="label">Arquivos</Text>
            {existing.map((n) => <Text key={n} variant="subtle" numberOfLines={1}>{n}</Text>)}
            <Text variant="small">Os arquivos de uma prova não mudam depois do envio. Para juntar outros, crie uma nova prova.</Text>
          </Card>
        ) : null}

        <View style={{ gap: space[2] }}>
          <View style={{ flexDirection: 'row', gap: space[3] }}>
            <View style={{ flex: 1, gap: 6 }}>
              <Text variant="label">Data do fato</Text>
              {Platform.OS === 'android' ? (
                <Pressable onPress={() => pickDate('date')} style={dateBox}><Text style={{ fontFamily: fonts.mono, fontSize: 15 }}>{dateLabel}</Text></Pressable>
              ) : (
                <DateTimePicker value={new Date(`${data}T${hora}`)} mode="date" display="compact" locale="pt-BR"
                  onChange={(_e, d) => { if (d) { setTouchedDate(true); setData(toDateInput(d)); } }} />
              )}
            </View>
            <View style={{ flex: 1, gap: 6 }}>
              <Text variant="label">Hora</Text>
              {Platform.OS === 'android' ? (
                <Pressable onPress={() => pickDate('time')} style={dateBox}><Text style={{ fontFamily: fonts.mono, fontSize: 15 }}>{hora.slice(0, 5)}</Text></Pressable>
              ) : (
                <DateTimePicker value={new Date(`${data}T${hora}`)} mode="time" display="compact" locale="pt-BR"
                  onChange={(_e, d) => { if (d) { setTouchedDate(true); setHora(`${pad(d.getHours())}:${pad(d.getMinutes())}:00`); } }} />
              )}
            </View>
          </View>
          {hint ? <Text variant="small">{hint}</Text> : null}
        </View>

        <Field label="Título" value={titulo} onChangeText={setTitulo} maxLength={300} placeholder="Ex.: Mensagem confirmando o horário" />
        <Field label="Descrição" hint="o que esta prova demonstra" value={descricao} onChangeText={setDescricao} multiline
          style={{ minHeight: 120 }} />
        <View style={{ gap: 8 }}>
          <Field label="Origem" value={origem} onChangeText={setOrigem} placeholder="WhatsApp, Instagram, e-mail, câmera…" />
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 6 }}>
            {ORIGENS.map((o) => (
              <Pressable key={o} onPress={() => setOrigem(o)} accessibilityRole="button" accessibilityLabel={`Origem ${o}`}>
                <Chip label={o} kind={origem === o ? 'dark' : 'default'} />
              </Pressable>
            ))}
          </ScrollView>
        </View>
        <Field label="Pessoas envolvidas" value={pessoas} onChangeText={setPessoas} />
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, minHeight: 48 }}>
          <Star size={18} color={colors.highlight} fill={destaque ? colors.highlight : 'transparent'} />
          <Text variant="label" style={{ flex: 1 }}>Marcar como destaque</Text>
          <Switch value={destaque} onValueChange={setDestaque} trackColor={{ true: colors.highlight, false: colors.borderStrong }}
            thumbColor="#fff" accessibilityLabel="Marcar como destaque" />
        </View>

        {error ? <Notice text={error} /> : null}
        {progress ? (
          <View style={{ gap: 6 }}>
            <View style={{ height: 8, borderRadius: 4, backgroundColor: colors.surface2, overflow: 'hidden' }}>
              <View style={{ width: `${pct}%`, height: '100%', backgroundColor: colors.action }} />
            </View>
            <Text variant="small">{progress.name ? `Enviando ${progress.name}… ${pct}%` : 'Calculando hash e salvando…'}</Text>
          </View>
        ) : null}
        <Button title={editing ? 'Salvar alterações' : 'Salvar prova'} onPress={save} loading={busy}
          disabled={busy || recState.isRecording || !titulo.trim()} />
        {editing ? <Button kind="ghost" icon={Trash2} title="Excluir esta prova" onPress={remove} style={{ alignSelf: 'center' }} /> : null}
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const dateBox = {
  minHeight: 48, borderWidth: 1, borderColor: colors.borderStrong, borderRadius: radius.md, paddingHorizontal: 14,
  justifyContent: 'center' as const, backgroundColor: colors.surface,
};
