"""
main_bq_load.py
===============
Charge le Parquet d'une date donnée depuis GCS vers BigQuery.

Flux :
    GCS (gs://{bucket}/trades/api/year=YYYY/month=MM/day=DD/trades.parquet)
    → BigQuery ({project}.validatrade_raw.trades)

Ce script est la 2e étape du pipeline Airflow :
    extract_validate (main_api.py)
    → load_bigquery  (main_bq_load.py)  ← ICI
    → dbt_run
    → dbt_test

Variables d'environnement attendues :
    GOOGLE_APPLICATION_CREDENTIALS  -> chemin vers la clé JSON du service account
    VALIDATRADE_GCS_BUCKET          -> nom du bucket GCS (défaut : 'validatrade-raw')
    GCP_PROJECT_ID                  -> identifiant du projet GCP
    INGESTION_DATE                  -> date au format YYYY-MM-DD pour le backfill.
                                       Airflow l'injecte via {{ ds }}.
                                       Si absente -> on prend "aujourd'hui" (UTC).
"""

import os
import sys
from datetime import date, datetime, timezone

from dotenv import load_dotenv

from loaders import BigQueryLoader

# Charge le .env du dossier courant si présent (dev local).
# En conteneur Airflow, les env vars sont déjà fournies par docker-compose.
load_dotenv()


DATASET = "validatrade_raw"
TABLE = "trades"
DEFAULT_BUCKET = "validatrade-raw"
# Prefix dans le bucket GCS. Doit correspondre EXACTEMENT à ce que main_api.py
# utilise dans son appel à GCSLoader.build_partitioned_key (prefix="trades/api").
GCS_PREFIX = "trades/api"


def build_gcs_uri(bucket: str, ts: datetime, prefix: str = GCS_PREFIX) -> str:
    """
    Reconstruit l'URI GCS du Parquet pour la date passée en paramètre.

    Le partitionnement Hive suit le même schéma que GCSLoader.build_partitioned_key :
        {prefix}/year=YYYY/month=MM/day=DD/trades.parquet
    """
    return (
        f"gs://{bucket}/{prefix}/"
        f"year={ts.year:04d}/"
        f"month={ts.month:02d}/"
        f"day={ts.day:02d}/"
        "trades.parquet"
    )


def main():
    # --- Lecture des variables d'environnement ----------------------------
    project_id = os.getenv("GCP_PROJECT_ID")
    if not project_id:
        print(
            "❌ GCP_PROJECT_ID n'est pas définie. "
            "Ajoute-la dans ton .env ou dans docker-compose.yaml."
        )
        sys.exit(1)

    bucket = os.getenv("VALIDATRADE_GCS_BUCKET", DEFAULT_BUCKET)

    # --- Détermination de la date d'ingestion -----------------------------
    # Si INGESTION_DATE est définie (cas Airflow : {{ ds }}), on l'utilise.
    # Sinon on tombe sur la date du jour (UTC) — pratique pour les runs manuels.
    ingestion_date_str = os.getenv("INGESTION_DATE")
    if ingestion_date_str:
        try:
            target_date = date.fromisoformat(ingestion_date_str)
        except ValueError:
            print(
                f"❌ INGESTION_DATE invalide : '{ingestion_date_str}'. "
                "Format attendu : YYYY-MM-DD."
            )
            sys.exit(1)
        ts = datetime.combine(target_date, datetime.min.time(), tzinfo=timezone.utc)
        print(f"--- Chargement GCS → BigQuery (date d'ingestion : {target_date}) ---")
    else:
        ts = datetime.now(timezone.utc)
        print(f"--- Chargement GCS → BigQuery (date du jour : {ts.date()}) ---")

    # --- Construction de l'URI GCS ----------------------------------------
    gcs_uri = build_gcs_uri(bucket, ts)
    print(f"   Source  : {gcs_uri}")
    print(f"   Cible   : {project_id}.{DATASET}.{TABLE}")

    # --- Chargement GCS → BigQuery ----------------------------------------
    try:
        loader = BigQueryLoader(project_id=project_id)
        loader.load(
            gcs_uri=gcs_uri,
            table_ref=f"{DATASET}.{TABLE}",
            write_disposition="WRITE_APPEND",
        )
        print(f"\n🌥️  Chargement terminé. Table disponible : {project_id}.{DATASET}.{TABLE}")
    except EnvironmentError as e:
        # GOOGLE_APPLICATION_CREDENTIALS non défini
        print(f"\n❌ Erreur d'environnement : {e}")
        sys.exit(1)
    except Exception as e:
        # Erreur GCP (fichier absent, droits insuffisants, schéma incompatible…)
        print(f"\n❌ Erreur lors du chargement BigQuery : {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
