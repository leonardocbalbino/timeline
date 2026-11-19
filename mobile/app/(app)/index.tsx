import { router, Stack, useFocusEffect } from 'expo-router';
import { Folder, Link2, Plus, ShieldCheck, UserRound } from 'lucide-react-native';
import { useCallback, useState } from 'react';
import { FlatList, Pressable, RefreshControl, View } from 'react-native';

import { Button, Card, Empty, Logo, Notice, Text } from '@/components/ui';
import { api, type ProcessSummary } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { fmtDate } from '@/lib/format';
import { colors, space } from '@/theme';

export default function Processes() {
  const { me, refresh } = useAuth();
  const [items, setItems] = useState<ProcessSummary[] | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [{ processes }] = await Promise.all([api.processes(), refresh().catch(() => undefined)]);
      setItems(processes);
      setError('');
    } catch (e: any) {
      setError(e?.message || 'Não foi possível carregar os processos.');
    } finally {
      setLoading(false);
    }
  }, [refresh]);

  useFocusEffect(useCallback(() => {
    load();
  }, [load]));

  const limit = me?.limits.processes ?? 0;
  const atLimit = !!limit && (me?.usage.processes ?? 0) >= limit;

  return (
    <>
      <Stack.Screen options={{
        headerTitle: () => <Logo />,
        headerRight: () => (
          <View style={{ flexDirection: 'row', gap: 18 }}>
            {me?.features.verificar ? (
              <Pressable onPress={() => router.push('/verificar')} hitSlop={10} accessibilityRole="button" accessibilityLabel="Verificar arquivo">
                <ShieldCheck size={22} color={colors.ink} />
              </Pressable>
            ) : null}
            <Pressable onPress={() => router.push('/conta')} hitSlop={10} accessibilityRole="button" accessibilityLabel="Conta">
              <UserRound size={22} color={colors.ink} />
            </Pressable>
          </View>
        ),
      }} />
      <FlatList
        data={items ?? []}
        keyExtractor={(p) => String(p.id)}
        contentContainerStyle={{ padding: space[4], gap: space[3], paddingBottom: 120 }}
        refreshControl={<RefreshControl refreshing={loading && items !== null} onRefresh={load} />}
        ListHeaderComponent={
          <View style={{ gap: 6, marginBottom: space[2] }}>
            <Text variant="h1">Processos</Text>
            <Text variant="subtle">{me?.account.name}{me ? ` · plano ${me.account.plan_label}` : ''}</Text>
            {error ? <Notice text={error} /> : null}
          </View>
        }
        ListEmptyComponent={items === null ? undefined : (
          <Card><Empty icon={Folder} title="Nenhum processo ainda" text="Crie um processo para cada caso e monte nele a linha do tempo de provas.">
            <Button title="Criar o primeiro processo" icon={Plus} onPress={() => router.push('/novo-processo')} />
          </Empty></Card>
        )}
        renderItem={({ item: p }) => (
          <Pressable onPress={() => router.push({ pathname: '/processo/[id]', params: { id: String(p.id) } })} accessibilityRole="button"
            style={({ pressed }) => ({ opacity: pressed ? 0.85 : 1 })}>
            <Card style={{ gap: space[2] }}>
              <Text variant="h3">{p.title}</Text>
              {p.number ? <Text variant="mono">Proc. {p.number}</Text> : null}
              {p.description ? <Text variant="subtle" numberOfLines={2}>{p.description}</Text> : null}
              <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 14, borderTopWidth: 1, borderTopColor: colors.surface2,
                paddingTop: space[3], marginTop: space[1] }}>
                <Text variant="small"><Text variant="label" style={{ fontSize: 13 }}>{p.evidence_count ?? 0}</Text> prova{p.evidence_count === 1 ? '' : 's'}</Text>
                {p.first_at ? <Text variant="mono" style={{ fontSize: 12 }}>{fmtDate(p.first_at)} → {fmtDate(p.last_at)}</Text> : null}
                {p.shared ? <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4 }}><Link2 size={13} color={colors.textSubtle} /><Text variant="small">Link ativo</Text></View> : null}
              </View>
            </Card>
          </Pressable>
        )}
      />
      {items?.length ? (
        <View style={{ position: 'absolute', left: space[4], right: space[4], bottom: space[8] }}>
          {atLimit ? (
            <Notice kind="info" text={`Seu plano permite até ${limit} processo${limit > 1 ? 's' : ''}.`} />
          ) : (
            <Button title="Novo processo" icon={Plus} onPress={() => router.push('/novo-processo')} />
          )}
        </View>
      ) : null}
    </>
  );
}
