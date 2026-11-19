import { IBMPlexMono_400Regular } from '@expo-google-fonts/ibm-plex-mono/400Regular';
import { IBMPlexMono_500Medium } from '@expo-google-fonts/ibm-plex-mono/500Medium';
import { PublicSans_400Regular } from '@expo-google-fonts/public-sans/400Regular';
import { PublicSans_500Medium } from '@expo-google-fonts/public-sans/500Medium';
import { PublicSans_600SemiBold } from '@expo-google-fonts/public-sans/600SemiBold';
import { SchibstedGrotesk_700Bold } from '@expo-google-fonts/schibsted-grotesk/700Bold';
import { SchibstedGrotesk_800ExtraBold } from '@expo-google-fonts/schibsted-grotesk/800ExtraBold';
import { useFonts } from 'expo-font';
import { router, Stack } from 'expo-router';
import { ShareIntentProvider, useShareIntentContext } from 'expo-share-intent';
import * as SplashScreen from 'expo-splash-screen';
import { StatusBar } from 'expo-status-bar';
import { useEffect } from 'react';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import { AuthProvider, useAuth } from '@/lib/auth';
import { DraftProvider, useDraft } from '@/lib/draft';
import { colors } from '@/theme';

SplashScreen.preventAutoHideAsync().catch(() => undefined);

/** Arquivos recebidos pelo "Compartilhar para Íntegra" (WhatsApp, galeria, gravador...). */
function ShareIntentBridge() {
  const { hasShareIntent, shareIntent, resetShareIntent } = useShareIntentContext();
  const { status } = useAuth();
  const draft = useDraft();
  useEffect(() => {
    if (!hasShareIntent || status !== 'signedIn') return;
    const files = (shareIntent.files ?? []).map((f) => ({
      uri: f.path, name: f.fileName || f.path.split('/').pop() || 'arquivo', size: f.size ?? 0,
      mimeType: f.mimeType || 'application/octet-stream',
    }));
    if (files.length) {
      draft.setFiles(files);
      router.push('/compartilhado');
    }
    resetShareIntent();
  }, [hasShareIntent, shareIntent, status, draft, resetShareIntent]);
  return null;
}

function RootStack() {
  const { status } = useAuth();
  const [fontsLoaded] = useFonts({
    SchibstedGrotesk_700Bold, SchibstedGrotesk_800ExtraBold, PublicSans_400Regular, PublicSans_500Medium,
    PublicSans_600SemiBold, IBMPlexMono_400Regular, IBMPlexMono_500Medium,
  });
  const ready = fontsLoaded && status !== 'loading';
  useEffect(() => {
    if (ready) SplashScreen.hideAsync().catch(() => undefined);
  }, [ready]);
  if (!ready) return null;
  return (
    <>
      <ShareIntentBridge />
      <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: colors.bg } }}>
        <Stack.Protected guard={status === 'signedIn'}>
          <Stack.Screen name="(app)" />
        </Stack.Protected>
        <Stack.Protected guard={status !== 'signedIn'}>
          <Stack.Screen name="login" />
        </Stack.Protected>
      </Stack>
    </>
  );
}

export default function RootLayout() {
  return (
    <ShareIntentProvider options={{ resetOnBackground: false }}>
      <SafeAreaProvider>
        <AuthProvider>
          <DraftProvider>
            <StatusBar style="dark" />
            <RootStack />
          </DraftProvider>
        </AuthProvider>
      </SafeAreaProvider>
    </ShareIntentProvider>
  );
}
