import * as WebBrowser from 'expo-web-browser';
import { useState } from 'react';
import { KeyboardAvoidingView, Platform, Pressable, ScrollView, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Button, Card, Field, Logo, Notice, Text } from '@/components/ui';
import { API_URL } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { colors, space } from '@/theme';

export default function Login() {
  const { signIn } = useAuth();
  const [email, setEmail] = useState('');
  const [senha, setSenha] = useState('');
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const submit = async () => {
    setError('');
    setBusy(true);
    try {
      await signIn(email, senha);
    } catch (e: any) {
      setError(e?.message || 'Não foi possível entrar.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }}>
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={{ flex: 1 }}>
        <ScrollView contentContainerStyle={{ flexGrow: 1, justifyContent: 'center', padding: space[5] }} keyboardShouldPersistTaps="handled">
          <Card style={{ padding: space[6], gap: space[5], borderRadius: 20 }}>
            <Logo />
            <View style={{ gap: 4 }}>
              <Text variant="h1" style={{ fontSize: 28 }}>Entrar</Text>
              <Text variant="subtle">Provas em ordem, do fato ao processo.</Text>
            </View>
            {error ? <Notice text={error} /> : null}
            <Field label="E-mail" value={email} onChangeText={setEmail} autoCapitalize="none" autoCorrect={false}
              keyboardType="email-address" autoComplete="email" textContentType="username" returnKeyType="next" />
            <View>
              <Field label="Senha" value={senha} onChangeText={setSenha} secureTextEntry={!show} autoComplete="current-password"
                textContentType="password" returnKeyType="go" onSubmitEditing={submit} />
              <Pressable onPress={() => setShow(!show)} accessibilityRole="button" style={{ alignSelf: 'flex-end', paddingVertical: 8 }}>
                <Text variant="small" style={{ color: colors.action }}>{show ? 'Ocultar senha' : 'Mostrar senha'}</Text>
              </Pressable>
            </View>
            <Button title="Entrar" onPress={submit} loading={busy} disabled={!email || !senha} />
            <View style={{ flexDirection: 'row', justifyContent: 'center', flexWrap: 'wrap', gap: 6 }}>
              <Text variant="subtle">Ainda não tem conta?</Text>
              <Pressable onPress={() => WebBrowser.openBrowserAsync(`${API_URL}/cadastro`)} accessibilityRole="link">
                <Text variant="subtle" style={{ color: colors.action }}>Crie grátis</Text>
              </Pressable>
            </View>
          </Card>
          <View style={{ flexDirection: 'row', justifyContent: 'center', gap: space[4], marginTop: space[5] }}>
            <Pressable onPress={() => WebBrowser.openBrowserAsync(`${API_URL}/privacidade`)} accessibilityRole="link">
              <Text variant="small">Privacidade</Text>
            </Pressable>
            <Pressable onPress={() => WebBrowser.openBrowserAsync(`${API_URL}/termos`)} accessibilityRole="link">
              <Text variant="small">Termos de uso</Text>
            </Pressable>
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}
