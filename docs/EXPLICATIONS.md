# MaintAI Cloud — Explications du projet

Ce document explique chaque partie du projet : **à quoi elle sert**, **comment elle
fonctionne**, **les fichiers concernés** et **pourquoi ce choix**. Il est écrit pour
pouvoir préparer la soutenance.

## 0. Vue d'ensemble

MaintAI Cloud est un logiciel en ligne (SaaS) de maintenance prédictive. Des usines
(les *organisations*) y connectent leurs machines-outils. Chaque machine envoie ses
mesures ; la plateforme estime le risque de panne, ouvre des alertes et explique
chaque décision au technicien.

```
 Machine / simulateur ──POST /api/v1/mesures (clé d'API)──►  API FastAPI ──► PostgreSQL
                                                              │  (mesures)
                                                              ▼
                                                      Redis (file de tâches)
                                                              │
                                                              ▼
                                         Worker Celery : modèle IA → prédictions,
                                         modes de panne, contributions, alertes
                                                              │
 Tableau de bord Streamlit ◄──── API (JWT) ◄──────────────────┘
```

| Service Docker | Rôle |
|---|---|
| `postgres` | base de données (organisations, machines, mesures, prédictions, alertes) |
| `redis` | file d'attente des tâches Celery |
| `migrate` | applique les migrations Alembic puis s'arrête |
| `api` | API REST FastAPI (documentation interactive : http://localhost:8000/docs) |
| `worker` | worker Celery : calcule le risque et gère les alertes |
| `trainer` | (à la demande) entraîne le modèle commun : `docker compose run --rm trainer` |

**Pourquoi un worker séparé ?** Calculer le risque prend du temps (modèle + explications).
L'API répond tout de suite à la machine (« mesures reçues ») et le calcul se fait en
arrière-plan. Si beaucoup de machines envoient en même temps, on peut lancer plusieurs
workers.

---

## 1. Intelligence artificielle

### 1.1 À quoi ça sert
Pour chaque mesure, le modèle calcule :
1. la **probabilité de panne** (`Machine failure`) ;
2. la **décision** : alerte ou non, avec un seuil qui minimise le coût ;
3. le **mode de panne probable** (TWF, HDF, PWF, OSF) ;
4. les **contributions** : quelles mesures ont fait monter le risque.

### 1.2 Les données (AI4I 2020)
- Fichier `data/ai4i2020.csv` (UCI, DOI 10.24432/C5HS5C, licence CC BY 4.0). Il n'est
  pas dans Git (`.gitignore`) : chaque membre le télécharge.
- Mesuré sur le fichier : 10 000 lignes, **339 pannes (3,39 %)**, modes TWF 46,
  HDF 115, PWF 95, OSF 98, RNF 19.

**Écart avec la page UCI** (affiché par `ml/train.py`) : le sujet indique que la page
UCI annonce 120 TWF et 5 RNF, alors que le fichier en contient 46 et 19. Ce qu'on
constate dans le fichier :
- les 46 TWF sont toutes marquées `Machine failure = 1` ;
- **18 des 19 RNF ont `Machine failure = 0`** : le mode est noté mais la machine
  n'est pas déclarée en panne ;
- 9 pannes n'ont aucun mode renseigné ;
- 24 lignes ont plusieurs modes à la fois.

Explication probable (**à vérifier sur la page UCI avant la soutenance**, nous n'avons
pas pu la consulter) : le « 120 » TWF compterait les moments où l'outil arrive en fin
de vie (remplacé ou cassé), et non les pannes ; seule une partie de ces événements
sont des pannes, d'où 46. Pour RNF, le fichier publié marque 19 lignes mais n'en
compte qu'une seule comme panne : les étiquettes du fichier ne sont donc pas
parfaitement cohérentes avec la description. **Conséquence pour nous** : on prend la
colonne `Machine failure` comme vérité pour le risque, et on garde les modes tels
qu'ils sont dans le fichier.

### 1.3 Comment ça fonctionne

**Variables d'entrée.** Les 5 mesures envoyées par la machine (températures air et
process, vitesse, couple, usure) + 3 variables physiques calculées :
- écart de température (process − air) → pannes de dissipation de chaleur (HDF) ;
- puissance = couple × vitesse angulaire → pannes de puissance (PWF) ;
- usure × couple → pannes de surcharge (OSF).

Ce calcul est **dans le pipeline scikit-learn** : l'entraînement et le worker
utilisent exactement le même code. La colonne `Type` (L/M/H) n'est pas utilisée car
les machines ne l'envoient pas.

**Modèle de risque.** On compare 3 modèles en validation croisée (5 blocs) sur 80 %
des données, puis on teste une seule fois sur les 20 % restants jamais vus.

| Modèle | PR-AUC (validation) | Coût (validation) |
|---|---|---|
| Régression logistique | 0,447 | 3 033 |
| **Random Forest (retenu)** | **0,869** | **1 378** |
| Gradient Boosting | 0,872 | 1 473 |

Test sur 20 % jamais vus : **PR-AUC 0,857** (le hasard ferait 0,034), **64 pannes
détectées sur 68**, 159 fausses alertes, coût 359 (contre 3 400 si on n'alerte jamais).

**Classes déséquilibrées.** `class_weight="balanced"` : pendant l'apprentissage, une
panne compte environ 30 fois plus qu'une ligne normale. On n'a **pas** créé de fausses
pannes (pas de SMOTE) : on ne fabrique pas de données.

**Pourquoi la PR-AUC et pas l'exactitude ?** Un modèle qui dit toujours « pas de
panne » a 96,6 % d'exactitude et ne sert à rien. La PR-AUC mesure si le modèle met les
vraies pannes en haut de la liste.

**Seuil de décision par le coût.** Coût = 50 × (pannes manquées) + 1 × (fausses
alertes). On teste tous les seuils possibles et on garde le moins cher. Le calcul est
fait sur des **probabilités hors-échantillon** : chaque ligne est notée par un modèle
qui ne l'a jamais vue (validation croisée). Sinon le modèle « connaît les réponses »,
ses probabilités sont trop sûres d'elles et le seuil serait faux.
Seuil obtenu : **0,022** (rappel 93 %). Il est bas parce qu'une panne manquée coûte
50 fois plus qu'une fausse alerte.

Ces probabilités hors-échantillon sont **sauvegardées avec le modèle** : si une usine
change son ratio de coût, on recalcule le seuil instantanément, sans réentraîner.

| Ratio | 10 | 20 | 50 | 100 |
|---|---|---|---|---|
| Seuil | 0,227 | 0,122 | 0,022 | 0,005 |
| Rappel | 85 % | 87 % | 93 % | 97 % |

**Modes de panne (multi-étiquette).** Un classifieur oui/non par mode, car une panne
peut avoir plusieurs modes. Un mode est gardé s'il est prévisible (PR-AUC > 5 × le
hasard) : PWF 1,00 ; HDF 0,99 ; OSF 0,89 ; TWF 0,10 (faible : la casse d'outil est en
partie aléatoire) ; **RNF exclu** (0,004, niveau du hasard : ce sont des pannes
aléatoires). Sur les vraies pannes du test, le mode le plus probable est le bon
**98 % du temps**. Le seuil de chaque mode maximise le F1 (le sujet ne donne pas de
coût pour un mauvais diagnostic).

**Contributions (explications).** Valeurs de Shapley exactes : on part d'une machine
« normale » (médiane des cycles sans panne) et on regarde de combien chaque mesure
réelle fait monter le risque, en moyenne sur tous les ordres possibles. Avec 5
mesures il n'y a que 32 combinaisons, donc le calcul est **exact** et ne demande pas
de librairie en plus. Propriété vérifiée : risque de référence + somme des
contributions = risque affiché. Exemple réel : « Couple 4.6 N·m (normal 39.9) :
+71 pts ; Vitesse 2861 tr/min (normal 1507) : +27 pts » pour une panne de puissance.

**Versions.** Chaque entraînement crée `models/risk_model_vN.joblib` (jamais écrasé)
et un rapport lisible `risk_model_vN.json`. Chaque prédiction en base garde le nom de
la version qui l'a produite. L'entraînement se fait **dans l'image Docker** pour avoir
exactement les mêmes versions de librairies que le worker (scikit-learn figé à 1.9.1).

### 1.4 Fichiers
| Fichier | Rôle |
|---|---|
| `ml/train.py` | script d'entraînement et rapport (données, comparaison, test, modes, contributions) |
| `app/ml/features.py` | les 5 mesures + 3 variables physiques |
| `app/ml/cost.py` | coût, seuil optimal, seuil F1 des modes |
| `app/ml/explain.py` | contributions (Shapley exact) et phrase pour le technicien |
| `app/ml/registry.py` | sauvegarde / chargement des versions |
| `app/ml/predictor.py` | utilisation du modèle par le worker |
| `models/` | modèles versionnés + rapports JSON |

### 1.5 Limites honnêtes
- Les chiffres du test reposent sur 68 pannes : un écart de quelques points n'est pas
  significatif.
- TWF est mal prévu ; RNF n'est pas prévisible du tout (c'est voulu par le jeu de données).
- Les contributions expliquent **le modèle**, pas la physique : sur une ligne isolée,
  la mesure mise en avant peut surprendre.

---

## 2. Réception des mesures (validation, déduplication, quarantaine)

### 2.1 À quoi ça sert
Les machines envoient leurs mesures par lots : `POST /api/v1/mesures` avec leur clé
d'API dans l'en-tête `x-api-key`. Le sujet demande de **valider** chaque mesure,
d'**ignorer les doublons** (même `message_id`) et de **rejeter avec une raison** les
valeurs physiquement impossibles.

### 2.2 Format d'un lot
```json
[
  {"message_id": "cnc1-000123", "timestamp": "2026-11-07T10:15:00Z",
   "air_temp": 298.1, "process_temp": 308.6, "rotational_speed": 1551,
   "torque": 42.8, "tool_wear": 0,
   "label": {"failure": false, "modes": []}}
]
```
- `message_id` (obligatoire) : identifiant unique donné par la machine.
- `timestamp` (optionnel) : heure de la mesure ; sinon l'heure de réception.
- `label` (optionnel) : **retour terrain** (la machine est-elle vraiment tombée en panne,
  et de quel mode ?). Il ne sert pas à la prédiction, seulement au réentraînement Pro.

### 2.3 Comment ça fonctionne
1. **Validation**, mesure par mesure (`app/services/validation.py`) :
   - format : champs présents, nombres, pas de NaN ni d'infini, date valide ;
   - **bornes physiques** : air 200–400 K, process 200–500 K, vitesse 0–10 000 tr/min,
     couple 0–500 N·m, usure 0–1 000 min.
2. Une mesure invalide va en **quarantaine** (table `quarantined_measures`) avec la
   mesure telle que reçue et la liste des raisons en français. Le reste du lot est
   quand même accepté. Consultation : `GET /api/v1/quarantaine`.
3. **Déduplication** : contrainte unique `(machine_id, message_id)` en base et
   insertion `ON CONFLICT DO NOTHING`. Si une machine renvoie un lot (coupure réseau,
   nouvel essai), les mesures déjà reçues sont ignorées et signalées dans `duplicates`.
4. L'API enregistre les mesures acceptées, puis confie au worker le calcul du risque
   (il reçoit seulement les identifiants des mesures, dans l'ordre d'arrivée).

Réponse (code **202 Accepted** = « reçu, traitement en cours ») :
```json
{"accepted": 1, "duplicates": ["cnc1-000122"],
 "rejected": [{"index": 2, "message_id": "cnc1-000124",
               "reasons": ["torque = -3 N·m : physiquement impossible (plage acceptée [0 ; 500] N·m)"]}]}
```

### 2.4 Pourquoi ces choix
- **Bornes larges** : on ne rejette que l'**impossible**. Une valeur **inhabituelle**
  (couple de 95 N·m) est acceptée : c'est justement au modèle de la juger dangereuse.
  Des bornes trop serrées feraient disparaître les mesures les plus intéressantes.
- **Quarantaine plutôt que suppression** : on garde la preuve de ce qui a été reçu et
  pourquoi c'est refusé ; le client peut corriger son capteur.
- **Doublons gérés par la base** (contrainte unique) et pas seulement par le code :
  même si deux lots identiques arrivent en même temps, la base n'en garde qu'un.
- **Mesures enregistrées par l'API** (et non plus par le worker) : une mesure reçue
  est en base même si le worker est arrêté ; elle sera traitée à son redémarrage.
- **Le même `message_id` sur deux machines différentes** est accepté : l'unicité est
  par machine.

### 2.5 Fichiers
| Fichier | Rôle |
|---|---|
| `app/services/validation.py` | format + bornes physiques, raisons en français |
| `app/api/v1/telemetry.py` | `POST /mesures`, `GET /quarantaine` |
| `app/api/v1/machines.py` | `GET /machines/{id}/mesures` : mesures + risque + explication |
| `migrations/versions/0003_…` | colonnes `message_id`, `label_*`, table de quarantaine |
| `tests/test_validation.py`, `tests/test_mesures.py` | 17 tests |

---

## 3. Alertes

### 3.1 Hystérésis : à quoi ça sert
Sans hystérésis, une alerte s'ouvrirait à chaque mesure à risque et se fermerait à la
mesure suivante : le technicien recevrait des dizaines d'alertes pour un seul problème.
Le sujet demande : **ouverture après K mesures au-dessus du seuil, fermeture sous un
seuil plus bas, une seule alerte ouverte par machine**.

### 3.2 Comment ça fonctionne
- **Seuil haut** = le seuil de coût du modèle (calculé pour le ratio de coût de l'usine).
- **Seuil bas** = `alert_close_factor` × seuil haut (0,5 par défaut).
- Deux compteurs par machine (`consecutive_high`, `consecutive_low`), gardés **en base**
  sur la machine : ils continuent d'un lot à l'autre et survivent à un redémarrage.

| Risque de la mesure | Effet |
|---|---|
| ≥ seuil haut | compteur haut + 1, compteur bas remis à 0 |
| < seuil bas | compteur bas + 1, compteur haut remis à 0 |
| entre les deux (zone morte) | les deux compteurs repartent à 0 |

- Pas d'alerte active et compteur haut ≥ K (`alert_open_k`, 3 par défaut) → **ouverture**.
- Alerte active et compteur bas ≥ K' (`alert_close_k`, 3 par défaut) → **fermeture**.
- Pendant l'alerte, on garde le **diagnostic du moment le plus grave** (risque maximal,
  mode probable, explication).

**Une seule alerte active par machine** est garantie par la base elle-même : un index
unique partiel `uq_alerts_one_active_per_machine` sur les alertes non fermées. Même si
deux workers se trompaient, la base refuserait la deuxième alerte. En plus, le worker
**verrouille la ligne de la machine** (`SELECT … FOR UPDATE`) pendant le traitement
d'un lot : deux lots de la même machine passent l'un après l'autre.

**Choix à justifier** : le sujet dit « fermeture sous un seuil plus bas ». Nous fermons
après K' mesures basses d'affilée (et pas une seule), pour qu'une mesure isolée ne
ferme pas une vraie alerte. Mettre `alert_close_k = 1` suit le sujet à la lettre.

**Test de bout en bout réalisé** (7 lots de vraies lignes AI4I, K = 3) : 2 hautes → rien ;
3ᵉ haute (dans un autre lot) → ouverture ; encore des hautes → toujours une seule
alerte ; 3 basses → fermeture ; « H L H H » → rien (le L remet à 0) ; 3ᵉ haute →
nouvelle alerte.

### 3.3 Fichiers
| Fichier | Rôle |
|---|---|
| `app/services/hysteresis.py` | la règle, écrite comme une fonction pure (facile à tester) |
| `app/worker/tasks.py` | applique la règle mesure par mesure, crée / met à jour / ferme l'alerte |
| `tests/test_hysteresis.py` | 12 tests de la règle |

---

## Annexe A. Base de données et migrations (Alembic)

**À quoi ça sert.** Au début, les tables étaient créées par `Base.metadata.create_all`,
qui sait créer une table mais **ne modifie jamais une table existante**. Dès qu'on
ajoute une colonne, les bases déjà créées (la tienne, celles de l'équipe) seraient
cassées. Alembic enregistre chaque modification du schéma dans un fichier numéroté
(une *migration*) et sait mettre n'importe quelle base à jour.

**Comment ça fonctionne.**
- `migrations/versions/0001_schema_initial.py` : le schéma de départ (vérifié identique
  à la base existante avec `alembic check`).
- Chaque étape suivante ajoute une migration (`0002_…`, `0003_…`).
- Le service Docker `migrate` lance `python -m app.db.migrate` à chaque `docker compose up`,
  **avant** l'API et le worker (`depends_on: service_completed_successfully`).
- Une base créée avant Alembic est reconnue (tables présentes mais pas de table
  `alembic_version`) : elle est marquée en version 0001 puis mise à jour.
- Ajouter une migration après avoir modifié `app/models/models.py` :
  `alembic revision --autogenerate -m "description"`, puis relire le fichier généré.

**Pourquoi.** C'est l'outil standard avec SQLAlchemy, et chaque changement de schéma
devient traçable dans Git.

## Annexe B. Vérification avant chaque commit

`bash scripts/verifier.sh` :
1. `docker compose up -d --build` (toute la plateforme) ;
2. lance les tests dans l'image Docker (`docker compose --profile tools run --rm --build tests`),
   sur une base séparée `maintai_test` pour ne jamais toucher aux vraies données ;
3. vérifie que `migrate` s'est terminé sans erreur et que `api`, `worker`, `postgres`,
   `redis` tournent ;
4. vérifie que l'API répond.
