#!/bin/bash
# Los controles de la OCA (pre-commit) en un contenedor propio (ci/controles.Dockerfile):
# Python, pre-commit y pandoc fijados, para no depender del Python, el Node ni el pandoc
# de la máquina. Corre con el usuario de quien lo llama, no como root, así los archivos
# que los ganchos reescriben (el README.rst, el index.html) siguen siendo suyos. La caché de los ganchos vive en la
# máquina y se reutiliza.
#
#   ci/controles.sh            desde la raíz del repositorio
set -euo pipefail
cd "$(dirname "$0")"
export PATH=/opt/homebrew/bin:/usr/local/bin:$PATH
CACHE="$HOME/.cache/pre-commit-survey-19"
mkdir -p "$CACHE"
docker build -q -t ci-controles-oca -f controles.Dockerfile . >/dev/null
# En un worktree de git, /repo/.git es un archivo que apunta al .git común del
# repositorio principal, fuera de /repo; sin montarlo en su misma ruta, git no encuentra
# el repositorio dentro del contenedor. En un clon normal es la misma carpeta .git.
COMUN="$(git -C .. rev-parse --path-format=absolute --git-common-dir)"
docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp \
  -v "$PWD/..:/repo" -v "$COMUN:$COMUN" -v "$CACHE:/cache" -w /repo \
  -e PRE_COMMIT_HOME=/cache -e RUFF_CACHE_DIR=/cache/ruff \
  ci-controles-oca sh -ec '
    git config --global --add safe.directory "*"
    pre-commit run --all-files --show-diff-on-failure'
