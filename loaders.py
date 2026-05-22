"""
loaders.py
==========
Module de chargement (Load) du pipeline ETL.

Symétrique de extractors.py : on définit une classe abstraite BaseLoader
et des implémentations concrètes par destination.

Phase 2 : GCSLoader pour pousser les fichiers Parquet validés vers
Google Cloud Storage.

Auteur : Farida Sintondji
"""

from abc import ABC, abstractmethod
from pathlib import Path
from datetime import datetime, timezone
import os

from google.cloud import storage, bigquery
from google.api_core.exceptions import GoogleAPICallError, NotFound


class BaseLoader(ABC):
    """
    Contrat commun à tous les loaders du pipeline.

    Tout loader doit savoir :
    - de quel "destination_name" il s'agit (pour les logs / observabilité),
    - comment charger un fichier local vers sa destination (méthode upload).
    """

    def __init__(self, destination_name: str):
        self.destination_name = destination_name

    @abstractmethod
    def upload(self, local_path: str, remote_key: str) -> str:
        """
        Charge un fichier local vers la destination distante.

        Args:
            local_path: chemin du fichier sur la machine (ex. 'output/trades.parquet').
            remote_key: clé/chemin distant (ex. 'trades/2026/04/27/btc.parquet').

        Returns:
            L'URI complet de l'objet écrit (ex. 'gs://bucket/trades/...parquet').
        """
        pass


class GCSLoader(BaseLoader):
    """
    Loader vers Google Cloud Storage.

    Authentification :
    - Utilise la variable d'environnement GOOGLE_APPLICATION_CREDENTIALS
      qui pointe vers la clé JSON du service account.
    - C'est le mécanisme par défaut du SDK Google : aucun credential en dur
      dans le code.

    Usage :
        loader = GCSLoader(bucket_name="validatrade-raw-fari")
        uri = loader.upload(
            local_path="output/trades.parquet",
            remote_key="trades/2026/04/27/api_btc.parquet",
        )
    """

    def __init__(self, bucket_name: str):
        super().__init__(destination_name=f"gcs://{bucket_name}")
        self.bucket_name = bucket_name

        # Le Client lit GOOGLE_APPLICATION_CREDENTIALS automatiquement.
        # On échoue tôt et clairement si la variable n'est pas définie.
        if not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
            raise EnvironmentError(
                "GOOGLE_APPLICATION_CREDENTIALS n'est pas définie. "
                "Pointe-la vers ta clé JSON de service account."
            )

        try:
            self.client = storage.Client()
            # bucket() crée une référence Python locale, SANS appel API.
            # On évite ainsi d'exiger storage.buckets.get au service account
            # (principe du moindre privilège).
            # Les vraies erreurs (bucket inexistant, droits insuffisants)
            # remonteront lors du upload, où on a les permissions objets.
            self.bucket = self.client.bucket(bucket_name)
        except GoogleAPICallError as e:
            raise ConnectionError(f"Erreur d'appel API GCP : {e}")

    def upload(self, local_path: str, remote_key: str) -> str:
        """
        Upload un fichier local vers gs://{bucket_name}/{remote_key}.

        Lève une FileNotFoundError si le fichier local est introuvable,
        et propage les erreurs GCP en cas de problème côté cloud.
        """
        path = Path(local_path)
        if not path.is_file():
            raise FileNotFoundError(f"Fichier local introuvable : {local_path}")

        print(
            f"⬆️  Upload {path.name} → {self.destination_name}/{remote_key} ..."
        )

        blob = self.bucket.blob(remote_key)
        # upload_from_filename gère le streaming automatiquement,
        # même pour les gros fichiers.
        blob.upload_from_filename(str(path))

        uri = f"gs://{self.bucket_name}/{remote_key}"
        print(f"✅ Upload réussi : {uri}")
        return uri

    @staticmethod
    def build_partitioned_key(
        prefix: str,
        filename: str,
        ts: datetime | None = None,
    ) -> str:
        """
        Construit une clé partitionnée par date au format Hive,
        compatible BigQuery, Spark, dbt :
            {prefix}/year=2026/month=04/day=27/{filename}

        Args:
            prefix:   ex. 'trades/api'
            filename: ex. 'btc.parquet'
            ts:       timestamp d'ingestion (UTC). Par défaut : maintenant.

        Returns:
            La clé complète, ex. 'trades/api/year=2026/month=04/day=27/btc.parquet'.
        """
        ts = ts or datetime.now(timezone.utc)
        return (
            f"{prefix.rstrip('/')}/"
            f"year={ts.year:04d}/"
            f"month={ts.month:02d}/"
            f"day={ts.day:02d}/"
            f"{filename}"
        )

class BigQueryLoader:
    """
    Charge un fichier Parquet depuis GCS vers une table BigQuery.

    Différence avec GCSLoader :
    - GCSLoader transfère un fichier LOCAL → GCS (cloud storage).
    - BigQueryLoader déclenche un job de chargement GCS → BigQuery
      (tout se passe côté GCP, sans transiter par la machine locale).

    C'est pourquoi BigQueryLoader n'hérite pas de BaseLoader :
    la signature de la méthode principale (gcs_uri → table BigQuery)
    est différente de celle de `upload(local_path, remote_key)`.

    Authentification :
        Utilise GOOGLE_APPLICATION_CREDENTIALS (même mécanisme que GCSLoader).

    Usage :
        loader = BigQueryLoader(project_id="mon-projet-gcp")
        loader.load(
            gcs_uri="gs://validatrade-raw/trades/csv/year=2026/.../trades.parquet",
            table_ref="validatrade_raw.trades",
        )
    """

    def __init__(self, project_id: str):
        if not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
            raise EnvironmentError(
                "GOOGLE_APPLICATION_CREDENTIALS n'est pas définie. "
                "Pointe-la vers ta clé JSON de service account."
            )
        self.project_id = project_id
        self.client = bigquery.Client(project=project_id)

    def load(
        self,
        gcs_uri: str,
        table_ref: str,
        write_disposition: str = "WRITE_APPEND",
    ) -> None:
        """
        Déclenche un job BigQuery Load : GCS Parquet → table BigQuery.

        Args:
            gcs_uri:           URI du fichier Parquet dans GCS.
                               ex. 'gs://validatrade-raw/trades/csv/.../trades.parquet'
            table_ref:         Référence de la table cible au format 'dataset.table'
                               ou 'project.dataset.table'.
                               ex. 'validatrade_raw.trades'
            write_disposition: 'WRITE_APPEND' (défaut) ou 'WRITE_TRUNCATE'.
                               APPEND conserve l'historique ; TRUNCATE écrase.

        Raises:
            google.cloud.exceptions.GoogleAPICallError : problème côté GCP.
        """
        full_table = (
            table_ref
            if "." in table_ref and table_ref.count(".") >= 2
            else f"{self.project_id}.{table_ref}"
        )

        job_config = bigquery.LoadJobConfig(
            source_format=bigquery.SourceFormat.PARQUET,
            write_disposition=write_disposition,
            # autodetect=True : BigQuery infère le schéma depuis le Parquet.
            # En prod on préférerait un schéma explicite, mais pour
            # ce projet de formation c'est suffisant et plus maintenable.
            autodetect=True,
        )

        print(f"⬆️  Lancement du job BigQuery Load : {gcs_uri} → {full_table} ...")

        load_job = self.client.load_table_from_uri(
            gcs_uri, full_table, job_config=job_config
        )
        # .result() est bloquant : on attend la fin du job avant de continuer.
        # C'est le comportement souhaité dans un DAG Airflow séquentiel.
        load_job.result()

        table = self.client.get_table(full_table)
        print(
            f"✅ Chargement terminé : {table.num_rows} lignes dans {full_table}."
        )
