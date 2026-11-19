import { useAudioPlayer, useAudioPlayerStatus } from 'expo-audio';
import { File, Paths } from 'expo-file-system';
import { Image } from 'expo-image';
import * as Sharing from 'expo-sharing';
import { useVideoPlayer, VideoView } from 'expo-video';
import { ChevronLeft, ChevronRight, Copy, FileText, Image as ImageIcon, Mic, Pause, Pencil, Play, ShieldCheck,
  Users, Video as VideoIcon, X } from 'lucide-react-native';
import { useState } from 'react';
import { ActivityIndicator, Alert, Modal, Pressable, Share, View } from 'react-native';

import { absoluteUrl, authHeaders, type Evidence, type EvidenceFile } from '@/lib/api';
import { humanSize, shortHash } from '@/lib/format';
import { colors, fonts, radius, space } from '@/theme';
import { Chip, Text } from './ui';

const source = (f: EvidenceFile, accountId: number) => ({
  uri: absoluteUrl(f.url), headers: authHeaders(), cacheKey: `integra-${accountId}-${f.id}`,
});

export function AuthImage({ file, accountId, style }: { file: EvidenceFile; accountId: number; style: object }) {
  return <Image source={source(file, accountId)} style={style} contentFit="cover" transition={150} accessibilityLabel={file.name} />;
}

function AudioRow({ file }: { file: EvidenceFile }) {
  const player = useAudioPlayer({ uri: absoluteUrl(file.url), headers: authHeaders() });
  const status = useAudioPlayerStatus(player);
  const dur = status.duration || 0;
  const pos = status.currentTime || 0;
  const mmss = (s: number) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`;
  const toggle = () => {
    if (status.playing) player.pause();
    else {
      if (dur && pos >= dur - 0.25) player.seekTo(0);
      player.play();
    }
  };
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12, backgroundColor: colors.bg, borderWidth: 1,
      borderColor: colors.border, borderRadius: radius.md, padding: 8, paddingRight: 14 }}>
      <Pressable onPress={toggle} accessibilityRole="button" accessibilityLabel={status.playing ? 'Pausar' : `Reproduzir ${file.name}`}
        style={{ width: 40, height: 40, borderRadius: 20, backgroundColor: colors.ink, alignItems: 'center', justifyContent: 'center' }}>
        {status.playing ? <Pause size={16} color="#fff" fill="#fff" /> : <Play size={16} color="#fff" fill="#fff" />}
      </Pressable>
      <View style={{ flex: 1, height: 6, borderRadius: 3, backgroundColor: colors.border, overflow: 'hidden' }}>
        <View style={{ width: `${dur ? Math.min(100, (pos / dur) * 100) : 0}%`, height: '100%', backgroundColor: colors.ink }} />
      </View>
      <Text variant="mono" style={{ fontSize: 12 }}>{mmss(pos)}{dur ? ` / ${mmss(dur)}` : ''}</Text>
    </View>
  );
}

function VideoBox({ file }: { file: EvidenceFile }) {
  const player = useVideoPlayer({ uri: absoluteUrl(file.url), headers: authHeaders() });
  return (
    <View style={{ aspectRatio: 16 / 9, backgroundColor: '#000', borderRadius: radius.md, overflow: 'hidden' }}>
      <VideoView player={player} style={{ flex: 1 }} nativeControls contentFit="contain" />
    </View>
  );
}

function DocRow({ file }: { file: EvidenceFile }) {
  const [busy, setBusy] = useState(false);
  const open = async () => {
    setBusy(true);
    try {
      const dest = new File(Paths.cache, `${file.id}-${file.name.replace(/[^\w.\-]+/g, '_')}`);
      if (!dest.exists) {
        await File.downloadFileAsync(absoluteUrl(file.url), dest, { headers: authHeaders(), idempotent: true });
      }
      await Sharing.shareAsync(dest.uri, { mimeType: file.mime, dialogTitle: file.name });
    } catch {
      Alert.alert('Não foi possível abrir', 'Verifique a conexão e tente de novo.');
    } finally {
      setBusy(false);
    }
  };
  return (
    <Pressable onPress={open} accessibilityRole="button" accessibilityLabel={`Abrir ${file.name}`}
      style={{ flexDirection: 'row', alignItems: 'center', gap: 10, padding: 12, borderWidth: 1, borderColor: colors.border,
        borderRadius: radius.md, backgroundColor: colors.bg }}>
      {busy ? <ActivityIndicator color={colors.ink} /> : <FileText size={18} color={colors.ink} />}
      <Text variant="body" numberOfLines={1} style={{ flex: 1, fontSize: 14 }}>{file.name}</Text>
    </Pressable>
  );
}

export function Integrity({ file }: { file: EvidenceFile }) {
  const copy = () => Share.share({ message: `SHA-256 de ${file.name}: ${file.sha256}` });
  return (
    <View style={{ flexDirection: 'row', alignItems: 'flex-start', gap: 8 }}>
      <ShieldCheck size={16} color={colors.verified} style={{ marginTop: 1 }} />
      <View style={{ flex: 1, gap: 2 }}>
        <Text style={{ fontFamily: fonts.mono, fontSize: 12, color: colors.verified }}>
          Íntegro desde o envio · SHA-256 {shortHash(file.sha256)}
        </Text>
        <Text variant="small" numberOfLines={1}>{file.name} · {humanSize(file.size)}</Text>
      </View>
      <Pressable onPress={copy} hitSlop={10} accessibilityRole="button" accessibilityLabel={`Compartilhar o hash SHA-256 de ${file.name}`}>
        <Copy size={16} color={colors.verified} />
      </Pressable>
    </View>
  );
}

function Gallery({ files, start, accountId, onClose }: { files: EvidenceFile[]; start: number; accountId: number; onClose: () => void }) {
  const [i, setI] = useState(start);
  const f = files[i];
  return (
    <Modal visible animationType="fade" onRequestClose={onClose} statusBarTranslucent>
      <View style={{ flex: 1, backgroundColor: 'rgba(14,26,43,0.97)', justifyContent: 'center' }}>
        <Image source={source(f, accountId)} style={{ width: '100%', height: '80%' }} contentFit="contain" accessibilityLabel={f.name} />
        <Text style={{ color: colors.onDarkMuted, fontFamily: fonts.mono, fontSize: 12, textAlign: 'center', marginTop: 12 }}>
          {files.length > 1 ? `${i + 1} / ${files.length} · ` : ''}{f.name}
        </Text>
        <Pressable onPress={onClose} accessibilityRole="button" accessibilityLabel="Fechar" style={lbBtn({ top: 52, right: 16 })}>
          <X size={22} color="#fff" />
        </Pressable>
        {files.length > 1 ? (
          <>
            <Pressable onPress={() => setI((i - 1 + files.length) % files.length)} accessibilityLabel="Imagem anterior" style={lbBtn({ left: 12, top: '48%' })}>
              <ChevronLeft size={22} color="#fff" />
            </Pressable>
            <Pressable onPress={() => setI((i + 1) % files.length)} accessibilityLabel="Próxima imagem" style={lbBtn({ right: 12, top: '48%' })}>
              <ChevronRight size={22} color="#fff" />
            </Pressable>
          </>
        ) : null}
      </View>
    </Modal>
  );
}
const lbBtn = (pos: object) => ({
  position: 'absolute' as const, width: 48, height: 48, borderRadius: 24, backgroundColor: colors.ink2,
  alignItems: 'center' as const, justifyContent: 'center' as const, ...pos,
});

const KIND: Record<EvidenceFile['kind'], { one: string; many: string; Icon: typeof ImageIcon }> = {
  imagem: { one: 'imagem', many: 'imagens', Icon: ImageIcon },
  audio: { one: 'áudio', many: 'áudios', Icon: Mic },
  video: { one: 'vídeo', many: 'vídeos', Icon: VideoIcon },
  documento: { one: 'documento', many: 'documentos', Icon: FileText },
};

export function EvidenceCard({ e, accountId, onEdit }: { e: Evidence; accountId: number; onEdit?: () => void }) {
  const [gallery, setGallery] = useState<number | null>(null);
  const imgs = e.files.filter((f) => f.kind === 'imagem');
  const others = e.files.filter((f) => f.kind !== 'imagem');
  return (
    <View style={{ backgroundColor: colors.surface, borderRadius: radius.lg, borderWidth: 1,
      borderColor: e.important ? '#F3D9B8' : colors.border, overflow: 'hidden' }}>
      <View style={{ padding: space[4], gap: space[3] }}>
        <View style={{ flexDirection: 'row', alignItems: 'flex-start', gap: 8 }}>
          <Text variant="h3" style={{ flex: 1 }}>{e.title}</Text>
          {onEdit ? (
            <Pressable onPress={onEdit} hitSlop={10} accessibilityRole="button" accessibilityLabel={`Editar ${e.title}`}>
              <Pencil size={17} color={colors.action} />
            </Pressable>
          ) : null}
        </View>
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>
          {e.important ? <Chip label="★ Destaque" kind="highlight" /> : null}
          {e.source ? <Chip label={e.source} /> : null}
          {(Object.keys(KIND) as EvidenceFile['kind'][]).map((k) => {
            const n = e.files.filter((f) => f.kind === k).length;
            return n ? <Chip key={k} icon={KIND[k].Icon} label={`${n} ${n === 1 ? KIND[k].one : KIND[k].many}`} /> : null;
          })}
          {e.people ? <Chip icon={Users} label={e.people} /> : null}
        </View>
        {e.description ? <Text variant="muted">{e.description}</Text> : null}
        {imgs.length ? (
          <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
            {imgs.slice(0, 4).map((f, i) => (
              <Pressable key={f.id} onPress={() => setGallery(i)} accessibilityRole="imagebutton" accessibilityLabel={`Ampliar ${f.name}`}
                style={{ width: '48.5%', height: 150, borderRadius: radius.md, overflow: 'hidden', backgroundColor: colors.surface2 }}>
                <AuthImage file={f} accountId={accountId} style={{ width: '100%', height: '100%' }} />
                {i === 3 && imgs.length > 4 ? (
                  <View style={{ position: 'absolute', inset: 0, backgroundColor: 'rgba(14,26,43,0.62)', alignItems: 'center', justifyContent: 'center' }}>
                    <Text style={{ color: '#fff', fontFamily: fonts.display, fontSize: 24 }}>+{imgs.length - 4}</Text>
                  </View>
                ) : null}
              </Pressable>
            ))}
          </View>
        ) : null}
        {others.map((f) => (f.kind === 'audio' ? <AudioRow key={f.id} file={f} /> : f.kind === 'video' ? <VideoBox key={f.id} file={f} /> : <DocRow key={f.id} file={f} />))}
      </View>
      {e.files.length ? (
        <View style={{ borderTopWidth: 1, borderTopColor: colors.surface2, padding: space[4], paddingVertical: space[3], gap: 8 }}>
          {e.files.map((f) => <Integrity key={f.id} file={f} />)}
        </View>
      ) : null}
      {gallery !== null ? <Gallery files={imgs} start={gallery} accountId={accountId} onClose={() => setGallery(null)} /> : null}
    </View>
  );
}

