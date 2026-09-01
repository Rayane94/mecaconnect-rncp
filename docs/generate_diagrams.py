from pathlib import Path
import subprocess, textwrap
from cairosvg import svg2png

root=Path('/mnt/data/MecaConnect/docs')
wf=root/'wireframes'; uml=root/'uml'; wf.mkdir(exist_ok=True); uml.mkdir(exist_ok=True)

def wireframe(name,title,sections):
    W,H=1200,760
    parts=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
           '<style>text{font-family:Arial,sans-serif;fill:#333}.h{font-size:25px;font-weight:700}.s{font-size:16px}.xs{font-size:13px}.box{fill:#fafafa;stroke:#9b9b9b;stroke-width:2}.dark{fill:#e7e7e7;stroke:#777;stroke-width:2}.btn{fill:#d7d7d7;stroke:#777;stroke-width:2}.line{stroke:#aaa;stroke-width:2}</style>',
           '<rect width="1200" height="760" fill="white"/>',
           '<rect x="35" y="25" width="1130" height="60" class="dark" rx="8"/><text x="65" y="63" class="h">MecaConnect</text><text x="835" y="61" class="s">Garages   Comment ça marche   Connexion</text>',
           f'<text x="55" y="125" class="h">{title}</text>']
    for shape in sections:
        parts.append(shape)
    parts.append('</svg>')
    svg=''.join(parts)
    sp=wf/f'{name}.svg'; sp.write_text(svg)
    svg2png(bytestring=svg.encode(),write_to=str(wf/f'{name}.png'),output_width=W,output_height=H)

wireframe('01-accueil','Accueil et recherche',[ 
'<rect x="55" y="155" width="710" height="240" class="box" rx="12"/><text x="85" y="205" class="h">Titre principal / promesse</text><rect x="85" y="240" width="625" height="36" class="dark"/><rect x="85" y="300" width="280" height="55" class="box"/><rect x="380" y="300" width="190" height="55" class="box"/><rect x="585" y="300" width="125" height="55" class="btn"/><text x="612" y="333" class="s">Rechercher</text>',
'<rect x="800" y="155" width="330" height="240" class="dark" rx="20"/><text x="915" y="275" class="s">Visuel</text>',
'<text x="55" y="445" class="h">Garages disponibles</text><rect x="55" y="480" width="340" height="220" class="box" rx="12"/><rect x="430" y="480" width="340" height="220" class="box" rx="12"/><rect x="805" y="480" width="325" height="220" class="box" rx="12"/><text x="80" y="525" class="s">Carte garage</text><text x="455" y="525" class="s">Carte garage</text><text x="830" y="525" class="s">Carte garage</text>'])

wireframe('02-fiche-garage','Fiche garage',[ 
'<rect x="55" y="155" width="280" height="190" class="dark" rx="10"/><text x="135" y="255" class="s">Photo / carte</text><text x="370" y="190" class="h">Nom du garage ★★★★★</text><rect x="370" y="220" width="500" height="26" class="dark"/><rect x="370" y="265" width="620" height="70" class="box"/>',
'<text x="55" y="405" class="h">Prestations</text><rect x="55" y="440" width="1075" height="70" class="box"/><text x="80" y="482" class="s">Vidange + filtre</text><rect x="970" y="455" width="130" height="40" class="btn"/><text x="997" y="481" class="s">Réserver</text><rect x="55" y="530" width="1075" height="70" class="box"/><text x="80" y="572" class="s">Diagnostic électronique</text><rect x="970" y="545" width="130" height="40" class="btn"/><text x="997" y="571" class="s">Réserver</text>',
'<text x="55" y="660" class="h">Avis vérifiés</text>'])

wireframe('03-reservation','Réservation et paiement',[ 
'<rect x="55" y="160" width="310" height="520" class="box" rx="12"/><text x="85" y="205" class="h">1. Véhicule</text><rect x="85" y="240" width="250" height="45" class="dark"/><text x="85" y="335" class="h">2. Créneau</text><rect x="85" y="370" width="250" height="45" class="dark"/><rect x="85" y="430" width="115" height="45" class="btn"/><rect x="220" y="430" width="115" height="45" class="btn"/>',
'<rect x="400" y="160" width="730" height="520" class="box" rx="12"/><text x="435" y="205" class="h">Résumé</text><line x1="435" y1="225" x2="1090" y2="225" class="line"/><text x="435" y="270" class="s">Garage / prestation / date</text><text x="435" y="320" class="s">Prix total</text><text x="920" y="320" class="s">119,00 €</text><text x="435" y="365" class="h">Acompte (20 %)</text><text x="910" y="365" class="h">23,80 €</text><rect x="435" y="420" width="655" height="65" class="dark"/><text x="460" y="460" class="s">Paiement sécurisé - Stripe Test</text><rect x="760" y="545" width="330" height="60" class="btn"/><text x="830" y="583" class="s">Confirmer et payer</text>'])

wireframe('04-dashboard-client','Tableau de bord automobiliste',[ 
'<rect x="55" y="155" width="220" height="535" class="dark" rx="10"/><text x="85" y="205" class="s">Mes réservations</text><text x="85" y="250" class="s">Mes véhicules</text><text x="85" y="295" class="s">Mes données</text><text x="85" y="340" class="s">Déconnexion</text>',
'<text x="315" y="180" class="h">Mes prochains rendez-vous</text><rect x="315" y="215" width="815" height="110" class="box" rx="10"/><text x="340" y="255" class="s">Garage Berthier - Vidange + filtre</text><text x="340" y="292" class="xs">02/09/2026 - 09:00 · CONFIRMÉ</text><rect x="315" y="360" width="390" height="220" class="box"/><text x="340" y="400" class="h">Mes véhicules</text><rect x="735" y="360" width="395" height="220" class="box"/><text x="760" y="400" class="h">Mes données RGPD</text><rect x="760" y="455" width="150" height="45" class="btn"/><rect x="930" y="455" width="160" height="45" class="btn"/>'])

wireframe('05-dashboard-garage','Tableau de bord professionnel',[ 
'<rect x="55" y="155" width="220" height="535" class="dark" rx="10"/><text x="85" y="205" class="s">Agenda</text><text x="85" y="250" class="s">Prestations</text><text x="85" y="295" class="s">Disponibilités</text><text x="85" y="340" class="s">Profil garage</text><text x="85" y="385" class="s">Sécurité 2FA</text>',
'<text x="315" y="180" class="h">Agenda du jour</text><rect x="315" y="215" width="815" height="95" class="box"/><rect x="315" y="330" width="815" height="95" class="box"/><rect x="315" y="445" width="815" height="95" class="box"/><rect x="890" y="575" width="240" height="55" class="btn"/><text x="930" y="610" class="s">Ajouter un créneau</text>'])

wireframe('06-dashboard-admin','Administration',[ 
'<rect x="55" y="155" width="220" height="535" class="dark" rx="10"/><text x="85" y="205" class="s">Vue globale</text><text x="85" y="250" class="s">Utilisateurs</text><text x="85" y="295" class="s">Garages</text><text x="85" y="340" class="s">Paiements</text><text x="85" y="385" class="s">Logs</text>',
'<text x="315" y="180" class="h">Indicateurs</text><rect x="315" y="220" width="190" height="120" class="box"/><rect x="525" y="220" width="190" height="120" class="box"/><rect x="735" y="220" width="190" height="120" class="box"/><rect x="945" y="220" width="185" height="120" class="box"/><text x="315" y="395" class="h">Activité récente</text><rect x="315" y="430" width="815" height="220" class="box"/>'])

# Graphviz helpers

def dot(name, source):
    dp=uml/f'{name}.dot'; dp.write_text(source)
    subprocess.run(['dot','-Tpng',str(dp),'-o',str(uml/f'{name}.png')],check=True)

common='fontname="Arial" fontsize=10'
dot('01-use-cases', r'''
digraph G { graph [rankdir=LR,bgcolor="white",pad=.4,nodesep=.25,ranksep=.6]; node [shape=ellipse,fontname="Arial",fontsize=10,style=filled,fillcolor="#f7f7f7",color="#777"]; edge [fontname="Arial",fontsize=9,color="#777"];
  user [shape=box,label="Automobiliste",fillcolor="#e8eef1"]; garage [shape=box,label="Garage",fillcolor="#e8eef1"]; admin [shape=box,label="Administrateur",fillcolor="#e8eef1"]; stripe [shape=box,label="Stripe Test",fillcolor="#fff0e9"];
  search [label="Rechercher un garage"]; detail [label="Consulter prestations"]; vehicle [label="Gérer véhicules"]; book [label="Réserver un créneau"]; pay [label="Payer acompte"]; hist [label="Consulter réservations"]; rgpd [label="Exporter / supprimer\nmes données"];
  profile [label="Gérer profil garage"]; services [label="Gérer prestations"]; slots [label="Gérer disponibilités"]; appointments [label="Gérer rendez-vous"]; twofa [label="Activer 2FA"];
  stats [label="Consulter statistiques"]; moderate [label="Modérer comptes / garages"]; logs [label="Consulter logs"];
  user -> {search detail vehicle book pay hist rgpd}; garage -> {profile services slots appointments twofa}; admin -> {stats moderate logs}; pay -> stripe [label="API paiement"];
}
''')

dot('02-class-diagram', r'''
digraph G { graph [rankdir=LR,bgcolor="white",pad=.3,nodesep=.3,ranksep=.5]; node [shape=record,fontname="Arial",fontsize=9,style=filled,fillcolor="#fafafa",color="#666"];
User [label="{User|id:int\lemail:string\lpassword_hash:string\lrole:enum\ltwo_factor_enabled:bool\l}"]; Vehicle [label="{Vehicle|id:int\lowner_id:int\lmake:string\lmodel:string\lyear:int\l}"]; Garage [label="{Garage|id:int\lowner_id:int?\lname:string\lslug:string\lcity:string\lrating:float\l}"]; Service [label="{Service|id:int\lgarage_id:int\lname:string\lprice:float\lduration_minutes:int\l}"]; Slot [label="{Availability|id:int\lgarage_id:int\lstarts_at:datetime\lends_at:datetime\lis_booked:bool\l}"]; Booking [label="{Booking|id:int\luser_id:int\lservice_id:int\lslot_id:int\lstatus:string\ltotal_amount:float\ldeposit_amount:float\l}"]; Payment [label="{Payment|id:int\lbooking_id:int\lprovider:string\lreference:string\lamount:float\lstatus:string\l}"]; Review [label="{Review|id:int\luser_id:int\lgarage_id:int\lbooking_id:int\lrating:int\l}"]; Log [label="{AuditLog|id:int\luser_id:int?\laction:string\lresource:string\lcreated_at:datetime\l}"];
User -> Vehicle [label="1..n"]; User -> Booking [label="1..n"]; User -> Garage [label="0..n (owner)"]; Garage -> Service [label="1..n"]; Garage -> Slot [label="1..n"]; Service -> Booking [label="1..n"]; Slot -> Booking [label="0..1"]; Booking -> Payment [label="0..1"]; Booking -> Review [label="0..1"];
}
''')

dot('03-sequence-booking', r'''
digraph G { graph [rankdir=LR,bgcolor="white",pad=.4]; node [shape=box,fontname="Arial",fontsize=10,style=filled,fillcolor="#f7f7f7"]; edge [fontname="Arial",fontsize=9]; U[label="Utilisateur"]; F[label="Front TypeScript"]; A[label="API FastAPI"]; D[label="SQLAlchemy / BDD"]; P[label="Stripe Test"];
U->F[label="choisit prestation + créneau"]; F->A[label="POST /api/bookings"]; A->D[label="vérifie créneau non réservé"]; D->A[label="OK"]; A->D[label="crée réservation + verrouille créneau"]; A->F[label="booking + acompte 20 %"]; F->A[label="POST /payments/{id}/session"]; A->P[label="crée Checkout Session (sk_test_)"]; P->A[label="id + URL Stripe Checkout"]; A->F[label="checkout_url"]; F->P[label="redirection vers Stripe"]; P->A[label="retour session_id"]; A->P[label="GET Checkout Session"]; P->A[label="payment_status=paid"]; A->D[label="Payment SUCCEEDED + Booking CONFIRMED"]; A->F[label="confirmation HTML"];
}
''')

dot('04-mpd', r'''
digraph G { graph [rankdir=LR,bgcolor="white",pad=.3,nodesep=.25,ranksep=.6]; node [shape=record,fontname="Arial",fontsize=9,style=filled,fillcolor="#fff",color="#555"];
users[label="{users|PK id INTEGER\lemail VARCHAR UNIQUE\lpassword_hash TEXT\lrole VARCHAR\lphone_encrypted TEXT\l}"]; vehicles[label="{vehicles|PK id\lFK owner_id -> users\lmake\lmodel\lyear\lplate\l}"]; garages[label="{garages|PK id\lFK owner_id -> users\lslug UNIQUE\lcity INDEX\lverified\lrating\l}"]; services[label="{services|PK id\lFK garage_id -> garages\lname\lprice\lduration_minutes\l}"]; availability[label="{availability|PK id\lFK garage_id -> garages\lstarts_at INDEX\lends_at\lis_booked\lUNIQUE(garage_id,starts_at)\l}"]; bookings[label="{bookings|PK id\lFK user_id -> users\lFK service_id -> services\lFK slot_id -> availability UNIQUE\lstatus\ltotal_amount\ldeposit_amount\l}"]; payments[label="{payments|PK id\lFK booking_id UNIQUE\lprovider\lprovider_reference\lamount\lstatus\l}"]; reviews[label="{reviews|PK id\lFK user_id\lFK garage_id\lFK booking_id UNIQUE\lrating\lcomment\l}"];
users->vehicles; users->bookings; users->garages; garages->services; garages->availability; services->bookings; availability->bookings; bookings->payments; bookings->reviews;
}
''')

dot('05-architecture', r'''
digraph G { graph [rankdir=TB,bgcolor="white",pad=.4,nodesep=.4,ranksep=.55]; node [shape=box,fontname="Arial",fontsize=10,style="rounded,filled",fillcolor="#f8f8f8",color="#666",margin=.15];
Browser[label="Navigateur\nHTML + CSS + TypeScript\nWCAG / SEO / consentement"]; API[label="API REST FastAPI\nValidation Pydantic\nRBAC / JWT / TOTP\nOpenAPI"]; DB[label="Couche persistance\nSQLAlchemy\nPostgreSQL en conteneur\nSQLite pour test local"]; Stripe[label="Stripe Test\nPaiement acompte"]; Mapbox[label="Mapbox\nGéocodage (option configurée)"]; Logs[label="AuditLog / Healthcheck\nMonitoring cible"];
Browser->API[label="HTTPS / JSON"]; API->DB[label="ORM / transactions"]; API->Stripe[label="HTTPS API"]; Browser->Mapbox[label="HTTPS API tierce"]; API->Logs[label="journalisation"];
}
''')

print('generated')
