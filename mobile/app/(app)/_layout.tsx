import { Stack } from 'expo-router';

import { colors, fonts } from '@/theme';

export default function AppLayout() {
  return (
    <Stack
      screenOptions={{
        headerStyle: { backgroundColor: colors.surface },
        headerShadowVisible: false,
        headerTintColor: colors.ink,
        headerTitleStyle: { fontFamily: fonts.bodySemi, fontSize: 17 },
        headerBackButtonDisplayMode: 'minimal',
        contentStyle: { backgroundColor: colors.bg },
      }}
    >
      <Stack.Screen name="index" options={{ title: '' }} />
      <Stack.Screen name="processo/[id]" options={{ title: '' }} />
      <Stack.Screen name="nova-prova" options={{ title: 'Nova prova' }} />
      <Stack.Screen name="novo-processo" options={{ title: 'Novo processo', presentation: 'modal' }} />
      <Stack.Screen name="compartilhado" options={{ title: 'Salvar como prova' }} />
      <Stack.Screen name="verificar" options={{ title: 'Verificar arquivo' }} />
      <Stack.Screen name="conta" options={{ title: 'Conta' }} />
    </Stack>
  );
}
