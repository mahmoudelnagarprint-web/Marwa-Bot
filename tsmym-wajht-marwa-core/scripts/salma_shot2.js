const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch();
  const p = await (await b.newContext({ viewport: { width: 1280, height: 940 } })).newPage();
  await p.goto('http://localhost:3000?agent=salma', { waitUntil: 'networkidle' });
  await p.waitForTimeout(2200);
  await p.getByText('جدول نواقص الإنتاج').click();
  await p.waitForTimeout(700);
  await p.getByRole('button', { name: /استعجال بيبو/ }).first().click();
  await p.waitForTimeout(6000);
  await p.screenshot({ path: 'G:/ai/Naggar Print POS Agent/tsmym-wajht-marwa-core/.shots/salma-shortages-rush.png' });
  await b.close();
  console.log('SHOT2 OK');
})().catch(e => { console.error('SHOT2 FAIL:', e.message); process.exit(1); });
