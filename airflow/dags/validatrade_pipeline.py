# ============================================================
# airflow/dags/validatrade_pipeline.py
# DAG d'orchestration du pipeline ValidaTrade
#
# Workflow complet (exécuté quotidiennement à 6h UTC) :
#   extract_validate → load_bigquery → dbt_run → dbt_test
#
#   1. extract_validate  : CoinGecko (history) → Pydantic → Parquet → GCS
#                          partitionnement Hive year=YYYY/month=MM/day=DD
#   2. load_bigquery     : GCS Parquet → table BigQuery validatrade_raw.trades
#   3. dbt_run           : staging (vue) + marts (table daily_vwap)
#   4. dbt_test          : 12 tests YAML (not_null, accepted_values, unique…)
#
# Variables d'environnement attendues (définies dans docker-compose.yaml) :
#   GOOGLE_APPLICATION_CREDENTIALS : chemin vers la clé SA (montée en :ro)
#   VALIDATRADE_GCS_BUCKET         : nom du bucket GCS cible
#   GCP_PROJECT_ID                 : identifiant du projet GCP
#
# Backfill (mécanique d'Airflow) :
#   - catchup=True       : Airflow rejoue automatiquement tous les intervalles
#                          manqués entre start_date et "now". Avec start_date au
#                          1er mai 2026 et today=23 mai, ça crée 22 runs d'un coup.
#   - max_active_runs=1  : un seul run à la fois (sériel). Évite de saturer
#                          le rate-limit free de CoinGecko (~30 calls/min).
#   - INGESTION_DATE={{ ds }} : Airflow injecte la date logique du run dans
#                          l'env du script Python. main_api.py utilise cette
#                          date pour appeler l'endpoint /coins/{id}/history
#                          et écrire le Parquet sous la bonne partition.
# ============================================================

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator

# Le code du projet est monté en read-only depuis le host.
# (volume `../:/opt/airflow/validatrade:ro` dans docker-compose.yaml)
PROJECT_ROOT = "/opt/airflow/validatrade"
DBT_PROJECT = f"{PROJECT_ROOT}/validatrade_dbt"
DBT_PROFILES_DIR = "/opt/airflow/dbt-profiles"

default_args = {
    "owner": "farida",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="validatrade_pipeline",
    description="Pipeline ELT crypto : CoinGecko → Pydantic → Parquet → GCS → BigQuery → dbt",
    schedule="0 6 * * *",
    start_date=datetime(2026, 5, 1),
    catchup=True,           # rejoue tous les intervalles manqués depuis start_date
    max_active_runs=1,      # un seul run à la fois pour respecter le rate-limit CoinGecko
    default_args=default_args,
    tags=["validatrade", "phase3"],
) as dag:

    # ------------------------------------------------------------------ #
    # Tâche 1 : Extraction + validation Pydantic + export Parquet + GCS   #
    # ------------------------------------------------------------------ #
    # Exécute main_api.py qui :
    #   - Lit la date d'ingestion via INGESTION_DATE (env var, injectée
    #     par Airflow via {{ ds }} = date logique du run, format YYYY-MM-DD)
    #   - Appelle CoinGecko /coins/{id}/history pour récupérer les prix
    #     BTC et ETH de cette date précise
    #   - Valide via Pydantic
    #   - Exporte un fichier Parquet local
    #   - Upload le Parquet vers GCS (partitionnement Hive
    #     year=YYYY/month=MM/day=DD basé sur INGESTION_DATE, pas sur "now")
    extract_validate = BashOperator(
        task_id="extract_validate",
        bash_command=f"cd {PROJECT_ROOT} && python main_api.py",
        env={"INGESTION_DATE": "{{ ds }}"},
    )

    # ------------------------------------------------------------------ #
    # Tâche 2 : Chargement GCS → BigQuery                                 #
    # ------------------------------------------------------------------ #
    # Exécute main_bq_load.py qui :
    #   - Lit INGESTION_DATE pour reconstruire l'URI GCS du jour
    #     (gs://bucket/trades/api/year=.../day=.../trades.parquet)
    #   - Déclenche un job BigQuery Load via BigQueryLoader
    #   - Charge en WRITE_APPEND dans validatrade_raw.trades
    load_bigquery = BashOperator(
        task_id="load_bigquery",
        bash_command=f"cd {PROJECT_ROOT} && python main_bq_load.py",
        env={"INGESTION_DATE": "{{ ds }}"},
        append_env=True,
    )

    # ------------------------------------------------------------------ #
    # Tâche 3 : Transformation dbt                                        #
    # ------------------------------------------------------------------ #
    # Exécute `dbt run` qui matérialise :
    #   - stg_trades  (vue)         : nettoyage + typage depuis la source BQ
    #   - daily_vwap  (table)       : VWAP par jour et symbole
    #
    # Pas besoin d'INGESTION_DATE ici : dbt lit l'intégralité de la source
    # BQ et recalcule daily_vwap à chaque run. C'est intentionnel : si un
    # backfill remplit 22 jours, dbt va naturellement les inclure tous.
    dbt_run = BashOperator(
        task_id="dbt_run",
        bash_command=(
            f"cd {DBT_PROJECT} && "
            f"dbt run --profiles-dir {DBT_PROFILES_DIR}"
        ),
    )

    # ------------------------------------------------------------------ #
    # Tâche 4 : Tests dbt                                                 #
    # ------------------------------------------------------------------ #
    # Exécute `dbt test` qui valide :
    #   - not_null sur les colonnes critiques
    #   - accepted_values sur le type de trade
    #   - unique_combination_of_columns sur (trade_date, symbol)
    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command=(
            f"cd {DBT_PROJECT} && "
            f"dbt test --profiles-dir {DBT_PROFILES_DIR}"
        ),
    )

    # ------------------------------------------------------------------ #
    # Dépendances : exécution strictement séquentielle                    #
    # ------------------------------------------------------------------ #
    # extract_validate doit réussir avant de charger dans BQ,
    # et BQ doit être à jour avant de lancer dbt (qui lit depuis BQ).
    extract_validate >> load_bigquery >> dbt_run >> dbt_test
