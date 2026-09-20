# Catalogue public des garages réels

État de vérification : 20 septembre 2026.

Le catalogue public MecaConnect contient uniquement des établissements réels dont le SIRET a été vérifié à partir de données publiques. Les prestations affichées proviennent du site officiel de l'établissement ou du réseau lorsque cette information est disponible.

**Important :** une fiche marquée `PUBLIC_REFERENCE` est une référence documentaire et n'implique aucun partenariat avec MecaConnect. Elle ne permet ni réservation ni paiement sur MecaConnect. Le propriétaire peut revendiquer la fiche avec son SIRET ; la fiche passe alors à `CLAIMED_PARTNER` et le garage peut publier ses propres prix, créneaux et conditions d'acompte.

| Garage | SIRET | Département | Source prestations |
|---|---:|---:|---|
| Midas Paris 04 - Célestins | 40308888300018 | 75 | Site officiel Midas |
| Midas Montreuil | 83209991500023 | 93 | Site officiel Midas |
| Midas Meaux | 85346792600012 | 77 | Site officiel Midas |
| Midas Chelles | 90814361300028 | 77 | Site officiel Midas |
| Midas Versailles | 53008423500023 | 78 | Site officiel Midas |
| Midas Deuil-la-Barre | 10573498200017 | 95 | Site officiel Midas |
| Midas Issy-les-Moulineaux | 82858931700027 | 92 | Site officiel Midas |
| Midas Argenteuil | 80201150200027 | 95 | Site officiel Midas |
| Midas Vitry-sur-Seine | 84103585000020 | 94 | Site officiel Midas |
| Midas Paris 17 - Rue de Rome | 52118323600020 | 75 | Site officiel Midas |
| Midas Paris 18 - La Fourche | 34092561900033 | 75 | Site officiel Midas |
| Alisson Garage | 83397857000020 | 92 | Site officiel Alisson Garage |
| Garage des 3 Communes | 40331528600019 | 93 | Site officiel Peugeot Proximity |
| Midas Saint-Denis | 83845747100012 | 93 | Site officiel Midas |
| Midas Vert-Saint-Denis | 47815359600042 | 77 | Site officiel Midas |
| Midas Viry-Châtillon | 78894256300016 | 91 | Site officiel Midas |
| Garage de Normandie | 34030305600022 | 92 | Site officiel Garage de Normandie |
| Garage Auto Jesus | 52417469500014 | 92 | Annuaire professionnel + source photo dédiée |
| Garage James Autos | 40995469000023 | 94 | Annuaire commerces de la Ville de Créteil |
| Audi Bauer Paris Roissy | 77566940100082 | 95 | Site officiel Bauer Paris |

## Règles appliquées

- Les anciennes fiches fictives du prototype restent uniquement en base pour préserver d'éventuelles relations historiques, mais elles sont masquées de l'API publique et de la carte.
- L'atelier fictif de démonstration est également masqué ; il sert seulement aux tests automatisés du tunnel réservation/paiement.
- Aucun prix n'est inventé pour un garage public non revendiqué. Si le site officiel ne publie pas un tarif exploitable, l'interface affiche **« Tarif sur devis - non publié par MecaConnect »**.
- Une photo n'est affichée que lorsqu'une image d'établissement issue du site officiel a été identifiée. À défaut, MecaConnect affiche un emplacement neutre.
- Les coordonnées cartographiques sont calculées à partir de l'adresse via la Géoplateforme IGN/BAN.
- L'inscription professionnelle revérifie le SIRET et l'activité de l'établissement avant de rattacher une fiche à un compte GARAGE.

Les URL sources détaillées sont stockées directement dans les champs `source_url`, `website_url`, `photo_url` et `photo_source_url` du seed afin de conserver une provenance vérifiable au niveau de chaque fiche.
