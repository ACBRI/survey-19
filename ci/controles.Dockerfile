# Imagen de los controles de la OCA: Python con pre-commit y el mismo pandoc que la PC,
# fijado por versión. El generador de README de la OCA escribe README.rst e index.html con
# pandoc, y dos versiones de pandoc dan dos salidas distintas: sin fijarla, la integración
# continua reescribiría lo que la PC generó. Se construye una vez y queda en caché.
FROM python:3.12-slim
ARG PANDOC=3.7.0.2
ARG PRE_COMMIT=4.6.0
RUN apt-get update -qq \
    && apt-get install -y -qq --no-install-recommends git curl ca-certificates >/dev/null \
    && curl -fsSL -o /tmp/pandoc.deb \
      "https://github.com/jgm/pandoc/releases/download/${PANDOC}/pandoc-${PANDOC}-1-$(dpkg --print-architecture).deb" \
    && dpkg -i /tmp/pandoc.deb && rm /tmp/pandoc.deb \
    && apt-get purge -y -qq curl >/dev/null && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir -q "pre-commit==${PRE_COMMIT}"
ENV PRE_COMMIT_HOME=/root/.cache/pre-commit
