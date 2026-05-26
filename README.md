# 🪙 ValidaTrade-Ingestor

**ValidaTrade-Ingestor** est un pipeline ELT modulaire qui ingère des trades crypto (sources CSV ou API CoinGecko), les valide avec Pydantic, les pousse dans Google Cloud Storage en partitionnement Hive, les charge dans BigQuery, les transforme en tables analytiques avec dbt, et orchestre l'ensemble via Apache Airflow.

## 🏗️ Architecture (Phase 3)

```text
   ┌────────────────────────────────────── Apache Airflow (DAG quotidien 6h UTC) ──────────────────────────────────────┐
   │                                                                                                                  │
   │   extract_validate  ───────▶   load_bigquery   ───────▶   dbt_run   ───────▶   dbt_test                          │
   │  (main_csv.py)              (main_bq_load.py)        (staging + marts)     (12 tests YAML)                       │
   │                                                                                                                  │
   └─────┬──────────────────────────────┬──────────────────────────────┬───────────────────────────────┬──────────────┘
         │                              │                              │                               │
         ▼                              ▼                              ▼                               ▼
   ┌────────────┐    ┌──────────────┐    ┌────────┐    ┌─────────────────┐    ┌───────────────┐    ┌───────────────┐
   │  CSV / API │───▶│   Pydantic   │───▶│ Parquet│───▶│ GCS (us-central1)│──▶│ BigQuery native│──▶│ dbt staging   │
   │  CoinGecko │    │  validation  │    │  (us)  │    │ partition. Hive  │   │ validatrade_raw│   │ stg_trades    │──┐
   └────────────┘    │              │    │        │    │ year=/month=/day=│   │     .trades    │   │   (view BQ)   │  │
                     └──────────────┘    └────────┘    └─────────────────┘    └────────────────┘   └───────┬───────┘  │
                                                                                                           │          │
                                                                                                           ▼          │
                                                                                                  ┌───────────────┐   │
                                                                                                  │  dbt marts    │   │
                                                                                                  │  daily_vwap   │◀──┘
                                                                                                  │  (table BQ)   │
                                                                                                  └───────────────┘
```

## 🚀 Fonctionnalités Clés

* **Extraction Multi-Sources** : architecture POO avec classe abstraite `BaseExtractor`, implémentations `CSVExtractor` et `APIExtractor`.
* **Validation Pydantic V2** : typage strict, prix et quantités positives, normalisation des symboles, timestamps en UTC.
* **Robustesse** : les données corrompues sont rejetées sans interrompre le pipeline.
* **Export Parquet** typé microsecondes (compatible BigQuery).
* **Stockage cloud** : Google Cloud Storage en région `us-central1`, partitionnement Hive `year=/month=/day=` pour partition pruning au moment des requêtes BigQuery.
* **Data Warehouse** : BigQuery, table native partitionnable, accessible aux analystes en SQL.
* **Transformation dbt-core** : modèles staging → marts en SQL versionné, refs et lineage automatique, 12 tests YAML (`not_null`, `accepted_values`, `unique_combination_of_columns`).
* **Sécurité** : Service Account dédié, principe du moindre privilège (rôles scopés au bucket et au dataset), clé JSON hors du repo, code projet monté en read-only (`:ro`) dans le conteneur Airflow.
* **FinOps** : alerte budget GCP à 5 EUR/mois avec notifications par email.
* **CI/CD** : 21 tests unitaires Python exécutés à chaque push via GitHub Actions.
* **Orchestration Airflow** : stack Apache Airflow 2.10.5 (CeleryExecutor) en Docker avec image custom, DAG quotidien à 6h UTC (`extract_validate → load_bigquery → dbt_run → dbt_test`), retries automatiques, healthchecks sur tous les services. Container immutability : code en `:ro`, état writeable redirigé vers `/tmp` via env vars (`VALIDATRADE_OUTPUT_DIR`, `DBT_LOG_PATH`, `DBT_TARGET_PATH`).

## 📁 Structure du Projet

```text
ValidaTrade-Ingestor/
├── extractors.py                    # Extracteurs API CoinGecko et CSV (Phase 0)
├── loaders.py                       # BaseLoader abstrait + GCSLoader + BigQueryLoader (Phase 2/3)
├── models.py                        # Schémas Pydantic V2 (Phase 0)
├── main_csv.py                      # Pipeline CSV → Parquet → GCS
├── main_api.py                      # Pipeline API CoinGecko → Parquet → GCS
├── main_bq_load.py                  # Load GCS → BigQuery (Phase 3, orchestré par Airflow)
├── trade.csv                        # Données CSV de test
├── requirements.txt                 # Dépendances Python (Pydantic, pandas, pyarrow, google-cloud-storage, google-cloud-bigquery, pytest, ...)
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
├── airflow/                         # Stack Airflow (Phase 3)
│   ├── Dockerfile                   # Image custom validatrade-airflow:latest (libs préinstallées)
│   ├── docker-compose.yaml          # CeleryExecutor + postgres + redis (6 conteneurs)
│   ├── .env.example                 # Modèle (AIRFLOW_UID, GCP_PROJECT_ID)
│   ├── dags/
│   │   └── validatrade_pipeline.py  # DAG quotidien 4 tâches
│   └── dbt-profiles/
│       └── profiles.yml             # Profil dbt service-account headless
└── docs/                            # (générée par dbt docs)
    setup_gcp
    setup_bigquery_dbt
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

#### 4. Orchestration Airflow (depuis le dossier airflow/)

Setup une seule fois :

```bash
cd airflow
cp .env.example .env
echo "AIRFLOW_UID=$(id -u)" >> .env       # remplace AIRFLOW_UID
# Édite .env pour mettre ton vrai GCP_PROJECT_ID

docker compose build                       # build image custom (3-5 min)
docker compose up airflow-init             # init métadonnées Airflow
```

Démarrage / arrêt :

```bash
docker compose up -d        # démarre toute la stack (6 conteneurs)
docker compose ps           # vérifie healthchecks
docker compose down         # arrêt simple (préserve la BDD)
docker compose down -v      # arrêt + reset complet
```

Puis ouvre `http://localhost:8080` (login `airflow` / `airflow`), active le DAG `validatrade_pipeline` et clique sur ▶ Trigger DAG. Le pipeline s'exécutera automatiquement chaque jour à 6h UTC ensuite.

Pour le détail des étapes : voir `docs/Phase3_Airflow_ModeOperatoire.docx`.

---

**Contact** : Farida SINTONDJI – [LinkedIn](http://www.linkedin.com/in/farida-sintondji-94919127a)
