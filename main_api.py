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
                                       (par défaut : 'validatrade-raw-CHANGEME')
"""

import os
from pathlib import Path
from datetime import datetime, timezone

import pandas as pd

from models import Trade
from extractors import APIExtractor
from loaders import GCSLoader


OUTPUT_DIR = Path("output")
DEFAULT_BUCKET = "validatrade-raw"


def main():
    # 1. Extraction --------------------------------------------------------
    source_api = APIExtractor("CoinGecko-Production")
    print("--- Démarrage du pipeline d'ingestion via API ---")

    raw_data = source_api.fetch_data()
    if not raw_data:
        print("Aucune donnée récupérée. Arrêt du pipeline.")
        return

    # 2. Validation Pydantic ----------------------------------------------
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

    # 3. Export Parquet (zone silver locale) ------------------------------
    OUTPUT_DIR.mkdir(exist_ok=True)
    df = pd.DataFrame([t.model_dump() for t in validated_trades])
    local_parquet = OUTPUT_DIR / "trades_api.parquet"
    df.to_parquet(local_parquet, engine="pyarrow", index=False, coerce_timestamps="us", allow_truncated_timestamps=True)
    print(f"💾 Parquet écrit en local : {local_parquet}")

    # 4. Upload vers GCS --------------------------------------------------
    bucket = os.getenv("VALIDATRADE_GCS_BUCKET", DEFAULT_BUCKET)
    try:
        loader = GCSLoader(bucket_name=bucket)
        remote_key = GCSLoader.build_partitioned_key(
            prefix="trades/api",
            filename="trades.parquet",
            ts=datetime.now(timezone.utc),
        )
        uri = loader.upload(local_path=str(local_parquet), remote_key=remote_key)
        print(f"\n🌥️  Pipeline terminé. Données disponibles à : {uri}")
    except EnvironmentError as e:
        print(f"\n⚠️  Upload GCS ignoré ({e})")
        print(f"   Parquet local conservé : {local_parquet}")


if __name__ == "__main__":
    main()
