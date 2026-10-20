const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch();
  const p = await (await b.newContext({ viewport: { width: 1280, height: 940 } })).newPage();
  await p.goto('http://localhost:3000?agent=sasa', { waitUntil: 'networkidle' });
  await p.waitForTimeout(2500);
  // 🚀 إرسال للماكينة على طلب زينب
  await p.locator('button', { hasText: 'إرسال للماكينة' }).first().click();
  await p.waitForTimeout(6000);
  const f1 = await p.locator('[role="status"]').textContent().catch(() => 'no-flash');
  console.log('LAUNCH:', f1);
  // 🔧 صيانة: Cooling Check لليزر
  await p.locator('button', { hasText: 'Cooling Check' }).first().click();
  await p.waitForTimeout(6000);
  const f2 = await p.locator('[role="status"]').textContent().catch(() => 'no-flash');
  console.log('MAINT:', f2);
  await p.screenshot({ path: 'G:/ai/Naggar Print POS Agent/tsmym-wajht-marwa-core/.shots/sasa-room.png' });
  await b.close();
  console.log('SASA E2E OK');
})().catch(e => { console.error('SASA FAIL:', e.message); process.exit(1); });
