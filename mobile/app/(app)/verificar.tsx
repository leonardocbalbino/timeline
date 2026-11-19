import * as DocumentPicker from 'expo-document-picker';
import { File } from 'expo-file-system';
import { router } from 'expo-router';
import { ShieldCheck, ShieldX } from 'lucide-react-native';
import { useState } from 'react';
import { Pressable, ScrollView, View } from 'react-native';

import { Button, Card, Notice, Text } from '@/components/ui';
import { api, uploadInParts, type VerifyResult } from '@/lib/api';
import { fmtDateTime } from '@/lib/format';
import { colors, fonts, radius, space } from '@/theme';

export default function Verify() {
  const [busy, setBusy] = useState(false);
  const [pct, setPct] = useState(0);
  const [result, setResult] = useState<VerifyResult | null>(null);
  const [error, setError] = useState('');

  const pick = async () => {
    const r = await DocumentPicker.getDocumentAsync({ copyToCacheDirectory: true, type: '*/*' });
    if (r.canceled) return;
    const a = r.assets[0];
    const size = a.size || new File(a.uri).size || 0;
    setError('');
    setResult(null);
    setBusy(true);
    setPct(0);
    try {
      const id = await uploadInParts({ uri: a.uri, name: a.name, size, mimeType: a.mimeType || 'application/octet-stream' },
        'verificar', (b) => setPct(Math.floor((b / (size || 1)) * 100)));
      setResult(await api.verify(id));
    } catch (e: any) {
      setError(e?.message || 'Não foi possível verificar.');
    } finally {
      setBusy(false);
    }
  };

  const ok = !!result?.matches.length;
  return (
    <ScrollView contentContainerStyle={{ padding: space[4], gap: space[4] }}>
      <Text variant="muted">Escolha uma cópia de um arquivo para conferir se ela é idêntica, bit a bit, a alguma prova registrada. O arquivo enviado aqui não é salvo.</Text>
      <Button title={busy ? `Enviando… ${pct}%` : 'Escolher arquivo'} icon={ShieldCheck} onPress={pick} loading={busy} />
      {error ? <Notice text={error} /> : null}
      {result ? (
        <View style={{ backgroundColor: ok ? colors.verifiedBg : colors.dangerBg, borderRadius: radius.lg, padding: space[4], gap: space[2] }}>
          <View style={{ flexDirection: 'row', gap: 10, alignItems: 'center' }}>
            {ok ? <ShieldCheck size={24} color={colors.verified} /> : <ShieldX size={24} color={colors.danger} />}
            <Text variant="h3" style={{ flex: 1, color: ok ? colors.verified : colors.danger }}>
              {ok ? `Arquivo íntegro — idêntico ao registrado em ${fmtDateTime(result.matches[0].uploaded_at)}` : 'Este arquivo não corresponde a nenhuma prova registrada'}
            </Text>
          </View>
          <Text variant="label">{result.name}</Text>
          <Text style={{ fontFamily: fonts.mono, fontSize: 12, color: ok ? colors.verified : colors.textMuted }}>SHA-256 {result.sha256}</Text>
          {result.matches.map((m) => (
            <Pressable key={m.id} onPress={() => router.push({ pathname: '/processo/[id]', params: { id: String(m.process_id) } })} accessibilityRole="link">
              <Card style={{ padding: space[3], gap: 2 }}>
                <Text variant="label">{m.process_title}</Text>
                <Text variant="subtle">{fmtDateTime(m.occurred_at)} — {m.title}</Text>
              </Card>
            </Pressable>
          ))}
          {!ok ? <Text variant="small">Se é uma cópia de uma prova, ela foi alterada, recomprimida ou é outro arquivo.</Text> : null}
        </View>
      ) : null}
    </ScrollView>
  );
}

