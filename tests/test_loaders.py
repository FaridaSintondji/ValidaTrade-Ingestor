"""
tests/test_loaders.py
=====================
Tests unitaires du module loaders.

Stratégie : on ne contacte JAMAIS GCP pendant les tests.
On mocke le SDK google.cloud.storage avec unittest.mock.
=> Tests rapides, déterministes, exécutables en CI sans secrets.
"""

import os
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

import pytest

from loaders import GCSLoader


# ---------------------------------------------------------------------------
# Tests de la méthode statique build_partitioned_key (pas de mock nécessaire)
# ---------------------------------------------------------------------------

class TestBuildPartitionedKey:
    """La construction de clé Hive est pure : on peut la tester directement."""

    def test_format_basique(self):
        ts = datetime(2026, 4, 27, 12, 0, 0, tzinfo=timezone.utc)
        key = GCSLoader.build_partitioned_key(
            prefix="trades/api", filename="btc.parquet", ts=ts
        )
        assert key == "trades/api/year=2026/month=04/day=27/btc.parquet"

    def test_zero_padding_mois_et_jour(self):
        """Mois et jour doivent toujours être sur 2 chiffres (01, 02, ...)."""
        ts = datetime(2026, 1, 5, tzinfo=timezone.utc)
        key = GCSLoader.build_partitioned_key(
            prefix="trades", filename="x.parquet", ts=ts
        )
        # year=2026/month=01/day=05 (pas month=1/day=5)
        assert "month=01" in key
        assert "day=05" in key

    def test_prefix_avec_slash_final_est_normalise(self):
        ts = datetime(2026, 4, 27, tzinfo=timezone.utc)
        key = GCSLoader.build_partitioned_key(
            prefix="trades/api/", filename="x.parquet", ts=ts
        )
        # Pas de double slash
        assert "//" not in key

    def test_timestamp_par_defaut_est_now_utc(self):
        """Sans ts explicite, on doit utiliser datetime.now(UTC)."""
        key = GCSLoader.build_partitioned_key(
            prefix="trades", filename="x.parquet"
        )
        now = datetime.now(timezone.utc)
        assert f"year={now.year:04d}" in key


# ---------------------------------------------------------------------------
# Tests de l'init du loader avec mock du SDK Google
# ---------------------------------------------------------------------------

class TestGCSLoaderInit:
    """Vérifie le comportement à l'instanciation."""

    def test_erreur_si_credentials_non_definies(self, monkeypatch):
        """Sans GOOGLE_APPLICATION_CREDENTIALS, on plante immédiatement."""
        monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
        with pytest.raises(EnvironmentError, match="GOOGLE_APPLICATION_CREDENTIALS"):
            GCSLoader(bucket_name="any-bucket")

    @patch("loaders.storage.Client")
    def test_init_ok_avec_credentials(self, mock_client_cls, monkeypatch):
        """Avec credentials et bucket existant, l'init doit réussir."""
        monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/fake/path.json")

        # On simule un client GCP qui retourne un bucket
        mock_bucket = MagicMock()
        mock_client_cls.return_value.get_bucket.return_value = mock_bucket

        loader = GCSLoader(bucket_name="my-bucket")
        assert loader.bucket_name == "my-bucket"
        assert loader.destination_name == "gcs://my-bucket"
        mock_client_cls.return_value.get_bucket.assert_called_once_with("my-bucket")


# ---------------------------------------------------------------------------
# Test de la méthode upload avec mock complet
# ---------------------------------------------------------------------------

class TestGCSLoaderUpload:
    """Vérifie le comportement d'upload sans appel réseau."""

    @patch("loaders.storage.Client")
    def test_upload_fichier_inexistant_leve_filenotfound(
        self, mock_client_cls, monkeypatch
    ):
        monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/fake/path.json")
        mock_client_cls.return_value.get_bucket.return_value = MagicMock()

        loader = GCSLoader(bucket_name="my-bucket")
        with pytest.raises(FileNotFoundError):
            loader.upload(local_path="ne_existe_pas.parquet", remote_key="x.parquet")

    @patch("loaders.storage.Client")
    def test_upload_appelle_le_blob_avec_la_bonne_cle(
        self, mock_client_cls, monkeypatch, tmp_path
    ):
        """Le upload doit créer un blob avec la remote_key exacte."""
        monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/fake/path.json")

        # Setup du mock
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_bucket.blob.return_value = mock_blob
        mock_client_cls.return_value.get_bucket.return_value = mock_bucket

        # Crée un fichier local fictif (vrai fichier sur le filesystem temporaire)
        fake_parquet = tmp_path / "trades.parquet"
        fake_parquet.write_bytes(b"fake parquet content")

        loader = GCSLoader(bucket_name="my-bucket")
        uri = loader.upload(
            local_path=str(fake_parquet),
            remote_key="trades/api/year=2026/month=04/day=27/trades.parquet",
        )

        # Vérifications
        mock_bucket.blob.assert_called_once_with(
            "trades/api/year=2026/month=04/day=27/trades.parquet"
        )
        mock_blob.upload_from_filename.assert_called_once_with(str(fake_parquet))
        assert uri == (
            "gs://my-bucket/trades/api/year=2026/month=04/day=27/trades.parquet"
        )
