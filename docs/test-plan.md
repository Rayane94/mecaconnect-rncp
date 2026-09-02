# Plan de tests

## Front-end
### Tests unitaires et contrats statiques
- Recherche et filtrage de garages.
- Calcul de l'acompte.
- Politique de mot de passe.
- Nettoyage des textes affichés.
- Tri des créneaux.
- Formatage des prix.
- Contrats HTML/SEO/accessibilité : langue, viewport, canonical, Open Graph, repères sémantiques, labels, aria-live, consentement et écrans métier.

### Scénario navigateur E2E (Chromium, API mockée)
- Inscription utilisateur.
- Ajout d’un véhicule.
- Recherche, ouverture d’une fiche garage et sélection d’une prestation.
- Réservation d’un créneau et paiement local de test.
- Newsletter double opt-in et consentement analytics.
- Connexion et affichage des dashboards GARAGE puis ADMIN.
- Couverture V8 mesurée : 98,08 % du bundle exécuté et 86,54 % des fonctions.

## Back-end
- Healthcheck.
- Inscription / connexion / session.
- Refus des mots de passe faibles.
- Liste et détail garage.
- Création d'un véhicule.
- Réservation + paiement test.
- Prévention de la double réservation.
- Double opt-in newsletter.
- RBAC administrateur.
- Export RGPD.
- Hachage mot de passe, JWT et TOTP.

Objectif de couverture : >= 50 % conformément à C18 et C25, cible interne >= 70 %. Les nombres de tests et la couverture sont actualisés à partir de la dernière exécution complète avant livraison, sans réutiliser les anciens rapports comme preuve d'une version plus récente.


## MecaBot / catalogue IDF
- Vérifier qu'au moins 30 garages sont chargés et que les huit départements IDF sont représentés.
- Vérifier qu'un symptôme de freinage suffisamment précis retourne la spécialité `freinage`, une estimation et plusieurs garages réellement compétents.
- Vérifier qu'un message vague ne produit ni estimation ni recommandation et demande une précision.
- Vérifier qu'un sujet hors automobile ne déclenche aucun diagnostic.
- Vérifier qu'une tentative d'injection de prompt ne modifie pas le périmètre du bot.
- Vérifier que les demandes de neutralisation d'airbag/ABS/FAP ou de falsification du kilométrage sont refusées.
- Vérifier que les signaux critiques (perte de freinage, direction, feu, surchauffe sévère, pression d'huile rouge) coupent l'estimation et recommandent l'immobilisation.
- Vérifier qu'un nouveau sujet n'hérite pas d'un ancien diagnostic via l'historique.
- Vérifier que deux familles de symptômes proches déclenchent une clarification au lieu d'un prix arbitraire.
- Vérifier que les garages recommandés possèdent une spécialité ou une prestation correspondant au problème.
- Vérifier que l'interface contient le formulaire MecaBot et la zone cartographique.
- Vérifier que la carte utilise MapLibre/OpenFreeMap sans token et qu'aucune dépendance Mapbox ne subsiste.
- Vérifier le fallback schématique si MapLibre ou les ressources OpenFreeMap ne chargent pas.
- Vérifier que Groq ne peut modifier ni l'urgence, ni le prix, ni les garages d'un diagnostic local.
- Vérifier le fallback local lorsque `GROQ_API_KEY` est absente.
