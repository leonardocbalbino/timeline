# Linha do Tempo de Provas

Sistema leve (Python/Flask + SQLite) para organizar prints, áudios e vídeos em
uma linha do tempo por dia e horário, para apresentação ao jurídico.

## Recursos

- Linha do tempo agrupada por dia, com hora de cada registro, player de áudio e vídeo e ampliação de imagens.
- Vários arquivos por registro, com título, descrição, origem (WhatsApp, Instagram...), pessoas envolvidas e destaque.
- Data e hora sugeridas pelo nome do arquivo (padrões do WhatsApp, `Screenshot_…`, `IMG_…`, `VID_…`).
- **Hash SHA-256** de cada arquivo calculado no envio, para provar que ele não foi alterado.
- Página **Verificar arquivo**: confere se uma cópia é idêntica ao arquivo registrado.
- **Relatório** pronto para imprimir ou salvar em PDF.
- **Pacote ZIP** com todos os originais em ordem cronológica, mais `manifesto.csv` com os hashes.
- **Auditoria**: logins, criações, edições, exclusões e downloads ficam registrados.
- Dois perfis: `admin` (cadastra e edita) e `leitor` (só visualiza; é este que vai para o advogado).

## Instalação (Ubuntu)

```sh
git clone https://github.com/leonardocbalbino/timeline.git /opt/timeline
sh /opt/timeline/deploy/install.sh
cat /opt/timeline/.env   # senhas geradas: ADMIN_PASSWORD e VIEWER_PASSWORD
```

O sistema roda em `http://SEU_IP:8400`. Os arquivos ficam em `/opt/timeline/data/`
e **não** vão para o repositório.

## Backup

```sh
tar czf provas-$(date +%F).tar.gz -C /opt/timeline data
```
