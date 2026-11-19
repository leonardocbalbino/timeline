import * as Device from 'expo-device';
import * as SecureStore from 'expo-secure-store';
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';

import { api, setToken, setUnauthorizedHandler, type Me } from './api';

const TOKEN_KEY = 'integra.token';

type AuthState = {
  status: 'loading' | 'signedOut' | 'signedIn';
  me: Me | null;
  signIn: (email: string, senha: string) => Promise<void>;
  signOut: () => Promise<void>;
  forget: () => Promise<void>;
  refresh: () => Promise<void>;
};

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthState['status']>('loading');
  const [me, setMe] = useState<Me | null>(null);

  // Apaga a sessão local (token expirado, senha trocada, conta excluída ou "Sair").
  const forget = useCallback(async () => {
    setToken(null);
    setMe(null);
    setStatus('signedOut');
    await SecureStore.deleteItemAsync(TOKEN_KEY).catch(() => undefined);
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(() => void forget());
    (async () => {
      const saved = await SecureStore.getItemAsync(TOKEN_KEY).catch(() => null);
      if (!saved) {
        setStatus('signedOut');
        return;
      }
      setToken(saved);
      try {
        setMe(await api.me());
        setStatus('signedIn');
      } catch (e: any) {
        // Sem internet: mantém a sessão e tenta de novo quando a tela pedir dados.
        if (e?.status === 0) setStatus('signedIn');
        else await forget();
      }
    })();
    return () => setUnauthorizedHandler(null);
  }, [forget]);

  const signIn = useCallback(async (email: string, senha: string) => {
    const device = [Device.manufacturer, Device.modelName].filter(Boolean).join(' ') || 'Celular';
    const res = await api.login(email.trim().toLowerCase(), senha, device);
    await SecureStore.setItemAsync(TOKEN_KEY, res.token);
    setToken(res.token);
    const { token: _t, ...rest } = res;
    setMe(rest);
    setStatus('signedIn');
  }, []);

  const signOut = useCallback(async () => {
    await api.logout().catch(() => undefined);
    await forget();
  }, [forget]);

  const refresh = useCallback(async () => {
    setMe(await api.me());
  }, []);

  const value = useMemo(() => ({ status, me, signIn, signOut, forget, refresh }), [status, me, signIn, signOut, forget, refresh]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth fora do AuthProvider');
  return ctx;
}
