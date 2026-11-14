#!/usr/bin/env sh
# A demo internal PKI for the reverse proxy examples: a root CA, and a server certificate signed by it.
#
#   sh example/pki/gen-certs.sh portal.example.internal
#   sh example/pki/gen-certs.sh portal.example.internal 192.168.1.10   # extra names / addresses
#
# It writes example/pki/certs/ (git-ignored):
#
#   ca.crt / ca.key        the demo authority. Import ca.crt into the browsers that will open the portal,
#                          and into Admin > Certificates if the backend has to trust something it signed.
#   portal.crt / portal.key  the server certificate, which is what the Traefik example mounts at /certs
#                          and what example/nginx/portal-ng.conf expects in /etc/nginx/ssl/.
#
# This is for a test or a demonstration. For anything real, use your company PKI or ACME / Let's Encrypt:
# the key here is written unencrypted, next to the repository, and the authority signs anything asked of it.
#
# Only openssl is needed (>= 1.1.1; 3.5+ also gives you X25519MLKEM768 on the proxy side).
set -eu

# Git Bash on Windows rewrites any argument that looks like a path, which turns openssl's
# "/CN=..." subject into "C:/Program Files/Git/CN=...". These two switch that off.
MSYS_NO_PATHCONV=1; MSYS2_ARG_CONV_EXCL='*'
export MSYS_NO_PATHCONV MSYS2_ARG_CONV_EXCL

cd "$(dirname "$0")"
OUT=certs
DAYS_CA=${DAYS_CA:-3650}
DAYS_CRT=${DAYS_CRT:-825}   # browsers refuse a server certificate valid much longer than this

[ $# -ge 1 ] || { echo "usage: $0 <hostname> [extra-name-or-ip ...]" >&2; exit 2; }
CN=$1
shift

mkdir -p "$OUT"

# Subject alternative names: the common name is never enough on its own — browsers ignore the CN and read
# this list only. An argument that parses as an IPv4 address becomes an IP entry rather than a DNS one.
SAN="DNS:$CN"
for extra in "$@"; do
    if echo "$extra" | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$'; then
        SAN="$SAN,IP:$extra"
    else
        SAN="$SAN,DNS:$extra"
    fi
done
# localhost is always included, so the same certificate works when you test through a tunnel
SAN="$SAN,DNS:localhost,IP:127.0.0.1"

if [ -f "$OUT/ca.crt" ] && [ -f "$OUT/ca.key" ]; then
    echo "reusing the existing authority in $OUT/ca.crt"
else
    echo "creating the demo authority..."
    openssl req -x509 -newkey ec -pkeyopt ec_paramgen_curve:prime256v1 -noenc \
        -keyout "$OUT/ca.key" -out "$OUT/ca.crt" -days "$DAYS_CA" -sha256 \
        -subj "/CN=Portal-NG demo CA" \
        -addext "basicConstraints=critical,CA:TRUE,pathlen:0" \
        -addext "keyUsage=critical,keyCertSign,cRLSign"
fi

echo "creating the server certificate for $CN..."
openssl req -newkey ec -pkeyopt ec_paramgen_curve:prime256v1 -noenc \
    -keyout "$OUT/portal.key" -out "$OUT/portal.csr" -subj "/CN=$CN"

openssl x509 -req -in "$OUT/portal.csr" -days "$DAYS_CRT" -sha256 \
    -CA "$OUT/ca.crt" -CAkey "$OUT/ca.key" -CAcreateserial \
    -out "$OUT/portal.crt" \
    -extfile - <<EOF
basicConstraints=critical,CA:FALSE
keyUsage=critical,digitalSignature,keyEncipherment
extendedKeyUsage=serverAuth
subjectAltName=$SAN
EOF

rm -f "$OUT/portal.csr"

# The Traefik example runs as uid 65532 and nginx-unprivileged as 101: both have to read the key, and
# neither is root. 0644 on a demo key in a git-ignored folder; a real key never looks like this.
chmod 644 "$OUT/portal.key" "$OUT/ca.key" 2>/dev/null || true

echo
echo "written to example/pki/$OUT/:"
ls -1 "$OUT"
echo
echo "names in the certificate: $SAN"
openssl x509 -in "$OUT/portal.crt" -noout -dates
echo
echo "Next: import example/pki/$OUT/ca.crt into your browser, then"
echo "  PUBLIC_URL=https://$CN docker compose -f docker-compose.yml -f example/traefik/compose.yml up -d"
