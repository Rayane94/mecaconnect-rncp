# MecaConnect

Projet annuel réalisé pour la certification Développeur Full Stack RNCP 38606.

MecaConnect est une application web de réservation de prestations automobiles. Un utilisateur peut consulter les garages, enregistrer un véhicule, choisir un créneau et réserver une prestation. Les garages disposent d'un tableau de bord et un administrateur peut suivre l'activité générale.

## Stack utilisée

- Front-end : HTML, CSS, TypeScript
- Back-end : Python 3 / FastAPI
- Persistance : SQLAlchemy, SQLite en local et PostgreSQL prévu en production
- Authentification : JWT stocké dans un cookie HttpOnly
- 2FA : TOTP pour les comptes garage et administrateur
- Paiement : simulation locale en développement, Stripe Checkout en mode Test lorsqu'une clé `sk_test_` est configurée
- API tierce : Mapbox Geocoding lorsqu'un token public est configuré
- Assistant : OpenAI Responses API en mode hybride, avec moteur local de secours et garde-fous déterministes
- Tests : Node Test Runner côté front, Pytest + Coverage côté back
- Conteneurisation : Docker / Docker Compose

## Lancement local

```bash
cd frontend
npm run build

cd ../backend
PYTHONPATH=. python -m app.seed
PYTHONPATH=. uvicorn app.main:app --reload --port 8000
```

Puis ouvrir : `http://localhost:8000`

Documentation API : `http://localhost:8000/api/docs`

## Comptes de démonstration

Le script de seed crée deux comptes techniques :

- administrateur : `admin@mecaconnect.example.com`
- garage : `garage@mecaconnect.example.com`

En production, les mots de passe initiaux des comptes techniques sont fournis par les variables `ADMIN_SEED_PASSWORD` et `GARAGE_SEED_PASSWORD`. Les valeurs de repli du code sont réservées au lancement local et ne doivent pas être utilisées en production.

## Tests

### Front-end

```bash
cd frontend
npm test
```

### Back-end

```bash
cd backend
PYTHONPATH=. coverage run --source=app -m pytest -q
coverage report -m
```

Lors de la dernière exécution locale :

- 15 tests front, dont un contrat vérifiant les pages dédiées ;
- 58 tests back, dont une suite adversariale dédiée à MecaBot et à l'intégration OpenAI ;
- couverture back : 82 % du package `app` ;
- couverture du moteur `assistant.py` : 89 %.

## Variables d'environnement

Copier `.env.example` vers `.env` puis compléter les valeurs nécessaires.

Aucun secret réel ne doit être envoyé dans Git.

## Structure

```text
MecaConnect/
├── backend/
│   ├── app/
│   └── tests/
├── frontend/
│   ├── src/
│   ├── public/
│   └── tests/
├── docs/
├── docker-compose.yml
└── README.md
```

## Limites actuelles

Le code Stripe et Mapbox est prêt, mais la preuve finale doit être réalisée avec de vrais identifiants de test. Le déploiement public et l'audit Lighthouse seront effectués après validation de la version locale.

## MecaBot et recherche IDF

Le prototype intègre maintenant **MecaBot**, un assistant de pré-diagnostic automobile. À partir d'un symptôme décrit en texte libre, il propose des pistes probables, un niveau d'urgence, une fourchette de coût indicative et classe les garages les plus adaptés selon leur spécialité, la marque du véhicule, leur note et la proximité.

Le catalogue de démonstration contient **31 garages répartis dans les 8 départements d'Île-de-France**. Une carte schématique fonctionne sans service externe et Mapbox active la carte routière interactive dès qu'un `MAPBOX_TOKEN` est configuré.

Endpoint principal : `POST /api/assistant/diagnose`. Le moteur applique d’abord des garde-fous déterministes : hors sujet, texte incompréhensible, injection de prompt, demandes dangereuses, symptômes critiques, ambiguïtés et historique parasite sont traités avant tout appel externe. Lorsque `OPENAI_API_KEY` est configurée, OpenAI enrichit uniquement l'explication structurée ; l'urgence ne peut pas être abaissée et les prix comme les garages restent calculés localement. Sans clé ou en cas d'indisponibilité, le moteur local répond automatiquement. État de l'intégration : `GET /api/assistant/status`. Documentation détaillée : `docs/mecabot.md`.
