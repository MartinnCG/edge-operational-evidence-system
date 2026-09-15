#!/usr/bin/env sh
set -eu

output_dir="${1:-ops/mqtt-secure/generated}"
if [ -e "$output_dir" ]; then
  echo "refusing to replace existing PKI directory: $output_dir" >&2
  exit 1
fi
mkdir -p "$output_dir"

openssl req -x509 -newkey rsa:2048 -nodes -sha256 -days 2 \
  -subj "/CN=edge-evidence-test-ca" \
  -keyout "$output_dir/ca.key" -out "$output_dir/ca.crt"

issue_certificate() {
  name="$1"
  usage="$2"
  san="$3"
  openssl req -new -newkey rsa:2048 -nodes -sha256 \
    -subj "/CN=$name" -addext "extendedKeyUsage=$usage" \
    -addext "subjectAltName=$san" \
    -keyout "$output_dir/$name.key" -out "$output_dir/$name.csr"
  openssl x509 -req -sha256 -days 2 -copy_extensions copy \
    -in "$output_dir/$name.csr" \
    -CA "$output_dir/ca.crt" -CAkey "$output_dir/ca.key" \
    -CAcreateserial -out "$output_dir/$name.crt"
}

issue_certificate "broker" "serverAuth" "DNS:localhost,IP:127.0.0.1"
issue_certificate "edge-consumer" "clientAuth" "DNS:edge-consumer"
issue_certificate "edge-publisher" "clientAuth" "DNS:edge-publisher"
issue_certificate "health-probe" "clientAuth" "DNS:health-probe"

openssl req -x509 -newkey rsa:2048 -nodes -sha256 -days 2 \
  -subj "/CN=rogue-test-ca" \
  -keyout "$output_dir/rogue-ca.key" -out "$output_dir/rogue-ca.crt"
openssl req -new -newkey rsa:2048 -nodes -sha256 \
  -subj "/CN=rogue-client" -addext "extendedKeyUsage=clientAuth" \
  -keyout "$output_dir/rogue-client.key" \
  -out "$output_dir/rogue-client.csr"
openssl x509 -req -sha256 -days 2 -copy_extensions copy \
  -in "$output_dir/rogue-client.csr" \
  -CA "$output_dir/rogue-ca.crt" -CAkey "$output_dir/rogue-ca.key" \
  -CAcreateserial -out "$output_dir/rogue-client.crt"

rm "$output_dir"/*.csr "$output_dir"/*.srl
chmod 0644 "$output_dir"/*.crt "$output_dir"/*.key
