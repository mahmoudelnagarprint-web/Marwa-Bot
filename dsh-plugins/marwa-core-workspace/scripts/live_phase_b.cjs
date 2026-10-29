// Marwa Command Center — الاختبار الحي للمرحلة B (Playwright + Chromium)
// يفتح واجهة DSH الحية، يدخل غرفة عمليات مروة، يفتح غرفة فارس، ويرصد:
//   1) سطر «[Phase B Test] Workspace: X | Session: Y» في Console
//   2) غياب خطأ «duplicate prop 'sessionId'» و«conversation.content»
//   3) رسم الشات الأصلي فعلياً داخل mcw-native
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const GUI = process.env.DSH_GUI_URL || 'http://127.0.0.1:55409';
const OUT_DIR = path.join(__dirname, '..', 'scripts', 'evidence');
fs.mkdirSync(OUT_DIR, { recursive: true });

(async () => {
  const consoleLines = [];
  const pageErrors = [];
  let phaseB = null;
  let duplicate = null;
  let nativeMounted = false;

  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  page.on('console', (m) => {
    const t = m.type();
    const text = m.text();
    consoleLines.push(`[${t}] ${text}`);
    if (/Phase B Test/.test(text)) phaseB = text;
    if (/duplicate prop/i.test(text)) duplicate = text;
  });
  page.on('pageerror', (e) => { pageErrors.push(String(e && e.message || e)); });

  const steps = [];
  const step = (name) => { steps.push({ at: new Date().toISOString().slice(11, 19), name }); console.log('>>> ' + name); };

  step('goto GUI');
  try {
    await page.goto(GUI, { waitUntil: 'domcontentloaded', timeout: 60000 });
  } catch (e) { console.log('goto error (maybe reloading): ' + e.message); }
  await page.waitForTimeout(6000);

  step('look for marwa sidebar item');
  let opened = false;
  const candidates = [
    () => page.getByText('غرفة عمليات مروة', { exact: false }).first().click({ timeout: 4000 }),
    () => page.locator('[aria-label*="غرفة"], [title*="غرفة"], [data-panel*="marwa"]').first().click({ timeout: 4000 }),
    () => page.getByText('🛡️ غرفة عمليات مروة', { exact: false }).first().click({ timeout: 4000 }),
  ];
  for (const c of candidates) {
    try { await c(); opened = true; break; } catch { /* next */ }
  }
  step('sidebar open: ' + opened);
  await page.waitForTimeout(4000);

  step('look for fares room item');
  let faresOpen = false;
  const fc = [
    () => page.getByText('فارس', { exact: false }).first().click({ timeout: 4000 }),  // زر في رصيف الوكلاء
    () => page.locator('button:has-text("فارس")').first().click({ timeout: 4000 }),
  ];
  for (const c of fc) {
    try { await c(); faresOpen = true; break; } catch { /* next */ }
  }
  step('fares open: ' + faresOpen);
  await page.waitForTimeout(6000);

  // فحص رسم الشات الأصلي داخل mcw-native
  try {
    const nat = await page.locator('.mcw-native').count();
    const mvc = await page.locator('.mcw-center').count();
    if (nat > 0) nativeMounted = true;
    step('mcw-native count=' + nat + ' mcw-center=' + mvc);
  } catch (e) { step('mount-check err: ' + e.message); }

  // لقطة شاشة للدليل
  try { await page.screenshot({ path: path.join(OUT_DIR, 'live_phase_b_' + Date.now() + '.png') }); } catch {}

  // محاولة الكشف لاحقاً (إن فُتحت الغرفة لاحقاً)
  await page.waitForTimeout(5000);

  const bodySnippet = await page.evaluate(() => document.body ? document.body.innerText.slice(0, 400) : '');

  // بحث إضافي عن phaseB في console بعد انتظار إضافي
  await browser.close();

  const report = {
    gui: GUI,
    at: new Date().toISOString(),
    opened_sidebar: opened,
    opened_fares: faresOpen,
    phaseB_log: phaseB,
    duplicate_prop_error: duplicate,
    page_errors: pageErrors.slice(0, 10),
    native_mounted: nativeMounted,
    console_matching: consoleLines.filter((l) => /marwa-core|Phase B|duplicate|conversation\.content|mcw/i.test(l)).slice(-30),
    body_snippet: bodySnippet,
    evidence_dir: OUT_DIR,
  };
  const outFile = path.join(OUT_DIR, 'live_phase_b_report.json');
  fs.writeFileSync(outFile, JSON.stringify(report, null, 2), 'utf-8');
  console.log('EVIDENCE_FILE=' + outFile);
  console.log(JSON.stringify({ phaseB_log: phaseB, duplicate_prop_error: duplicate, opened: opened && faresOpen, native_mounted: nativeMounted, page_errors: pageErrors.slice(0, 5) }, null, 2));
})().catch((e) => { console.error('FATAL', e); process.exit(1); });
