# Phase 2 — Mode opératoire : BigQuery & dbt-core

> Setup du Data Warehouse et du projet de transformation.
>
> **Projet :** ValidaTrade-Ingestor
> **Date :** Avril 2026

---

## 📋 Sommaire

1. [Contexte](#0-contexte)
2. [Création du dataset BigQuery](#1-création-du-dataset-bigquery)
3. [Attribution du rôle IAM sur le dataset](#2-attribution-du-rôle-iam-sur-le-dataset)
4. [Chargement du Parquet GCS vers une table native](#3-chargement-du-parquet-gcs-vers-une-table-native)
5. [Test SQL de validation](#4-test-sql-de-validation)
6. [Installation de dbt-core et dbt-bigquery](#5-installation-de-dbt-core-et-dbt-bigquery)
7. [Initialisation du projet dbt](#6-initialisation-du-projet-dbt)
8. [Vérification de la connexion (dbt debug)](#7-vérification-de-la-connexion-dbt-debug)
9. [Variables d'environnement et fichiers](#8-variables-denvironnement-et-fichiers)
10. [Récapitulatif des décisions](#9-récapitulatif-des-décisions)

---

## 0. Contexte

Ce mode opératoire complète celui du [setup GCP](setup_gcp.md). Il documente, étape par étape, la création du **Data Warehouse BigQuery** et l'initialisation du **projet dbt-core**.

**Pré-requis :**
- Projet GCP activé
- Bucket GCS `validatrade-raw` créé avec le Parquet déjà chargé
- Service account `validatrade-ingestor` fonctionnel

---

## 1. Création du dataset BigQuery

### Pourquoi un dataset

Un **dataset BigQuery** est un regroupement logique de tables, équivalent du *schema* en SQL classique. Il est l'unité de granularité pour les permissions IAM.

> 💡 **Bonne pratique :** un dataset par zone du Lakehouse (`raw`, `marts`, etc.) plutôt qu'un dataset unique pour tout.

### Marche à suivre

1. **Console GCP → Menu burger → BigQuery**.
2. Dans l'**Explorateur**, trois points à côté du projet `validatrade-ingestor` → **Créer un ensemble de données**.
3. **ID :** `validatrade_raw` *(avec underscore, BigQuery interdit les tirets dans les noms de dataset)*.
4. **Type d'emplacement :** Region. **Région :** `us-central1` *(même que le bucket GCS, évite les frais cross-region)*.
5. **Activer l'expiration :** non. **Clé de chiffrement :** Clé Google par défaut.
6. Cliquer sur **Créer l'ensemble de données**.

### Choix retenus

| Paramètre | Valeur |
|---|---|
| **ID** | `validatrade_raw` |
| **Région** | `us-central1` (Iowa) |
| **Expiration tables** | Désactivée |
| **Chiffrement** | Clé Google |

> ⚠️ **Note :** Le dataset s'appelle `validatrade_raw` avec un **underscore** alors que le bucket s'appelle `validatrade-raw` avec un **tiret**. C'est une contrainte de nommage BigQuery : pas de tirets dans les datasets ni les tables.

---

## 2. Attribution du rôle IAM sur le dataset

### Pourquoi scoper au dataset et pas au projet

Au sprint 2.1, le rôle `Storage Object Admin` a été donné au service account au niveau du **bucket**. Même principe ici : on accorde le rôle `BigQuery Data Editor` **sur le dataset**, pas sur le projet entier.

Si la clé JSON fuyait, l'attaquant ne pourrait toucher qu'à ce dataset, pas à tous les datasets BigQuery du projet. **Principe du moindre privilège.**

### Marche à suivre

1. Dans l'Explorateur BigQuery, trois points à côté du dataset `validatrade_raw` → **Partager → Autorisations**.
2. Cliquer sur **Ajouter un compte principal**.
3. Coller l'email du service account :
   ```
   validatrade-ingestor@validatrade-ingestor.iam.gserviceaccount.com
   ```
4. Sélectionner le rôle : taper `BigQuery Data Editor` dans la barre de recherche.
5. Cliquer sur **Enregistrer**.

---

## 3. Chargement du Parquet GCS vers une table native

### Pourquoi une table native plutôt qu'externe

Une **table externe** pointerait directement vers le Parquet sur GCS sans duplication. Mais on choisit une **table native** pour quatre raisons :

| Avantage | Détail |
|---|---|
| **Performance** | 5 à 10× plus rapide grâce au format colonnaire Capacitor |
| **Pas de rate limit GCS** | (5 000 lectures/sec/objet sur GCS) |
| **Fonctionnalités natives** | DML, clustering, materialized views |
| **Schema enforcement** | Le typage est garanti |

> 💡 Le Parquet GCS reste comme **zone bronze d'archivage**.

### Marche à suivre

1. Trois points à côté du dataset `validatrade_raw` → **Créer une table**.
2. **Source :** Google Cloud Storage. **Parcourir** → sélectionner :
   ```
   validatrade-raw/trades/csv/year=2026/month=05/day=04/trades.parquet
   ```
3. **Format :** Parquet (auto-détecté).
4. **Destination :** projet `validatrade-ingestor`, dataset `validatrade_raw`, table `trades`, type **Native**.
5. **Schéma :** Détection automatique (le Parquet contient son schéma).
6. **Partitionnement et clustering :** laisser vide (pour cette première fois).
7. Cliquer sur **Créer la table**.

> 💡 **Note :** L'auto-détection du schéma fonctionne parce que Parquet est un format **auto-décrivant**. Le schéma (`symbol STRING`, `price FLOAT`, `amount FLOAT`, `timestamp TIMESTAMP`, `platform STRING`, `total_value FLOAT`) est lu directement depuis les métadonnées du fichier.

---

## 4. Test SQL de validation

Une fois la table chargée, on lance une requête SQL pour vérifier que les données sont bien là et calculer un VWAP de démonstration.

### Requête

```sql
SELECT
  symbol,
  COUNT(*)                            AS nb_trades,
  AVG(price)                          AS prix_moyen,
  SUM(amount)                         AS volume_total,
  SUM(price * amount) / SUM(amount)   AS vwap
FROM `validatrade-ingestor.validatrade_raw.trades`
GROUP BY symbol
ORDER BY symbol;
```

### Lecture de la requête

- Le format complet d'une table BQ est `` `projet.dataset.table` `` entouré de backticks.
- **VWAP** = `SUM(price * amount) / SUM(amount)`. C'est le prix moyen pondéré par les volumes échangés.
- Pour notre test avec 2 trades (un par symbole), le VWAP est égal au prix — c'est attendu.
- BigQuery affiche en haut le **volume estimé scanné** (utile pour estimer le coût : ~5 $/To).

---

## 5. Installation de dbt-core et dbt-bigquery

### Pourquoi cette commande

**dbt-core** est le moteur de transformation. Il ne sait pas parler aux DWH tout seul : il faut un **adaptateur** (plugin) qui fait le pont. Pour BigQuery, c'est `dbt-bigquery`.

Mêmes adaptateurs disponibles pour Snowflake, Redshift, Postgres, etc. **Cette modularité explique pourquoi dbt est devenu le standard du marché.**

### Commande

Dans le terminal Debian, venv activé, dans le dossier projet :

```bash
python -m pip install dbt-core dbt-bigquery
```

> ⏳ L'install peut prendre **5 à 15 minutes** en WSL sur `/mnt/c` (~70 dépendances incluant Jinja, networkx, agate, google-cloud-bigquery, protobuf, grpc…).

### Vérification

```bash
dbt --version
```

**Sortie attendue :** `Core 1.11.x`, `Plugins bigquery 1.11.x`.

> 💡 **Note :** Si `dbt` n'est pas trouvé à cause de pyenv : passer par `python -m dbt --version`.

---

## 6. Initialisation du projet dbt

### Commande

```bash
dbt init validatrade_dbt
```

dbt crée un dossier `validatrade_dbt/` avec le squelette du projet, et pose des questions interactives pour générer le fichier `~/.dbt/profiles.yml` (les credentials de connexion).

### Réponses aux questions interactives

| Question dbt | Réponse |
|---|---|
| Which database would you like to use? | **1** (bigquery) |
| Desired authentication method | **2** (`service_account`) |
| keyfile (path to JSON key) | `/mnt/c/Users/faris/.gcp/validatrade-ingestor-key.json` |
| project (GCP project id) | `validatrade-ingestor` |
| dataset (the name of your dbt dataset) | `validatrade_marts` |
| threads (1 or more) | **4** |
| job_execution_timeout_seconds | *(vide, défaut 300)* |
| Desired location option | **1** (US) |

### Pourquoi `validatrade_marts` comme dataset dbt

dbt va **écrire** ses tables transformées dans le dataset configuré. On sépare les zones :
- `validatrade_raw` contient les données brutes (chargées depuis GCS)
- `validatrade_marts` contiendra les modèles dbt (staging, marts)

> 💡 Cette séparation suit le pattern **Lakehouse Bronze/Silver/Gold**.

### Résultat de `dbt init`

- 📁 **Dossier créé** : `./validatrade_dbt/` avec `models/`, `tests/`, `dbt_project.yml`, etc.
- 🔐 **Profil créé** : `~/.dbt/profiles.yml` *(HORS du repo, ne sera jamais commit)*.

---

## 7. Vérification de la connexion (dbt debug)

### Commande

```bash
cd validatrade_dbt
dbt debug
```

### Ce que `dbt debug` vérifie

- Validité de `dbt_project.yml` et `profiles.yml`
- Existence et lisibilité de la clé JSON service account
- Connexion API BigQuery
- Droits du service account sur le dataset configuré

> ✅ **Tous les checks doivent être OK** avant de lancer le moindre modèle dbt.

---

## 8. Variables d'environnement et fichiers

### Localisation des fichiers clés

| Élément | Chemin |
|---|---|
| **Clé JSON service account** | `/mnt/c/Users/faris/.gcp/validatrade-ingestor-key.json` |
| **Profil dbt (credentials)** | `~/.dbt/profiles.yml` *(= `/home/faris/.dbt/profiles.yml`)* |
| **Projet dbt** | `./validatrade_dbt/` (dans le repo) |
| **Dataset BigQuery brut** | `validatrade-ingestor.validatrade_raw` |
| **Dataset BigQuery dbt** | `validatrade-ingestor.validatrade_marts` *(à créer par dbt)* |

> 💡 **Note :** `profiles.yml` est le **SEUL** fichier dbt qui contient des credentials. Il vit dans `~/.dbt/` par convention, **hors du repo**. Les fichiers du dossier `validatrade_dbt/` sont du code (modèles SQL, configuration) et peuvent être commits sans risque.

---

## 9. Récapitulatif des décisions

| Décision | Choix retenu / justification |
|---|---|
| **Dataset name** | `validatrade_raw` (underscore obligatoire) |
| **Région BQ** | `us-central1` (cohérent avec GCS, évite cross-region) |
| **Type de table** | Native (perf 5-10×, DML, clustering, materialized views) |
| **IAM scope** | `BigQuery Data Editor` sur le DATASET seulement (moindre privilège) |
| **Adaptateur dbt** | `dbt-bigquery` (modulaire, standard de l'industrie) |
| **Auth dbt** | `service_account` avec clé JSON (mêmes credentials que le pipeline) |
| **Dataset dbt cible** | `validatrade_marts` (séparation raw / marts) |
| **Threads dbt** | 4 (parallélisme raisonnable pour un dev local) |

