#!/bin/sh
# Atualiza /opt/timeline para a última versão do branch main. Rodar como root.
# O GitHub Actions chama este script via SSH (chave restrita a este comando).
set -eu
cd /opt/timeline
exec 9>/var/lock/timeline-deploy.lock
flock 9

# Backup do banco antes de atualizar (guarda os 15 mais recentes)
if [ -f data/provas.db ] && [ -x venv/bin/python ]; then
  mkdir -p data/backups
  venv/bin/python - "data/backups/provas-$(date +%Y%m%d-%H%M%S).db" <<'PY'
import sqlite3, sys
src, dst = sqlite3.connect("data/provas.db"), sqlite3.connect(sys.argv[1])
src.backup(dst)
dst.close(); src.close()
PY
  ls -1t data/backups/provas-*.db | tail -n +16 | xargs -r rm -f
fi

git fetch -q origin main
git reset -q --hard origin/main
echo "Versão: $(git log -1 --format='%h %s')"
sh deploy/install.sh

for _ in 1 2 3 4 5 6 7 8 9 10; do
  if curl -fsS -o /dev/null http://127.0.0.1:8410/login; then
    echo "Aplicação respondendo."
    exit 0
  fi
  sleep 2
done
echo "ERRO: a aplicação não respondeu após o deploy." >&2
journalctl -u timeline -n 40 --no-pager >&2
exit 1
