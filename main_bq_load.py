"""
main_bq_load.py
===============
Charge le Parquet du jour depuis GCS vers BigQuery.

Flux :
    GCS (gs://{bucket}/trades/csv/year=YYYY/month=MM/day=DD/trades.parquet)
    → BigQuery ({project}.validatrade_raw.trades)

Variables d'environnement attendues :
    GOOGLE_APPLICATION_CREDENTIALS  -> chemin vers la clé JSON du service account
    VALIDATRADE_GCS_BUCKET          -> nom du bucket GCS (défaut : 'validatrade-raw')
    GCP_PROJECT_ID                  -> identifiant du projet GCP
"""

import os
import sys
from datetime import datetime, timezone

from loaders import BigQueryLoader


DATASET = "validatrade_raw"
TABLE = "trades"
DEFAULT_BUCKET = "validatrade-raw"


def build_gcs_uri(bucket: str, ts: datetime) -> str:
    """Reconstruit l'URI GCS du Parquet écrit par main_csv.py."""
    return (
        f"gs://{bucket}/trades/csv/"
        f"year={ts.year:04d}/"
        f"month={ts.month:02d}/"
        f"day={ts.day:02d}/"
        "trades.parquet"
    )


def main():
    project_id = os.getenv("GCP_PROJECT_ID")
    if not project_id:
        print("❌ GCP_PROJECT_ID n'est pas définie. Abandon.")
        sys.exit(1)

    bucket = os.getenv("VALIDATRADE_GCS_BUCKET", DEFAULT_BUCKET)
    ts = datetime.now(timezone.utc)
    gcs_uri = build_gcs_uri(bucket, ts)

    print("--- Démarrage du chargement GCS → BigQuery ---")
    print(f"   Source  : {gcs_uri}")
    print(f"   Cible   : {project_id}.{DATASET}.{TABLE}")

    try:
        loader = BigQueryLoader(project_id=project_id)
        loader.load(
            gcs_uri=gcs_uri,
            table_ref=f"{DATASET}.{TABLE}",
            write_disposition="WRITE_APPEND",
        )
        print(f"\n🌥️  Chargement terminé : {project_id}.{DATASET}.{TABLE}")
    except EnvironmentError as e:
        print(f"\n❌ Erreur d'environnement : {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Erreur lors du chargement BigQuery : {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()