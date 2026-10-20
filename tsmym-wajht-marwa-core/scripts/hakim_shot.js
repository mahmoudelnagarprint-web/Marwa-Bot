const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch();
  const p = await (await b.newContext({ viewport: { width: 1280, height: 940 } })).newPage();
  await p.goto('http://localhost:3000?agent=hakim', { waitUntil: 'networkidle' });
  await p.waitForTimeout(3000);
  await p.screenshot({ path: 'G:/ai/Naggar Print POS Agent/tsmym-wajht-marwa-core/.shots/hakim-room.png' });
  await b.close();
  console.log('HAKIM SHOT OK');
})().catch(e => { console.error('FAIL:', e.message); process.exit(1); });
