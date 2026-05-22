# ============================================================
# airflow/Dockerfile
# Image Airflow custom pour ValidaTrade
#
# Pourquoi une image custom plutôt que _PIP_ADDITIONAL_REQUIREMENTS ?
# - _PIP_ADDITIONAL_REQUIREMENTS réinstalle les libs à CHAQUE démarrage
#   du conteneur (10-15 min de blocage du worker → tasks "stuck in queued").
# - Officiellement, Apache documente cette variable comme "dev-only".
# - Une image custom build les libs UNE fois, puis chaque démarrage = 30 s.
#
# Build :
#   docker compose build
# ============================================================

# ------------------------------------------------------------
# Airflow 2.10.5 (et non 2.10.4) :
# - 2.10.4 a 2 bugs combinés sur le worker Celery :
#     1. `--pidfile=` (vide) refusé par Celery 5.5+ -> exit 2
#     2. `pidfile=None` -> AttributeError dans node_format()  [vu chez nous]
# - Les 2 sont corrigés dans 2.10.5 (patch release, AUCUN breaking change
#   versus 2.10.4, même schéma de BDD, mêmes API).
# ------------------------------------------------------------
FROM apache/airflow:2.10.5


# Installation des dépendances projet (mêmes versions que requirements.txt)
# + dbt-core et dbt-bigquery pour les BashOperator dbt run / dbt test
RUN pip install --no-cache-dir \
    pydantic==2.12.0 \
    requests==2.32.3 \
    pandas==2.2.3 \
    pyarrow==19.0.1 \
    google-cloud-storage==2.18.2 \
    google-cloud-bigquery==3.34.0 \
    dbt-core==1.11.8 \
    dbt-bigquery==1.11.1
