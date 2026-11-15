#!/usr/bin/env node
// autopilot.mjs — leagă scout.mjs (găsire prospecte) de outreach.mjs (contactare)
// PRINCIPIU DE SIGURANȚĂ: autopilotul NU trimite niciodată email.
// Comanda `node outreach.mjs send --send` rămâne ÎNTOTDEAUNA decizia ta, manuală.
//
// Comenzi:
//   node autopilot.mjs daily [nisa]   → rulează scout + construiește coada de lucru
//   node autopilot.mjs queue          → coada + pașii exacți pentru fiecare candidat
//   node autopilot.mjs done <domeniu> → scoate din coadă un domeniu procesat
//   node autopilot.mjs cron           → linia de crontab pentru rulare zilnică
import fs from 'fs';
import { spawnSync } from 'child_process';

const CAND = 'candidates.json';
const QUEUE = 'queue.json';
const MAX_QUEUE = 10;
// Comanda suitei de audit public (audit.mjs — doar cereri publice de citire,
// nicio comandă plasată, nicio plată). <domain> e substituit automat.
// Ieșiri: <slug>/index.html (raport pentru GitHub Pages) + reports/<slug>.json
const AUDIT_CMD = 'node audit.mjs <domain>';

const loadCand = () => fs.existsSync(CAND) ? JSON.parse(fs.readFileSync(CAND, 'utf8')) : { candidates: [] };
const loadQueue = () => fs.existsSync(QUEUE) ? JSON.parse(fs.readFileSync(QUEUE, 'utf8')) : { queue: [] };
const saveQueue = q => fs.writeFileSync(QUEUE, JSON.stringify(q, null, 2));
const saveCand = db => fs.writeFileSync(CAND, JSON.stringify(db, null, 2));
const slug = d => d.replace(/\.ro$/, '');

function buildQueue() {
  const db = loadCand();
  const done = new Set(loadQueue().queue.map(x => x.domain));
  const actionable = db.candidates
    .filter(c => (c.status === 'new' || c.status === 'candidate') && !done.has(c.domain))
    .sort((a, b) => (b.score || 0) - (a.score || 0))
    .slice(0, MAX_QUEUE)
    .map(c => ({
      domain: c.domain,
      email: c.email,
      niche: c.niche || '-',
      score: c.score || 0,
      addedAt: new Date().toISOString().slice(0, 10),
    }));
  return { queue: actionable };
}

function printQueue() {
  const q0 = loadQueue(); let queue = q0.queue; if(!queue.length){ queue = buildQueue().queue; saveQueue({queue}); }
  if (!queue.length) {
    console.log('Coada e goală. Rulează: node autopilot.mjs daily');
    console.log('Dacă scoutul nu a găsit nimic acum (rate-limit), reîncearcă peste 5-10 minute.');
    return;
  }
  console.log('Coada de lucru (' + queue.length + ' prospecte) — pași exacți pentru fiecare:\n');
  for (const c of queue) {
    console.log('─ ' + c.domain + '  (' + c.email + ', nisa: ' + c.niche + ', score ' + c.score + ')');
    console.log('  1. AUDIT:    ' + AUDIT_CMD.replace('<domain>', c.domain));
    console.log('  2. ADD:      node outreach.mjs add ' + c.domain + ' https://thekyng1.github.io/qa-automation-showcase/' + slug(c.domain) + '/');
    console.log('  3. DRAFT:    node outreach.mjs draft   (verifică outbox/' + c.domain.replace(/\./g, '_') + '.eml)');
    console.log('  4. DONE:     node autopilot.mjs done ' + c.domain);
    console.log('  5. (opțional, DECIZIA TA) node outreach.mjs send --send\n');
  }
  console.log('⚠️ Pasul 5 e mereu manual. Autopilotul nu rulează niciodată send --send.');
}

function runDaily(arg) {
  console.log('🚀 Autopilot zilnic — pasul 1: scout');
  const scoutCmd = arg ? ['node', 'scout.mjs', 'run', arg] : ['node', 'scout.mjs', 'run'];
  const scout = spawnSync(scoutCmd[0], scoutCmd.slice(1), { stdio: 'inherit', timeout: 180000 });
  if (scout.status !== 0) console.log('⚠ scout a eșuat parțial — coada se construiește din candidații existenți');

  console.log('\n📦 Pasul 2: coada de lucru');
  const q = buildQueue();
  saveQueue(q);
  console.log('→ ' + q.queue.length + ' prospecte în coadă.');
  const statuses = {};
  const db = loadCand();
  for (const c of db.candidates) statuses[c.status || '-'] = (statuses[c.status || '-'] || 0) + 1;
  console.log('Statusuri candidati: ' + JSON.stringify(statuses));

  console.log('\n📋 Pasul 3: lista de acțiuni');
  printQueue();

  console.log('✅ Gata. Execută pașii manual sau lasă-l pe cron doar pentru scout+queue (send rămâne al tău).');
}

const [cmd, arg] = process.argv.slice(2);
if (cmd === 'daily') runDaily(arg);
else if (cmd === 'queue') printQueue();
else if (cmd === 'done') {
  if (!arg) { console.log('Folosire: node autopilot.mjs done <domeniu>'); process.exit(1); }
  const q = loadQueue();
  const before = q.queue.length;
  q.queue = q.queue.filter(x => x.domain !== arg);
  saveQueue(q);
  console.log('✅ ' + arg + ' scos din coadă (' + before + ' → ' + q.queue.length + ')');
}
else if (cmd === 'cron') {
  console.log('# Rulează în fiecare dimineață la 08:00 (ora serverului):');
  console.log('0 8 * * * cd $HOME/demo-prospect/outreach && node autopilot.mjs daily >> autopilot.log 2>&1');
  console.log('# Instalare: crontab -e → lipește linia de mai sus → salvează');
  console.log('# NOTĂ: daily nu trimite email; doar găsește prospecte și construiește coada.');
}
else {
  console.log('Comenzi: daily [nisa] | queue | done <domeniu> | cron');
}
