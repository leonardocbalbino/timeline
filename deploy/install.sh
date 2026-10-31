#!/bin/sh
# Instala/atualiza o sistema em /opt/timeline (Ubuntu). Rodar como root.
set -e
cd /opt/timeline
apt-get install -y -q python3-venv >/dev/null
id timeline >/dev/null 2>&1 || useradd --system --home /opt/timeline --shell /usr/sbin/nologin timeline
[ -d venv ] || python3 -m venv venv
venv/bin/pip install -q -r requirements.txt
if [ ! -f .env ]; then
  cat > .env <<ENV
SECRET_KEY=$(openssl rand -hex 32)
ADMIN_EMAIL=admin
ADMIN_PASSWORD=$(openssl rand -base64 18 | tr -d '/+=' | cut -c1-16)
ENV
  chmod 600 .env
fi
# Asaas: token do webhook gerado aqui; a chave da API (ASAAS_API_KEY) é preenchida à mão no .env
grep -q '^ASAAS_WEBHOOK_TOKEN=' .env || echo "ASAAS_WEBHOOK_TOKEN=$(openssl rand -hex 24)" >> .env
grep -q '^ASAAS_ENV=' .env || echo "ASAAS_ENV=sandbox" >> .env
grep -q '^ASAAS_API_KEY=' .env || echo "ASAAS_API_KEY=" >> .env
mkdir -p data/uploads
chown -R timeline:timeline data
chmod 750 data data/uploads
# nginx (www-data) precisa ler os uploads para servir via X-Accel-Redirect
usermod -aG timeline www-data
cp deploy/timeline.service /etc/systemd/system/timeline.service
cp deploy/nginx.conf /etc/nginx/sites-available/timeline
ln -sf /etc/nginx/sites-available/timeline /etc/nginx/sites-enabled/timeline
# Domínio (processointegra.com.br) atrás do Cloudflare; HTTPS na origem só quando o certificado existir
mkdir -p /etc/nginx/snippets /var/www/letsencrypt
cp deploy/nginx-cloudflare.conf /etc/nginx/snippets/integra-cloudflare.conf
cp deploy/nginx-app.conf /etc/nginx/snippets/integra-app.conf
cp deploy/nginx-dominio.conf /etc/nginx/sites-available/timeline-dominio
ln -sf /etc/nginx/sites-available/timeline-dominio /etc/nginx/sites-enabled/timeline-dominio
if [ -f /etc/letsencrypt/live/processointegra.com.br/fullchain.pem ]; then
  cp deploy/nginx-dominio-ssl.conf /etc/nginx/sites-available/timeline-dominio-ssl
  ln -sf /etc/nginx/sites-available/timeline-dominio-ssl /etc/nginx/sites-enabled/timeline-dominio-ssl
else
  rm -f /etc/nginx/sites-enabled/timeline-dominio-ssl
fi
systemctl daemon-reload
systemctl enable --now timeline >/dev/null
systemctl restart timeline
nginx -t && systemctl reload nginx
echo "OK"
