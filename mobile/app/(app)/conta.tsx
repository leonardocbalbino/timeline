import * as WebBrowser from 'expo-web-browser';
import { LogOut, Trash2 } from 'lucide-react-native';
import { useState } from 'react';
import { Alert, Pressable, ScrollView, View } from 'react-native';

import { Button, Card, Chip, Field, Notice, Text } from '@/components/ui';
import { api, API_URL } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { fmtDate, humanSize } from '@/lib/format';
import { colors, space } from '@/theme';

// Regras da App Store e do Google Play: o app não vende nem leva para a compra do plano.
export default function Account() {
  const { me, signOut, forget } = useAuth();
  const [deleting, setDeleting] = useState(false);
  const [senha, setSenha] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  if (!me) return null;

  const storageLimit = me.limits.storage_mb * 1024 * 1024;
  const confirmDelete = () => Alert.alert(
    'Excluir conta',
    'Todos os processos, provas e arquivos serão apagados definitivamente. Uma assinatura do Pro, se houver, é cancelada. Não tem como desfazer.',
    [{ text: 'Cancelar', style: 'cancel' }, {
      text: 'Excluir definitivamente', style: 'destructive', onPress: async () => {
        setBusy(true);
        setError('');
        try {
          await api.deleteAccount(senha);
          await forget();
        } catch (e: any) {
          setError(e?.message || 'Não foi possível excluir a conta.');
        } finally {
          setBusy(false);
        }
      },
    }],
  );

  return (
    <ScrollView contentContainerStyle={{ padding: space[4], gap: space[4] }}>
      <Card style={{ gap: space[2] }}>
        <Text variant="h2">{me.account.name}</Text>
        <Text variant="subtle">{me.user.email}</Text>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: space[2] }}>
          <Chip label={me.account.plan_label} kind={me.account.plan === 'pro' ? 'dark' : 'default'} />
          {me.account.plan === 'pro' ? <Text variant="small">{me.account.pro_until ? `até ${fmtDate(me.account.pro_until)}` : 'sem vencimento'}</Text> : null}
        </View>
        <Text variant="small">
          {me.usage.processes}{me.limits.processes ? ` de ${me.limits.processes}` : ''} processo{me.usage.processes === 1 ? '' : 's'} ·{' '}
          {humanSize(me.usage.storage_bytes)}{storageLimit ? ` de ${humanSize(storageLimit)}` : ''}
        </Text>
      </Card>

      <View style={{ flexDirection: 'row', justifyContent: 'center', gap: space[5] }}>
        <Pressable onPress={() => WebBrowser.openBrowserAsync(`${API_URL}/privacidade`)} accessibilityRole="link">
          <Text variant="subtle" style={{ color: colors.action }}>Privacidade</Text>
        </Pressable>
        <Pressable onPress={() => WebBrowser.openBrowserAsync(`${API_URL}/termos`)} accessibilityRole="link">
          <Text variant="subtle" style={{ color: colors.action }}>Termos de uso</Text>
        </Pressable>
      </View>

      <Button kind="secondary" icon={LogOut} title="Sair" onPress={signOut} />

      <Card style={{ gap: space[3], borderColor: '#F5C9C4' }}>
        <Text variant="h3" style={{ color: colors.danger }}>Excluir minha conta</Text>
        {!deleting ? (
          <>
            <Text variant="subtle">Apaga a conta e todos os dados: processos, provas, arquivos e links. Baixe antes o pacote ZIP dos processos pelo site se quiser guardar os originais.</Text>
            <Button kind="ghost" icon={Trash2} title="Excluir minha conta" onPress={() => setDeleting(true)} style={{ alignSelf: 'flex-start' }} />
          </>
        ) : (
          <>
            <Field label="Confirme com sua senha" value={senha} onChangeText={setSenha} secureTextEntry autoComplete="current-password" />
            {error ? <Notice text={error} /> : null}
            <Button kind="danger" icon={Trash2} title="Excluir definitivamente" onPress={confirmDelete} loading={busy} disabled={!senha} />
            <Button kind="ghost" title="Cancelar" onPress={() => { setDeleting(false); setSenha(''); setError(''); }} />
          </>
        )}
      </Card>
    </ScrollView>
  );
}
