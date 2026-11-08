#!/bin/bash
# Guarda os registros da montagem numa branch própria (ci-registro-<nome>), para conferir de fora do GitHub.
# Monta um repositório à parte, para não mexer na pasta da montagem (no Windows o checkout dela falhava).
set +e
NOME="$1"
[ -d registro ] || exit 0
URL=$(git config --get remote.origin.url)
HDR=$(git config --get http.https://github.com/.extraheader)
TMP=$(mktemp -d)
cp -R registro "$TMP/"
echo "$GITHUB_SHA $(date -u +%FT%TZ) ${GITHUB_JOB}" > "$TMP/registro/QUANDO.txt"
cd "$TMP" || exit 0
git init -q
git config user.name "efc3d-ci"; git config user.email "efc3d-ci@users.noreply.github.com"
[ -n "$HDR" ] && git config http.https://github.com/.extraheader "$HDR"
git checkout -q -b "ci-registro-$NOME"
git add registro
git commit -qm "registro $NOME $GITHUB_SHA"
git push -qf "$URL" "ci-registro-$NOME"
exit 0
