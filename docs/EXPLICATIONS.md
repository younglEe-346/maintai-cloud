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
| `mailpit` | faux serveur mail de développement (e-mails visibles sur http://localhost:8025) |
| `worker` | worker Celery : calcule le risque, gère les alertes, réentraîne les modèles Pro |
| `dashboard` | tableau de bord Streamlit : http://localhost:8501 |
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

- Pas d'alerte active et compteur haut ≥ K (`alert_open_k`, **1 par défaut**, voir 3.3) → **ouverture**.
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

**Test de bout en bout réalisé** (7 lots de vraies lignes AI4I, avec K = 3) : 2 hautes → rien ;
3ᵉ haute (dans un autre lot) → ouverture ; encore des hautes → toujours une seule
alerte ; 3 basses → fermeture ; « H L H H » → rien (le L remet à 0) ; 3ᵉ haute →
nouvelle alerte.

### 3.3 Pourquoi K = 1 par défaut (et pas 3)
Nous avons rejoué AI4I dans l'ordre du fichier avec les **vraies prédictions
hors-échantillon** du modèle, puis compté les pannes qui arrivent pendant qu'une alerte
est active :

| K (ouverture) | Alertes ouvertes | Pannes couvertes par une alerte |
|---|---|---|
| **1** | 434 | **327 / 339 (96 %)** |
| 2 | 128 | 150 / 339 (44 %) |
| 3 | 67 | 85 / 339 (25 %) |

Raison : AI4I contient des **cycles d'usinage indépendants**, pas une série temporelle
d'une même machine. Une panne est presque toujours **une seule** mesure à risque,
entourée de mesures normales. Exiger 3 mesures hautes d'affilée ferait rater 3 pannes
sur 4. Avec K = 1, l'hystérésis reste utile : une seule alerte par machine, fermeture
après 3 mesures basses, et 434 alertes au lieu de 1 097 (une par mesure à risque).
Sur de vraies machines, où une dégradation dure plusieurs mesures, une usine peut
monter K à 2 ou 3 : c'est un réglage par usine.

### 3.4 Acquittement
**À quoi ça sert.** Le technicien indique « j'ai vu l'alerte, je m'en occupe », avec son
nom et un commentaire. Les collègues savent que l'alerte est prise en charge.

**Comment ça fonctionne.** `POST /api/v1/alerts/{id}/acknowledge` avec
`{"name": "Miloud", "comment": "outil changé"}` :
- l'alerte passe de `OPEN` à `ACKNOWLEDGED` (« acquittée ») ; on enregistre le nom, le
  commentaire et l'heure ;
- une alerte acquittée **reste active** : le risque est toujours là. Elle ne crée pas
  de deuxième alerte et **se ferme seule** quand le risque redescend (hystérésis) ;
- acquitter une alerte déjà acquittée ou fermée → erreur **409** (conflit) ;
- l'alerte d'une autre usine → **404** (on ne révèle pas qu'elle existe).

`GET /api/v1/alerts?status=active` liste les alertes ouvertes ou acquittées ;
`status=OPEN|ACKNOWLEDGED|CLOSED` filtre un statut précis.

**Pourquoi acquitter ne ferme pas l'alerte ?** Fermer, c'est dire « le risque a
disparu » : seul le modèle peut le constater avec les nouvelles mesures. Acquitter,
c'est dire « un humain s'en occupe ». Mélanger les deux ferait disparaître des alertes
alors que la machine est toujours en danger.

### 3.5 Fichiers
| Fichier | Rôle |
|---|---|
| `app/services/hysteresis.py` | la règle, écrite comme une fonction pure (facile à tester) |
| `app/worker/tasks.py` | applique la règle mesure par mesure, crée / met à jour / ferme l'alerte |
| `app/api/v1/alerts.py` | liste, détail, acquittement |
| `migrations/versions/0004_…` | colonnes d'acquittement, K = 1 par défaut |
| `tests/test_hysteresis.py`, `tests/test_alertes.py` | 16 tests (règle + bout en bout par l'API) |

---

## 4. Utilisateurs, rôles et invitations

### 4.1 À quoi ça sert
Le sujet distingue plusieurs personnes dans une usine : le **responsable maintenance**
(configure machines, coûts, seuils) et le **technicien** (consulte le risque, acquitte
les alertes). Il demande des **rôles** (propriétaire, administrateur, membre) et
l'**invitation de collègues par e-mail**.

Avant, le compte *était* l'usine (e-mail et mot de passe sur l'organisation) : une seule
personne par usine. Maintenant il y a une table `users` : chaque personne a son compte,
appartient à une usine et a un rôle.

### 4.2 Qui peut faire quoi

| Action | Propriétaire | Administrateur | Membre (technicien) |
|---|---|---|---|
| Consulter machines, mesures, alertes, quarantaine | ✅ | ✅ | ✅ |
| Acquitter une alerte | ✅ | ✅ | ✅ |
| Déclarer une machine, gérer ses clés | ✅ | ✅ | ❌ |
| Inviter un membre | ✅ | ✅ | ❌ |
| Inviter un administrateur | ✅ | ❌ | ❌ |
| Retirer un membre | ✅ | ✅ | ❌ |
| Retirer un administrateur, changer un rôle | ✅ | ❌ | ❌ |
| Changer de plan d'abonnement | ✅ | ❌ | ❌ |

(Le propriétaire = la personne qui a inscrit l'usine. Son rôle ne peut pas être changé
ni retiré : une usine a toujours un propriétaire.)

### 4.3 Comment ça fonctionne
- **Inscription** `POST /auth/register` : crée l'usine (plan Gratuit) + son propriétaire.
- **Connexion** `POST /auth/login` : renvoie un **jeton JWT** signé qui contient
  l'identifiant de l'utilisateur. Chaque requête l'envoie dans
  `Authorization: Bearer …`. Le serveur vérifie la signature et retrouve l'utilisateur.
- **Contrôle des droits** dans `app/core/deps.py` : chaque route déclare ce qu'elle
  exige, par exemple `Depends(require_roles("owner", "admin"))`. Un rôle insuffisant
  → **403**. Pas de jeton ou jeton invalide → **401**.
- **Isolation des usines** : toutes les requêtes filtrent sur l'usine de l'utilisateur
  connecté. Une ressource d'une autre usine répond **404** (on ne révèle même pas
  qu'elle existe).
- **Mots de passe** hachés avec **bcrypt** (lent exprès : difficile à casser), 8
  caractères minimum.

**Invitation, étape par étape :**
1. `POST /org/invitations {"email", "role"}` : on crée un **jeton aléatoire** de 256 bits.
   En base on ne stocke que son **empreinte SHA-256** : quelqu'un qui lirait la base ne
   pourrait pas utiliser les invitations.
2. Un e-mail part avec le lien `http://localhost:8501/?invitation=<jeton>` (valable 7 jours).
   En développement, **Mailpit** reçoit l'e-mail : on le lit sur http://localhost:8025.
3. Le collègue ouvre le lien ; `GET /auth/invitations/{jeton}` affiche l'usine et le rôle.
4. `POST /auth/accept-invitation {"token", "full_name", "password"}` crée son compte.
   Le lien ne sert qu'**une fois** (409 ensuite), expire (410) et peut être annulé (404).

**Retirer un membre** : son compte est **désactivé** (pas supprimé), pour garder
l'historique (par exemple « alerte acquittée par Miloud »). Son jeton ne marche plus (401).

**Acquittement** : le nom enregistré vient maintenant **du compte connecté**, pas d'un
champ tapé à la main : on ne peut pas acquitter au nom de quelqu'un d'autre.

### 4.4 Pourquoi ces choix
- **JWT** : l'API n'a pas besoin de garder les sessions en mémoire ; plusieurs
  instances de l'API peuvent vérifier le même jeton.
- **SHA-256 pour le jeton d'invitation, bcrypt pour le mot de passe** : un mot de passe
  humain est court et devinable, il faut un hachage lent (bcrypt). Un jeton aléatoire
  de 256 bits est impossible à deviner : un hachage rapide suffit et permet de le
  retrouver directement en base.
- **Mailpit** : de vrais e-mails SMTP, visibles dans un navigateur, sans risque d'en
  envoyer à de vraies personnes. En production, il suffit de changer `SMTP_HOST`.
- **Migration sans perte** (0005) : chaque usine existante garde son compte, transformé
  en utilisateur propriétaire.

### 4.5 Fichiers
| Fichier | Rôle |
|---|---|
| `app/core/deps.py` | utilisateur connecté, usine, contrôle des rôles |
| `app/api/v1/auth.py` | inscription, connexion, `/me`, acceptation d'invitation |
| `app/api/v1/organization.py` | membres, rôles, invitations |
| `app/services/email.py` | envoi SMTP (Mailpit en développement) |
| `migrations/versions/0005_…` | tables `users` et `invitations`, reprise des comptes existants |
| `tests/test_roles.py` | 12 tests (droits, invitation, expiration, isolation) |

---

## 5. Plans d'abonnement et limites

### 5.1 À quoi ça sert
Le produit est vendu par abonnement. Le sujet fixe deux plans :

| Plan | Machines | Mesures par jour | Modèle | Export |
|---|---|---|---|---|
| Gratuit (`FREE`) | 2 | 10 000 | commun | ❌ |
| Pro (`PRO`) | 50 | 1 000 000 | réentraîné sur les données de l'usine | ✅ |

### 5.2 Comment ça fonctionne
- Les limites sont écrites **à un seul endroit** : `app/core/plans.py`.
- **Machines** : à la création, on compte les machines actives. Au-delà de la limite →
  **402** (« paiement requis ») avec un message clair. Archiver une machine
  (`DELETE /machines/{id}`) libère une place : elle n'envoie plus de mesures (401) mais
  son historique est gardé.
- **Mesures par jour** : un compteur **Redis** par usine et par jour UTC
  (`usage:measures:<usine>:<date>`).
  1. Avant d'enregistrer un lot, on **réserve** ses mesures valides (`INCRBY`).
  2. Si on dépasse la limite, on annule la réservation et on refuse **tout le lot** :
     **429** (« trop de requêtes ») avec l'en-tête `Retry-After` (secondes jusqu'à minuit UTC).
  3. Après l'enregistrement, on **rend** les doublons : ils ne consomment pas de quota.
  La clé expire seule après 2 jours.
- **Changer de plan** : `PUT /org/plan {"plan": "PRO"}`, réservé au **propriétaire**.
  Le paiement est **simulé** (pas de vrai paiement dans ce projet). Repasser en Gratuit
  est refusé (409) s'il y a plus de 2 machines actives.
- **Voir sa consommation** : `GET /org` renvoie le plan, les limites, le nombre de
  machines et de mesures du jour ; chaque réponse de `POST /mesures` contient aussi le quota.

### 5.3 Pourquoi ces choix
- **Redis pour le compteur** : `INCRBY` est **atomique**. Si deux lots arrivent en même
  temps, le compteur reste juste, sans verrou. Compter les lignes en base à chaque lot
  deviendrait lent à 1 million de mesures par jour.
- **Refuser tout le lot** plutôt qu'en accepter une partie : la machine sait qu'elle
  doit renvoyer le lot entier plus tard ; pas de lot « à moitié » à reconstituer.
- **402 pour les machines, 429 pour les mesures** : 402 dit « il faut un plan
  supérieur », 429 dit « trop pour aujourd'hui, réessayez plus tard ».

### 5.4 Fichiers
| Fichier | Rôle |
|---|---|
| `app/core/plans.py` | les deux plans et leurs limites |
| `app/services/usage.py` | compteur Redis du jour |
| `app/api/v1/telemetry.py` | contrôle du quota à la réception |
| `app/api/v1/machines.py` | limite de machines, archivage |
| `app/api/v1/organization.py` | `GET /org`, `PUT /org/plan` |
| `migrations/versions/0006_…` | anciennes valeurs de plan → `FREE` |
| `tests/test_plans.py` | 8 tests |

---

## 6. Clés d'API des machines (hachées, montrées une fois, révocables)

### 6.1 À quoi ça sert
Une machine n'a pas d'utilisateur ni de mot de passe : elle s'authentifie avec une
**clé d'API** envoyée dans l'en-tête `x-api-key`. Le sujet demande une clé par machine,
**affichée une seule fois** et **révocable**.

### 6.2 Comment ça fonctionne
- **Création** (`POST /machines`) : on génère une clé aléatoire de 192 bits
  (`maint_…`). La réponse la contient **une seule fois**, avec l'avertissement
  « Copiez cette clé maintenant ». En base, on ne garde que :
  - son **empreinte SHA-256** (`api_key_hash`) ;
  - ses 12 premiers caractères (`api_key_prefix`), pour reconnaître la clé dans la liste.
- **Réception des mesures** : on calcule l'empreinte de la clé reçue et on cherche la
  machine qui a cette empreinte. Clé inconnue, révoquée ou machine archivée → **401**.
- **Révoquer** (`POST /machines/{id}/api-key/revoke`) : par exemple si le boîtier de la
  machine est volé. Les mesures envoyées avec cette clé sont refusées.
- **Remplacer** (`POST /machines/{id}/api-key/rotate`) : nouvelle clé montrée une fois,
  l'ancienne cesse immédiatement de fonctionner.
- Seuls le propriétaire et l'administrateur gèrent les clés (le technicien : 403).

### 6.3 Pourquoi ces choix
- **Ne jamais stocker la clé en clair** : si la base fuit (sauvegarde perdue, injection
  SQL…), l'attaquant ne peut pas se faire passer pour les machines. C'est le même
  principe que pour les mots de passe.
- **SHA-256 et pas bcrypt** : bcrypt est lent exprès, utile pour des mots de passe
  humains faciles à deviner. Une clé aléatoire de 192 bits est impossible à deviner :
  SHA-256 suffit, et comme il donne toujours la même empreinte pour la même clé, on
  retrouve la machine **directement par index** (bcrypt obligerait à tester chaque machine).
- **Montrée une fois** : c'est la conséquence logique : on ne peut pas réafficher une
  clé qu'on ne connaît plus. On en génère une nouvelle si elle est perdue.
- **Migration 0007** : les clés existantes sont hachées **dans PostgreSQL**
  (`sha256()`), puis la colonne en clair est supprimée. Nous avons vérifié que
  PostgreSQL et Python donnent la même empreinte, et qu'une machine existante continue
  d'envoyer ses mesures après la migration. Cette migration est **irréversible** :
  on ne peut pas retrouver une clé à partir de son empreinte.

### 6.4 Fichiers
| Fichier | Rôle |
|---|---|
| `app/api/v1/machines.py` | création, liste, révocation, remplacement |
| `app/api/v1/telemetry.py` | authentification de la machine par empreinte |
| `app/core/security.py` | `hash_token` (SHA-256) |
| `migrations/versions/0007_…` | hachage des clés existantes |
| `tests/test_cles_api.py` | 7 tests |

---

## 7. Coûts et seuils réglables

### 7.1 À quoi ça sert
Le sujet : « le coût d'une panne manquée change le seuil optimal recalculé ». Une usine
où une panne coûte très cher (chaîne entière arrêtée) préfère beaucoup de fausses
alertes ; une petite usine préfère être dérangée moins souvent. Chaque usine règle :

| Réglage | Défaut | Sens |
|---|---|---|
| `cost_ratio` | 50 | une panne manquée coûte N fois une fausse alerte |
| `alert_open_k` | 1 | mesures hautes d'affilée pour ouvrir une alerte |
| `alert_close_k` | 3 | mesures basses d'affilée pour fermer |
| `alert_close_factor` | 0,5 | seuil bas = facteur × seuil haut |

### 7.2 Comment ça fonctionne
- `GET /org/settings` : les réglages, le **seuil haut** et le **seuil bas** calculés, et
  ce que ce seuil aurait donné sur les 10 000 probabilités hors-échantillon du modèle
  (pannes détectées, pannes manquées, fausses alertes).
- `PUT /org/settings` (propriétaire, administrateur) : enregistre et renvoie le
  **nouveau seuil, recalculé immédiatement**.
- `GET /org/settings/preview?cost_ratio=10` : aperçu sans enregistrer (pour un curseur
  dans le tableau de bord).
- Le recalcul ne réentraîne **rien** : le modèle est sauvegardé avec ses probabilités
  hors-échantillon (partie 1), on cherche simplement le seuil le moins cher pour le
  nouveau ratio. Le résultat est mis en cache.
- Le worker applique le seuil de l'usine à chaque lot, avec le modèle choisi par
  `app/ml/selection.py`.

| Ratio | 1 | 10 | 50 | 100 | 1 000 |
|---|---|---|---|---|---|
| Seuil | 0,375 | 0,227 | 0,022 | 0,005 | 0,002 |
| Pannes détectées | 82 % | 85 % | 93 % | 97 % | 98 % |
| Fausses alertes (sur 10 000) | 35 | 74 | 783 | 1 735 | 2 681 |

### 7.3 Pourquoi ces choix
- **Valeurs contrôlées** (422 sinon) : ratio > 0, K ≥ 1, facteur strictement entre 0 et 1
  (sinon le seuil bas dépasserait le seuil haut et l'hystérésis n'aurait plus de sens).
- **Cas limite trouvé et corrigé pendant les tests** : avec un ratio énorme (≥ 5 000),
  le seuil optimal devient 0 (« alerter sur tout »). La règle d'hystérésis refusait un
  seuil nul et le worker aurait planté. Elle accepte maintenant ce cas (l'alerte
  s'ouvre et ne se ferme jamais, ce qui est logique). Un test le vérifie.

### 7.4 Fichiers
| Fichier | Rôle |
|---|---|
| `app/api/v1/organization.py` | `GET/PUT /org/settings`, `/org/settings/preview` |
| `app/ml/predictor.py` | `threshold_info` : seuil + effets attendus, mis en cache |
| `app/ml/selection.py` | quel modèle utilise l'usine |
| `tests/test_reglages.py` | 11 tests |

---

## 8. Réentraînement du modèle de l'usine (plan Pro)

### 8.1 À quoi ça sert
Le modèle commun a appris sur AI4I. Les machines d'une usine peuvent se comporter
autrement. Le plan Pro permet de **réentraîner un modèle sur les données de l'usine**.
Le sujet : « tâche longue ; nouveau modèle candidat, promu s'il est meilleur ».

### 8.2 D'où viennent les étiquettes ?
Une mesure seule ne dit pas si la machine est tombée en panne. Les machines (ou la GMAO
de l'usine) peuvent envoyer avec leurs mesures un **retour terrain** optionnel :
`"label": {"failure": true, "modes": ["PWF"]}` (partie 2). Seules ces mesures
étiquetées servent au réentraînement. Le simulateur envoie les vraies étiquettes d'AI4I.

### 8.3 Comment ça fonctionne
1. `POST /org/models/retrain` (propriétaire ou administrateur, plan Pro sinon **402**) :
   crée une ligne `org_models` au statut `training` et lance une **tâche Celery**.
   L'API répond tout de suite (**202**) ; un deuxième réentraînement en même temps → 409.
2. Le worker (`app/ml/retraining.py`) :
   - récupère les mesures étiquetées de l'usine ; il en faut **au moins 500 dont 10
     pannes**, sinon statut `failed` avec un message qui explique quoi envoyer ;
   - met **25 % de côté** (jamais vus) et entraîne un **candidat** sur les 75 % restants,
     avec exactement la même méthode que le modèle commun (`app/ml/training.py`) ;
   - compare le candidat et le **modèle actuel** sur ces 25 %, avec le **ratio de coût
     de l'usine** ;
   - si le candidat **coûte moins cher** : il est réentraîné sur 100 % des données,
     sauvegardé dans `org_models/<id de l'usine>/risk_model_vN.joblib` et devient
     `active` (l'ancien passe `retired`) ; sinon il est `rejected`. Le message et toutes
     les métriques sont enregistrés.
3. `GET /org/models` : le modèle utilisé et l'historique des réentraînements.
4. `app/ml/selection.py` choisit le modèle : **Pro avec un modèle actif → le sien**,
   sinon le modèle commun. Le worker l'utilise pour les prédictions (son nom est
   enregistré avec chaque prédiction) et l'API pour calculer les seuils.

### 8.4 Pourquoi ces choix
- **Promu seulement s'il est meilleur, mesuré par le coût** : un réentraînement sur peu
  de données peut donner un modèle pire. On ne remplace jamais un modèle sans preuve.
- **Comparaison sur des données que le candidat n'a pas vues** : sinon le candidat
  gagnerait toujours (il « connaît les réponses »).
- **Tâche Celery** : l'entraînement prend ~30 s (bien plus avec beaucoup de données) ;
  une requête HTTP ne doit pas attendre aussi longtemps.
- **Isolation** : chaque usine a son dossier ; le modèle n'est jamais envoyé par l'API
  ni utilisé pour une autre usine (testé). Le worker écrit dans le volume Docker
  `org_models`, l'API le monte en **lecture seule**.
- **Un seul modèle actif par usine**, garanti par un index unique en base.

### 8.5 Résultat réel et limite honnête
Test de bout en bout sur la vraie plateforme : usine Pro, 1 500 vraies lignes AI4I
étiquetées (42 pannes), réentraînement en 27 s → **candidat rejeté** (coût 59 contre 14
pour le modèle commun).

C'est **attendu avec nos données de démonstration** : le modèle commun a été entraîné
sur tout AI4I, donc il a **déjà vu** ces 375 lignes de comparaison (sa PR-AUC dessus
vaut 1,0). La comparaison l'avantage. Avec de vraies données d'usine, jamais vues par
le modèle commun, la comparaison serait équitable. Le cas « promu » est vérifié par un
test automatique qui simule un modèle actuel mauvais.

### 8.6 Fichiers
| Fichier | Rôle |
|---|---|
| `app/ml/training.py` | méthode d'entraînement commune (modèle commun et modèles d'usine) |
| `app/ml/retraining.py` | données étiquetées, candidat, comparaison, promotion |
| `app/ml/selection.py` | quel modèle pour quelle usine |
| `app/worker/tasks.py` | tâche `retrain_org_model` |
| `app/api/v1/models_api.py` | `GET /org/models`, `POST /org/models/retrain` |
| `migrations/versions/0008_…` | table `org_models` |
| `tests/test_reentrainement.py` | 6 tests |

---

## 9. Export (plan Pro)

### 9.1 À quoi ça sert
Le plan Pro inclut l'**export** : l'usine récupère ses données pour les analyser
ailleurs (Excel, rapport qualité, GMAO).

### 9.2 Comment ça fonctionne
- `GET /api/v1/export/mesures.csv` : chaque mesure avec sa prédiction (risque, décision,
  seuil, version du modèle, mode probable, explication) et son retour terrain.
  Filtres optionnels : `machine_id`, `start`, `end` (dates ISO 8601).
- `GET /api/v1/export/alertes.csv` : toutes les alertes avec leur acquittement.
- Réservé au plan Pro (**402** sinon) et au propriétaire / administrateur (**403** pour
  un technicien).
- Toujours filtré sur l'usine connectée : demander la machine d'une autre usine renvoie
  un fichier vide.

### 9.3 Pourquoi ces choix
- **CSV** : le format que tout le monde sait ouvrir.
- **Séparateur `;` et BOM UTF-8** : Excel en français ouvre le fichier directement, avec
  les accents corrects (avec `,` il mettrait tout dans une seule colonne).
- **Envoi en flux** (`StreamingResponse` + `yield_per(1000)`) : les lignes sont lues et
  envoyées par paquets de 1 000. On peut exporter des centaines de milliers de mesures
  sans remplir la mémoire du serveur.

### 9.4 Fichiers
| Fichier | Rôle |
|---|---|
| `app/api/v1/export.py` | les deux exports CSV |
| `tests/test_export.py` | 6 tests |

---

## 10. Super-administrateur (équipe MaintAI)

### 10.1 À quoi ça sert
Le sujet : « Super-administrateur : équipe MaintAI ; suit les usines et les workers ».
C'est l'exploitant de la plateforme, pas un client.

### 10.2 Comment ça fonctionne
- **Création en ligne de commande, sur le serveur** (aucune route d'inscription) :
  ```
  docker compose exec api python -m app.cli create-superadmin --email admin@maintai.local --name "Équipe MaintAI"
  ```
  (le mot de passe est demandé au clavier). Il se connecte ensuite normalement
  (`POST /auth/login`). Son compte n'appartient à **aucune usine** (`is_superadmin = true`).
- `GET /api/v1/admin/organizations` : pour chaque usine, le plan, le nombre de membres,
  de machines (et la limite), les mesures du jour (et la limite), les alertes actives,
  l'heure de la dernière mesure, le modèle utilisé.
- `PUT /api/v1/admin/organizations/{id}/plan` : change le plan d'une usine (même règle
  que pour le propriétaire).
- `GET /api/v1/admin/workers` : les workers Celery qui répondent (`inspect().ping()`),
  leurs tâches en cours, leur nombre de processus, et le nombre de tâches en attente
  dans la file Redis.

### 10.3 Pourquoi ces choix
- **Pas de route pour devenir super-admin** : un tel compte peut tout voir ; il ne doit
  pouvoir être créé que par quelqu'un qui a déjà accès au serveur.
- **Des chiffres, pas les données** : le super-admin voit des compteurs, jamais les
  mesures ni les clés d'une usine. Les routes des usines lui répondent 403 (il n'a pas
  d'usine). Cela respecte la règle du sujet : une usine ne voit jamais les données d'une
  autre, et l'exploitant non plus sans raison.
- **Ce suivi a trouvé un vrai problème** : le worker lançait **20 processus** (un par
  cœur du processeur), chacun avec son propre exemplaire du modèle en mémoire (environ
  1 Go au total). Nous l'avons limité à 2 (`--concurrency=2`) : environ 460 Mo. Pour plus
  de charge, on lance plusieurs conteneurs worker plutôt que des dizaines de processus.

### 10.4 Fichiers
| Fichier | Rôle |
|---|---|
| `app/cli.py` | commande `create-superadmin` |
| `app/api/v1/admin.py` | usines, plan, workers |
| `app/core/deps.py` | `require_superadmin` |
| `tests/test_superadmin.py` | 6 tests |

---

## 11. Simulateur multi-usines

### 11.1 À quoi ça sert
Le sujet : « simulateur fourni par l'équipe qui rejoue AI4I sur les machines de
plusieurs usines en même temps ». Il sert à faire la démonstration et à vérifier que
la plateforme tient la charge et isole bien les usines.

### 11.2 Comment ça fonctionne
```
python -m simulator.stream_simulator setup      # crée les usines de démo
python -m simulator.stream_simulator run --labels --errors 0.02
python -m simulator.stream_simulator demo       # les deux d'un coup
```
- **`setup`** crée 3 usines par l'API, comme un vrai client :
  Casablanca (**Pro**, 3 machines), Rabat et Tanger (**Gratuit**, 2 machines chacune).
  Les comptes (e-mail, mot de passe) et les clés des machines (montrées une seule fois)
  sont enregistrés dans `simulator/config.json` (exclu de Git).
- **`run`** découpe les 10 000 lignes d'AI4I en tranches consécutives, une par machine,
  et lance **un thread par machine** : les 7 machines des 3 usines envoient **en même
  temps**, par lots (`--batch`, défaut 25) espacés de `--delay` secondes.
- Chaque mesure a un `message_id` unique (`nom de la machine-UDI`).
- `--labels` ajoute le **retour terrain** (vraies étiquettes AI4I) : il alimente le
  réentraînement Pro.
- `--errors 0.02` injecte **volontairement** 2 % de mesures impossibles (couple négatif,
  900 K…) et quelques doublons, pour montrer la quarantaine et la déduplication.
- Une machine dont la clé est révoquée (401) ou dont l'usine dépasse son quota (429)
  s'arrête et l'affiche.

### 11.3 Résultat réel
Démo sur la plateforme (1 400 lignes, 7 machines en parallèle, retour terrain, 2 %
d'erreurs) : **1 400 mesures acceptées, 27 doublons détectés, 32 mesures en
quarantaine**, 40 alertes ouvertes puis fermées (modes PWF, OSF, TWF), chaque usine ne
voit que ses machines.

### 11.4 Pourquoi ces choix
- **Passer par l'API publique** (inscription, plan, machines, mesures) : le simulateur
  teste la plateforme exactement comme un vrai client.
- **Threads** : l'envoi attend surtout le réseau ; des threads suffisent pour simuler
  plusieurs machines en même temps, sans complexité.
- **Aucune donnée inventée** : les mesures sont les vraies lignes AI4I ; seules les
  erreurs injectées sont fausses, et elles sont faites pour être rejetées.

### 11.5 Fichiers
| Fichier | Rôle |
|---|---|
| `simulator/stream_simulator.py` | `setup`, `run`, `demo` |
| `simulator/config.json` | comptes et clés de la démo (créé par `setup`, pas dans Git) |
| `tests/test_simulateur.py` | 4 tests (découpage, erreurs, rejeu de bout en bout) |

---

## 12. Tableau de bord (Streamlit)

### 12.1 À quoi ça sert
L'interface des utilisateurs : http://localhost:8501 (service Docker `dashboard`).

### 12.2 Ce qu'on y trouve
| Écran | Pour qui | Contenu |
|---|---|---|
| Connexion / inscription | tout le monde | se connecter, inscrire son usine ; le lien d'invitation (`?invitation=…`) ouvre le formulaire d'acceptation |
| 🚨 Alertes | tous | alertes actives **rafraîchies toutes les 5 s**, risque max, mode probable, explication, bouton **Acquitter** ; historique |
| 🏭 Machines | tous (gestion : responsables) | liste, courbe du **risque et du seuil**, courbes des mesures, mesures à risque avec leur explication ; déclarer une machine (clé montrée une fois), remplacer / révoquer la clé, archiver |
| 🎚️ Coûts et seuils | tous (modification : responsables) | curseur du ratio de coût avec **aperçu immédiat** du seuil, des pannes détectées et des fausses alertes ; réglages d'hystérésis |
| 👥 Équipe | tous (gestion : responsables) | membres, invitations, changement de rôle, retrait |
| 💳 Abonnement, IA, export | tous | consommation du plan, changement de plan (propriétaire), modèle utilisé, **réentraînement** (Pro), **export CSV** (Pro), quarantaine |
| Super-administrateur | équipe MaintAI | tableau des usines, changement de plan, état des workers |

### 12.3 Pourquoi ces choix
- **Le tableau de bord ne parle qu'à l'API**, comme n'importe quel client : il n'a aucun
  accès direct à la base. Toutes les règles (rôles, plans, isolation) sont appliquées
  par l'API ; un bouton caché dans l'interface n'est jamais la seule protection.
- **Streamlit** : une interface complète en Python, sans HTML ni JavaScript, adaptée à
  un projet de data science.
- **`st.fragment(run_every=5)`** : seule la zone des alertes se rafraîchit, pas toute la page.
- **Export généré à la demande** : sinon chaque affichage de la page téléchargerait toutes
  les données.

### 12.4 Vérification
- Test automatique `tests/test_dashboard.py` : la page se charge sans erreur (outil
  officiel `streamlit.testing.v1.AppTest`, sans navigateur).
- Vérifié contre la vraie API avec le même outil : connexion d'un propriétaire Pro (5
  onglets, seuil 2,2 %, 3/50 machines, aucune erreur), du super-administrateur (usines,
  workers) et message clair pour un mauvais mot de passe.

### 12.5 Fichiers
| Fichier | Rôle |
|---|---|
| `app_frontend.py` | tout le tableau de bord |
| `tests/test_dashboard.py` | test de chargement |

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
   sur une base séparée `maintai_test` pour ne jamais toucher aux vraies données
   (`TESTS=local bash scripts/verifier.sh` : tests avec le venv local, moins de mémoire) ;
3. vérifie que `migrate` s'est terminé sans erreur et que `api`, `worker`, `postgres`,
   `redis` tournent ;
4. vérifie que l'API répond.
