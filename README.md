# 🪙 ValidaTrade-Ingestor

**ValidaTrade-Ingestor** est un pipeline ELT modulaire qui ingère des trades crypto (sources CSV ou API CoinGecko), les valide avec Pydantic, les pousse dans Google Cloud Storage en partitionnement Hive, les charge dans BigQuery, et les transforme en tables analytiques avec dbt.

## 🏗️ Architecture (Phase 2)

```text
                                                                    ┌───────────────┐
   ┌────────┐    ┌────────────┐    ┌──────────────┐    ┌────────┐   │ dbt staging   │
   │  CSV   │───▶│ Pydantic   │───▶│ Parquet (us) │───▶│  GCS   │──▶│ stg_trades    │──┐
   └────────┘    │ validation │    │ + timestamps │    │ bucket │   │  (view BQ)    │  │
   ┌────────┐    │            │    │ microseconds │    │ Hive   │   └───────┬───────┘  │
   │CoinGecko│──▶│            │    │              │    │partit. │           │          │
   │   API   │   └────────────┘    └──────────────┘    └────┬───┘           ▼          │
   └────────┘                                               │       ┌───────────────┐  │
                                                            ▼       │ dbt marts     │  │
                                                  ┌─────────────────┐│ daily_vwap    │◀┘
                                                  │ BigQuery native ││  (table BQ)   │
                                                  │ validatrade_raw ││ + 12 tests    │
                                                  │     .trades     │└───────────────┘
                                                  └─────────────────┘
```

## 🚀 Fonctionnalités Clés

* **Extraction Multi-Sources** : architecture POO avec classe abstraite `BaseExtractor`, implémentations `CSVExtractor` et `APIExtractor`.
* **Validation Pydantic V2** : typage strict, prix et quantités positives, normalisation des symboles, timestamps en UTC.
* **Robustesse** : les données corrompues sont rejetées sans interrompre le pipeline.
* **Export Parquet** typé microsecondes (compatible BigQuery).
* **Stockage cloud** : Google Cloud Storage en région `us-central1`, partitionnement Hive `year=/month=/day=` pour partition pruning au moment des requêtes BigQuery.
* **Data Warehouse** : BigQuery, table native partitionnable, accessible aux analystes en SQL.
* **Transformation dbt-core** : modèles staging → marts en SQL versionné, refs et lineage automatique, 12 tests YAML (`not_null`, `accepted_values`, `unique_combination_of_columns`).
* **Sécurité** : Service Account dédié, principe du moindre privilège (rôles scopés au bucket et au dataset), clé JSON hors du repo.
* **FinOps** : alerte budget GCP à 5 EUR/mois avec notifications par email.
* **CI/CD** : 21 tests unitaires Python exécutés à chaque push via GitHub Actions.

## 📁 Structure du Projet

```text
ValidaTrade-Ingestor/
├── extractors.py                    # Extracteurs API CoinGecko et CSV (Phase 0)
├── loaders.py                       # BaseLoader abstrait + GCSLoader (Phase 2)
├── models.py                        # Schémas Pydantic V2 (Phase 0)
├── main_csv.py                      # Pipeline CSV → Parquet → GCS
├── main_api.py                      # Pipeline API CoinGecko → Parquet → GCS
├── trade.csv                        # Données CSV de test
├── requirements.txt                 # Dépendances Python (Pydantic, pandas, pyarrow, google-cloud-storage, pytest, ...)
├── tests/
│   ├── conftest.py                  # Config pytest (PYTHONPATH)
│   ├── test_models.py               # 13 tests sur le modèle Trade (Phase 1)
│   └── test_loaders.py              # 8 tests mockés du GCSLoader (Phase 2)
├── .github/workflows/ci.yml         # CI GitHub Actions (Phase 1)
├── validatrade_dbt/                 # Projet dbt-core (Phase 2)
│   ├── dbt_project.yml              # Config dbt
│   ├── packages.yml                 # dbt_utils
│   └── models/
│       ├── staging/
│       │   ├── _sources.yml         # Déclaration de la source BQ
│       │   ├── _models.yml          # Tests YAML staging
│       │   └── stg_trades.sql       # Modèle staging (vue)
│       └── marts/
│           ├── _models.yml          # Tests YAML marts
│           └── daily_vwap.sql       # Modèle mart (table) — calcul VWAP
└── docs/                            # (générée par dbt docs)
    Phase1_Git_Tests_CICD.docx
    Phase2_Cloud_dbt.docx
    Phase2_Setup_GCP_ModeOperatoire.docx
    Phase2_Setup_BigQuery_dbt_ModeOperatoire.docx
```

## 🛠️ Installation & Utilisation

### Prérequis

* Python 3.12+
* Docker (optionnel)

### Installation locale

1. Clonez le dépôt :
```bash
git clone https://github.com/ton-pseudo/ValidaTrade-Ingestor.git
cd ValidaTrade-Ingestor

```


2. Installez les dépendances :
```bash
pip install -r requirements.txt

```



### Exécution

#### 1. Pipeline d'ingestion vers GCS

Définir les variables d'environnement (chemin clé service account + bucket cible) :

```bash
export GOOGLE_APPLICATION_CREDENTIALS="/chemin/vers/cle.json"
export VALIDATRADE_GCS_BUCKET="validatrade-raw"
```

Puis lancer un des deux pipelines :

```bash
python main_csv.py      # ingestion via CSV local
python main_api.py      # ingestion via API CoinGecko
```

#### 2. Tests Python

```bash
python -m pytest tests/ -v
```

#### 3. Pipeline dbt (depuis le dossier validatrade_dbt/)

```bash
cd validatrade_dbt
dbt debug       # vérifie la connexion BigQuery
dbt run         # exécute tous les modèles (staging + marts)
dbt test        # vérifie les 12 tests YAML
dbt docs generate && dbt docs serve   # documentation interactive
```

---

**Contact** : Farida SINTONDJI – [LinkedIn](http://www.linkedin.com/in/farida-sintondji-94919127a)
