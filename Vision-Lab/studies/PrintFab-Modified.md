# 🏗️ ملخص معماري: PrintFab_Modified

> دراسة «قراءة أسماء وتوثيق فقط — بلا فكّ ثنائيات» · وكيل المذاكرة المعمارية «فيجن» · 2026-10-18 · الجاهزية: 90%

## 1) الهوية والإصدار
- **المنتج**: **PrintFab for Windows** — نظام طباعة/إدارة ألوان احترافي (RIP-style) من **ZEDOnet GmbH** — 87660 Irsee، ألمانيا (عنوانان في التوثيق: Sedanstraße 8 في RTF، وMeinrad-Spieß-Platz 2 في نص locale — تعديلان لعنوان الشركة عبر السنوات).
- **الصلة العائلية**: نواة `tpprint.exe` وبطاقات `.tpp` وقوائم `[Turboprint_Printer_List]` من عائلة **TurboPrint** (الشقيق اللينكس لنفس الشركة) — نص الترخيص الداخلي ما زال يحمل «TurboPrint ©2008».
- **إصدارات موثقة من ميتاداتا الملفات**: PrintFab Printjob Monitor `2.0.0.0` · PrintFab API DLL `1.0.12.2` · Qt `5.15.2` · DynaPDF `4.0.73.213`.
- **رقم الإصدار الكلي**: غير معلن في ميتاداتا `PrintFab.exe` (بلا Version Resource). القرائن (كتيبات PDF 2025-06، نواة 2026-03-25، إلغاء التثبيت 2026-05-06) ⇒ سلسلة PrintFab 2.x حديثة — تقدير وليس رقمًا مؤكدًا.
- **نموذج الترخيص**: Trial بلا قيود 30 يومًا ثم يُطبع «شعار PrintFab» على كل طباعة؛ التحويل للنسخة الكاملة بمفتاح من printfab.com — وفي هذه النسخة توجد صيغة **«PrintFab Free Edition»** داخل نصوص الواجهة (وضع تجريبي لبعض أنماط الطباعة).
- **بصمة «Modified»**: مجلد تثبيت كامل منقول بلا مثبت + تعديلات بيانات موثقة بتواريخ (تفصيل في §4): جداول ألوان Epson P5000/R3000/ET-8550، قائمة الطابعات، نصوص الواجهة، وتعريفات مخصصة باسم `_RIP` و`_piezography`.

## 2) الغرض
- طبقة طباعة احترافية تعمل بجانب/فوق سواقات Windows: تحكم كامل بالألوان (ملفات تعريف لكل طابعة+حبر+ورق)، معاينة + **محرر تخطيط (Layout Editor)** للصفحات المتعددة على ورقة واحدة، أدوات صيانة الرؤوس (Nozzle check/Clean/Align)، وتحكم بحبر لكل قناة.
- **دوره في ورشة «النجار برنت»**: تحويل الطباعة الفنية/الفوتوغرافية على طابعات Epson عريضة التنسيق إلى تدريب مضبوط — والأدلة (.tpm المعدلة على P5000/R3000 أوضاع Matte/Photo Black) تشير إلى طباعة Fine-Art بتحكم دقيق في الأسود.

## 3) الهيكل
مجلد تثبيت جاهز للتشغيل (1069 ملفًا، ~200MB، بلا مثبت):
- **الجذر**: 5 تطبيقات/أدوات + مكتبات Qt5/DynaPDF/VC++ + 4 تراخيص RTF + كتيب PDF (EN/DE) + `ghostscript.ini` + `create-logfile.bat` + `ziptool.exe`.
- `printers\` 542 · `colors\` 155 · `dump\` 113 · `html_en\` 69 · `html_de\` 77 · `locale\` 17 · `translations\` 23 · `profiles\` 5 · `win_x64\`/`win32x86\`/`win_arm64\` 6 لكل معمارية · `ps_plugin\` 2 · `plugins\` (Qt: imageformats/platforms/styles).

## 4) المكونات
| المكون | الدور | القرينة |
|---|---|---|
| `PrintFab.exe` (2.9MB) | الواجهة الرسومية Qt5: حوار طباعة بتبويبات Main/Layout/Color/Correction/Consumption/Ink Ctrl/Options | دليل HTML فصل 9 |
| `tpprint.exe` (1.6MB) | نواة محرك الطباعة (تراث TurboPrint) | الاسم + بطاقات .tpp |
| `printfabservice.exe` | خدمة خلفية | الاسم؛ نواة 2026-03 |
| `PrintFabPreview.exe` (5.9MB) | معاينة الوظيفة + Layout Editor | دليل فصل 10 |
| `PrintFabMonitor.exe` v2.0.0.0 | مراقب وظائف الطباعة | ميتاداتا |
| `printapi(64).dll` v1.0.12.2 | API برمجي (تكامل خارجي/أتمتة) | ميتاداتا «PrintFab API DLL» |
| `pspfdrv.dll/.ini/.xml` + `pspfui.dll` + `zedoport.dll` + `zedomon010.dll` | سواقة OEM لثلاث معمارات (x64/x86/ARM64) + مراقب منافذ + قناة BIDI | ملفات win_* |
| `dynapdf.dll` | معالجة/معاينة PDF | DynaPDF 4.0.73.213 |
| `ghostscript.ini` | ربط Ghostscript عبر `HKLM\SOFTWARE\GPL Ghostscript\zedo` | قراءة الملف |
| `printers\` 537×`.tpp` + `printers.lst` (3886 سطرًا، بنية `[Model] Number=<رقم>,"<رمز مُعمّى>"` + `Driver=` مستعار) | تعريفات الطابعات: **Epson×216**، Canon×211، HP×93، Brother×14، + عائلات خاصة | أسماء + قراءة جزئية |
| `colors\` 150×`.tpm` + 5×`.bak` | جداول حبر/لون لكل خزان (BCI/BJC=Canon وEpson) | أسماء + تواريخ .bak |
| `profiles\` | ICC قياسية (AdobeRGB1998, ISOcoated_v2_eci) + تراخيصها PDF | أسماء |
| `ps_plugin\*.8be` | إضافة Photoshop 32/64 بت | امتداد 8be |
| `dump\` 107×`.prn` + `.ps/.pcx` | صفحات محاذاة/اختبار خام (Brother b*, HP dj*) | أسماء |
| `html_en/de\` | دليل كامل 12 فصلًا | index.html |
| `license-*.rtf` ×4 + `locale\license_*.txt` | EULA EN/FR/DE/ES | قراءة EN |

### بصمات التعديل (لماذا «Modified»)
1. **جداول ألوان Epson معدلة**: `ET8550.tpm.bak` (2023) · `P5000matteblk/photoblk.tpm.bak` (2026-02-20) · `R3000matteblk/photoblk.tpm.bak` (2026-01-28) — أحدث التعديلات تستهدف **أوضاع الحبر الأسود** لطابعتين فنيتين.
2. **تعريفات مضافة/مشتقة بالأسماء**: `Epson_EcoTank_ET8550_piezography.tpp` و`*_RIP.tpp` (ET8550, SureColor P700, P900) — تسميات غير قياسية في الحزمة الأصلية (نمط ملفات مجتمع/ضبط فني: Piezography وحبيبات RIP مخصصة).
3. `printers.lst.bak` (2025-03) — قائمة الطابعات عدلت (بنية الملف تسمح بإضافة طراز بأسطر 4: الاسم/الرقم/السواقة).
4. `printfab_en/de.loc.bak` (2025-02) — تعديل نصوص واجهة (`.loc` جداول نصية `key=value` وليست ثنائية).
5. مزيج تواريخ بناء متدرجة 2020→2026 مع نواة موحدة 2026-03-25 = تثبيت حديث مركّب على قاعدة أقدم + ترقيات.

## 5) التكاملات (مع الطابعات/الورشة)
- **الطابعات**: سواقة OEM بثلاث معمارات + `zedoport.dll` (منفذ طباعة) + `zedomon010.dll` (مراقب) + `pspfdrv.xml` (BIDI): يقرأ حالة الطابعة ومستويات الحبر عبر SNMP/IEEE1284.4 — ومنه **OID Epson المخصص (1.3.6.1.4.1.1248)** = قراءة مباشرة من طابعات Epson.
- **Ghostscript** (GPL V3، مثبت منفصل): `ghostscript.ini` يقرأ مساره من Registry (`SOFTWARE\GPL Ghostscript\zedo`) — معالجة PDF/PS.
- **Adobe**: إضافة فوتوشوب `psplugin64.8be` (والدليل فيه فصول لـ Photoshop/CorelDraw/InDesign/PDF).
- **إخراج ملفات**: سواقات `Image_PPM`/`Image_TIFF` (طباعة إلى ملف صورة) + `Universal_Windows` (طابعة عامة).
- **الورشة «النجار برنت»**: جداول معدلة لـ **SureColor P5000، Stylus Photo R3000، EcoTank ET-8550** (فنّي/فوتوغرافي) + سواقة Epson واسعة (P400–P900، StylusPro 3800–7890، T-series بلوتر، F-series سَبلايمايشن، EcoTank) + Toolbox صيانة رؤوس + محرر مقاسات مخصصة (مفيد لألواح/مقاسات غير قياسية) + `printapi` لأتمتة الطباعة من نظام الطلبات مستقبلًا.

## 6) تقييم الصحة
- تثبيت مكتمل ومتماسك: تطبيق + خدمة + سواقات + قواعد طابعات/ألوان + توثيق HTML/PDF + إزالة تثبيت + جامع سجلات.
- ممارسة تعديل منضبطة: كل تعديل ترك أصلًا `.bak` بجانبه.
- **تحفظات**: (1) EULA يحظر صراحة تعديل البرنامج وإعادة توزيعه — التعديلات الحالية على مستوى بيانات الطباعة (سلوك شائع للمعايرة، لكنه خارج الترخيص حرفيًا). (2) لا يظهر ملف مفتاح ترخيص في الجذر؛ إن كانت النسخة بلا مفتاح فهي Trial/Free Edition يطبع شعارًا — الحالة الفعلية لا تُثبت من الأسماء وحدها. (3) `Uninstall.exe` أحدث من النواة (2026-05 مقابل 2026-03) — حدث تثبيت/تحديث لاحق.

## 7) خريطة دخول
- **واجهة**: `PrintFab.exe` → حوارات الطباعة (Main/Layout/Color/Correction/Consumption/Ink Ctrl) عبر Qt5.
- **محرك**: `tpprint.exe` + بطاقات `printers\*.tpp` + جداول `colors\*.tpm` → سواقة OEM → الطابعة.
- **الخدمة والمراقبة**: `printfabservice.exe` + `PrintFabMonitor.exe` + `printapi(64).dll` (API خارجي).
- **أدوات**: PrintFab Control Center (إدارة الطابعات)، Printer Toolbox (فحوصات الرؤوس)، Print Preview/Layout Editor، محرر مقاسات مخصصة، إدارة Profiles (بما فيها إنشاء ICC بمقياس طيفي).
- **دعم**: `create-logfile.bat` → `ziptool.exe` (حزمة سجلات للدعم)؛ مرجع صفحات المحاذاة في `dump\`.

## 8) فهرس مختصر
- `G:\ai\PrintFab_Modified\` — 13 مجلدًا، 1069 ملفًا، ~200MB.
- أهم المسارات: `printers\printers.lst` (فهرس كل الطابعات) · `colors\*.tpm` (جداول الحبر) · `profiles\*.icc` · `html_en\index.html` (دليل 12 فصلًا) · `win_x64\` (سواقة 64بت) · `ps_plugin\` (فوتوشوب).
- توثيق متاح: كتيب PDF EN/DE (2025-06) + دليل HTML EN/DE + تراخيص.

## 9) سجل القراءة (10/10 — الميزانية اكتملت)
1. `ghostscript.ini` ✅ (ربط Ghostscript عبر Registry `…\GPL Ghostscript\zedo`)
2. `create-logfile.bat` ✅ (جامع سجلات دعم → ziptool)
3. `locale\license_en.txt` ✅ (ZEDOnet GmbH / TurboPrint 2008 / Demo 30 يوم)
4. `win_x64\pspfdrv.ini` ✅ (تعريف ملفات OEM driver)
5. `win_x64\pspfdrv.xml` ✅ (BIDI: حالة الطابعة/الحبر + OID Epson 1.3.6.1.4.1.1248)
6. `html_en\index.html` ✅ (فهرس الدليل: 12 فصلًا — Toolbox/Profiles/Layout Editor/التطبيقات)
7. `html_en\1-.html` ✅ (شروط الترخيص: Trial 30 يوم + حظر التعديل)
8. `printers\printers.lst` (جزء أول) ✅ (بنية `[Model] Number=…,"رمز مُعمّى"` + `Driver=`)
9. `license-english.rtf` (جزء أول) ✅ («PrintFab for Windows»، ZEDOnet GmbH، Ghostscript GPL V3 خارجي، Qt LGPL)
10. `locale\printfab_en.loc` (جزء أول) ✅ (نصوص واجهة نصية `key=value` — تذكر «PrintFab Free Edition» + DEMO MODE)
- استُبعد: `locale\languages.loc` (ليس UTF-8 — اعتُبر ثنائيًا/ترميزًا خاصًا ولم يُفتح).

## 10) الفجوات وحدود الدراسة
- رقم الإصدار الرئيسي غير مثبت رقميًا (لا Version Resource على PrintFab.exe؛ التقدير 2.x من تواريخ 2025–2026). يظهر داخل التطبيق (Control Center → About) أو في Registry.
- لم تُفتح: PDF (كتيب)، `.tpm/.tpp` (بنية خاصة)، `.qm`، ملفات `.loc` الأخرى، محتوى `.prn`.
- حالة الترخيص الفعلية (مفتاح كامل/تجريبي) غير قابلة للتأكيد من الأسماء وحدها.
- لم يُقارن `printers.lst` مع `.bak` لاستخراج قائمة الإضافات بالضبط (التكلفة تتجاوز الميزانية) — لكن أسماء `*_RIP/_piezography` تثبت إضافات مخصصة.

## 11) توصيات عملية للورشة
1. **ارفع نسخة احتياطية فورًا** من `colors\` و`printers\` و`locale\` (مع ملفات `.bak`) — ساعات معايرة مكثفة مخزنة في هذه الملفات.
2. أي تحديث مستقبلي من ZEDOnet سيستبدل `.tpm/.tpp/.lst` — وثّق التعديلات (أي طراز/أي تغيير) قبل الترقية.
3. تحقق من حالة الترخيص من داخل الواجهة (بلا مفتاح: شعار على كل طباعة بعد 30 يومًا).
4. بطاقات `*_RIP.tpp` و`ET8550_piezography.tpp` غير قياسية — اسأل مصدر النسخة عن مصدرها قبل الاعتماد عليها في عمل مدفوع.
5. عند شراء طابعة جديدة: ابحث عن `.tpp` لها في `printers\` أولًا (216 تعريف Epson بينها P700/P900/P5000/T-series).
6. توثيق التعديلات في ملف نصي بجانب كل `.tpm` معدل (تاريخ/سبب/قيم) — التواريخ الحالية هي الدليل الوحيد.
