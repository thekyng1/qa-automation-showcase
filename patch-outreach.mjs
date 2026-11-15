#!/usr/bin/env node
// patch-outreach.mjs — face outreach.mjs onest și selectiv (de rulat O SINGURĂ dată, din ~/demo-prospect/outreach).
// CE FACE:
//   1. tplFirst/tplFollow citesc numărul REAL de probleme din reports/<slug>.json
//      (generat de `node audit.mjs <domeniu>`) — emailul nu mai pretinde teste care nu au rulat.
//   2. send devine selectiv: `node outreach.mjs send e-jumbo.ro --send` trimite DOAR acel prospect.
//   3. SIGURANȚĂ: send refuză orice prospect fără raport de audit (reports/<slug>.json lipsă) —
//      niciun email nu pleacă fără dovadă în spatele linkului.
// Backup automat: outreach.mjs.bak. Idempotent — a doua rulare nu modifică nimic.
import fs from 'node:fs';

const FILE = 'outreach.mjs';
if (!fs.existsSync(FILE)) {
  console.error('❌ rulează acest script din directorul cu outreach.mjs (~/demo-prospect/outreach)');
  process.exit(1);
}
let src = fs.readFileSync(FILE, 'utf8');
if (src.includes('readFindings')) {
  console.log('✅ outreach.mjs e deja patch-uit — nimic de făcut.');
  process.exit(0);
}

const reFirst  = /const tplFirst = p => \(\{[\s\S]*?\}\);/;
const reFollow = /const tplFollow = p => \(\{[\s\S]*?\}\);/;
if (!reFirst.test(src) || !reFollow.test(src)) {
  console.error('❌ tplFirst/tplFollow nu au forma așteptată — nu modific nimic.');
  console.error('   Lipește-mi conținutul outreach.mjs în chat și îl patch-uiesc manual.');
  process.exit(1);
}

const helpers = `// --- PATCH onest: findings REALE din reports/<slug>.json (generate de audit.mjs) ---
const readFindings = p => {
  let slug = String(p.domain).replace('https://', '').replace('http://', '').replace('www.', '');
  if (slug.endsWith('.ro')) slug = slug.slice(0, -3);
  try {
    const r = JSON.parse(fs.readFileSync('reports/' + slug + '.json', 'utf8'));
    return { n: (r.findings || []).length, top: ((r.findings || [])[0] || {}).title || null };
  } catch (e) { return { n: null, top: null }; }
};`;

const newFirst = `const tplFirst = function (p) {
  const f = readFindings(p);
  const nr = (f.n === null) ? 'câteva' : String(f.n);
  const topLine = f.top ? ('Cea mai gravă: ' + f.top + '\\n\\n') : '';
  return {
    subject: p.domain + ' — ' + nr + ' probleme găsite de un audit automat (raport gratuit)',
    text: 'Bună ziua,\\n\\n' +
      'Am rulat un audit automat pe paginile publice ale ' + p.domain + ' — doar citire: nicio comandă plasată, nicio plată.\\n\\n' +
      'Am găsit ' + nr + ' probleme reale, fiecare cu pași de reproducere; unde browserul a fost disponibil, raportul conține și screenshot-uri (desktop + mobil).\\n\\n' +
      topLine +
      'Raportul complet:\\n' + p.reportUrl + '\\n\\n' +
      'Codul auditului e public, ca să-l verificați singuri: github.com/thekyng1/qa-automation-showcase\\n\\n' +
      'Dacă vi se pare util, extind gratuit suita pe fluxurile voastre critice (căutare → coș → checkout). Răspundeți cu „da, extinde” și primul raport extins e la voi în 48 de ore.\\n\\n' +
      'Dacă nu vă interesează, un simplu „nu” e suficient și nu vă mai contactez.\\n\\n' +
      'Toate bune,\\n' + (env.FROM_NAME || 'Luca')
  };
};`;

const newFollow = `const tplFollow = function (p) {
  const f = readFindings(p);
  const nr = (f.n === null) ? 'câteva' : String(f.n);
  return {
    subject: 'Re: raportul de audit pentru ' + p.domain + ' (' + nr + ' probleme)',
    text: 'Bună ziua,\\n\\n' +
      'Trec doar rapid pe lângă raportul de audit trimis săptămâna trecută despre ' + p.domain + ' — ' + nr + ' probleme, cu pași de reproducere:\\n' +
      p.reportUrl + '\\n\\n' +
      'Dacă v-a ajuns la cine trebuie, ignorați acest mesaj. Dacă nu e persoana potrivită, un reply cu „nu” sau cu adresa corectă mă ajută enorm.\\n\\n' +
      'Toate bune,\\n' + (env.FROM_NAME || 'Luca')
  };
};`;

src = src.replace(reFirst, helpers + '\n\n' + newFirst);
src = src.replace(reFollow, newFollow);

// send selectiv + blocaj de onestate: fără domeniu → vechiul comportament (toate "new"),
// cu domeniu → doar acel prospect; orice prospect fără raport de audit e sărit cu avertisment.
const loopRe = /for \(const p of db\.prospects\) \{/g;
const ins = "for (const p of db.prospects) {\n" +
  "    const onlyDomain = (args || []).find(a => a.indexOf('.ro') !== -1);\n" +
  "    if (onlyDomain && p.domain !== onlyDomain) continue;\n" +
  "    if (readFindings(p).n === null) { console.log('⏭ ' + p.domain + ' — fără raport de audit (rulează: node audit.mjs ' + p.domain + ') — sărit, nimic trimis.'); continue; }";
src = src.replace(loopRe, ins);

fs.copyFileSync(FILE, FILE + '.bak');
fs.writeFileSync(FILE, src);
console.log('✅ outreach.mjs patch-uit (backup: outreach.mjs.bak)');
console.log('   1. tplFirst/tplFollow citesc reports/<slug>.json — email onest, cu numărul real de probleme');
console.log('   2. send selectiv: node outreach.mjs send <domeniu> --send');
console.log('   3. send refuză prospecte fără raport de audit');
console.log('   Verifică sintaxa: node --check outreach.mjs');
