"""
main_api.py
===========
Pipeline d'ingestion via API CoinGecko.

Flux :
    1. Extraction       -> APIExtractor.fetch_data()
    2. Validation       -> Pydantic (modèle Trade)
    3. Export Parquet   -> Pandas + PyArrow (zone "silver" locale)
    4. Upload GCS       -> GCSLoader (zone bronze/silver dans le cloud)

Variables d'environnement attendues :
    GOOGLE_APPLICATION_CREDENTIALS  -> chemin vers la clé JSON du service account
    VALIDATRADE_GCS_BUCKET          -> nom du bucket GCS cible
                                       (par défaut : 'validatrade-raw')
    VALIDATRADE_OUTPUT_DIR          -> dossier où écrire le Parquet local
                                       (par défaut : 'output' relatif au cwd)
                                       Surchargé par Airflow vers /tmp/validatrade
                                       car le code projet est monté en :ro.
    INGESTION_DATE                  -> date d'ingestion au format YYYY-MM-DD.
                                       Si présente -> mode BACKFILL (CoinGecko history).
                                       Si absente  -> mode LIVE (prix actuels).
                                       Airflow l'injecte via {{ ds }} dans le DAG.
"""

import os
import sys
from pathlib import Path
from datetime import date, datetime, timezone

import pandas as pd

from models import Trade
from extractors import APIExtractor
from loaders import GCSLoader

from dotenv import load_dotenv
load_dotenv()


# Dossier de sortie configurable via env var (pour Airflow / Docker en :ro).
# En dev local : "output/" relatif au repo. En conteneur : /tmp/validatrade.
OUTPUT_DIR = Path(os.getenv("VALIDATRADE_OUTPUT_DIR", "output"))
DEFAULT_BUCKET = "validatrade-raw"


def main():
    # 1. Détermination du mode (live vs backfill) --------------------------
    # Airflow passe INGESTION_DATE={{ ds }} (date logique du run) via bash_command.
    # Si absente, on tombe en mode "live" (prix du moment) pour les exécutions
    # locales / debug.
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
        # Timestamp utilisé pour le partitionnement Hive du fichier GCS.
        # On met midi UTC du jour cible -> partition day= cohérente.
        ts_for_partition = datetime.combine(
            target_date, datetime.min.time(), tzinfo=timezone.utc
        )
        print(f"--- Mode BACKFILL : ingestion historique pour {target_date} ---")
    else:
        target_date = None
        ts_for_partition = datetime.now(timezone.utc)
        print("--- Mode LIVE : ingestion prix actuels CoinGecko ---")

    # 2. Extraction --------------------------------------------------------
    source_api = APIExtractor("CoinGecko-Production")
    if target_date is not None:
        raw_data = source_api.fetch_historical(target_date)
    else:
        raw_data = source_api.fetch_data()

    if not raw_data:
        print("Aucune donnée récupérée. Arrêt du pipeline.")
        return

    # 3. Validation Pydantic ----------------------------------------------
    validated_trades = []
    for item in raw_data:
        try:
            trade_obj = Trade(**item)
            trade_obj.calculate_total()
            validated_trades.append(trade_obj)
            print(f"✅ Validation réussie pour {trade_obj.symbol}")
        except Exception as e:
            print(f"⚠️  Erreur de validation sur un élément : {e}")

    if not validated_trades:
        print("Aucun trade valide après filtrage. Arrêt du pipeline.")
        return

    print(f"\n--- {len(validated_trades)} trades validés, prêts pour le stockage ---")

    # 4. Export Parquet (zone silver locale) ------------------------------
    OUTPUT_DIR.mkdir(exist_ok=True)
    df = pd.DataFrame([t.model_dump() for t in validated_trades])
    local_parquet = OUTPUT_DIR / "trades_api.parquet"
    df.to_parquet(
        local_parquet,
        engine="pyarrow",
        index=False,
        coerce_timestamps="us",
        allow_truncated_timestamps=True,
    )
    print(f"💾 Parquet écrit en local : {local_parquet}")

    # 5. Upload vers GCS --------------------------------------------------
    # Le partitionnement Hive utilise ts_for_partition, pas datetime.now().
    # Crucial pour que le backfill crée bien des partitions year=2026/month=05/day=01,
    # day=02, day=03, ... etc. au lieu d'écraser tout dans day=today.
    bucket = os.getenv("VALIDATRADE_GCS_BUCKET", DEFAULT_BUCKET)
    try:
        loader = GCSLoader(bucket_name=bucket)
        remote_key = GCSLoader.build_partitioned_key(
            prefix="trades/api",
            filename="trades.parquet",
            ts=ts_for_partition,
        )
        uri = loader.upload(local_path=str(local_parquet), remote_key=remote_key)
        print(f"\n🌥️  Pipeline terminé. Données disponibles à : {uri}")
    except EnvironmentError as e:
        print(f"\n⚠️  Upload GCS ignoré ({e})")
        print(f"   Parquet local conservé : {local_parquet}")


if __name__ == "__main__":
    main()
