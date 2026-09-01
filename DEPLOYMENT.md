# MecaConnect - Guide de mise en production

Ce guide sert de checklist opérationnelle pour rendre MecaConnect accessible en ligne avant la soutenance.

## 1. Pré-requis

- Un dépôt GitHub ou GitLab contenant le projet `MecaConnect`.
- Un hébergeur applicatif acceptant Docker, par exemple Render, Railway, Fly.io ou équivalent.
- Une base PostgreSQL managée, par exemple Railway PostgreSQL, Neon ou Render PostgreSQL.
- Un compte Stripe en mode test.
- Un token public Mapbox.
- Une URL publique HTTPS.

## 2. Variables d'environnement de production

Les valeurs ci-dessous doivent être configurées dans l'hébergeur. Ne jamais les commiter dans Git.

```env
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST:5432/DBNAME
APP_BASE_URL=https://votre-domaine-ou-url.onrender.com
CORS_ORIGINS=https://votre-domaine-ou-url.onrender.com
COOKIE_SECURE=true
COOKIE_SAMESITE=lax
JWT_SECRET=<secret-long-genere-aleatoirement>
FERNET_KEY=<cle-fernet-generee>
STRIPE_SECRET_KEY=sk_test_xxxxxxxxxxxxxxxxx
MAPBOX_TOKEN=pk.xxxxxxxxxxxxxxxxx
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxx
OPENAI_MODEL=gpt-5.6-terra
OPENAI_TIMEOUT_SECONDS=15
ADMIN_SEED_PASSWORD=<mot-de-passe-admin-fort>
GARAGE_SEED_PASSWORD=<mot-de-passe-garage-fort>
```

`OPENAI_API_KEY` est une clé serveur : elle ne doit jamais être envoyée au navigateur,
affichée dans une capture ou commitée. Sans cette variable, MecaBot conserve automatiquement
son moteur local et tous ses garde-fous.

Pour générer une clé Fernet :

```bash
python - <<'PY'
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())
PY
```

Pour générer un secret JWT :

```bash
python - <<'PY'
import secrets
print(secrets.token_urlsafe(64))
PY
```

## 3. Déploiement Docker

Le Dockerfile de production est situé dans `backend/Dockerfile`. Il sert l'API FastAPI et les fichiers front-end statiques.

Commande de build locale :

```bash
docker build -t mecaconnect -f backend/Dockerfile .
```

Commande de lancement locale avec variables :

```bash
docker run --env-file .env -p 8000:8000 mecaconnect
```

Vérification :

```bash
curl http://localhost:8000/api/health
```

Réponse attendue :

```json
{"status":"ok","service":"mecaconnect-api"}
```

## 4. Déploiement conseillé sur Render

1. Créer une base PostgreSQL Render.
2. Copier l'URL PostgreSQL dans `DATABASE_URL` en l'adaptant au format SQLAlchemy : `postgresql+psycopg://...`.
3. Créer un nouveau Web Service connecté au dépôt Git.
4. Choisir Docker comme environnement.
5. Indiquer le Dockerfile : `backend/Dockerfile`.
6. Ajouter toutes les variables d'environnement de production.
7. Déployer.
8. Ouvrir `https://URL_PUBLIC/api/health`.
9. Lancer le seed si nécessaire via une console/shell de l'hébergeur :

```bash
PYTHONPATH=. python -m app.seed
```

## 5. Déploiement conseillé sur Railway

1. Créer un nouveau projet Railway.
2. Ajouter PostgreSQL.
3. Ajouter le service applicatif depuis GitHub.
4. Définir le Dockerfile `backend/Dockerfile`.
5. Renseigner les variables d'environnement.
6. Générer un domaine public HTTPS.
7. Vérifier `/api/health`.
8. Lancer le seed si nécessaire.

## 6. Test de recette production

À faire après déploiement, avec captures d'écran à conserver pour le mémoire et la soutenance.

| Étape | Résultat attendu | Capture à prendre |
|---|---|---|
| Accueil HTTPS | Page chargée sans erreur | Page d'accueil + cadenas HTTPS |
| Cookies | Bannière de consentement visible | Bannière cookies |
| Inscription utilisateur | Compte créé | Retour API ou espace personnel |
| Connexion | Cookie de session HttpOnly | DevTools/Application/Cookies |
| Ajout véhicule | Véhicule visible dans l'espace personnel | Tableau de bord user |
| Recherche garage | Garages filtrés | Liste des garages |
| Mapbox | Carte ou géolocalisation fonctionnelle | Carte + appel réseau |
| Réservation | Créneau réservé | Confirmation réservation |
| Stripe Test | Paiement test validé | Checkout/Dashboard Stripe Test |
| Espace garage | Réservation visible côté garage | Dashboard garage |
| Espace admin | Statistiques/logs visibles | Dashboard admin |
| API Docs | Swagger accessible | `/api/docs` |
| Sécurité | Headers présents | DevTools Network ou SecurityHeaders |
| SEO | Lighthouse >= 70 % | Rapport Lighthouse |

## 7. Cartes Stripe Test

Utiliser uniquement les cartes de test Stripe.

Paiement accepté :

```text
4242 4242 4242 4242
Date future quelconque
CVC quelconque
```

## 8. Comptes de démonstration conseillés

À créer/valider avant la soutenance :

| Rôle | Email | Mot de passe |
|---|---|---|
| Admin | admin@mecaconnect.example.com | valeur de `ADMIN_SEED_PASSWORD` |
| Garage | garage@mecaconnect.example.com | valeur de `GARAGE_SEED_PASSWORD` |
| Utilisateur | à créer manuellement | mot de passe choisi lors de l'inscription |

## 9. Commandes de vérification avant rendu

```bash
cd frontend
npm test

cd ../backend
PYTHONPATH=. coverage run -m pytest -q
coverage report
```

## 10. Éléments à ajouter au mémoire après mise en production

- URL publique HTTPS.
- Capture de `/api/health` en production.
- Capture de l'accueil en HTTPS.
- Capture Mapbox avec token réel.
- Capture paiement Stripe Test réussi.
- Capture audit Lighthouse/SEO production.
- Capture des headers de sécurité.
- Capture du pipeline CI réussi si disponible.

## 11. Plan de secours soutenance

- Garder le projet local fonctionnel.
- Garder une archive ZIP du projet.
- Préparer les captures de la démonstration complète.
- Avoir les comptes de démonstration déjà connectés si possible.
- Garder le PDF mémoire, le PPTX et le code source disponibles hors ligne.
