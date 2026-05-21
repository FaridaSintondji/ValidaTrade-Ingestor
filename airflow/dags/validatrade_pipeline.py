"""
validatrade_pipeline.py
=======================
DAG Airflow orchestrant le pipeline ValidaTrade end-to-end.

Flux :
    1. extract_validate   -> lance main_csv.py (Pydantic + Parquet + upload GCS)
    2. load_bigquery      -> charge le Parquet GCS vers la table native BigQuery
    3. dbt_run            -> execute les modeles dbt (staging + marts)
    4. dbt_test           -> verifie les 12 tests de qualite

Planification : tous les jours a 6h UTC.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from airflow import DAG
from airflow.operators.bash import BashOperator

# ============================================================
# Configuration globale du DAG
# ============================================================

# Chemin de notre projet ValidaTrade-Ingestor a l'interieur du conteneur Airflow.
# On le verra : ce dossier sera monte via docker-compose.
PROJECT_ROOT = "/opt/airflow/validatrade"
DBT_PROJECT  = f"{PROJECT_ROOT}/validatrade_dbt"

default_args = {
    "owner": "farida",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "email_on_failure": False,
    "depends_on_past": False,
}

with DAG(
    dag_id="validatrade_pipeline",
    description="Pipeline ETL ValidaTrade : extract -> GCS -> BQ -> dbt",
    schedule="0 6 * * *",                       # cron : tous les jours a 6h UTC
    start_date=datetime(2026, 5, 1),
    catchup=False,                              # ne pas rejouer les jours passes
    default_args=default_args,
    tags=["validatrade", "etl", "dbt"],
) as dag:

    # --------------------------------------------------------
    # Task 1 : extraction + validation + upload GCS
    # --------------------------------------------------------
    extract_validate = BashOperator(
        task_id="extract_validate",
        bash_command=f"cd {PROJECT_ROOT} && python main_csv.py",
    )

    # --------------------------------------------------------
    # Task 2 : charger le Parquet GCS dans BigQuery
    # (placeholder pour l'instant - on le fera en Python plus tard)
    # --------------------------------------------------------
    load_bigquery = BashOperator(
        task_id="load_bigquery",
        bash_command="echo 'TODO : automatiser le chargement Parquet -> BQ en Python'",
    )

    # --------------------------------------------------------
    # Task 3 : dbt run (staging + marts)
    # --------------------------------------------------------
    dbt_run = BashOperator(
        task_id="dbt_run",
        bash_command=f"cd {DBT_PROJECT} && dbt run",
    )

    # --------------------------------------------------------
    # Task 4 : dbt test (les 12 tests de qualite)
    # --------------------------------------------------------
    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command=f"cd {DBT_PROJECT} && dbt test",
    )

    # --------------------------------------------------------
    # Definition des dependances (orchestration)
    # --------------------------------------------------------
    extract_validate >> load_bigquery >> dbt_run >> dbt_test