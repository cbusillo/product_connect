#!/usr/bin/env bash
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive

apt-get update -qq && \
apt-get install -y --no-install-recommends \
  build-essential git wget curl ca-certificates gnupg dirmngr \
  libxml2-dev libxslt1-dev libpq-dev libjpeg-turbo8 zlib1g-dev \
  libldap2-dev libsasl2-dev postgresql xxd fontconfig libpng16-16 \
  libxrender1 libxtst6 xfonts-75dpi xfonts-base libssl-dev \
  python3.12 python3.12-venv python3.12-dev python3.12-full \
  libx11-6 libxcb1 libxext6 gettext libcairo2-dev libcairo2 && \
apt-get clean && rm -rf /var/lib/apt/lists/*

tmp_deb=$(mktemp --suffix=.deb)
wget -q "https://github.com/wkhtmltopdf/packaging/releases/download/${WKHTML_VERSION%.*}/wkhtmltox_${WKHTML_VERSION}_amd64.deb" -O "$tmp_deb"
dpkg -i "$tmp_deb" || apt-get -f -y install
rm -f "$tmp_deb"

mkdir -p "$ODOO_BASE_DIR" "$ODOO_ENTERPRISE_DIR"
curl -Ls "https://codeload.github.com/${ODOO_BASE_REPOSITORY}/tar.gz/refs/heads/${ODOO_VERSION}" | tar -xz --strip-components=1 -C "$ODOO_BASE_DIR"
curl -Ls -H "Authorization: Bearer $GITHUB_TOKEN" "https://codeload.github.com/${ODOO_ENTERPRISE_REPOSITORY}/tar.gz/refs/heads/${ODOO_VERSION}" | tar -xz --strip-components=1 -C "$ODOO_ENTERPRISE_DIR"

curl -LsSf https://astral.sh/uv/install.sh | bash
uv venv "$VENV_DIR" -p "$PYTHON_VERSION"
source "$VENV_DIR/bin/activate"

uv pip install 'pydantic>=2.11,<3' 'fastapi>=0.110' ariadne-codegen rlpycairo

if [ -d /workspace ]; then
  find /workspace -type f -name 'requirements*.txt' -print0 | sort -z -u | xargs -0 -I{} uv pip install -r {}
fi
uv pip install -r "$ODOO_BASE_DIR/requirements.txt"

cat >/etc/profile.d/odoo_env.sh <<EOF
export PYTEST_ADDOPTS="--cov=/odoo --cov=/workspace --cov-report=term-missing -q -s -o python_files=test_*.py -n auto --dist=loadfile --odoo-addons-path=$ODOO_ADDONS_PATH"
. /venv/bin/activate
EOF
chmod +x /etc/profile.d/odoo_env.sh
. /etc/profile.d/odoo_env.sh

ln -sf /etc/ssl/certs/ca-certificates.crt /usr/lib/ssl/cert.pem

service postgresql start
for _ in {1..60}; do pg_isready -q && break; sleep 1; done || exit 1

sudo -u postgres createuser --superuser root || true
sudo -u postgres createdb --owner=root "$ODOO_DATABASE"
sudo -u postgres psql -c "ALTER SYSTEM SET synchronous_commit TO off;"
sudo -u postgres psql -c "ALTER SYSTEM SET full_page_writes TO off;"
read -r pg_version pg_cluster <<< "$(pg_lsclusters -h | awk 'NR==1{print $1, $2}')"
sudo -u postgres pg_ctlcluster "$pg_version" "$pg_cluster" restart

uv cache prune --ci

/odoo/odoo-bin -d "$ODOO_DATABASE" --init base,product_connect --addons-path="$ODOO_ADDONS_PATH" --without-demo=all --load-language=en_US --workers=0 --max-cron-threads=0 --log-level=warn --stop-after-init