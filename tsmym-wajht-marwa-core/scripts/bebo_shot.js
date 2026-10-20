const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch();
  const p = await (await b.newContext({ viewport: { width: 1280, height: 940 } })).newPage();
  await p.goto('http://localhost:3000?agent=bebo', { waitUntil: 'networkidle' });
  await p.waitForTimeout(2500);
  await p.screenshot({ path: 'G:/ai/Naggar Print POS Agent/tsmym-wajht-marwa-core/.shots/bebo-kanban.png' });
  await b.close();
  console.log('BEBO KANBAN SHOT OK');
})().catch(e => { console.error('FAIL:', e.message); process.exit(1); });
