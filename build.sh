#!/usr/bin/env bash
# Gera o pacote .nvda-addon (zip) do WhatsApp Unificado.
# Uso: ./build.sh [pasta-de-saida]   (padrao: ./dist)
set -euo pipefail
cd "$(dirname "$0")"

VERSAO=$(sed -n 's/^version *= *//p' manifest.ini | head -1 | tr -d '\r ')
SAIDA="${1:-dist}"
PACOTE="whatsAppUnified-${VERSAO}.nvda-addon"

# 1. Documentacao: README.md -> doc/pt_BR e README.en.md -> doc/en
if command -v pandoc >/dev/null 2>&1; then
  mkdir -p doc/pt_BR doc/en
  pandoc -s -f gfm -t html5 --metadata title="WhatsApp Unificado ${VERSAO}" --metadata lang=pt-BR README.md -o doc/pt_BR/readme.html
  pandoc -s -f gfm -t html5 --metadata title="WhatsApp Unified ${VERSAO}" --metadata lang=en README.en.md -o doc/en/readme.html
else
  echo "pandoc nao encontrado: usando o HTML ja existente em doc/" >&2
fi

# 2. Pacote: so o que o NVDA precisa (sem testes, sem __pycache__)
mkdir -p "$SAIDA"
zip -r -X -FS "$SAIDA/$PACOTE" manifest.ini COPYING appModules globalPlugins doc \
  -x '*/__pycache__/*' '*.pyc' '*.pyo' >/dev/null

echo "Pacote: $(cd "$SAIDA" && pwd)/$PACOTE"
unzip -l "$SAIDA/$PACOTE"
