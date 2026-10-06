#!/bin/bash
# Las pruebas de los módulos que este taller migra, en una base desechable.
#
# El repositorio es OCA/survey 19.0 con los módulos traídos de otras ramas encima. Los
# demás módulos son los de la OCA, tal cual: los prueba la integración continua de la
# OCA (.github/workflows/test.yml). Aquí se prueban los de MODULOS, con la imagen de
# pruebas del sitio: el Odoo de producción con un Chromium sin pantalla, porque el
# formulario de la encuesta se prueba también en un navegador (tests/test_survey_tour.py).
# Un cerrojo en /tmp serializa las corridas con las de los demás repositorios, que
# comparten la máquina. Al terminar, pase lo que pase, el laboratorio se desmonta con sus
# volúmenes.
#
#   ci/pruebas.sh                  survey y los módulos, como en la OCA
#   CON_SITIO=1 ci/pruebas.sh      lo mismo con website instalado, como en producción
set -euo pipefail
cd "$(dirname "$0")"
export PATH=/opt/homebrew/bin:/usr/local/bin:$PATH
PROYECTO="ci-survey-19-${GITHUB_RUN_ID:-local-$$}"
MODULOS=survey_question_type_binary
ETIQUETAS="/${MODULOS//,/,/}"
INSTALAR="$MODULOS"
[ -n "${CON_SITIO:-}" ] && INSTALAR="website,$MODULOS"
CERROJO=/tmp/ci-odoo.lock
RUTAS=/mnt/survey,/usr/lib/python3/dist-packages/odoo/addons

# Cada módulo de la lista tiene que existir y tener pruebas: una lista que nombra un
# módulo sin carpeta tests/ daría un verde sin haber probado nada.
for modulo in ${MODULOS//,/ }; do
  [ -f "../$modulo/__manifest__.py" ] || { echo "FALLO: no existe el módulo $modulo" >&2; exit 1; }
  [ -d "../$modulo/tests" ] || { echo "FALLO: $modulo no tiene pruebas" >&2; exit 1; }
done

limpiar() {
  docker compose -p "$PROYECTO" -f compose.yaml down -v --remove-orphans >/dev/null 2>&1 || true
  # El cerrojo solo lo suelta quien lo tomó.
  if [ "$MIO" = si ]; then rmdir "$CERROJO" 2>/dev/null || true; fi
}
MIO=no
trap limpiar EXIT

until mkdir "$CERROJO" 2>/dev/null; do echo "esperando a otra corrida..."; sleep 30; done
MIO=si
echo "== instalando $INSTALAR y corriendo las pruebas de $MODULOS =="
# El código de Odoo se guarda antes de que nada lo pise, y el filtro de la salida va
# aparte: grep sin coincidencias devuelve 1 y no puede tapar el resultado de Odoo.
ESTADO=0
docker compose -p "$PROYECTO" -f compose.yaml run --rm -T web \
  odoo -d ci --addons-path="$RUTAS" -i "$INSTALAR" --test-tags="$ETIQUETAS" \
  --stop-after-init --log-level=test \
  2>&1 | tee registro.log | grep -E "tests when loading|post-tests in|FAIL:|ERROR:|CRITICAL" || ESTADO="${PIPESTATUS[0]}"
[ "$ESTADO" = 0 ] || { echo "FALLO: Odoo terminó con código $ESTADO"; exit 1; }

# Verde solo si Odoo dice que no falló nada, corrió alguna prueba, cada módulo dejó su
# línea de estadísticas, el tour terminó y ningún módulo dejó un ERROR o CRITICAL.
grep -qE " 0 failed, 0 error\(s\) of [1-9][0-9]* tests" registro.log || {
  grep -E "failed, .* error\(s\) of" registro.log || echo "(Odoo no llegó a contar las pruebas)"
  echo "FALLO: hay pruebas que no pasan, o no corrió ninguna"; exit 1; }
for modulo in ${MODULOS//,/ }; do
  grep -q "odoo.tests.stats: $modulo: " registro.log || {
    echo "FALLO: $modulo no corrió ni una prueba" >&2; exit 1; }
done
grep -q "TOUR survey_question_type_binary_tour SUCCEEDED" registro.log || {
  echo "FALLO: el tour del formulario no corrió hasta el final" >&2; exit 1; }
if grep -E " (ERROR|CRITICAL) " registro.log | grep -v "odoo.tests" | grep -q .; then
  grep -E " (ERROR|CRITICAL) " registro.log | grep -v "odoo.tests" | head -n 20
  echo "FALLO: errores en el registro fuera de las pruebas"; exit 1
fi

echo "== los módulos quedaron instalados =="
SALIDA="$({ printf 'PEDIDOS = "%s"\n' "$INSTALAR"; cat instalados.py; } |
  docker compose -p "$PROYECTO" -f compose.yaml run --rm -T web \
    odoo shell -d ci --addons-path="$RUTAS" --no-http --log-level=error 2>&1)" || true
if ! printf '%s\n' "$SALIDA" | grep "^R instalados:"; then
  printf '%s\n' "$SALIDA" | tail -n 20 >&2
  echo "FALLO: no se pudo comprobar en la base qué módulos quedaron instalados" >&2
  exit 1
fi
if printf '%s\n' "$SALIDA" | grep -q "^R instalados: faltan"; then
  echo "FALLO: se pidieron módulos que no quedaron instalados (arriba, con su estado)" >&2
  exit 1
fi
grep -E "odoo.tests.stats: |failed, .* error\(s\) of" registro.log | tail -n 5
echo "batería en verde"
