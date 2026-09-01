# MecaBot - assistant de pré-diagnostic et orientation garage

MecaBot est un assistant métier intégré à MecaConnect. Il ne remplace pas un diagnostic mécanique : il transforme la description libre d'un symptôme en pistes probables, niveau d'urgence, fourchette de coût indicative et spécialités à rechercher.

## Fonctionnement

1. L'utilisateur décrit le problème en langage naturel et peut préciser marque, modèle, année et zone.
2. Le back-end normalise le texte et calcule un score sur une base de règles couvrant notamment freinage, batterie/démarrage, voyant moteur, embrayage, transmission, pneus, climatisation, suspension, refroidissement, distribution, diesel/FAP/injection, échappement et entretien.
3. La fourchette de prix est ajustée avec des facteurs simples liés au véhicule. Elle reste explicitement présentée comme indicative.
4. Les garages sont classés avec un score mêlant spécialité, compatibilité de marque, note, statut vérifié et proximité lorsqu'une position Mapbox est disponible.
5. Les meilleurs garages sont retournés avec la raison du classement et la prestation correspondante lorsqu'elle existe.

## Carte Île-de-France

Le catalogue de démonstration contient 31 ateliers répartis dans les départements 75, 77, 78, 91, 92, 93, 94 et 95. Les noms et localisations sont fictifs ou indicatifs : ils servent uniquement au prototype RNCP.

Sans token Mapbox, l'application affiche un aperçu schématique des points. Avec `MAPBOX_TOKEN`, elle active une carte routière interactive avec marqueurs, popups, zoom et recentrage.

## Garde-fous et fiabilité

Avant de chercher une panne, MecaBot passe chaque message dans une couche de contrôle déterministe. L'objectif est simple : lorsqu'il ne sait pas, il pose une question au lieu d'inventer une réponse.

- **Périmètre automobile uniquement** : une question de météo, politique, recette, programmation ou autre sujet sans rapport avec le véhicule ne déclenche aucun diagnostic.
- **Entrées incompréhensibles** : les chaînes aléatoires ou descriptions inexploitables retournent une demande de reformulation, sans prix ni garage.
- **Protection contre les injections de prompt** : les formulations du type « ignore les instructions », « system prompt » ou « jailbreak » restent hors périmètre et n'altèrent pas le comportement du moteur.
- **Demandes dangereuses ou non conformes** : MecaBot refuse d'expliquer comment neutraliser un airbag, l'ABS, un équipement antipollution ou falsifier le kilométrage.
- **Signaux critiques** : perte de freinage, direction bloquée, feu/fumée sous le capot, fuite de carburant, forte surchauffe, pression d'huile rouge ou risque roue/pneu déclenchent une réponse `safety_stop`. Dans ce cas, aucun prix et aucun trajet vers un garage ne sont proposés : la priorité est l'immobilisation et l'assistance.
- **Message trop vague** : un seul mot comme « frein » ou « batterie » ne suffit pas pour chiffrer des travaux. L'assistant demande le symptôme, le moment d'apparition et le contexte.
- **Symptômes contradictoires ou multiples** : lorsque plusieurs familles de panne obtiennent des scores proches, MecaBot suspend l'estimation et demande quel symptôme est principal.
- **Historique maîtrisé** : un ancien symptôme n'est réutilisé que pour une vraie réponse de suivi courte. Un nouveau sujet n'hérite pas du diagnostic précédent.
- **Garages filtrés** : un garage n'est jamais recommandé uniquement parce qu'il est bien noté. Il doit réellement déclarer une spécialité ou une prestation cohérente avec le problème détecté.
- **Estimation bornée** : les prix proviennent de fourchettes par famille d'intervention ; ils sont toujours présentés comme indicatifs et ne constituent jamais un devis.
- **Aucun diagnostic définitif** : les causes restent formulées comme des pistes à confirmer par un professionnel.

Cette couche est volontairement indépendante d'un modèle génératif : les règles de sécurité, le score de confiance, l'urgence, les bornes de coût et le filtrage des garages restent contrôlables et testables. Une éventuelle brique LLM future ne pourrait donc pas contourner ces garde-fous métier.

## Tests adversariaux

Une suite dédiée vérifie les cas normaux et les entrées volontairement problématiques : hors sujet, message vague, texte aléatoire, injection de prompt, neutralisation d'équipements de sécurité, signaux critiques, historique parasite et mélange de plusieurs symptômes.

Résultat actuel : **52 tests back-end réussis**, **89 % de couverture sur le moteur `assistant.py`** et **82 % sur l'ensemble du package applicatif**. Le front conserve **14 tests réussis**.
