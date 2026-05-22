# Airflow — Orchestration ValidaTrade (Phase 3)

Stack Airflow 2.10.4 (CeleryExecutor) en Docker pour orchestrer le pipeline ELT crypto.

## Pourquoi cette structure ?

- **`Dockerfile`** : image custom Airflow avec toutes les libs projet pré-installées
  (pydantic, pandas, pyarrow, google-cloud-storage, dbt-core, dbt-bigquery). Évite
  `_PIP_ADDITIONAL_REQUIREMENTS` qui réinstallait tout à chaque démarrage et bloquait
  le worker en "stuck in queued".
- **`docker-compose.yaml`** : adaptée de la version officielle Apache 2.10.4. Modifs
  ValidaTrade : `build: .`, montage du code projet en `:ro`, montage de la clé GCP
  en `:ro`, `LOAD_EXAMPLES: false`, variables d'environnement GCP.
- **`dags/validatrade_pipeline.py`** : DAG quotidien (6h UTC) avec 4 tâches enchaînées
  `extract_validate → load_bigquery → dbt_run → dbt_test`.

## Setup

```bash
# 1. Créer le fichier .env (gitignoré)
touch .env
echo "AIRFLOW_UID=$(id -u)" > .env

# 2. Build de l'image custom (3-5 min, à faire une fois)
docker compose build

# 3. Init de la base de métadonnées (à faire une fois)
docker compose up airflow-init

# 4. Démarrage de toute la stack
docker compose up -d

# 5. Vérifier que tous les services sont healthy
docker compose ps

# 6. UI Airflow
# http://localhost:8080  (login : airflow / airflow)
```

## Arrêt / nettoyage

```bash
docker compose down            # arrêt simple (préserve la BDD)
docker compose down -v         # arrêt + suppression des volumes (reset complet)
```

## Structure des volumes montés

| Conteneur                         | Host                              | Accès |
|-----------------------------------|-----------------------------------|-------|
| `/opt/airflow/dags`               | `./dags`                          | rw    |
| `/opt/airflow/logs`               | `./logs`                          | rw    |
| `/opt/airflow/plugins`            | `./plugins`                       | rw    |
| `/opt/airflow/config`             | `./config`                        | rw    |
| `/opt/airflow/validatrade`        | `../` (racine du projet)          | ro    |
| `/opt/airflow/keys`               | `/mnt/c/Users/faris/.gcp`         | ro    |
| `/opt/airflow/dbt-profiles`       | `./dbt-profiles`                  | ro    |

## Prérequis

- Docker Desktop + WSL 2 (Debian/Ubuntu) sur Windows.
- Clé service account GCP stockée dans `~/.gcp/validatrade-ingestor-key.json` côté Windows
  (=`/mnt/c/Users/faris/.gcp/validatrade-ingestor-key.json` côté WSL).
- Bucket GCS `validatrade-raw` et dataset BigQuery `validatrade_raw` déjà créés (Phase 2).
