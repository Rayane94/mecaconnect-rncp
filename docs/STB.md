# Spécifications techniques de besoin - MecaConnect

## Périmètre MVP

1. Création de compte et connexion.
2. Gestion d'un ou plusieurs véhicules.
3. Recherche de garages publics par ville et prestation.
4. Consultation d'une fiche garage et des prestations.
5. Consultation des créneaux disponibles.
6. Réservation atomique d'un créneau.
7. Paiement d'un acompte en environnement de test.
8. Historique des réservations.
9. Espace garage : établissement, services et créneaux.
10. Espace administrateur : statistiques et supervision.
11. Export / suppression des données personnelles.
12. Newsletter avec demande et confirmation de souscription : démonstration fonctionnelle en local. L'expédition réelle d'e-mails et la gestion commerciale sont à qualifier avant ouverture au public.

## Contraintes non fonctionnelles

- Responsive à partir de 360 px.
- Navigation clavier et focus visible.
- API REST JSON documentée OpenAPI.
- Authentification et contrôle d'accès par rôle.
- Validation serveur systématique.
- Couverture de tests >= 50 % front et back.
- SEO technique >= 70 % sur les pages publiques.
- Journalisation et monitoring prévus.
- Données bancaires jamais stockées localement.
- Paiements simulés autorisés uniquement en local sur loopback ; sur un environnement public sans Stripe Test disponible, le paiement reste désactivé (aucun faux succès).


## Assistant MecaBot
- Saisie libre d'un symptôme automobile.
- Pré-diagnostic par moteur de règles, avec niveau d'urgence et estimation indicative.
- Prise en compte facultative de la marque, du modèle, de l'année et de la zone.
- Classement des garages par spécialité, marque, note et proximité.
- Catalogue de 20 établissements réels sourcés couvrant les 8 départements d'Île-de-France. Les fiches publiques non revendiquées ne proposent ni réservation ni paiement. La réservation est réservée aux garages partenaires ayant activé leurs prestations et créneaux.
- Carte interactive MapLibre/OpenFreeMap sans token, avec carte schématique locale de secours.
- Avertissement explicite : la réponse ne remplace ni l'examen d'un mécanicien ni un devis.
