# Référentiels publics utilisés

## Adresses et villes
MecaConnect utilise le service officiel de géocodage de la Géoplateforme (IGN), alimenté notamment par la Base Adresse Nationale (BAN), via le backend. L'ancien domaine api-adresse.data.gouv.fr a été remplacé par data.geopf.fr.

Endpoint applicatif :
- `GET /api/public/address-search?q=...`

Le navigateur n'appelle pas directement l'API externe : FastAPI sert de proxy et renvoie uniquement les informations utiles à l'autocomplétion.

## Vérification des garages
L'inscription professionnelle demande un SIRET de 14 chiffres. Le backend interroge l'API publique de recherche d'entreprises et vérifie :
- que le SIRET existe ;
- que l'établissement demandé correspond au SIRET ;
- que l'activité principale enregistrée correspond à la famille NAF 45.20 (entretien/réparation automobile).

Le compte GARAGE et l'établissement ne sont créés qu'après cette vérification automatique.

## Véhicules
La saisie véhicule est guidée par un référentiel local de marques, modèles et motorisations courantes afin d'éviter les erreurs tout en laissant la saisie possible. Pour une industrialisation, ce référentiel peut être synchronisé avec un jeu de données public automobile (par exemple les données de caractéristiques/homologation publiées sur data.gouv.fr) sans modifier le modèle de données.

La plaque est validée au format SIV courant `AA-123-AA`. MecaConnect ne prétend pas décoder automatiquement une plaque : ce type de service complet est généralement fourni par des bases spécialisées.
