#!/usr/bin/env node
// scout.mjs — agent de prospectare multi-nisă .ro
// run:   node scout.mjs run            → toate nisele built-in
//        node scout.mjs run jucarii    → o singură nisă (după id)
//        node scout.mjs run "cuvinte"  → căutare custom
//        node scout.mjs niches         → lista niselor
//        node scout.mjs list           → candidații găsiți
//        node scout.mjs best           → top candidați după scor
import fs from 'fs';
import dns from 'dns/promises';

const CAND = 'candidates.json';
const PROSPECTS = 'prospects.json';
const UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120 Safari/537.36';
const SHOP = /(adaug[ăa][^<]{0,15}co[sș]|co[sș] de cump[ăa]r[ăa]turi|checkout|woocommerce|shoprenter|shopify|prestashop|magazin online|comand[ăa] (acum|online))/i;
const GOOD = /(comenzi|office|contact|vanzari|sales|info|hello|admin|client)@/i;
const BAD  = /(example|sentry|wix|squarespace|no-?reply|noreply|domain|abuse|webmaster|privacy|gdpr|postmaster|hostmaster)@/i;
// giganți și non-magazine: au QA proprii sau nu sunt clienți
const SKIP_DOMAIN = /(emag|altex|dedeman|decathlon|pcgarage|okazii|olx\.ro|shopmania|compari|facebook|instagram|youtube|tiktok|linkedin|wikipedia|blog|forum|stiri|anunturi|libertatea|adevarul|digi|mojeek|duckduckgo)/i;
const MAX_PER_QUERY = 10;

// --- Nisele: unde un audit QA aduce cel mai multă valoare ---
const NICHES = [
  { id:'jucarii',      q:'magazin online jucarii',           score:3 },
  { id:'bebelusi',     q:'magazin online articole bebelusi', score:3 },
  { id:'cosmetice',    q:'magazin online cosmetice',         score:3 },
  { id:'haine',        q:'magazin online haine femei',       score:3 },
  { id:'electronice',  q:'magazin online electronice',       score:3 },
  { id:'incaltaminte', q:'magazin online incaltaminte',      score:2 },
  { id:'sport',        q:'magazin online articole sport',    score:2 },
  { id:'petshop',      q:'pet shop online magazin',          score:2 },
  { id:'bijuterii',    q:'magazin online bijuterii',         score:2 },
  { id:'piese-auto',   q:'piese auto magazin online',        score:2 },
  { id:'mobilier',     q:'mobilier magazin online',          score:2 },
  { id:'farmacie',     q:'farmacie online magazin',          score:2 },
  { id:'deco',         q:'magazin online decoratiuni casa',  score:1 },
  { id:'carti',        q:'librarie online magazin',         score:1 },
];

const sleep = ms => new Promise(r=>setTimeout(r,ms));
const load = () => fs.existsSync(CAND) ? JSON.parse(fs.readFileSync(CAND,'utf8')) : {candidates:[]};
const save = db => fs.writeFileSync(CAND, JSON.stringify(db,null,2));
const loadProspectDomains = () => {
  try { return JSON.parse(fs.readFileSync(PROSPECTS,'utf8')).prospects.map(p=>p.domain); }
  catch { return []; }
};

async function get(url, timeout=15000){
  const c = new AbortController();
  const t = setTimeout(()=>c.abort(), timeout);
  try {
    const r = await fetch(url, {headers:{'User-Agent':UA,'Accept-Language':'ro,en;q=0.8'}, signal:c.signal, redirect:'follow'});
    if(!r.ok) return null;
    return await r.text();
  } catch { return null; }
  finally { clearTimeout(t); }
}

function roDomain(host){
  host = (host||'').toLowerCase().replace(/^www\./,'');
  if(!/\.ro$/.test(host)) return null;
  if(SKIP_DOMAIN.test(host)) return null;
  return host;
}

function extractDomains(html){
  const out = new Set(); const re = /<a[^>]+href="(https?:\/\/[^"]+)"[^>]*>/g; let m;
  while((m = re.exec(html))){
    let href = m[1];
    const u = href.match(/[?&]uddg=([^&" ]+)/);
    if(u) href = decodeURIComponent(u[1]);
    try { const d = roDomain(new URL(href).hostname); if(d) out.add(d); } catch {}
  }
  // fallback: orice URL .ro din text (prinde și linkurile care nu sunt în <a href>)
  for(const m2 of html.matchAll(/https?:\/\/(?:www\.)?([a-z0-9-]+(?:\.[a-z0-9-]+)*\.ro)\b/gi)){
    const d = roDomain(m2[1].toLowerCase());
    if(d) out.add(d);
  }
  return [...out];
}

async function search(query){
  let domains = [];
  // 4 surse în lanț: dacă una e rate-limitată, următoarea preia
  const sources = [
    'https://html.duckduckgo.com/html/?q=',
    'https://lite.duckduckgo.com/lite/?q=',
    'https://www.mojeek.com/search?q=',
    'https://search.brave.com/search?q=',
  ];
  for(const s of sources){
    if(domains.length >= 5) break;
    if(domains.length) await sleep(1200);
    const html = await get(s + encodeURIComponent(query));
    if(html) domains = [...new Set([...domains, ...extractDomains(html)])];
  }
  return domains.slice(0, MAX_PER_QUERY);
}

async function findEmail(domain){
  const pages = ['', '/contact', '/contacte', '/contact-us', '/despre-noi'];
  let best = null;
  for(const p of pages){
    const html = await get('https://'+domain+p);
    if(!html) continue;
    const found = new Set();
    const mailto = /mailto:([\w.+-]+@[\w-]+\.[\w.-]+)/gi; let m;
    while((m = mailto.exec(html))) found.add(m[1].toLowerCase());
    for(const e of html.match(/[\w.+-]+@[\w-]+\.[\w.-]{2,}/g)||[]) found.add(e.toLowerCase());
    for(const e of found){
      if(!e.endsWith(domain) && !e.includes(domain.replace(/^www\./,''))) continue;
      if(BAD.test(e)) continue;
      if(!best || (GOOD.test(e) && !GOOD.test(best))) best = e;
      if(/^(comenzi|vanzari|office|contact)@/.test(e)) return e;
    }
    if(best) break;
    await sleep(700);
  }
  return best;
}

async function checkDomain(domain){
  const home = await get('https://'+domain) || await get('http://'+domain);
  if(!home) return {ok:false, why:'inaccesibil'};
  if(!SHOP.test(home)) return {ok:false, why:'nu pare magazin'};
  try { const mx = await dns.resolveMx(domain); if(!mx.length) throw new Error(); }
  catch { return {ok:false, why:'fara MX'}; }
  const email = await findEmail(domain);
  if(!email) return {ok:false, why:'fara email public'};
  return {ok:true, email};
}

async function runNiche(niche, known){
  console.log(`\n🔎 Nisă: ${niche.id} (${niche.q}) — prioritate ${niche.score}/3`);
  const domains = await search(niche.q);
  if(!domains.length){
    console.log(`   ⚠ căutarea nu a returnat nimic (motoarele pot fi temporar limitate) — încearcă din nou peste câteva minute`);
    return 0;
  }
  let added = 0;
  for(const d of domains){
    if(known.has(d)) { console.log(`   ↷ ${d} — deja cunoscut, sar`); continue; }
    process.stdout.write(`   ✓? ${d} … `);
    const r = await checkDomain(d);
    if(!r.ok){ console.log(`✗ (${r.why})`); known.add(d); await sleep(800); continue; }
    const db = load();
    db.candidates.push({domain:d, email:r.email, niche:niche.id, score:niche.score + (GOOD.test(r.email)?1:0), foundAt:new Date().toISOString().slice(0,10), status:'new'});
    save(db); known.add(d); added++;
    console.log(`✓ ${r.email}`);
    await sleep(1000);
  }
  console.log(`   → ${added} candidați noi din ${domains.length} domenii`);
  return added;
}

const cmd = process.argv[2], arg = process.argv[3];
if(cmd === 'niches'){
  console.log('Nise built-in (id → căutare, prioritate):');
  for(const n of NICHES) console.log(`  ${n.id.padEnd(14)} "${n.q}"  score ${n.score}/3`);
} else if(cmd === 'list' || cmd === 'best'){
  const db = load();
  if(!db.candidates.length){ console.log('Niciun candidat. Rulează: node scout.mjs run'); process.exit(0); }
  let list = db.candidates;
  if(cmd === 'best') list = [...list].sort((a,b)=>(b.score||0)-(a.score||0));
  // fallback-uri pentru candidații găsiți de versiunile vechi (fără câmpul niche/score)
  console.log(list.map(c => `${(c.domain||'?').padEnd(22)} ${(c.email||'-').padEnd(26)} ${(c.niche||c.kw||'-').padEnd(13)} score=${c.score||0} ${c.status||'-'} ${c.foundAt||c.gasit||'-'}`).join('\n'));
  console.log(`\nTotal: ${list.length} candidați`);
} else if(cmd === 'run'){
  let niches, label;
  if(!arg){ niches = NICHES; label = 'TOATE nisele'; }
  else if(NICHES.some(n=>n.id===arg)){ niches = [NICHES.find(n=>n.id===arg)]; label = arg; }
  else { niches = [{id:'custom', q:arg, score:2}]; label = arg; }
  const db = load();
  const known = new Set([...db.candidates.map(c=>c.domain), ...loadProspectDomains()]);
  console.log(`🚀 Scout pornit: ${label} — ${db.candidates.length} candidați existenți, ${known.size} domenii de evitat`);
  let total = 0;
  for(const n of niches){ total += await runNiche(n, known); await sleep(2500); }
  console.log(`\n✅ Gata: ${total} candidați noi. Vezi-i cu: node scout.mjs best`);
} else {
  console.log('Comenzi: run [nisă|"cuvinte"] | niches | list | best');
}
