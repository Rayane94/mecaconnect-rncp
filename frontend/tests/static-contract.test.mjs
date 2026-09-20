import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const html=readFileSync(new URL('../public/index.html', import.meta.url),'utf8');
const privacy=readFileSync(new URL('../public/privacy.html', import.meta.url),'utf8');
const appSource=readFileSync(new URL('../src/app.ts', import.meta.url),'utf8');
const enhancements=readFileSync(new URL('../src/enhancements.ts', import.meta.url),'utf8');

test('HTML language and responsive viewport are declared',()=>{
  assert.match(html,/<html lang="fr">/);
  assert.match(html,/name="viewport"/);
});
test('main SEO metadata and canonical are present',()=>{
  assert.match(html,/<title>[^<]+<\/title>/);
  assert.match(html,/name="description"/);
  assert.match(html,/rel="canonical"/);
  assert.match(html,/application\/ld\+json/);
});
test('Open Graph metadata are present',()=>{
  assert.match(html,/property="og:title"/);
  assert.match(html,/property="og:description"/);
  assert.match(html,/property="og:url"/);
});
test('semantic landmarks and skip link exist',()=>{
  for(const token of ['<header','<nav','<main','<footer','skip-link']) assert.ok(html.includes(token));
});
test('forms expose labels and status region',()=>{
  assert.ok((html.match(/<label/g)||[]).length >= 10);
  assert.match(html,/aria-live="polite"/);
  assert.match(html,/role="status"/);
});
test('cookie consent and privacy access are present',()=>{
  assert.match(html,/cookie-dialog/);
  assert.match(html,/Nécessaires uniquement/);
  assert.match(html,/Politique de confidentialité/);
  assert.match(privacy,/Vos droits|droits/i);
});
test('role-specific dashboard and booking dialog exist',()=>{
  assert.match(html,/id="dashboard"/);
  assert.match(html,/id="booking-dialog"/);
  assert.match(html,/id="booking-slot"/);
});

test('main features use dedicated browser routes',()=>{
  for(const route of ['/mecabot','/garages']) {
    assert.ok(html.includes(route));
  }
  for(const route of ['/connexion','/mon-espace','/espace-garage','/admin']) {
    assert.ok(appSource.includes(route));
  }
  assert.match(html,/data-page="assistant"/);
  assert.match(html,/data-page="garages"/);
  assert.match(html,/data-page="dashboard"/);
  assert.doesNotMatch(html,/id="auth-dialog"/);
});

test('MecaBot assistant and IDF map are present',()=>{
  assert.match(html,/id="assistant"/);
  assert.match(html,/id="assistant-form"/);
  assert.match(html,/id="garage-map"/);
  assert.match(html,/MECABOT - ASSISTANT AUTO/);
  assert.match(html,/maplibre-gl@5\.24\.0/);
  assert.match(appSource,/tiles\.openfreemap\.org\/styles\/liberty/);
  assert.doesNotMatch(html,/mapbox/i);
  assert.doesNotMatch(appSource,/mapbox/i);
});

test('navigation exposes home and garage workspace management',()=>{
  assert.match(html,/>Accueil<\/a>/);
  assert.match(html,/Retour à l'accueil/);
  for(const token of ['/api/services/','/api/availability/','/api/bookings/','data-dashboard-tab="services"']) {
    assert.ok(appSource.includes(token));
  }
});


test('legal pages and professional registration are exposed',()=>{
  for(const token of ['/mentions-legales','/confidentialite','/cgu','/cgv','garage-register-form','pro-siret']) {
    assert.ok(html.includes(token));
  }
  assert.match(privacy,/Durées de conservation|Durées/i);
  assert.match(privacy,/Responsable du traitement/i);
});

test('UX feedback fixes are implemented',()=>{
  assert.match(html,/reg-password-error/);
  assert.match(html,/reschedule-dialog/);
  assert.match(enhancements,/api\/public\/address-search/);
  assert.match(enhancements,/AA-123-AA/);
  assert.match(enhancements,/data-user-cancel/);
  assert.match(enhancements,/api\/privacy\/account/);
  assert.match(enhancements,/api\/auth\/register-garage/);
});


test('public garage catalog explains sourcing and real-establishment status',()=>{
  assert.match(html,/16 établissements réels/);
  assert.match(html,/SIRET vérifié/);
  assert.match(html,/prestations sourcées|prestations issues de sources officielles/i);
  assert.match(appSource,/CLAIMED_PARTNER/);
  assert.match(appSource,/SIRET vérifié/);
  assert.match(appSource,/Aucun partenariat/);
  assert.match(appSource,/price_label/);
  assert.match(appSource,/photo_url/);
});
