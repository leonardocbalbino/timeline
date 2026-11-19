import { router, Stack, useFocusEffect, useLocalSearchParams } from 'expo-router';
import { Clock, Plus, Share2 } from 'lucide-react-native';
import { useCallback, useMemo, useState } from 'react';
import { ActivityIndicator, Alert, Pressable, RefreshControl, SectionList, Share, View } from 'react-native';

import { EvidenceCard } from '@/components/media';
import { Button, Card, Empty, Notice, Text } from '@/components/ui';
import { api, type Evidence, type ProcessSummary } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { useDraft } from '@/lib/draft';
import { fmtDate, fmtDay, fmtTime } from '@/lib/format';
import { colors, fonts, space } from '@/theme';

export default function Timeline() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const pid = Number(id);
  const { me } = useAuth();
  const draft = useDraft();
  const [proc, setProc] = useState<ProcessSummary | null>(null);
  const [evs, setEvs] = useState<Evidence[] | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [sharing, setSharing] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await api.process(pid);
      setProc(r.process);
      setEvs(r.evidences);
      setError('');
    } catch (e: any) {
      setError(e?.message || 'Não foi possível carregar o processo.');
    } finally {
      setLoading(false);
    }
  }, [pid]);
  useFocusEffect(useCallback(() => {
    load();
  }, [load]));

  const sections = useMemo(() => {
    const out: { day: string; data: Evidence[] }[] = [];
    for (const e of evs ?? []) {
      const day = e.occurred_at.slice(0, 10);
      if (!out.length || out[out.length - 1].day !== day) out.push({ day, data: [] });
      out[out.length - 1].data.push(e);
    }
    return out;
  }, [evs]);

  const shareLink = async () => {
    setSharing(true);
    try {
      const { url } = await api.shareLink(pid);
      await Share.share({ message: `Linha do tempo de provas — ${proc?.title}\n${url}`, url });
    } catch (e: any) {
      Alert.alert('Link para o advogado', e?.message || 'Não foi possível gerar o link.');
    } finally {
      setSharing(false);
    }
  };

  const newEvidence = () => {
    draft.clear();
    router.push({ pathname: '/nova-prova', params: { pid: String(pid) } });
  };

  const accountId = me?.account.id ?? 0;
  const imgs = (evs ?? []).flatMap((e) => e.files).length;

  return (
    <>
      <Stack.Screen options={{
        title: proc?.title ?? '',
        headerRight: () => me?.features.compartilhar ? (
          <Pressable onPress={shareLink} hitSlop={10} accessibilityRole="button" accessibilityLabel="Compartilhar link somente leitura com o advogado">
            {sharing ? <ActivityIndicator color={colors.ink} /> : <Share2 size={21} color={colors.ink} />}
          </Pressable>
        ) : null,
      }} />
      <SectionList
        sections={sections}
        keyExtractor={(e) => String(e.id)}
        stickySectionHeadersEnabled={false}
        contentContainerStyle={{ padding: space[4], paddingBottom: 120 }}
        refreshControl={<RefreshControl refreshing={loading && evs !== null} onRefresh={load} />}
        ListHeaderComponent={proc ? (
          <View style={{ gap: 6, marginBottom: space[4] }}>
            <Text variant="h1" style={{ fontSize: 26, lineHeight: 31 }}>{proc.title}</Text>
            <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 12 }}>
              {proc.number ? <Text variant="mono">Proc. {proc.number}</Text> : null}
              <Text variant="subtle"><Text variant="label">{evs?.length ?? 0}</Text> registro{evs?.length === 1 ? '' : 's'} · {imgs} arquivo{imgs === 1 ? '' : 's'}</Text>
              {sections.length ? <Text variant="mono">{fmtDate(sections[0].day)} → {fmtDate(sections[sections.length - 1].day)}</Text> : null}
            </View>
            {error ? <Notice text={error} /> : null}
          </View>
        ) : error ? <Notice text={error} /> : <ActivityIndicator style={{ marginTop: 40 }} color={colors.ink} />}
        ListEmptyComponent={evs && !evs.length ? (
          <Card><Empty icon={Clock} title="Nenhuma prova ainda" text="Adicione prints, áudios, vídeos e documentos na ordem em que aconteceram.">
            <Button title="Adicionar a primeira prova" icon={Plus} onPress={newEvidence} />
          </Empty></Card>
        ) : undefined}
        renderSectionHeader={({ section }) => (
          <View style={{ flexDirection: 'row', alignItems: 'baseline', gap: 8, marginTop: space[4], marginBottom: space[3] }}>
            <Text variant="h2" style={{ fontSize: 18 }}>{fmtDay(section.day)}</Text>
            <Text variant="small">{section.data.length}</Text>
          </View>
        )}
        renderItem={({ item: e, index, section }) => {
          const first = index === 0;
          const last = index === section.data.length - 1;
          return (
            <View style={{ flexDirection: 'row', gap: 8 }}>
              <Text style={{ width: 46, textAlign: 'right', fontFamily: fonts.monoMedium, fontSize: 12, color: colors.textMuted, paddingTop: 18 }}>
                {fmtTime(e.occurred_at)}
              </Text>
              <View style={{ width: 18, alignItems: 'center' }}>
                <View style={{ position: 'absolute', top: first ? 22 : 0, bottom: last ? undefined : 0, height: last ? 22 : undefined,
                  width: 2, backgroundColor: section.data.length > 1 ? colors.borderStrong : 'transparent' }} />
                <View style={{ marginTop: e.important ? 16 : 18, width: e.important ? 16 : 12, height: e.important ? 16 : 12,
                  borderRadius: 8, borderWidth: 2, borderColor: e.important ? colors.highlight : colors.ink,
                  backgroundColor: e.important ? colors.highlight : colors.surface }} />
              </View>
              <View style={{ flex: 1, paddingBottom: space[3] }}>
                <EvidenceCard e={e} accountId={accountId}
                  onEdit={() => router.push({ pathname: '/nova-prova', params: { pid: String(pid), eid: String(e.id) } })} />
              </View>
            </View>
          );
        }}
      />
      {evs?.length ? (
        <View style={{ position: 'absolute', left: space[4], right: space[4], bottom: space[8] }}>
          <Button title="Nova prova" icon={Plus} onPress={newEvidence} />
        </View>
      ) : null}
    </>
  );
}
