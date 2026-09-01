# RGPD - mesures prévues et implémentées

- Minimisation : identité, coordonnées nécessaires, véhicules, réservation et paiement uniquement.
- Consentement analytics : aucun outil optionnel avant validation du choix dans le centre de préférences.
- Newsletter : inscription en deux étapes (demande + confirmation).
- Droit d'accès/portabilité : endpoint `/api/privacy/export`.
- Droit à l'effacement : endpoint `DELETE /api/privacy/account`, avec anonymisation lorsque la conservation d'un historique est nécessaire.
- Politique de confidentialité : vue publique prévue dans le front.
- Sécurité : chiffrement applicatif de certaines données, hachage des mots de passe, contrôle d'accès et journalisation.
