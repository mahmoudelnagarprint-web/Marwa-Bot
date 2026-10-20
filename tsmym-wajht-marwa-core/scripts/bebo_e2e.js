const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch();
  const p = await (await b.newContext({ viewport: { width: 1280, height: 940 } })).newPage();
  await p.goto('http://localhost:3000?agent=bebo', { waitUntil: 'networkidle' });
  await p.waitForTimeout(2500);
  // انقل زينب #328: design → printing (زر '→ قيد و' في كارت #328)
  await p.locator('button', { hasText: '→ قيد' }).first().click();
  await p.waitForTimeout(4500);
  const flash1 = await p.locator('[role="status"]').textContent().catch(() => 'no-flash');
  console.log('FLASH1:', flash1);
  // ثم printing → ready (يجب أن يُطلق summon لسلمى)
  await p.locator('button', { hasText: '→ جاهز' }).first().click();
  await p.waitForTimeout(7000);
  const flash2 = await p.locator('[role="status"]').textContent().catch(() => 'no-flash');
  console.log('FLASH2:', flash2);
  // ✅ تم التنفيذ على مهمة زينب في صندوق الوارد
  await p.locator('button', { hasText: 'تم التنفيذ' }).first().click();
  await p.waitForTimeout(6000);
  const flash3 = await p.locator('[role="status"]').textContent().catch(() => 'no-flash');
  console.log('FLASH3:', flash3);
  await p.screenshot({ path: 'G:/ai/Naggar Print POS Agent/tsmym-wajht-marwa-core/.shots/bebo-e2e.png' });
  await b.close();
  console.log('E2E DONE');
})().catch(e => { console.error('E2E FAIL:', e.message); process.exit(1); });
