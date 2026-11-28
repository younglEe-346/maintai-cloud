# MaintAI Cloud — maintenance prédictive pour usines

Projet de fin de module, Programmation avancée (partie Python), ENSAM Casablanca, 2026-2027.
Sujet 1, équipe n° 3 : Jamal Lachguer, Miloud Oujakka, Soulaimane Lbah.

Logiciel en ligne (SaaS) : les usines connectent leurs machines-outils, la plateforme
reçoit les mesures, estime le **risque de panne** avec un modèle d'IA, ouvre des
**alertes** et **explique** chaque décision au technicien. Chaque usine ne voit que ses
propres données.

> 📘 **Toutes les explications** (rôle de chaque partie, fonctionnement, choix, fichiers,
> questions probables de soutenance) sont dans [`docs/EXPLICATIONS.md`](docs/EXPLICATIONS.md).

## Fonctionnalités

- **IA** : risque de panne (Random Forest, PR-AUC 0,86 sur données jamais vues), seuil qui
  minimise le coût (panne manquée = 50 × fausse alerte, réglable), mode de panne
  multi-étiquette (TWF, HDF, PWF, OSF), contributions de chaque mesure (Shapley exact),
  modèles versionnés.
- **Mesures** : réception par lots, validation, rejet motivé des valeurs impossibles
  (quarantaine), déduplication par `message_id`.
- **Alertes** : hystérésis, une seule alerte active par machine, acquittement.
- **SaaS** : usines (organisations) isolées, rôles propriétaire / administrateur / membre,
  invitations par e-mail, clés d'API hachées et révocables, plans Gratuit et Pro
  (machines, mesures par jour, réentraînement, export), super-administrateur.
- **Simulateur** qui rejoue AI4I sur plusieurs usines en parallèle.
- **Interface web React** : l'application que les utilisateurs ouvrent dans leur navigateur.

## Interface utilisateur : front-end React

L'interface est l'application **React + TypeScript + Vite** (mise en forme Tailwind) du dossier
`frontend/`. Elle n'accède jamais à la base : elle appelle uniquement l'API, qui applique
les rôles, les plans et l'isolation des usines.

| Écran | Rôle |
|---|---|
| Connexion / inscription | créer une usine ou se connecter (`AuthPage`) |
| Machines | liste, ajout, clé d'API montrée une seule fois (`MachinesPage`) |
| Détail d'une machine | risque, mode de panne, contributions, clé à remplacer ou révoquer, archivage (`MachineDetailPage`) |
| Alertes | alertes actives, acquittement avec commentaire, historique (`AlertsPage`) |
| Réglages | coût d'une panne manquée, seuil, plan et usage, export, modèle (`SettingsPage`) |
| Équipe | membres, rôles, invitations par e-mail (`TeamPage`) |
| Acceptation d'invitation | page ouverte par le lien reçu par e-mail (`AcceptInvitationPage`) |
| Super-administrateur | usines et workers (`AdminPage`) |

Aussi : **mode sombre** (bouton lune / soleil), interface **français / anglais**, et
**déconnexion automatique après 1 heure d'inactivité**.

- **Adresse de l'API** : `http://localhost:8000/api/v1` par défaut ; pour la changer,
  copier `frontend/.env.example` en `frontend/.env` et modifier `VITE_API_URL`.
- **CORS** : l'API n'autorise que les sites listés dans `ALLOWED_ORIGINS`
  (`http://localhost:5173` inclus). Le port 5173 est fixé dans `frontend/vite.config.ts`
  (`strictPort`) : s'il est pris, Vite s'arrête au lieu d'en choisir un autre.
- **Liens d'invitation** : l'e-mail pointe vers `FRONTEND_URL` (`http://localhost:5173` par défaut).

Commandes (depuis le dossier `frontend/`, Node.js 20 ou plus) :

```bash
cd frontend
npm install        # une seule fois
npm run dev        # serveur de développement : http://localhost:5173
npm run build      # vérifie TypeScript puis fabrique la version de production
npm run typecheck  # vérifie les types
npm test           # tests Vitest
```

## Architecture

| Service (Docker) | Rôle | Adresse |
|---|---|---|
| `api` | API REST FastAPI | http://localhost:8000/docs |
| `worker` | worker Celery : prédictions, alertes, réentraînement | — |
| `postgres` | base de données | localhost:5432 |
| `redis` | file de tâches + compteurs de quotas | localhost:6379 |
| `mailpit` | faux serveur mail (invitations) | http://localhost:8025 |
| `migrate` | met la base à jour (Alembic) puis s'arrête | — |
| *(hors Docker)* `frontend/` | interface React (`npm run dev`) | http://localhost:5173 |

> L'ancien tableau de bord Streamlit (`app_frontend.py`, service Docker `dashboard`, port 8501)
> est encore dans le code mais n'est plus utilisé : il sera supprimé.

## Démarrage rapide

**Prérequis** : Docker Desktop ; Node.js 20+ pour le front-end ; Python 3.11+ pour le
simulateur et les tests locaux.

1. **Données** : télécharger *AI4I 2020 Predictive Maintenance Dataset* sur le site de l'UCI
   (DOI 10.24432/C5HS5C, licence CC BY 4.0) et placer `ai4i2020.csv` dans `data/`.
   Le fichier n'est pas dans Git.
2. **Configuration** (facultatif en développement) : copier `.env.example` en `.env` et
   y mettre une vraie `SECRET_KEY` (voir les commentaires du fichier).
3. **Lancer la plateforme** (API, worker, base, Redis, Mailpit) :
   ```bash
   docker compose -p maintai up -d --build
   ```
   (`-p maintai` : les conteneurs ont des noms fixes `maintai_*`, garder toujours ce nom de projet.)
4. **Créer le super-administrateur** (équipe MaintAI) :
   ```bash
   docker compose -p maintai exec api python -m app.cli create-superadmin --email admin@maintai.local
   ```
5. **Lancer le front-end** dans un second terminal :
   ```bash
   cd frontend
   npm install
   npm run dev
   ```
   Ouvrir http://localhost:5173 et créer une usine (écran d'inscription).
6. **Démo (facultatif)** : créer 3 usines et rejouer AI4I sur leurs 7 machines en parallèle
   ```powershell
   python -m venv venv
   venv\Scripts\activate            # Windows (Linux/Mac : source venv/bin/activate)
   pip install -r requirements.txt
   python -m simulator.stream_simulator demo --labels --errors 0.02
   ```
   Les comptes des usines de démo sont affichés et enregistrés dans `simulator/config.json` :
   s'en servir pour se connecter dans le front-end. Les e-mails d'invitation se lisent
   dans Mailpit (http://localhost:8025).

## Modèle d'IA

Le modèle commun est déjà fourni (`models/risk_model_v3.joblib` + rapport `.json`).
Pour le réentraîner (crée une nouvelle version, sans jamais écraser les anciennes) :
```bash
docker compose -p maintai --profile tools run --rm trainer
```
Le script `ml/train.py` affiche le rapport complet : données et écart avec la page UCI,
comparaison de 3 modèles, test sur 20 % jamais vus, seuil, modes de panne, contributions.

## Tests

| Partie | Nombre | Commande |
|---|---|---|
| Back-end (pytest) | 104 tests | `docker compose -p maintai --profile tools run --rm --build tests` |
| Front-end (Vitest) | 63 tests | `npm test` dans `frontend/` |

```bash
docker compose -p maintai --profile tools run --rm --build tests   # back-end
cd frontend && npm test                                            # front-end
bash scripts/verifier.sh               # démarre tout puis lance les tests back-end dans Docker
TESTS=local bash scripts/verifier.sh   # tests avec le venv local (moins de mémoire)
```
Les tests back-end utilisent une base séparée (`maintai_test`) : ils ne touchent jamais aux vraies données.

## API (principales routes, préfixe `/api/v1`)

| Route | Rôle |
|---|---|
| `POST /auth/register`, `POST /auth/login`, `GET /auth/me` | inscription d'une usine, connexion (JWT) |
| `POST /auth/accept-invitation` | rejoindre une usine par invitation |
| `POST /mesures` (en-tête `x-api-key`) | lot de mesures d'une machine |
| `GET/POST /machines`, `POST /machines/{id}/api-key/revoke` et `/rotate` | machines et clés |
| `GET /machines/{id}/mesures` | mesures + risque + explication |
| `GET /alerts`, `POST /alerts/{id}/acknowledge` | alertes, acquittement |
| `GET /org`, `PUT /org/plan`, `GET/PUT /org/settings` | usine, plan, coûts et seuils |
| `GET /org/members`, `POST /org/invitations` | équipe |
| `GET /org/models`, `POST /org/models/retrain` | modèle d'IA, réentraînement (Pro) |
| `GET /export/mesures.csv`, `GET /export/alertes.csv` | export (Pro) |
| `GET /quarantaine` | mesures rejetées |
| `GET /admin/organizations`, `GET /admin/workers` | super-administrateur |

Documentation interactive complète : http://localhost:8000/docs

## Structure du projet

```
app/
  api/v1/      routes de l'API (auth, machines, mesures, alertes, org, modèles, export, admin)
  core/        sécurité (JWT, hachage), droits et rôles, plans
  db/          connexion et migrations au démarrage
  ml/          IA : variables, coût et seuil, explications, entraînement, réentraînement
  models/      tables de la base (SQLAlchemy)
  services/    validation, hystérésis, e-mails, quotas
  worker/      tâches Celery
ml/train.py    entraînement du modèle commun
models/        modèles versionnés (joblib + rapport JSON)
migrations/    migrations Alembic (0001 à 0008)
simulator/     simulateur multi-usines
tests/         104 tests pytest (back-end)
scripts/       verifier.sh (vérification complète), nouvelle_migration.sh
docs/          EXPLICATIONS.md
frontend/      interface React + Vite + TypeScript + Tailwind
  src/pages/       écrans (connexion, machines, alertes, réglages, équipe, invitation, admin)
  src/components/  composants communs (boutons, graphique du risque, confirmation, thème)
  src/locales/     textes français et anglais
  src/__tests__/   tests Vitest
  src/api.ts       tous les appels à l'API
app_frontend.py  ancien tableau de bord Streamlit (inutilisé, à supprimer)
```
