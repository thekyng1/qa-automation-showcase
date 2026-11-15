#!/usr/bin/env node
// audit.mjs — audit public al unui site .ro, cu sau fără browser.
// PRINCIPIU: doar cereri publice de citire (GET/HEAD). Nicio comandă, nicio plată,
// niciun formular trimis. Dacă Playwright + Chromium sunt disponibile, adaugă
// screenshot-uri (desktop + mobil), erori de consolă și test de scroll orizontal;
// altfel rulează browserless și raportează cu pași de reproducere manuali.
//
// Folosire:  node audit.mjs <domeniu.ro>
// Ieșiri:
//   reports/<slug>.json  — rezultatele brute (machine-readable)
//   <slug>/index.html   — raport self-contained, gata de publicat pe GitHub Pages
import fs from 'node:fs';
import tls from 'node:tls';

const UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36';
const TIMEOUT = 15000;

const domain = (process.argv[2] || '').replace(/^https?:\/\//, '').replace(/\/.*$/, '').toLowerCase();
if (!/^[a-z0-9][a-z0-9.-]*\.ro$/.test(domain)) {
  console.error('Folosire: node audit.mjs <domeniu.ro>');
  process.exit(1);
}
const slug = domain.replace(/\.ro$/, '');
const base = `https://${domain}`;
const now = new Date().toISOString();

const findings = [];
const add = (sev, title, detail, repro) => findings.push({ sev, title, detail, repro });

async function get(url, method = 'GET') {
  const t0 = Date.now();
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), TIMEOUT);
  try {
    const r = await fetch(url, { method, headers: { 'user-agent': UA }, signal: ctrl.signal, redirect: 'follow' });
    const html = method === 'GET' ? await r.text() : '';
    return { ok: r.ok, status: r.status, finalUrl: r.url, ms: Date.now() - t0, html };
  } catch (e) {
    return { ok: false, status: 0, finalUrl: url, ms: Date.now() - t0, html: '', error: String(e?.message || e) };
  } finally { clearTimeout(t); }
}

// 1) Redirecționare http -> https
const http = await get(`http://${domain}`);
if (http.status !== 0 && !http.finalUrl.startsWith('https://')) {
  add('high', 'http:// nu redirecționează către https://',
    'Vizitatorii care tastează adresa fără https ajung pe versiunea necriptată.',
    `curl -sI http://${domain}/ | grep -i '^location'`);
}
if (http.status === 0) {
  add('med', 'http:// nu răspunde deloc',
    'Serverul refuză conexiunea pe portul 80.',
    `curl -v http://${domain}/`);
}

// 2) Pagina principală
const home = await get(base);
if (!home.ok) {
  console.error('❌ ' + domain + ' nu răspunde la https (' + (home.error || 'HTTP ' + home.status) + ') — nu pot audita.');
  process.exit(1);
}
if (home.ms > 1500) {
  add('med', 'Răspuns lent (TTFB)',
    `Pagina principală a livrat primul byte în ${home.ms} ms — peste pragul de 1500 ms.`,
    `curl -o /dev/null -s -w 'TTFB: %{time_starttransfer}s\\n' ${base}/`);
}

// 3) Certificat SSL
const sslDays = await new Promise(resolve => {
  const s = tls.connect({ host: domain, port: 443, servername: domain }, () => {
    const cert = s.getPeerCertificate();
    s.end();
    resolve(cert && cert.valid_to ? Math.round((new Date(cert.valid_to).getTime() - Date.now()) / 86400000) : null);
  });
  s.on('error', () => resolve(null));
});
if (sslDays !== null && sslDays < 21) {
  add(sslDays < 7 ? 'high' : 'med', 'Certificat SSL aproape de expirare',
    `Certificatul expiră în ${sslDays} zile — după aceea, clienții văd un avertisment de securitate.`,
    `echo | openssl s_client -connect ${domain}:443 -servername ${domain} 2>/dev/null | openssl x509 -noout -enddate`);
}

// 4) Meta de bază
const html = home.html;
const hasViewport = /<meta[^>]+name=["']viewport["']/i.test(html);
const hasDesc = /<meta[^>]+name=["']description["']/i.test(html);
const title = ((html.match(/<title[^>]*>([\s\S]{0,200}?)<\/title>/i) || [])[1] || '').trim();
if (!hasViewport) {
  add('high', 'Lipsă meta viewport (afectează telefoanele)',
    'Fără <meta name="viewport">, site-ul se afișează pe mobil la scară de desktop — text minuscul, zoom obligatoriu.',
    `Deschide view-source:${base}/ și caută "viewport".`);
}
if (!hasDesc) {
  add('low', 'Lipsă meta description',
    'Google nu poate afișa un rezumat coerent în rezultatele căutărilor.',
    `Deschide view-source:${base}/ și caută "description".`);
}
if (title.length < 10) {
  add('low', 'Titlu de pagină prea scurt sau gol',
    `Titlul actual: "${title || '(gol)'}" — relevant pentru SEO și pentru tab-urile browserului.`,
    `Deschide ${base}/ și uită-te la textul din tab.`);
}
const emailOnPage = (html.match(/[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}/i) || [])[0] || null;
if (!emailOnPage) {
  add('low', 'Niciun email vizibil pe pagina principală',
    'Clienții care preferă emailul nu au unde să scrie fără să caute prin site.',
    `Deschide ${base}/ — caută o adresă de email vizibilă.`);
}

// 5) Link-uri rupte (max 20, doar interne)
const links = [...new Set((html.match(/href=["'][^"']+["']/g) || [])
  .map(h => h.slice(6, -1))
  .filter(l => !/^(mailto:|tel:|javascript:|#|data:)/i.test(l))
  .map(l => l.startsWith('/') ? base + l : l)
  .filter(l => l.replace(/^https?:\/\//, '').startsWith(domain.replace(/^www\./, '')) || l.includes(domain)))].slice(0, 20);
const broken = [];
for (const l of links) {
  let r = await get(l, 'HEAD');
  if (r.status === 405 || r.status === 403) r = await get(l, 'GET');
  if (!r.ok) broken.push(`${r.status || 'eroare'} ${l}`);
}
if (broken.length) {
  add(broken.length > 3 ? 'high' : 'med', `${broken.length} link${broken.length > 1 ? 'uri' : ''} rupt${broken.length > 1 ? 'e' : ''} (pagini care dau eroare)`,
    'Link-uri găsite pe pagina principală care returnează erori HTTP:\n' + broken.join('\n'),
    'Deschide URL-urile de mai sus — fiecare returnează o eroare HTTP.');
}

// 6) Playwright (opțional — screenshot-uri + erori consolă + scroll orizontal)
let shots = { desktop: null, mobile: null };
let playwrightMode = false;
const consoleErrors = [];
try {
  const { chromium } = await import('playwright');
  const browser = await chromium.launch({ timeout: 30000 });
  playwrightMode = true;
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await ctx.newPage();
  page.on('console', m => { if (m.type() === 'error') consoleErrors.push(m.text().slice(0, 200)); });
  await page.goto(base, { waitUntil: 'domcontentloaded', timeout: 30000 });
  shots.desktop = (await page.screenshot({ timeout: 30000 })).toString('base64');
  const mctx = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true });
  const mpage = await mctx.newPage();
  await mpage.goto(base, { waitUntil: 'domcontentloaded', timeout: 30000 });
  shots.mobile = (await mpage.screenshot({ timeout: 30000 })).toString('base64');
  const scrollWidth = await mpage.evaluate(() => document.documentElement.scrollWidth);
  if (scrollWidth > 398) {
    add('med', 'Scroll orizontal pe mobil',
      `La lățimea unui telefon (390px) pagina are ${scrollWidth}px — conținutul iese din ecran.`,
      'Deschide site-ul pe un telefon sau în DevTools la 390px și glisează spre dreapta.');
  }
  await browser.close();
} catch { playwrightMode = false; }
if (consoleErrors.length) {
  add('med', `${consoleErrors.length} erori de consolă JavaScript pe pagina principală`,
    consoleErrors.slice(0, 5).join('\n'),
    'Deschide DevTools → Console pe pagina principală.');
}

// Ieșiri
const report = {
  domain, base, auditedAt: now,
  mode: playwrightMode ? 'browser (Playwright)' : 'browserless (fetch)',
  checks: { ttfbMs: home.ms, sslDaysLeft: sslDays, metaViewport: hasViewport, metaDescription: hasDesc, title, emailOnPage, linksChecked: links.length, brokenLinks: broken.length, consoleErrors: consoleErrors.length },
  findings,
};
fs.mkdirSync('reports', { recursive: true });
fs.mkdirSync(slug, { recursive: true });
fs.writeFileSync(`reports/${slug}.json`, JSON.stringify(report, null, 2));

const esc = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
const sevRo = { high: 'critic', med: 'mediu', low: 'minor' };
const shotHtml = shots.desktop
  ? `<h2>Capturi</h2><p><b>Desktop 1440px</b><br><img src="data:image/png;base64,${shots.desktop}" alt="desktop"></p><p><b>Mobil 390px</b><br><img src="data:image/png;base64,${shots.mobile}" alt="mobil" style="max-width:390px"></p>`
  : `<p class="note">Audit rulat fără browser (${esc(report.mode)}) — fiecare problemă are pașii de reproducere de mai jos, verificabili manual.</p>`;
const findHtml = findings.length
  ? findings.map(f => `<li class="${f.sev}"><b>[${sevRo[f.sev] || f.sev}] ${esc(f.title)}</b><p>${esc(f.detail).replace(/\n/g, '<br>')}</p><pre>Reproducere: ${esc(f.repro)}</pre></li>`).join('\n')
  : '<li><b>Nicio problemă găsită de verificările automate.</b></li>';
const nProbleme = findings.length;
const pageHtml = `<!DOCTYPE html>
<html lang="ro"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Audit automat — ${esc(domain)}</title>
<style>
body{font-family:system-ui,sans-serif;max-width:820px;margin:2rem auto;padding:0 1rem;color:#222;line-height:1.5}
h1{font-size:1.4rem} .meta{color:#666;font-size:.9rem}
li{border-left:4px solid #ccc;padding:.6rem 1rem;margin:.7rem 0;list-style:none;background:#f8f8f8}
li.high{border-color:#c0392b} li.med{border-color:#e67e22} li.low{border-color:#7f8c8d}
pre{background:#eee;padding:.5rem;overflow-x:auto;font-size:.85rem}
img{max-width:100%;border:1px solid #ccc}
.note{background:#fffbe6;padding:.6rem 1rem}
</style></head><body>
<h1>Audit automat — ${esc(domain)}</h1>
<p class="meta">Rulat ${esc(now)} · mod: ${esc(report.mode)} · verificări publice, nicio comandă plasată, nicio plată.<br>
Cod de audit: <a href="https://github.com/thekyng1/qa-automation-showcase">github.com/thekyng1/qa-automation-showcase</a></p>
${shotHtml}
<h2>${nProbleme} problem${nProbleme === 1 ? 'ă' : 'e'} găsit${nProbleme === 1 ? 'ă' : 'e'}</h2>
<ul>${findHtml}</ul>
<h2>Verificări rulate</h2>
<pre>${esc(JSON.stringify(report.checks, null, 2))}</pre>
<p class="meta">Vrei extinderea suitei pe fluxurile tale critice (coș, checkout, cont)? Răspunde la email și primul raport extins e la tine în 48h.</p>
</body></html>`;
fs.writeFileSync(`${slug}/index.html`, pageHtml);

console.log('✅ Audit ' + domain + ' — ' + findings.length + ' probleme găsite (mod: ' + report.mode + ')');
console.log('   raport: ' + slug + '/index.html');
console.log('   json:   reports/' + slug + '.json');
if (!playwrightMode) console.log('   ℹ fără Chromium pe această mașină: raportul conține pași de reproducere în loc de screenshot-uri.');
