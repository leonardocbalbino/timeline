import { router } from 'expo-router';
import { useState } from 'react';
import { KeyboardAvoidingView, Platform, ScrollView } from 'react-native';

import { Button, Field, Notice, Text } from '@/components/ui';
import { api } from '@/lib/api';
import { space } from '@/theme';

export default function NewProcess() {
  const [titulo, setTitulo] = useState('');
  const [numero, setNumero] = useState('');
  const [descricao, setDescricao] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const save = async () => {
    setBusy(true);
    setError('');
    try {
      const { process } = await api.createProcess(titulo, numero, descricao);
      router.replace({ pathname: '/processo/[id]', params: { id: String(process.id) } });
    } catch (e: any) {
      setError(e?.message || 'Não foi possível criar o processo.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={{ flex: 1 }}>
      <ScrollView contentContainerStyle={{ padding: space[5], gap: space[5] }} keyboardShouldPersistTaps="handled">
        <Text variant="muted">Um processo para cada caso. Dentro dele você monta a linha do tempo de provas.</Text>
        {error ? <Notice text={error} /> : null}
        <Field label="Nome do processo ou caso" value={titulo} onChangeText={setTitulo} placeholder="Ex.: Ação trabalhista — Empresa X" maxLength={200} />
        <Field label="Número do processo" hint="opcional" value={numero} onChangeText={setNumero}
          placeholder="0000000-00.0000.0.00.0000" maxLength={80} />
        <Field label="Descrição" hint="opcional" value={descricao} onChangeText={setDescricao} multiline numberOfLines={4}
          style={{ minHeight: 110 }} placeholder="Partes, vara, advogado, objetivo" />
        <Button title="Criar processo" onPress={save} loading={busy} disabled={!titulo.trim()} />
      </ScrollView>
    </KeyboardAvoidingView>
  );
}
