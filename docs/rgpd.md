# RGPD - mesures prévues et implémentées

- Minimisation : identité, coordonnées nécessaires, véhicules, réservation et paiement uniquement.
- Consentement analytics : aucun outil optionnel avant validation du choix dans le centre de préférences.
- Newsletter : deux étapes fonctionnelles dans le prototype ; le code corrigé exige un envoi SMTP pour l'activation publique. En son absence, la demande est refusée et aucun jeton n'est divulgué. La délivrabilité et les règles commerciales restent à tester.
- Droit d'accès/portabilité : endpoint `/api/privacy/export`.
- Droit à l'effacement : endpoint `DELETE /api/privacy/account`, avec anonymisation lorsque la conservation d'un historique est nécessaire.
- Politique de confidentialité : page publique disponible sur `/confidentialite` et préférence cookies révisable depuis le pied de page.
- Sécurité : chiffrement applicatif de certaines données, hachage des mots de passe, contrôle d'accès et journalisation.
- Les cookies nécessaires à l'authentification ne requièrent pas le même consentement que les mesures statistiques facultatives. La présence de la bannière, sans audit des traitements et sous-traitants, ne constitue pas une conformité RGPD certifiée.
