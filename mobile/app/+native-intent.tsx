// O "Compartilhar para Íntegra" abre o app por um link interno (integra://dataUrl=...).
// Esse link não é uma tela: mandamos para a escolha do processo; os arquivos chegam pelo ShareIntentProvider.
export function redirectSystemPath({ path }: { path: string; initial: boolean }) {
  try {
    if (path.includes('dataUrl=')) return '/compartilhado';
    return path;
  } catch {
    return '/';
  }
}
