#!/bin/sh
# Emite (ou renova) o certificado do Let's Encrypt da origem e ativa o HTTPS no nginx.
# Rodar como root depois que processointegra.com.br estiver ativo no Cloudflare.
# Depois, no Cloudflare: SSL/TLS > modo "Full (strict)".
set -eu
cd /opt/timeline
mkdir -p /var/www/letsencrypt
certbot certonly --webroot -w /var/www/letsencrypt \
  -d processointegra.com.br -d www.processointegra.com.br \
  --cert-name processointegra.com.br \
  --non-interactive --agree-tos --register-unsafely-without-email \
  --deploy-hook "systemctl reload nginx" --keep-until-expiring
sh deploy/install.sh
