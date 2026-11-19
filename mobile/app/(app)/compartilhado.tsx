import { router, useFocusEffect } from 'expo-router';
import { ChevronRight, FileText, Plus } from 'lucide-react-native';
import { useCallback, useState } from 'react';
import { ActivityIndicator, FlatList, Pressable, View } from 'react-native';

import { Button, Card, Empty, Notice, Text } from '@/components/ui';
import { api, type ProcessSummary } from '@/lib/api';
import { useDraft } from '@/lib/draft';
import { humanSize } from '@/lib/format';
import { colors, space } from '@/theme';

/** Arquivos recebidos pelo "Compartilhar para Íntegra": o usuário escolhe em qual processo salvar. */
export default function SharedFiles() {
  const draft = useDraft();
  const [items, setItems] = useState<ProcessSummary[] | null>(null);
  const [error, setError] = useState('');

  useFocusEffect(useCallback(() => {
    api.processes().then((r) => setItems(r.processes)).catch((e) => setError(e?.message || 'Não foi possível carregar.'));
  }, []));

  const total = draft.files.reduce((t, f) => t + f.size, 0);
  const choose = (p: ProcessSummary) => router.replace({ pathname: '/nova-prova', params: { pid: String(p.id) } });

  return (
    <FlatList
      data={items ?? []}
      keyExtractor={(p) => String(p.id)}
      contentContainerStyle={{ padding: space[4], gap: space[3] }}
      ListHeaderComponent={
        <View style={{ gap: space[3], marginBottom: space[2] }}>
          <Card style={{ gap: 6 }}>
            <Text variant="label">{draft.files.length} arquivo{draft.files.length === 1 ? '' : 's'} recebido{draft.files.length === 1 ? '' : 's'} · {humanSize(total)}</Text>
            {draft.files.slice(0, 5).map((f) => (
              <View key={f.uri} style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                <FileText size={15} color={colors.textSubtle} />
                <Text variant="subtle" numberOfLines={1} style={{ flex: 1 }}>{f.name}</Text>
              </View>
            ))}
            {draft.files.length > 5 ? <Text variant="small">e mais {draft.files.length - 5}</Text> : null}
          </Card>
          <Text variant="h2">Em qual processo salvar?</Text>
          {error ? <Notice text={error} /> : null}
          {items === null && !error ? <ActivityIndicator color={colors.ink} /> : null}
        </View>
      }
      ListEmptyComponent={items ? (
        <Card><Empty icon={Plus} title="Nenhum processo ainda" text="Crie um processo para salvar estes arquivos.">
          <Button title="Criar processo" icon={Plus} onPress={() => router.push('/novo-processo')} />
        </Empty></Card>
      ) : undefined}
      renderItem={({ item: p }) => (
        <Pressable onPress={() => choose(p)} accessibilityRole="button" accessibilityLabel={`Salvar em ${p.title}`}>
          <Card style={{ flexDirection: 'row', alignItems: 'center', gap: space[3] }}>
            <View style={{ flex: 1, gap: 2 }}>
              <Text variant="h3">{p.title}</Text>
              <Text variant="small">{p.evidence_count ?? 0} prova{p.evidence_count === 1 ? '' : 's'}</Text>
            </View>
            <ChevronRight size={20} color={colors.textSubtle} />
          </Card>
        </Pressable>
      )}
      ListFooterComponent={items?.length ? (
        <Button kind="ghost" title="Cancelar" onPress={() => { draft.clear(); router.back(); }} style={{ marginTop: space[3] }} />
      ) : undefined}
    />
  );
}
