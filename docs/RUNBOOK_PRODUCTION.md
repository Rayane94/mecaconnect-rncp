# MecaConnect - guide de production (C27-C32)

Ce document est un mode opératoire ; seules les actions réellement exécutées et capturées peuvent servir de preuves de soutenance.

## Architecture
- Front HTML/CSS/TypeScript + back Python/FastAPI dans une image Docker multi-stage.
- PostgreSQL sur Railway, connexion par DATABASE_URL.
- Dossier docs/ : spécifications, UML, RGPD, cas de test.
- API OpenAPI : /api/docs ; disponibilité : /api/health.

## Paramètres
Configurer les secrets dans Railway, jamais dans Git : DATABASE_URL, JWT_SECRET, FERNET_KEY, STRIPE_SECRET_KEY, GROQ_API_KEY et mots de passe d'initialisation. Pour la newsletter en ligne, ajouter SMTP_HOST, SMTP_PORT, SMTP_FROM, SMTP_USERNAME et SMTP_PASSWORD. Sans serveur SMTP configuré, la demande de newsletter est refusée plutôt que d'exposer le lien de confirmation. En production, valider COOKIE_SECURE=true, COOKIE_SAMESITE=lax, CORS_ORIGINS et APP_BASE_URL.

## Vérification après déploiement
1. Vérifier la branche Railway reliée au dépôt et le SHA réellement publié.
2. Vérifier les tests GitHub Actions, le build Docker et le statut des services Railway.
3. Contrôler GET /api/health (HTTP 200 et JSON status=ok).
4. Tester le consentement cookies (refus puis acceptation), l'accueil et la recherche.
5. Tester l'authentification, les rôles, la réservation des garages partenaires et Stripe en mode Test.
6. Vérifier les logs Railway et l'accès PostgreSQL.
7. Faire un relevé daté sans exposer les secrets.

## Surveillance
Le workflow .github/workflows/uptime.yml vérifie l'API publique chaque heure après fusion sur la branche par défaut. Configurer les notifications GitHub Actions ou un service indépendant (Uptime Kuma) pour recevoir une alerte. La sonde HTTP ne remplace pas des métriques de base de données, une alerte sur les erreurs 5xx et un test de restauration.

## Gestion d'incident
1. Confirmer l'incident, son heure et les utilisateurs touchés.
2. Vérifier /api/health, les logs et le dernier SHA Railway.
3. Isoler l'origine : API, PostgreSQL, secrets, front ou fournisseur externe.
4. Appliquer un correctif ou redéployer le dernier SHA stable après vérification des migrations.
5. Refaire la recette et consigner la résolution.
6. Tester périodiquement la restauration des sauvegardes PostgreSQL.

## Limites à déclarer
Une vérification automatisée par navigateur Chromium depuis GitHub Actions a confirmé l'accès HTTP 200 au site public Railway, au chemin `/api/health` et à la documentation Swagger. Des captures datées existent dans l'artefact GitHub Actions `mecaconnect-current-evidence`. En revanche, le SHA effectivement actif sur Railway, le statut administratif du certificat TLS, les alertes réellement reçues, la supervision indépendante et les restaurations PostgreSQL n'ont pas été vérifiés. Les captures publiées sont des observations ponctuelles, pas une garantie de disponibilité continue.

La sécurité des paiements simulés est renforcée **dans la branche de correction uniquement** : confirmation strictement locale et refus des faux succès publics. Tant qu'elle n'est pas fusionnée puis déployée et recettée, l'ancienne version peut rester en ligne. La newsletter côté serveur public utilise désormais un envoi SMTP chiffré et ne retourne pas de lien secret au demandeur. L'envoi réel, les rebonds et la délivrabilité doivent encore être vérifiés avec des identifiants SMTP exploitables.
