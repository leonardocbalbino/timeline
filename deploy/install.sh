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
ADMIN_PASSWORD=$(openssl rand -base64 18 | tr -d '/+=' | cut -c1-16)
VIEWER_PASSWORD=$(openssl rand -base64 18 | tr -d '/+=' | cut -c1-16)
ENV
  chmod 600 .env
fi
mkdir -p data/uploads
chown -R timeline:timeline data
chmod 750 data data/uploads
# nginx (www-data) precisa ler os uploads para servir via X-Accel-Redirect
usermod -aG timeline www-data
cp deploy/timeline.service /etc/systemd/system/timeline.service
cp deploy/nginx.conf /etc/nginx/sites-available/timeline
ln -sf /etc/nginx/sites-available/timeline /etc/nginx/sites-enabled/timeline
systemctl daemon-reload
systemctl enable --now timeline >/dev/null
systemctl restart timeline
nginx -t && systemctl reload nginx
echo "OK"
