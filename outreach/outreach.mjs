#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import nodemailer from 'nodemailer';

const DB = path.resolve('prospects.json');
const OUTBOX = path.resolve('outbox');
const FOLLOWUP_AFTER_DAYS = 5;
const COLD_AFTER_DAYS = 12;

// --- .env simplu (fără dependențe) ---
const env = {};
if (fs.existsSync('.env'))
  for (const l of fs.readFileSync('.env','utf8').split('\n')) {
    const m = l.match(/^\s*([A-Z_]+)\s*=\s*(.+)\s*$/);
    if (m) env[m[1]] = m[2].replace(/^["']|["']$/g,'');
  }

const load = () => fs.existsSync(DB) ? JSON.parse(fs.readFileSync(DB,'utf8')) : {prospects:[]};
const save = db => fs.writeFileSync(DB, JSON.stringify(db,null,2));
const daysSince = ts => (Date.now()-ts)/86400000;
const sleep = ms => new Promise(r=>setTimeout(r,ms));

// --- slug + linkul corect de raport (GitHub Pages, structura reală din repo) ---
function slugify(domain) {
  return domain.replace(/^https?:\/\//,'').replace(/^www\./,'').replace(/\/$/,'').replace(/\.ro$/,'').replace(/\.com$/,'').toLowerCase();
}
function defaultReportUrl(domain) {
  return `https://thekyng1.github.io/qa-automation-showcase/${slugify(domain)}/`;
}

// --- Patch 1: verifică LIVE linkul raportului înainte de trimitere ---
async function reportIsLive(url) {
  if (!url || !/^https?:\/\//.test(url)) return false;
  try {
    const res = await fetch(url, {
      headers: {'user-agent':'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'},
      redirect: 'follow', signal: AbortSignal.timeout(15000),
    });
    return res.ok;
  } catch { return false; }
}

// --- 1. GĂSIREA EMAILULUI ---
const GOOD = /(comenzi|office|contact|vanzari|sales|info|hello|admin)@/i;
const BAD  = /(example|sentry|wix|squarespace|cloudflare|no-?reply|domain)/i;

async function findEmail(domain) {
  const pages = ['/contact','/contacte','/contacteaza-ne','/contact-us','/despre-noi',''];
  const found = [];
  for (const p of pages) {
    try {
      const res = await fetch(`https://${domain}${p}`, {
        headers: {'user-agent':'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'},
        redirect: 'follow', signal: AbortSignal.timeout(15000),
      });
      if (!res.ok) continue;
      const html = await res.text();
      const mails = [...html.matchAll(/[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-z]{2,}/gi)]
        .map(m => m[0].toLowerCase()).filter(e => !BAD.test(e));
      if (mails.length) { found.push(...new Set(mails)); break; }
    } catch {}
  }
  if (!found.length) return null;
  return found.find(e => GOOD.test(e)) || found[0];
}

// --- 2. Șabloane (pitch per prospect: p.pitch = 'bug' | 'a11y') ---
const bugFirst = p => {
  const n = p.issueCount ? `${p.issueCount} probleme` : '2 probleme';
  return {
    subject: `${n} pe ${p.domain} care pot costa comenzi (audit automat)`,
    text: `Bună ziua,

Am rulat automat, de la zero, o suită QA pe site-ul ${p.domain} (Playwright, teste publice, oprite înainte de plată — nicio comandă reală).

Am găsit ${n} reale, cu screenshot-uri și pași de reproducere:
${p.reportUrl}

Codul testelor e public, ca să le verificați singuri: github.com/thekyng1/qa-automation-showcase

Dacă vi se pare util, extind gratuit suita cu încă 5–10 teste pe fluxurile voastre critice. Răspundeți cu „da, extinde" și primul raport e la voi în 48 de ore.

Dacă nu vă interesează, un simplu „nu" e suficient și nu vă mai contactez.

Toate bune,
${env.FROM_NAME || 'Luca'}`,
  };
};
const bugFollow = p => ({
  subject: `Re: raportul QA pentru ${p.domain}`,
  text: `Bună ziua,

Trec doar rapid pe lângă raportul trimis săptămâna trecută despre ${p.domain} — probleme care pot bloca comenzi, cu screenshot-uri:
${p.reportUrl}

Dacă v-a ajuns la cine trebuie, ignorați acest mesaj. Dacă nu e persoana potrivită, un reply cu „nu" sau cu adresa corectă mă ajută enorm.

Toate bune,
${env.FROM_NAME || 'Luca'}`,
});
const a11yFirst = p => ({
  subject: `${p.domain} — fluxurile de comandă funcționează, dar EAA vă expune (audit automat)`,
  text: `Bună ziua,

Am rulat automat, de la zero, o suită QA pe site-ul ${p.domain} (Playwright, teste publice, oprite înainte de pasul de plată — nicio comandă reală).

Vestea bună: toate fluxurile critice de cumpărare trec — homepage-ul se încarcă fără erori JavaScript, produsul ajunge efectiv în coș, checkout-ul se deschide corect. Site-ul e sănătos.

Vestea care contează: scanarea de accesibilitate WCAG a identificat 4 tipuri de probleme, afectând 111 elemente — butonul de căutare fără etichetă (critic), 67 de zone cu contrast insuficient, 42 de linkuri fără text alternativ și zoom-ul dezactivat pe mobil. Din 28 iunie 2025, European Accessibility Act face accesibilitatea obligatorie pentru magazinele online din UE, inclusiv România. Două dintre fix-uri sunt, literal, câte o linie de cod.

Raportul complet, cu fiecare problemă explicată pe limba omului:
${p.reportUrl}

Codul testelor, public, ca să verificați singuri: github.com/thekyng1/qa-automation-showcase

Dacă vreți, re-rulez gratuit suita după ce aplicați fix-urile și vă confirm prin același raport automat că totul e curat. Răspundeți cu „re-rulează" și confirmarea e la voi în 48 de ore.

Dacă nu vă interesează, un simplu „nu" e suficient și nu vă mai contactez.

Toate bune,
${env.FROM_NAME || 'Luca'}`,
});
const a11yFollow = p => ({
  subject: `Re: auditul de accesibilitate pentru ${p.domain} (EAA)`,
  text: `Bună ziua,

Trec doar rapid pe lângă raportul de accesibilitate trimis pentru ${p.domain} — 4 probleme WCAG care vă expun la EAA, cu fiecare fix explicat:
${p.reportUrl}

Dacă v-a ajuns la cine trebuie, ignorați acest mesaj. Dacă nu e persoana potrivită, un reply cu „nu" sau cu adresa corectă mă ajută enorm.

Toate bune,
${env.FROM_NAME || 'Luca'}`,
});
const tplFirst = p => (p.pitch === 'a11y' ? a11yFirst(p) : bugFirst(p));
const tplFollow = p => (p.pitch === 'a11y' ? a11yFollow(p) : bugFollow(p));

// --- 3. Comenzi ---
const [cmd, ...args] = process.argv.slice(2);
const db = load();

// --- Patch 2: filtru de domeniu — primul argument care nu e flag ---
function pickFilter(argList) {
  const f = argList.find(a => !a.startsWith('--'));
  return f ? slugify(f) : null;
}

if (cmd === 'add') {
  const [domain, reportUrl] = args;
  if (!domain) { console.error('Folosire: add <domeniu> [url-raport]'); process.exit(1); }
  const url = reportUrl || defaultReportUrl(domain);
  const email = await findEmail(domain.replace(/^https?:\/\//,'').replace(/^www\./,''));
  if (!email) { console.log(`❌ ${domain}: nicio adresă găsită pe paginile publice — adaugă manual.`); process.exit(1); }
  db.prospects.push({ domain, email, reportUrl: url, status: 'new', sentAt: null });
  save(db);
  console.log(`✅ ${domain} → ${email} (raport: ${url}) (status: new)`);
}

else if (cmd === 'seturl') {
  const [domain, url] = args;
  if (!domain || !url) { console.error('Folosire: seturl <domeniu> <url-raport>'); process.exit(1); }
  const p = db.prospects.find(x => slugify(x.domain) === slugify(domain));
  if (!p) { console.error('Prospect inexistent'); process.exit(1); }
  p.reportUrl = url; save(db);
  console.log(`✅ ${p.domain}: reportUrl → ${url}`);
}

else if (cmd === 'check') {
  for (const p of db.prospects) {
    const live = await reportIsLive(p.reportUrl);
    console.log(`${live ? '✅' : '❌'} ${p.domain}\t${p.reportUrl}`);
  }
}

else if (cmd === 'draft') {
  fs.mkdirSync(OUTBOX, {recursive:true});
  const filter = pickFilter(args);
  let list = db.prospects.filter(x => x.status === 'new');
  if (filter) list = list.filter(p => {
    const d = slugify(p.domain);
    return d === filter || d.endsWith(`.${filter}`) || d.endsWith(filter);
  });
  for (const p of list) {
    const live = await reportIsLive(p.reportUrl);
    if (!live) console.warn(`⚠ ${p.domain}: linkul raportului NU e live (${p.reportUrl}) — draft generat oricum, dar NU trimite până nu publici raportul.`);
    const t = tplFirst(p);
    const file = path.join(OUTBOX, `${p.domain.replace(/\./g,'_')}.eml`);
    fs.writeFileSync(file, `To: ${p.email}\nSubject: ${t.subject}\n\n${t.text}`);
    console.log(`📝 draft: outbox/${path.basename(file)}`);
  }
}

else if (cmd === 'send') {
  if (!args.includes('--send')) { console.error('Confirmare: rulează cu --send pentru trimitere reală. Altfel folosește „draft".'); process.exit(1); }
  if (!env.SMTP_USER || !env.SMTP_PASS) { console.error('Lipsesc SMTP_USER / SMTP_PASS în .env'); process.exit(1); }

  // Patch 2: FILTRU — trimite DOAR prospectele cerute
  const filter = pickFilter(args.filter(a => a !== '--send'));
  let targets = db.prospects;
  if (filter) {
    targets = targets.filter(p => {
      const d = slugify(p.domain);
      return d === filter || d.endsWith(`.${filter}`) || d.endsWith(filter);
    });
    if (targets.length === 0) {
      console.error(`❌ Nicio potrivire pentru "${filter}". Disponibile: ${db.prospects.map(p=>p.domain).join(', ')}`);
      process.exit(1);
    }
  }
  console.log(`Prospecte țintă (${targets.length}): ${targets.map(p=>p.domain).join(', ')}`);

  const transport = nodemailer.createTransport({
    host: env.SMTP_HOST || 'smtp.gmail.com',
    port: Number(env.SMTP_PORT || 587),
    auth: { user: env.SMTP_USER, pass: env.SMTP_PASS },
  });

  for (const p of targets) {
    let tpl = null;
    if (p.status === 'new') tpl = tplFirst(p);
    else if (p.status === 'sent' && daysSince(p.sentAt) >= FOLLOWUP_AFTER_DAYS) tpl = tplFollow(p);
    else if (p.status === 'followed' && daysSince(p.sentAt) >= COLD_AFTER_DAYS) { p.status = 'cold'; save(db); console.log(`🧊 ${p.domain}: fără răspuns → cold (nu îl mai contactez)`); continue; }
    if (!tpl) continue;

    // Patch 1: NU trimite niciodată cu link mort
    if (!(await reportIsLive(p.reportUrl))) {
      const fallback = defaultReportUrl(p.domain);
      if (await reportIsLive(fallback)) {
        p.reportUrl = fallback; save(db);
        console.log(`🔧 ${p.domain}: reportUrl corectat automat → ${fallback}`);
      } else {
        console.warn(`⏭ ${p.domain} — raportul NU e live (${p.reportUrl}). Ritual: node audit.mjs ${p.domain} → push pe main → send ${p.domain} --send`);
        continue;
      }
    }

    await transport.sendMail({ from: `"${env.FROM_NAME}" <${env.FROM_EMAIL || env.SMTP_USER}>`, to: p.email, subject: tpl.subject, text: tpl.text });
    p.status = p.status === 'new' ? 'sent' : 'followed';
    p.sentAt = Date.now();
    save(db);
    console.log(`📤 ${p.domain} → ${p.email} (${p.status})`);
    await sleep(30000 + Math.random()*30000); // pauză umană între trimiteri
  }
}

else if (cmd === 'mark') {
  const [email, status] = args;
  const p = db.prospects.find(x => x.email === email);
  if (!p) { console.error('Prospect inexistent'); process.exit(1); }
  p.status = status; save(db);
  console.log(`✅ ${p.domain}: ${status} — ${status==='replied'||status==='nu' ? 'nu îl mai contactez' : ''}`);
}

else if (cmd === 'status') {
  for (const p of db.prospects)
    console.log(`${p.domain}\t${p.email}\t${p.status}\t${p.reportUrl}\t${p.sentAt ? Math.floor(daysSince(p.sentAt))+' zile' : '-'}`);
}

else {
  console.log(`Comenzi:
add <domeniu> [url-raport]   găsește emailul, adaugă prospectul (url implicit: GitHub Pages)
seturl <domeniu> <url>        corectează linkul raportului pentru un prospect
check                         verifică LIVE toate linkurile de raport
draft [domeniu]               scrie .eml în outbox/ pentru verificare
send [domeniu] --send         trimite DOAR prospectul/domeniul cerut (fără filtru = toate scadente)
mark <email> replied|nu       oprește orice follow-up
status                        tabel cu toate prospectele`);
}
