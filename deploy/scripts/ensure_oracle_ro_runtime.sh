#!/usr/bin/env bash
# Ensure Oracle Instant Client thick mode uses Instant Client >= 19.1.
# Safe to re-run. Does not touch business DBs.
set -euo pipefail

ORACLE_HOME="${ORACLE_HOME:-/opt/oracle}"
TARGET_LIB="${ORACLE_HOME}/libclntsh.so"
PREFERRED=(
  "${ORACLE_HOME}/libclntsh.so.19.1"
  "${ORACLE_HOME}/instantclient_21/libclntsh.so.21.1"
  "${ORACLE_HOME}/instantclient_19_19/libclntsh.so.19.1"
  "/opt/oracle/instantclient_21/libclntsh.so.21.1"
)

if [[ ! -d "${ORACLE_HOME}" ]]; then
  echo "ORACLE_HOME missing: ${ORACLE_HOME}" >&2
  exit 1
fi

src=""
for cand in "${PREFERRED[@]}"; do
  if [[ -e "${cand}" ]]; then
    src="${cand}"
    break
  fi
done

if [[ -z "${src}" ]]; then
  # fallback: first libclntsh.so.19* / 21*
  src="$(ls -1 "${ORACLE_HOME}"/libclntsh.so.1[9]* "${ORACLE_HOME}"/libclntsh.so.2[0-9]* 2>/dev/null | head -n1 || true)"
fi

if [[ -z "${src}" ]]; then
  echo "No Instant Client 19+ libclntsh found under ${ORACLE_HOME}" >&2
  exit 2
fi

ln -sfn "$(basename "${src}")" "${TARGET_LIB}" 2>/dev/null || ln -sfn "${src}" "${TARGET_LIB}"
echo "libclntsh -> $(readlink -f "${TARGET_LIB}" 2>/dev/null || readlink "${TARGET_LIB}" || echo "${src}")"

# Credentials mount check (host path expected when using docker -v)
CREDS="${DATA_ASSET_CREDENTIALS_DIR:-/etc/data-asset/credentials}"
if [[ -d "${CREDS}" ]]; then
  echo "credentials dir OK: ${CREDS}"
  ls -1 "${CREDS}" 2>/dev/null | head -n 20 || true
else
  echo "WARN: credentials dir not mounted: ${CREDS}" >&2
fi
