# ValidaTrade-Ingestor
Pipeline ETL Python modulaire pour l'ingestion de données financières. Utilisation de la POO pour l'extensibilité des sources et de Pydantic V2 pour la validation et le nettoyage strict des données (Data Quality).

# 🪙 ValidaTrade-Ingestor

**ValidaTrade-Ingestor** est un pipeline ETL (Extract, Transform, Load) modulaire conçu pour ingérer des données financières provenant de sources hétérogènes (API REST et fichiers CSV). L'objectif principal est de garantir la qualité et l'intégrité des données avant leur stockage en Data Warehouse.

## 🚀 Fonctionnalités Clés

* **Extraction Multi-Sources** : Architecture basée sur la Programmation Orientée Objet (POO) permettant d'extraire des données depuis l'API CoinGecko ou des fichiers CSV locaux.
* **Validation Stricte (Data Quality)** : Utilisation de modèles **Pydantic V2** pour forcer le typage, valider les prix (positifs) et normaliser les symboles (uppercase).
* **Gestion de la Robustesse** : Le pipeline ignore les données corrompues sans interrompre le processus d'ingestion (gestion des erreurs de parsing et de typage).
* **Export Industriel** : Sauvegarde des données validées au format **Apache Parquet**, optimisé pour les charges de travail Big Data.
* **Dockerisé** : Prêt pour le déploiement en production via containerisation.

## 📁 Structure du Projet

```text
ValidaTrade-Ingestor/
├── raw_data/
│   └── trade.csv          # Données sources brutes
├── extractors.py          # Logique d'extraction (Classes Abstraites, API, CSV)
├── models.py              # Schémas de données et validation (Pydantic)
├── main_api.py            # Point d'entrée pour l'ingestion via API
├── main_csv.py            # Point d'entrée pour l'ingestion via CSV
├── requirements.txt       # Dépendances du projet
└── Dockerfile             # Configuration de l'image Docker

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

Pour ingérer les données depuis le fichier CSV :

```bash
python main_csv.py

```

Pour ingérer les données depuis l'api coin_gecko' :

```bash
python api_csv.py

```

**Contact** : Farida SINTONDJI – [LinkedIn](https://github.com/FaridaSintondji/pipeline_marketing)
