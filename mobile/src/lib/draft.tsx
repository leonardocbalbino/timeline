// Arquivos escolhidos (câmera, galeria, arquivos, gravação ou "Compartilhar para") aguardando virar prova.
import { createContext, useContext, useMemo, useState, type ReactNode } from 'react';

import type { LocalFile } from './api';

type DraftState = {
  files: LocalFile[];
  setFiles: (files: LocalFile[]) => void;
  add: (files: LocalFile[]) => void;
  remove: (uri: string) => void;
  clear: () => void;
};

const DraftContext = createContext<DraftState | null>(null);

export function DraftProvider({ children }: { children: ReactNode }) {
  const [files, setFiles] = useState<LocalFile[]>([]);
  const value = useMemo<DraftState>(() => ({
    files,
    setFiles,
    add: (more) => setFiles((cur) => [...cur, ...more.filter((m) => !cur.some((c) => c.uri === m.uri))]),
    remove: (uri) => setFiles((cur) => cur.filter((f) => f.uri !== uri)),
    clear: () => setFiles([]),
  }), [files]);
  return <DraftContext.Provider value={value}>{children}</DraftContext.Provider>;
}

export function useDraft() {
  const ctx = useContext(DraftContext);
  if (!ctx) throw new Error('useDraft fora do DraftProvider');
  return ctx;
}
