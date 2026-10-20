const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch();
  const p = await (await b.newContext({ viewport: { width: 1280, height: 900 } })).newPage();
  await p.goto(process.argv[2] || 'http://localhost:3000?agent=salma', { waitUntil: 'networkidle' });
  await p.waitForTimeout(2500);
  await p.screenshot({ path: process.argv[3] || 'G:/ai/Naggar Print POS Agent/tsmym-wajht-marwa-core/.shots/salma-dashboard.png' });
  await b.close();
  console.log('SHOT OK');
})().catch(e => { console.error('SHOT FAIL:', e.message); process.exit(1); });
