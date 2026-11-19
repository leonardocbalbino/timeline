# Íntegra — app Android e iOS

App nativo (Expo SDK 58 / React Native) que usa a API do site (`/api/v1`).

## O que o app faz

- Login com a conta do site (token guardado no armazenamento seguro do aparelho; trocar a senha derruba o app).
- Lista de processos, criação de processo, linha do tempo com imagens, áudio, vídeo e documentos.
- Nova prova: câmera, galeria (várias de uma vez), arquivos e gravação de áudio. Data e hora sugeridas pelos dados
  da foto (EXIF) ou pelo nome do arquivo. Envio em partes de 8 MB com retomada (passa pelo Cloudflare).
- **Compartilhar para Íntegra**: prints, áudios, vídeos e PDFs enviados do WhatsApp, galeria ou gravador.
- Editar e excluir prova, link somente leitura para o advogado, verificação de integridade.
- Conta: plano e uso, privacidade, termos, sair e **excluir a conta** (exigência das lojas).

O app **não vende o plano Pro** nem leva à compra (regras da App Store 3.1.1 e do Google Play): a assinatura é feita
só pelo site, e o app apenas respeita o plano da conta.

## Desenvolvimento

```sh
cd mobile
npm install
npx expo prebuild --clean          # gera android/ e ios/ (não vão para o Git)
npx expo run:android               # ou run:ios num Mac
```

O "Compartilhar para" e os módulos nativos não funcionam no Expo Go: use um *development build* (`run:android`
ou `eas build --profile development`). Para apontar para um servidor local: `EXPO_PUBLIC_API_URL=http://10.0.2.2:8410`.

Antes de entregar: `npx tsc --noEmit` e `npx expo-doctor`.

## Publicação

1. Contas: [Google Play Console](https://play.google.com/console) (taxa única) e
   [Apple Developer Program](https://developer.apple.com/programs/) (anual). Conta Expo para o EAS.
2. `npm i -g eas-cli && eas login && eas init` (cria o projeto no EAS e grava o `projectId` no app.json).
3. Builds: `eas build --profile production --platform android` (AAB) e `--platform ios` (IPA, sem precisar de Mac).
4. Envio: `eas submit --profile production --platform android|ios`.

### Ficha das lojas

| Item | Valor |
|---|---|
| Nome | Íntegra — Provas em ordem |
| Pacote / Bundle ID | `br.com.processointegra.app` |
| Categoria | Produtividade (Google) / Produtividade (Apple) |
| Política de privacidade | https://processointegra.com.br/privacidade |
| Termos | https://processointegra.com.br/termos |
| Exclusão de conta | https://processointegra.com.br/excluir-conta (e dentro do app: Conta › Excluir minha conta) |
| Classificação etária | 18+ (conteúdo enviado pelo usuário, sem conteúdo próprio impróprio) |
| Login para revisão | crie uma conta de teste Pro com processos de exemplo e informe e-mail/senha na ficha |

**Segurança dos dados (Google) / Privacidade (Apple):** o app coleta nome, e-mail, fotos, vídeos, áudios e arquivos
enviados pelo usuário e identificadores do aparelho (modelo), para funcionalidade do app; dados criptografados em
trânsito; o usuário pode pedir a exclusão; nada é usado para rastreamento ou publicidade; compartilhado com
processadores (Cloudflare, provedor de servidores). Confira as respostas com a política de privacidade antes de enviar.
