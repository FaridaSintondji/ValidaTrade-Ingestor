# Phase 2 — Mode opératoire : Setup GCP

> Configuration étape par étape : projet, facturation, bucket GCS, service account, clé JSON.
>
> **Projet :** ValidaTrade-Ingestor
> **Date :** Avril 2026

---

## 📋 Sommaire

1. [Contexte](#0-contexte)
2. [Création du projet GCP](#1-création-du-projet-gcp)
3. [Activation du compte de facturation](#2-activation-du-compte-de-facturation)
4. [Liaison du compte de facturation au projet](#3-liaison-du-compte-de-facturation-au-projet)
5. [Mise en place de l'alerte budget](#4-mise-en-place-de-lalerte-budget)
6. [Création du bucket Cloud Storage](#5-création-du-bucket-cloud-storage)
7. [Création du service account](#6-création-du-service-account)
8. [Attribution du rôle IAM (scopé au bucket)](#7-attribution-du-rôle-iam-scopé-au-bucket)
9. [Téléchargement et sécurisation de la clé JSON](#8-téléchargement-et-sécurisation-de-la-clé-json)
10. [Récapitulatif des décisions](#9-récapitulatif-des-décisions)
11. [Variables d'environnement](#10-variables-denvironnement-utilisées-ensuite)
12. [Pitch entretien](#11-pitch-entretien-condensé)

---

## 0. Contexte

Ce document trace, étape par étape, la configuration GCP réalisée pour permettre au pipeline **ValidaTrade-Ingestor** de pousser ses fichiers Parquet dans Google Cloud Storage. Il sert à deux choses :

- Refaire la configuration depuis zéro si le projet GCP est supprimé ou si tu repars sur un compte différent.
- Justifier les choix techniques en entretien (région, IAM, alertes budget).

**Pré-requis :** un compte Google personnel (free trial GCP déjà consommé dans notre cas).

---

## 1. Création du projet GCP

### Marche à suivre

1. Aller sur [console.cloud.google.com](https://console.cloud.google.com) et se connecter avec son compte Google.
2. En haut de la page, à côté du logo Google Cloud, ouvrir le sélecteur de projet.
3. Cliquer sur **Nouveau projet**.
4. Saisir le nom : `validatrade-ingestor`.
5. Laisser l'ID auto-généré et l'organisation à vide. Cliquer sur **Créer**.

### Choix retenu

Nom de projet simple et explicite. L'ID auto-généré était identique au nom (`validatrade-ingestor`), aucun suffixe numérique n'a été ajouté, ce qui nous donne un email de service account court par la suite.

---

## 2. Activation du compte de facturation

### Contexte spécifique

Le free trial GCP avait déjà été consommé, ce qui a placé le compte de facturation en état **« essai expiré »**. Dans cet état, aucune ressource ne peut être créée (ni bucket, ni alerte budget, ni service account avec rôles).

### Marche à suivre

1. **Menu burger → Facturation**.
2. Bandeau rouge en haut : cliquer sur le bouton **Activer**.
3. Renseigner les informations de paiement (carte bancaire requise).

### Justification du choix

> ⚠️ **Activer le compte ne signifie pas payer.** Le mode « compte complet » est un mode post-paiement : tu ne paies que ce que tu consommes au-delà des quotas Always Free. Pour ce projet (volumes minuscules), la facture attendue est **de zéro**.

> 💡 **Always Free GCP n'est PAS le free trial.** C'est un tier *permanent* qui inclut notamment :
> - **5 Go de stockage GCS / mois** en région US
> - **1 To de requêtes BigQuery / mois**, partout dans le monde
>
> Il reste accessible **même après la fin du free trial $300 / 90 jours**.

---

## 3. Liaison du compte de facturation au projet

### Pourquoi cette étape

Activer le compte de facturation ne le rattache pas automatiquement à tous les projets. La liaison **projet ↔ facturation** se fait manuellement, projet par projet. Sans cette liaison, le projet `validatrade-ingestor` reste en état « Facturation désactivée » et ne peut créer aucune ressource.

### Marche à suivre

1. **Sélecteur de projet** en haut → choisir `validatrade-ingestor`.
2. **Menu burger → Facturation**.
3. Cliquer sur **Associer un compte de facturation**.
4. Sélectionner le compte que l'on vient d'activer → **Définir le compte**.

---

## 4. Mise en place de l'alerte budget

### Pourquoi avant tout

Le réflexe **FinOps** de base : on ne déploie rien dans le cloud sans avoir d'observabilité sur les coûts. L'alerte budget crée une notification automatique par email si la consommation atteint des seuils prédéfinis.

### Marche à suivre

1. **Menu burger → Facturation → Budgets et alertes → Créer un budget**.
2. **Étape 1** : nom `Budget ValidaTrade-Ingestor`, période *Monthly*, projet `validatrade-ingestor`, services *All services*.
3. **Étape 2** : *Specified amount*, montant **5**, devise **EUR**.
4. **Étape 3** : seuils par défaut **50 % / 90 % / 100 %**, cocher l'envoi d'emails aux administrateurs et utilisateurs de la facturation.
5. Cliquer sur **Terminer**.

### Choix retenus

| Paramètre | Valeur retenue |
|---|---|
| Période | Mensuelle |
| Montant | 5 EUR |
| Seuils d'alerte | 50 %, 90 %, 100 % |
| Canal | Email aux admins de facturation |
| Pub/Sub | Non utilisé (besoin uniquement d'un signal humain) |

---

## 5. Création du bucket Cloud Storage

### Marche à suivre

1. **Menu burger → Cloud Storage → Buckets → Créer**.
2. **Section 1 — Nom :** `validatrade-raw`.
3. **Section 2 — Emplacement :** type **Region**, région `us-central1` (Iowa). Réplication entre buckets : **NON cochée**.
4. **Section 3 — Classe de stockage :** *Standard*.
5. **Section 4 — Contrôle d'accès :** *Uniforme*. **Empêchement de l'accès public : appliqué**.
6. **Section 5 — Protection :** laisser par défaut (soft delete 7 jours, pas de versioning, chiffrement Google-managed).
7. Cliquer sur **Créer** puis confirmer la popup d'accès public bloqué.

### Choix retenus et justifications

| Paramètre | Valeur | Pourquoi ce choix |
|---|---|---|
| **Nom** | `validatrade-raw` | Convention bronze : ce bucket reçoit des données brutes / semi-traitées. |
| **Type emplacement** | Region (single) | Multi-region et dual-region sont plus chers, sans utilité pour de l'apprentissage. |
| **Région** | `us-central1` (Iowa) | **Seule région éligible Always Free 5 Go/mois.** Latence FR ~130 ms invisible en batch ETL. |
| **Classe** | Standard | Accès fréquent. Nearline / Coldline / Archive sont pour de l'archivage long terme. |
| **Accès** | Uniforme + accès public bloqué | Recommandé Google. Empêche un objet d'être rendu public par accident. |
| **Réplication** | Désactivée | La réplication double le coût et n'a d'intérêt qu'en disaster recovery prod. |
| **Versioning** | Désactivé | Éviter de doubler la consommation. Réactivable plus tard si besoin. |

---

## 6. Création du service account

### Pourquoi un service account dédié

Un **service account** est un compte non-humain. Il permet à un script Python de s'authentifier auprès de GCP sans utiliser le compte personnel du développeur. Avantages :

- **Révocation indépendante** : on peut couper l'accès du script sans toucher au compte humain.
- **Traçabilité** : tous les appels GCP sont attribués à ce SA dans les logs Cloud Audit.
- **Principe de moindre privilège** : le SA ne porte que les permissions strictement nécessaires.

### Marche à suivre

1. **Menu burger → IAM et administration → Comptes de service → Créer un compte de service**.
2. **Étape 1 :** nom `validatrade-ingestor`, description *« Compte de service pour le pipeline ValidaTrade »*. Cliquer sur **Créer et continuer**.
3. **Étape 2 — Accès au projet : NE RIEN sélectionner.** *(On ne donne pas de rôle au niveau projet, on scope au bucket.)* Cliquer sur **Continuer**.
4. **Étape 3 — Accès utilisateurs :** ne rien remplir. Cliquer sur **OK**.

### Email du service account

```
validatrade-ingestor@validatrade-ingestor.iam.gserviceaccount.com
```

> 💡 **Note :** L'email du SA suit la règle :
> `<nom-SA>@<id-projet>.iam.gserviceaccount.com`.
> Ici l'ID projet est le même que le nom (pas de suffixe), ce qui rend l'email court.

---

## 7. Attribution du rôle IAM (scopé au bucket)

### Pourquoi scoper au bucket et pas au projet

Au moment de la création du SA, on aurait pu lui donner le rôle **Storage Admin** au niveau du projet entier. C'est ce que GCP propose par défaut. **On a refusé** parce que :

- Ça aurait donné au SA accès à **TOUS** les buckets du projet (actuels et futurs).
- Une fuite de la clé JSON aurait exposé tous les buckets, pas juste celui du pipeline.
- En entretien, savoir « pourquoi on ne donne pas Storage Admin au niveau projet » est un classique.

### Marche à suivre

1. **Cloud Storage → Buckets → cliquer sur `validatrade-raw`**.
2. Onglet **Autorisations → Accorder l'accès**.
3. **Nouveaux comptes principaux :** coller l'email du SA.
4. **Sélectionner un rôle :** taper *« objets »* dans la barre, choisir **Administrateur des objets Storage** (`Storage Object Admin`).
5. **Enregistrer**.

### Différence Storage Admin vs Storage Object Admin

| Rôle | Permissions accordées |
|---|---|
| **Storage Admin** | Tout : objets ET buckets (création, suppression, modification config bucket). |
| **Storage Object Admin** *(retenu)* | Lire, écrire, lister, supprimer les **objets**. Pas de droit sur le bucket lui-même. |
| Storage Object Creator | Écrire seulement. Pas de lecture, pas de suppression. |
| Storage Object Viewer | Lecture seule. |

---

## 8. Téléchargement et sécurisation de la clé JSON

### Marche à suivre

1. **IAM et administration → Comptes de service → cliquer sur l'email du SA**.
2. Onglet **Clés → Ajouter une clé → Créer une clé**.
3. Choisir le format **JSON → Créer**. Le fichier est téléchargé automatiquement.

### Stockage local

> ⚠️ **La clé JSON ne doit JAMAIS être commitée sur Git.** Elle est déplacée dans un dossier conventionnel hors du repo :
> ```
> C:\Users\faris\.gcp\validatrade-ingestor-key.json
> ```

Le dossier `.gcp` est déjà inscrit dans le `.gitignore` du projet (via les motifs `*-key.json` et `.gcp/`), ce qui empêche tout commit accidentel même si le fichier était copié à la racine du repo.

### Que faire si la clé fuit

Si une clé JSON est compromise (publiée sur GitHub, partagée par erreur, etc.) :

1. Aller dans **IAM → Comptes de service → cliquer sur le SA → onglet Clés**.
2. **Supprimer la clé compromise IMMÉDIATEMENT.**
3. Générer une nouvelle clé et mettre à jour le chemin local.
4. Surveiller les logs **Cloud Audit** pour détecter d'éventuelles utilisations abusives.

> 💡 **Note :** La suppression Git ne suffit pas. Si la clé a été poussée même une seconde sur GitHub, elle est déjà indexée par les bots qui scannent les repos publics. **La révocation côté GCP est la seule mesure efficace.**

---

## 9. Récapitulatif des décisions

| Élément | Valeur retenue | Justification synthétique |
|---|---|---|
| **Cloud provider** | GCP | Free tier généreux (BigQuery 1 To/mois, GCS 5 Go/mois en US). |
| **Projet** | `validatrade-ingestor` | Nom unique, court, parlant. |
| **Compte de facturation** | Activé post free trial | Nécessaire pour créer toute ressource. Always Free reste accessible. |
| **Alerte budget** | 5 EUR/mois — 50/90/100 % | Réflexe FinOps : observer les coûts avant de déployer. |
| **Bucket** | `validatrade-raw` | Standard, région `us-central1`, accès public bloqué, pas de versioning. |
| **Service account** | `validatrade-ingestor@validatrade-ingestor.iam.gserviceaccount.com` | Compte technique dédié au pipeline. |
| **Rôle IAM** | `Storage Object Admin` sur le bucket UNIQUEMENT | Principe du moindre privilège : pas de rôle au niveau projet. |
| **Clé JSON** | `C:\Users\faris\.gcp\validatrade-ingestor-key.json` | Hors du repo. `.gitignore` protège contre tout commit accidentel. |

---

## 10. Variables d'environnement utilisées ensuite

Ces deux variables d'environnement seront lues par le code Python du pipeline. Elles sont à définir **avant** de lancer `main_csv.py` ou `main_api.py` :

### Sous Windows (PowerShell)

```powershell
$env:GOOGLE_APPLICATION_CREDENTIALS = "C:\Users\faris\.gcp\validatrade-ingestor-key.json"
$env:VALIDATRADE_GCS_BUCKET = "validatrade-raw"
```

### Sous Windows (CMD)

```cmd
set GOOGLE_APPLICATION_CREDENTIALS=C:\Users\faris\.gcp\validatrade-ingestor-key.json
set VALIDATRADE_GCS_BUCKET=validatrade-raw
```

### Sous Linux / macOS / WSL

```bash
export GOOGLE_APPLICATION_CREDENTIALS="$HOME/.gcp/validatrade-ingestor-key.json"
export VALIDATRADE_GCS_BUCKET="validatrade-raw"
```

> 💡 **Note :** La variable `GOOGLE_APPLICATION_CREDENTIALS` est le **standard Google** : la lib `google-cloud-storage` la lit automatiquement, sans aucune configuration explicite dans le code.

---

## 11. Pitch entretien condensé

> *« J'ai mis en place une intégration GCP propre pour mon pipeline. Le bucket GCS `validatrade-raw` est en single-region `us-central1` pour rester dans le free tier. L'authentification passe par un service account dédié, scopé à ce bucket uniquement avec le rôle `Storage Object Admin` — pas de rôle au niveau projet, principe du moindre privilège. La clé JSON est stockée hors du repo, dans un dossier protégé par `.gitignore`. J'ai mis en place une alerte budget de 5 EUR avec notifications à 50/90/100 % avant tout déploiement, dans une logique FinOps. »*
