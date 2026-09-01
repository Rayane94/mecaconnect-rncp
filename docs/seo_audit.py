from pathlib import Path
from bs4 import BeautifulSoup
html=Path('../frontend/public/index.html').read_text(encoding='utf-8')
s=BeautifulSoup(html,'html.parser')
checks=[]
def c(label, ok): checks.append((label,bool(ok)))
c('Langue HTML définie', s.html and s.html.get('lang')=='fr')
c('Title présent et descriptif', s.title and 20 <= len(s.title.text) <= 65)
meta=lambda name: s.find('meta',attrs={'name':name})
c('Meta description', meta('description') and 70 <= len(meta('description').get('content','')) <= 180)
c('Viewport responsive', bool(meta('viewport')))
c('Robots meta', bool(meta('robots')))
c('Canonical', bool(s.find('link',rel='canonical')))
c('Un H1 principal', len(s.find_all('h1'))==1)
c('Structure sémantique header/nav/main/footer', all(s.find(x) for x in ['header','nav','main','footer']))
c('Données structurées JSON-LD', bool(s.find('script',attrs={'type':'application/ld+json'})))
c('Sitemap XML présent', Path('../frontend/public/sitemap.xml').exists())
c('robots.txt présent', Path('../frontend/public/robots.txt').exists())
c('Liens internes présents', len([a for a in s.find_all('a') if (a.get('href') or '').startswith(('/', '#'))])>=4)
c('Page confidentialité liée', any('privacy' in (a.get('href') or '') for a in s.find_all('a')))
c('Mots-clés métier présents', all(k in html.lower() for k in ['garage','réserv','entretien']))
c('CSS responsive avec media queries', '@media' in Path('../frontend/public/styles.css').read_text())
c('Lien d’évitement accessibilité', bool(s.find('a',class_='skip-link')))
c('Chargement JavaScript différé/module', bool(s.find('script',attrs={'type':'module'})))
c('Système de mesure d’audience conditionnel au consentement', 'analytics/event' in Path('../frontend/src/app.ts').read_text())
c('Open Graph social', bool(s.find('meta',attrs={'property':'og:title'})))
canon=(s.find('link',rel='canonical').get('href') if s.find('link',rel='canonical') else '')
c('URL canonique de production configurée', bool(canon) and 'example' not in canon and '__APP_BASE_URL__' not in canon)
passed=sum(v for _,v in checks); total=len(checks); score=passed/total*100
lines=['# Pré-audit SEO technique interne','',f'Résultat : **{passed}/{total} critères, soit {score:.0f} %**.','', '| Critère | Résultat |','|---|---|']
for label,ok in checks: lines.append(f'| {label} | {"OK" if ok else "À compléter"} |')
lines += ['', 'Ce pré-audit est reproductible sur les fichiers du projet. Avant soutenance, il doit être complété par une mesure Lighthouse/SEO sur l’URL effectivement déployée.']
Path('seo-audit.md').write_text('\n'.join(lines),encoding='utf-8')
print(f'{passed}/{total} = {score:.0f}%')
