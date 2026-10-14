# Linha do Tempo de Provas

Sistema leve (Python/Flask + SQLite), multi-cliente, para organizar prints, áudios e vídeos
em uma linha do tempo por processo, dia e horário, para apresentação ao jurídico.

## Como funciona

- **Admin** (você): cadastra clientes, define quem é **Free** ou **Pro** (com ou sem vencimento),
  escolhe o que cada plano libera, configura o Pix e confirma pagamentos. Pode “Acessar conta” de um
  cliente para dar suporte (fica registrado na auditoria).
- **Cliente**: entra com e-mail e senha, cria **processos** e, dentro de cada processo, monta a linha do
  tempo de provas.
- **Advogado / terceiros**: recebem um link somente leitura do processo (recurso Pro).

## Recursos

- Linha do tempo **vertical** (padrão) ou **horizontal**, agrupada por dia, com player de áudio e vídeo e ampliação de imagens.
- Vários arquivos por registro, com título, descrição, origem (WhatsApp, Instagram...), pessoas envolvidas e destaque.
- Data e hora sugeridas pelo nome do arquivo (padrões do WhatsApp, `Screenshot_…`, `IMG_…`, `VID_…`).
- **Hash SHA-256** de cada arquivo calculado no envio, para provar que ele não foi alterado.
- **Verificar arquivo**: confere se uma cópia é idêntica ao arquivo registrado.
- **Relatório** pronto para imprimir ou salvar em PDF.
- **Pacote ZIP** com todos os originais em ordem cronológica, mais `manifesto.csv` com os hashes.
- **Auditoria**: logins, criações, edições, exclusões, downloads e acessos por link ficam registrados.

## Planos e pagamento

Em **Admin › Planos e Pix** você marca quais funcionalidades cada plano libera e os limites de
processos e de armazenamento. Por padrão:

| | Free | Pro |
|---|---|---|
| Processos | 1 | ilimitados |
| Armazenamento | 1 GB | 50 GB |
| Linha do tempo horizontal, ZIP, link para advogado, auditoria | – | ✓ |
| Relatório e verificação de arquivo | ✓ | ✓ |

O Pro é pago via **Pix**. O sistema gera QR Code e “copia e cola” com o valor e um identificador
por cobrança. O cliente clica em “Já paguei” (pode anexar o comprovante) e o admin confirma em
**Pagamentos**, o que libera o Pro somando os dias ao vencimento. Quando o Pro vence, o cliente
volta para o Free sem perder dados.

## Instalação (Ubuntu)

```sh
git clone https://github.com/leonardocbalbino/timeline.git /opt/timeline
sh /opt/timeline/deploy/install.sh
cat /opt/timeline/.env   # login do admin: ADMIN_EMAIL / ADMIN_PASSWORD
```

O sistema roda em `http://SEU_IP:8400`. Os arquivos ficam em `/opt/timeline/data/`
e **não** vão para o repositório.

O usuário admin é criado na primeira inicialização a partir de `ADMIN_EMAIL` (padrão `admin`) e
`ADMIN_PASSWORD`. Depois disso a senha pode ser trocada em “Minha conta”.

### Atualizando a partir da versão de usuário único

```sh
cd /opt/timeline && git pull && sh deploy/install.sh
```

Na primeira inicialização, as provas existentes vão para o cliente **“Conta principal”**
(Pro sem vencimento), no processo **“Processo principal”**. Entre como `admin` com a mesma
`ADMIN_PASSWORD` e use “Acessar” nesse cliente. A senha `VIEWER_PASSWORD` deixa de existir:
para o advogado, gere um link somente leitura em *Processo e link*.

## Backup

```sh
tar czf provas-$(date +%F).tar.gz -C /opt/timeline data
```
