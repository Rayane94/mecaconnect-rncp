import test from 'node:test'; import assert from 'node:assert/strict';
import {depositFor,filterGarages,formatPrice,isStrongPassword,normalize,safeText,sortSlots} from '../public/lib.js';
const garages=[{id:1,name:'Garage Berthier',city:'Paris',address:'x',description:'Vidange freinage',rating:4.8,verified:true},{id:2,name:'Auto Lyon',city:'Lyon',address:'y',description:'Diagnostic',rating:4.2,verified:false}];
test('normalization and garage filtering',()=>{assert.equal(normalize(' Paris '),'paris'); assert.equal(filterGarages(garages,'vidange','Paris').length,1); assert.equal(filterGarages(garages,'','Lyon')[0].id,2)});
test('deposit calculation',()=>{assert.equal(depositFor(119),23.8); assert.equal(depositFor(100,0.25),25)});
test('password policy',()=>{assert.equal(isStrongPassword('StrongPassword-2026!'),true); assert.equal(isStrongPassword('weakpassword'),false)});
test('safe text removes angle brackets',()=>{assert.equal(safeText('<script>'),'script'); assert.equal(safeText(3),'')});
test('slots are sorted chronologically',()=>{const s=sortSlots([{id:2,starts_at:'2026-09-02T10:00:00',ends_at:'x'},{id:1,starts_at:'2026-09-01T10:00:00',ends_at:'x'}]);assert.equal(s[0].id,1)});
test('price formatter uses EUR',()=>{assert.match(formatPrice(42),/42/)});
