/**
 * Marwa Core Workspace — Client half: غرفة عمليات مروة (الهيكل الرباعي).
 *
 * الش
 *   1) Omni-Bar (شريط سيادي علوي): أمر سريع Ctrl+K + مؤشر NB2 + رام حي + عقدة
 *   2) Agent Dock (رصيف الكتيبة يمين): مجموعات × وكلاء مع شارات حالة حية
 *   3) Workspace (مساحة العمليات وسط): غرف محادثة، Scratchpad، @/ #، أزرار سريعة، بوابات اعتماد
 *   4) Omni-Inspector (درج يسار): أفكاري / مرسم فيجين / السياق الحي
 *
 * الهوية: أسود مطفي #09090b + ذهبي ملكي #d4af37 + خط Cairo + توقيع لوني لكل وكيل.
 * البيانات: جسر POST /marwa-core/api (يوفره نصف المضيف في index.js).
 */
window.__ModuleLoader__.load({
  id: '@local/marwa-core-workspace',
  factory(require) {
    const React = require('react');
    const h = React.createElement;
    const { useState, useEffect, useRef, useCallback, useMemo, Component } = React;

    const ROUTE = '/api/marwa-core';

    // ------------------------------------------------------------------- سجل الكتيبة (من المسح الذاتي 2026-10-26)
    const GROUPS = [
      { id: 'lead', name: 'القيادة والذاكرة', icon: '👑' },
      { id: 'wisdom', name: 'الحكمة والرصد', icon: '🧠' },
      { id: 'ops', name: 'التشغيل والإنتاج', icon: '🏭' },
      { id: 'gear', name: 'العتاد والدعم', icon: '🖥️' },
    ];
    const AGENTS = [
      { id: 'marwa', name: 'مروة', nick: 'المايسترو', emoji: '🧠', role: 'المنسق العام (الوكيل الأصلي)', group: 'lead', color: '#d4af37', triggers: ['يا مروة', 'يا مروه', 'يا مرو8'], prompt: 'AGENT.md', chips: [
        { label: 'حالة المشروع', text: 'يا مروة اقرأ STATUS.md واذكر أهم 3 بنود' },
        { label: 'تقرير الإيقاظ', text: 'يا مروة جهزي تقرير الإيقاظ الصباحي' },
        { label: 'كلّف وكيل', text: 'يا مروة كلّف الوكيل المناسب لـ: ' },
      ] },
      { id: 'afkar', name: 'أفكاري', nick: 'فوفا · Notebook v2', emoji: '📓', role: 'الذاكرة الثانية ومركز القيادة الموحد', group: 'lead', color: '#e879f9', triggers: ['يا أفكار', 'فوفا'], prompt: 'Vision-Lab/projects/notebook-v2/NB2_CHAT_BOOTSTRAP_PROMPT.md', external: true, chips: [
        { label: 'نوت جديد', text: 'يا أفكار سجّل نوت: ' },
        { label: 'مناداة الفريق', text: 'يا أفكار نادي الفريق واعمل ملخص' },
        { label: 'قائمتي', text: 'يا أفكار قائمتي' },
      ] },
      { id: 'rased', name: 'راصد', nick: 'المراقب الذاتي', emoji: '📊', role: 'سجل الخبرة والأداء والدروس', group: 'wisdom', color: '#a78bfa', triggers: ['يا راصد', 'راصد'], prompt: 'orchestrator/squad/rased/CHAT_BOOTSTRAP_PROMPT.md', chips: [
        { label: 'تقرير الأداء', text: 'يا راصد تقرير الأداء' },
        { label: 'سجل الخبرة', text: 'يا راصد آخر الاستدعاءات' },
        { label: 'اقتراحات التطوير', text: 'يا راصد اقتراحات التطوير' },
      ] },
      { id: 'hakim', name: 'حكيم', nick: 'طبيب البيانات', emoji: '🩺', role: 'البيانات والتطابق والإكسيل', group: 'wisdom', color: '#fb923c', triggers: ['يا حكيم'], prompt: 'orchestrator/squad/hakim/CHAT_BOOTSTRAP_PROMPT.md', chips: [
        { label: 'فحص سريع', text: 'يا حكيم اعمل فحص سريع' },
        { label: 'الروتين الصباحي', text: 'يا حكيم الروتين الصباحي' },
        { label: 'صنف المنتجات', text: 'يا حكيم صنف المنتجات' },
      ] },
      { id: 'fares', name: 'فارس', nick: 'المدير المالي', emoji: '💼', role: 'الخزينة والديون والربحية', group: 'ops', color: '#38bdf8', triggers: ['يا فارس'], prompt: 'orchestrator/squad/fares/CHAT_BOOTSTRAP_PROMPT.md', chips: [
        { label: 'الخزينة', text: 'يا فارس الخزينة كام؟' },
        { label: 'المديونيات', text: 'يا فارس المديونيات' },
        { label: 'مصروفات الشيفت', text: 'يا فارس مصروفات الشيفت' },
      ] },
      { id: 'salma', name: 'سلمى', nick: 'علاقات العملاء', emoji: '🤝', role: 'العملاء والطلبيات والمتابعة', group: 'ops', color: '#fb7185', triggers: ['يا سلمى'], prompt: 'orchestrator/squad/salma/CHAT_BOOTSTRAP_PROMPT.md', chips: [
        { label: 'المتأخر', text: 'يا سلمى الطلبات المتأخرة' },
        { label: 'الجاهز', text: 'يا سلمى الجاهز للتسليم' },
        { label: 'طلبات اليوم', text: 'يا سلمى طلبات اليوم' },
      ] },
      { id: 'koko', name: 'كوكو', nick: 'التسويق', emoji: '🎯', role: 'العروض والباقات والبوستات', group: 'ops', color: '#34d399', triggers: ['يا كوكو', 'كوكو'], prompt: 'orchestrator/squad/koko/CHAT_BOOTSTRAP_PROMPT.md', chips: [
        { label: 'اقترح باقة', text: 'يا كوكو اقترح باقة' },
        { label: 'المنتجات الراكدة', text: 'يا كوكو المنتجات الراكدة' },
        { label: 'بوست 3-in-1', text: 'يا كوكو جهز بوست 3-in-1 لـ: ' },
      ] },
      { id: 'bibo', name: 'بيبو', nick: 'التصنيع والليزر', emoji: '🏭', role: 'الخامات وحسابات الليزر', group: 'ops', color: '#fbbf24', triggers: ['يا بيبو', 'بيبو'], prompt: 'orchestrator/squad/bibo/CHAT_BOOTSTRAP_PROMPT.md', chips: [
        { label: 'احسب ليزر', text: 'يا بيبو احسب ليزر 30 40' },
        { label: 'الخامات', text: 'يا بيبو الخامات' },
        { label: 'بطاقة شغل', text: 'يا بيبو بطاقة شغل لـ: ' },
      ] },
      { id: 'sasa', name: 'مصطفى', nick: 'صاصا', emoji: '🖥️', role: 'التحكم بالكمبيوتر والماكينات', group: 'gear', color: '#2dd4bf', triggers: ['يا صاصا', 'يا مصطفى', 'صاصا'], prompt: 'orchestrator/squad/sasa/CHAT_BOOTSTRAP_PROMPT.md', chips: [
        { label: 'لقطة شاشة', text: 'يا صاصا صوّر الشاشة' },
        { label: 'حالة الجهاز', text: 'يا صاصا حالة الجهاز' },
        { label: 'افتح برنامج', text: 'يا صاصا افتح: ' },
      ] },
      { id: 'vision', name: 'فيجن', nick: 'الكودر', emoji: '👨‍💻', role: 'التطوير والبرمجة — معمله Vision-Lab', group: 'gear', color: '#818cf8', triggers: ['يا فيجن', 'يا فجن', 'فيجن', 'vision'], prompt: 'Vision-Lab/SQUAD_BOOTSTRAP_PROMPT.md', external: true, chips: [
        { label: 'راجع الكود', text: 'يا فيجن راجع الكود' },
        { label: 'حالة Git', text: 'يا فيجن حالة الـ Git' },
        { label: 'رصد الأخطاء', text: 'يا فيجن رصد الأخطاء من سجل الخبرة' },
      ] },
    ];
    const AGENT_MAP = {};
    AGENTS.forEach((a) => { AGENT_MAP[a.id] = a; });
    // خريطة غرفة ← Preset DSH (أسماء الـPresets الحية المسجلة من المضيف عند الإقلاع)
    const PRESET_ID_MAP = { marwa: 'marwa', afkar: 'notebook', rased: 'rased', hakim: 'hakim', fares: 'fares', salma: 'salma', koko: 'koko', bibo: 'bibo', sasa: 'sasa', vision: 'vision' };

    // ------------------------------------------------------------------- الأنماط (الهوية السيادية)
    const CSS = [
      '.mcw-root{position:relative;display:flex;flex-direction:column;height:100%;min-height:0;background:radial-gradient(1200px 600px at 85% -10%,rgba(212,175,55,.07),transparent 60%),linear-gradient(180deg,#0d0d11 0%,#09090b 100%);color:#ece7da;font-family:"Cairo","Tajawal","Segoe UI",Tahoma,Arial,sans-serif;direction:rtl;overflow:hidden}',
      '.mcw-root *{box-sizing:border-box}',
      '.mcw-omni{display:flex;align-items:center;gap:10px;padding:8px 14px;background:rgba(20,20,26,.92);border-bottom:1px solid rgba(212,175,55,.22);flex:none;z-index:5}',
      '.mcw-brand{display:flex;align-items:center;gap:10px;min-width:190px}',
      '.mcw-brand-mark{width:34px;height:34px;border-radius:9px;background:linear-gradient(135deg,#d4af37,#8a6d1f);display:flex;align-items:center;justify-content:center;font-size:18px;box-shadow:0 0 14px rgba(212,175,55,.35)}',
      '.mcw-brand-name{font-size:15px;font-weight:800;letter-spacing:.5px;color:#f2e7c3;line-height:1.1}',
      '.mcw-brand-sub{font-size:10px;color:rgba(236,231,218,.5)}',
      '.mcw-cmd{flex:1;display:flex;align-items:center;gap:8px;background:rgba(9,9,11,.72);border:1px solid rgba(212,175,55,.28);border-radius:10px;padding:7px 12px;color:rgba(236,231,218,.55);cursor:pointer;font-family:inherit;font-size:13px;min-width:120px}',
      '.mcw-cmd kbd{background:rgba(212,175,55,.16);color:#d4af37;border-radius:5px;padding:1px 6px;font-size:11px;border:1px solid rgba(212,175,55,.35)}',
      '.mcw-chip{display:inline-flex;align-items:center;gap:6px;border:1px solid rgba(212,175,55,.25);background:rgba(212,175,55,.07);border-radius:999px;padding:4px 10px;font-size:11px;color:#e9ddb6;white-space:nowrap}',
      '.mcw-dot{width:8px;height:8px;border-radius:50%;display:inline-block}',
      '.mcw-rambar{width:44px;height:4px;border-radius:2px;background:rgba(255,255,255,.12);overflow:hidden}',
      '.mcw-rambar>i{display:block;height:100%;background:linear-gradient(90deg,#d4af37,#f2e7c3)}',
      '.mcw-body{display:flex;flex:1;min-height:0}',
      '.mcw-drawer{width:330px;min-width:280px;display:flex;flex-direction:column;background:rgba(13,13,18,.96);border-left:1px solid rgba(212,175,55,.16);font-size:12px}',
      '.mcw-tabs{display:flex;border-bottom:1px solid rgba(212,175,55,.18)}',
      '.mcw-tab{flex:1;padding:9px 4px;background:transparent;border:none;border-bottom:2px solid transparent;color:rgba(236,231,218,.55);font-family:inherit;font-size:11.5px;cursor:pointer}',
      '.mcw-tab.on{color:#f2e7c3;border-bottom-color:#d4af37;background:rgba(212,175,55,.06)}',
      '.mcw-tabpane{flex:1;overflow:auto;padding:10px}',
      '.mcw-center{flex:1;min-width:0;display:flex;flex-direction:column;min-height:0}',
      '.mcw-roomhead{display:flex;align-items:center;gap:12px;padding:10px 16px;border-bottom:1px solid rgba(255,255,255,.08);background:linear-gradient(90deg,color-mix(in srgb,var(--mcw-accent,#d4af37) 12%,transparent),transparent)}',
      '.mcw-roomhead .mcw-emoji{width:38px;height:38px;border-radius:10px;background:color-mix(in srgb,var(--mcw-accent,#d4af37) 16%,#101014);display:flex;align-items:center;justify-content:center;font-size:20px;box-shadow:0 0 12px color-mix(in srgb,var(--mcw-accent,#d4af37) 45%,transparent)}',
      '.mcw-roomhead h2{margin:0;font-size:16px;font-weight:800;color:#f2e7c3}',
      '.mcw-roomhead small{color:rgba(236,231,218,.55)}',
      '.mcw-roomacts{margin-inline-start:auto;display:flex;gap:6px}',
      '.mcw-btn{background:rgba(212,175,55,.12);border:1px solid rgba(212,175,55,.35);color:#ecd58a;border-radius:8px;padding:5px 10px;font-size:11px;font-family:inherit;cursor:pointer}',
      '.mcw-btn:hover{background:rgba(212,175,55,.22)}',
      '.mcw-btn.ghost{background:transparent;border-color:rgba(255,255,255,.16);color:rgba(236,231,218,.7)}',
      '.mcw-msgs{flex:1;overflow:auto;padding:14px 16px;display:flex;flex-direction:column;gap:10px}',
      '.mcw-msg{max-width:88%;border-radius:12px;padding:8px 12px;border:1px solid rgba(255,255,255,.07);font-size:13px;line-height:1.65;white-space:pre-wrap;word-break:break-word;background:rgba(255,255,255,.045)}',
      '.mcw-msg.me{align-self:flex-start;background:rgba(212,175,55,.10);border-color:rgba(212,175,55,.3)}',
      '.mcw-msg.agent{align-self:flex-end;border-inline-start:3px solid var(--mcw-accent,#d4af37)}',
      '.mcw-msg .who{font-size:10.5px;font-weight:700;color:var(--mcw-accent,#d4af37);margin-bottom:3px}',
      '.mcw-msg table{border-collapse:collapse;width:100%;margin:6px 0;font-size:11.5px}',
      '.mcw-msg th,.mcw-msg td{border:1px solid rgba(255,255,255,.14);padding:3px 7px;text-align:start}',
      '.mcw-msg th{background:rgba(212,175,55,.12)}',
      '.mcw-msg code{background:rgba(9,9,11,.6);border:1px solid rgba(255,255,255,.08);border-radius:5px;padding:1px 5px;font-size:11.5px;direction:ltr;display:inline-block}',
      '.mcw-msg pre{background:rgba(9,9,11,.8);border:1px solid rgba(212,175,55,.2);border-radius:8px;padding:8px;overflow:auto;direction:ltr;text-align:left}',
      '.mcw-scratch{margin:0 16px 8px;border:1px dashed rgba(212,175,55,.35);border-radius:10px;background:rgba(9,9,11,.55)}',
      '.mcw-scratch summary{cursor:pointer;padding:6px 10px;font-size:11px;color:#ecd58a;font-weight:700}',
      '.mcw-scratch textarea{width:100%;min-height:56px;background:rgba(9,9,11,.6);border:none;color:#ece7da;padding:8px 10px;font-family:inherit;font-size:12px;resize:vertical}',
      '.mcw-chips{display:flex;gap:6px;padding:0 16px 8px;flex-wrap:wrap}',
      '.mcw-composer{border-top:1px solid rgba(212,175,55,.18);padding:8px 16px;display:flex;gap:8px;align-items:flex-end;background:rgba(13,13,18,.9)}',
      '.mcw-composer textarea{flex:1;min-height:46px;max-height:130px;background:rgba(9,9,11,.7);border:1px solid rgba(212,175,55,.28);border-radius:10px;color:#ece7da;padding:9px 12px;font-family:inherit;font-size:13px;resize:vertical}',
      '.mcw-composer textarea:focus{outline:none;border-color:#d4af37}',
      '.mcw-send{background:linear-gradient(135deg,#d4af37,#b8922c);border:none;color:#09090b;font-weight:800;border-radius:10px;padding:10px 16px;cursor:pointer;font-family:inherit;font-size:13px}',
      '.mcw-dock{width:224px;min-width:190px;display:flex;flex-direction:column;background:rgba(13,13,18,.96);border-right:1px solid rgba(212,175,55,.16);overflow:auto;font-size:12px;padding:8px}',
      '.mcw-group-title{font-size:11px;font-weight:800;color:#d4af37;margin:10px 4px 5px;display:flex;align-items:center;gap:6px}',
      '.mcw-agent{display:flex;align-items:center;gap:8px;padding:6px 8px;border-radius:9px;cursor:pointer;border:1px solid transparent}',
      '.mcw-agent:hover{background:rgba(255,255,255,.05)}',
      '.mcw-agent.on{background:color-mix(in srgb,var(--mcw-accent,#d4af37) 10%,transparent);border-color:color-mix(in srgb,var(--mcw-accent,#d4af37) 45%,transparent)}',
      '.mcw-agent .dot{width:9px;height:9px;border-radius:50%;box-shadow:0 0 8px var(--mcw-accent,#d4af37);flex:none}',
      '.mcw-agent .nm{flex:1;min-width:0}',
      '.mcw-agent .nm b{display:block;font-size:12.5px;color:#f2e7c3}',
      '.mcw-agent .nm span{font-size:10px;color:rgba(236,231,218,.5);display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}',
      '.mcw-badge{background:#d4af37;color:#09090b;border-radius:999px;min-width:18px;height:18px;display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:800;padding:0 5px}',
      '.mcw-badge.think{background:transparent;border:1px solid var(--mcw-accent,#d4af37);color:var(--mcw-accent,#d4af37)}',
      '.mcw-approval{border:1px solid rgba(212,175,55,.4);border-radius:12px;background:linear-gradient(180deg,rgba(212,175,55,.07),rgba(9,9,11,.5));padding:12px;max-width:92%}',
      '.mcw-approval h4{margin:0 0 6px;color:#f2e7c3;font-size:13px}',
      '.mcw-approval .det{font-size:12px;color:rgba(236,231,218,.8);white-space:pre-wrap}',
      '.mcw-approval .acts{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}',
      '.mcw-approve{background:linear-gradient(135deg,#2e7d32,#1b5e20);border:1px solid #4caf50;color:#d7ffd9;border-radius:8px;padding:6px 10px;font-size:11.5px;font-weight:700;cursor:pointer;font-family:inherit}',
      '.mcw-editb{background:rgba(212,175,55,.14);border:1px solid rgba(212,175,55,.4);color:#ecd58a;border-radius:8px;padding:6px 10px;font-size:11.5px;cursor:pointer;font-family:inherit}',
      '.mcw-audit{background:rgba(122,93,246,.14);border:1px solid #7a5df6;color:#cbbbfe;border-radius:8px;padding:6px 10px;font-size:11.5px;cursor:pointer;font-family:inherit}',
      '.mcw-savenote{background:rgba(232,121,249,.12);border:1px solid #e879f9;color:#f6d3fb;border-radius:8px;padding:6px 10px;font-size:11.5px;cursor:pointer;font-family:inherit}',
      '.mcw-palette{position:absolute;top:64px;inset-inline:10%;z-index:50;background:#101014;border:1px solid rgba(212,175,55,.4);border-radius:14px;box-shadow:0 18px 60px rgba(0,0,0,.6);overflow:hidden}',
      '.mcw-palette input{width:100%;background:transparent;border:none;color:#f2e7c3;padding:14px 16px;font-size:14px;font-family:inherit;outline:none}',
      '.mcw-palette .res{max-height:340px;overflow:auto;border-top:1px solid rgba(255,255,255,.08)}',
      '.mcw-palette .row{display:flex;gap:8px;align-items:center;padding:8px 14px;cursor:pointer;font-size:12.5px}',
      '.mcw-palette .row:hover{background:rgba(212,175,55,.09)}',
      '.mcw-note{border:1px solid rgba(255,255,255,.08);border-radius:9px;padding:7px 9px;margin-bottom:6px;background:rgba(255,255,255,.03)}',
      '.mcw-note b{font-size:12px;color:#f2e7c3;display:block}',
      '.mcw-note p{margin:3px 0;font-size:11px;color:rgba(236,231,218,.65);white-space:pre-wrap;max-height:64px;overflow:hidden}',
      '.mcw-note .meta{font-size:9.5px;color:rgba(236,231,218,.4)}',
      '.mcw-grid{display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-bottom:8px}',
      '.mcw-kart{border:1px solid rgba(212,175,55,.25);border-radius:9px;padding:6px 8px;background:rgba(212,175,55,.05)}',
      '.mcw-kart b{display:block;font-size:15px;color:#f2e7c3}',
      '.mcw-kart span{font-size:9.5px;color:rgba(236,231,218,.5)}',
      '.mcw-tbl{width:100%;border-collapse:collapse;font-size:10.5px;margin:6px 0}',
      '.mcw-tbl th,.mcw-tbl td{border:1px solid rgba(255,255,255,.12);padding:2px 5px;text-align:start;white-space:nowrap}',
      '.mcw-tbl th{background:rgba(212,175,55,.1);color:#ecd58a}',
      '.mcw-vgrid{display:grid;grid-template-columns:1fr 1fr;gap:6px}',
      '.mcw-vitem{border:1px solid rgba(255,255,255,.1);border-radius:8px;overflow:hidden;cursor:pointer;background:rgba(9,9,11,.5)}',
      '.mcw-vitem img{width:100%;height:64px;object-fit:cover;display:block}',
      '.mcw-vitem span{display:block;font-size:9.5px;color:rgba(236,231,218,.6);padding:3px 5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}',
      '.mcw-preview{border:1px solid rgba(212,175,55,.3);border-radius:10px;margin-top:8px;overflow:hidden}',
      '.mcw-preview img{width:100%;display:block}',
      '.mcw-foot{font-size:9.5px;color:rgba(236,231,218,.38);text-align:center;padding:6px}',
      '.mcw-empty{color:rgba(236,231,218,.45);text-align:center;font-size:12px;padding:24px 8px}',
      '.mcw-toast{position:absolute;bottom:14px;inset-inline:40%;background:#101014;border:1px solid rgba(212,175,55,.5);color:#f2e7c3;border-radius:10px;padding:8px 14px;font-size:12px;z-index:60;text-align:center;box-shadow:0 8px 30px rgba(0,0,0,.5)}',
      '.mcw-drawer.hid,.mcw-dock.hid{display:none}',
      '@media (max-width:1100px){.mcw-dock{width:64px;min-width:56px}.mcw-dock .nm,.mcw-dock .mcw-group-title span{display:none}.mcw-drawer{width:250px}}',
    ].join('\n');

    // ------------------------------------------------------------------- أدوات مساعدة
    function cls() { return Array.prototype.slice.call(arguments).filter(Boolean).join(' '); }

    function fmtBytes(n) {
      if (!n && n !== 0) return '?';
      return (n / 1073741824).toFixed(1) + ' ج.ب';
    }

    function fmtTime(ts) {
      try {
        if (!ts) return '';
        const ms = ts > 1e12 ? ts : ts * 1000; // ثوانٍ (بايثون) أو ميلي ثانية (نود)
        return new Date(ms).toLocaleTimeString('ar-EG', { hour: '2-digit', minute: '2-digit' });
      } catch { return ''; }
    }

    function copyText(text) {
      try {
        if (navigator.clipboard && navigator.clipboard.writeText) { navigator.clipboard.writeText(text).catch(() => {}); return true; }
      } catch {}
      try { const ta = document.createElement('textarea'); ta.value = text; document.body.appendChild(ta); ta.select(); document.execCommand('copy'); ta.remove(); return true; } catch { return false; }
    }

    // جسر البيانات إلى نصف المضيف
    function useBridge() {
      const ref = useRef(null);
      if (!ref.current) {
        const b = {
          status: 'unknown',
          lastPing: null,
          async call(endpoint, params) {
            const res = await fetch(ROUTE, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ endpoint: endpoint, params: params || {} }),
            });
            if (!res.ok) throw new Error('HTTP ' + res.status);
            const data = await res.json();
            if (!data || data.ok !== true) throw new Error((data && data.error) || 'جسر غير متاح');
            this.status = 'live';
            return data.value;
          },
          async ping() {
            const v = await this.call('ping', {});
            this.lastPing = v;
            return v;
          },
        };
        ref.current = b;
      }
      return ref.current;
    }

    // عرض Markdown مبسّط (عناصر React — بلا innerHTML)
    function inlineMd(text, keyBase) {
      const out = [];
      let i = 0;
      let key = 0;
      const re = /(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)/g;
      let m;
      let last = 0;
      while ((m = re.exec(text)) !== null) {
        if (m.index > last) out.push(text.slice(last, m.index));
        const tok = m[0];
        const k = keyBase + 'i' + key++;
        if (tok[0] === '`') out.push(h('code', { key: k }, tok.slice(1, -1)));
        else if (tok.startsWith('**')) out.push(h('b', { key: k }, tok.slice(2, -2)));
        else out.push(h('i', { key: k }, tok.slice(1, -1)));
        last = m.index + tok.length;
      }
      if (last < text.length) out.push(text.slice(last));
      return out;
    }

    function renderBlocks(text, accent) {
      const lines = String(text || '').split('\n');
      const els = [];
      let key = 0;
      let i = 0;
      let list = null;
      while (i < lines.length) {
        const ln = lines[i];
        if (ln.trim().startsWith('```')) {
          const buf = [];
          i++;
          while (i < lines.length && !lines[i].trim().startsWith('```')) { buf.push(lines[i]); i++; }
          i++;
          els.push(h('pre', { key: 'b' + key++ }, h('code', null, buf.join('\n'))));
          list = null;
          continue;
        }
        if (/^\s*(?:-|\*)\s+/.test(ln)) {
          if (!list) { list = []; }
          list.push(inlineMd(ln.replace(/^\s*(?:-|\*)\s+/, ''), 'li' + key++));
          i++;
          continue;
        }
        if (list) { els.push(h('div', { key: 'l' + key++, style: { paddingInlineStart: 10 } }, list.map((it, ix) => h('div', { key: ix }, '• ' + it)))); list = null; }
        const t = ln.trim();
        if (!t) { i++; continue; }
        if (/^\|.*\|$/.test(t) && lines[i + 1] && /^\|[\s:|-]+\|$/.test(lines[i + 1].trim())) {
          const head = t.split('|').slice(1, -1).map((s) => s.trim());
          const rows = [];
          i += 2;
          while (i < lines.length && /^\|.*\|$/.test(lines[i].trim())) {
            rows.push(lines[i].split('|').slice(1, -1).map((s) => s.trim()));
            i++;
          }
          els.push(h('table', { key: 't' + key++ },
            h('thead', null, h('tr', null, head.map((c, ix) => h('th', { key: ix }, c)))),
            h('tbody', null, rows.map((r, ix) => h('tr', { key: ix }, r.map((c, jx) => h('td', { key: jx }, c)))))));
          continue;
        }
        if (/^#{1,4}\s/.test(t)) {
          const level = t.match(/^#+/)[0].length;
          const content = inlineMd(t.replace(/^#+\s*/, ''), 'h' + key++);
          els.push(h('div', { key: 'hd' + key++, style: { fontWeight: 700, fontSize: [13, 12, 11.5, 11][level - 1], color: accent || '#f2e7c3', marginTop: 4 } }, content));
          i++;
          continue;
        }
        if (t.startsWith('>')) {
          els.push(h('div', { key: 'q' + key++, style: { borderInlineStart: '3px solid ' + (accent || '#d4af37'), paddingInlineStart: 8, color: 'rgba(236,231,218,.7)', fontStyle: 'italic' } }, inlineMd(t.replace(/^>\s?/, ''), 'q' + key++)));
          i++;
          continue;
        }
        els.push(h('div', { key: 'p' + key++ }, inlineMd(t, 'p' + key++)));
        i++;
      }
      if (list) els.push(h('div', { key: 'l' + key++ }, list.map((it, ix) => h('div', { key: ix }, '• ' + it))));
      return els;
    }

    // ------------------------------------------------------------------- المكونات
    function BrandMark({ size }) {
      return h('div', { className: 'mcw-brand-mark', style: size ? { width: size, height: size, fontSize: size * 0.5 } : {} }, 'م');
    }

    function OmniBar(props) {
      const { onOpenPalette, ping, ram, onRefresh, clock, presets, notesMeta, bars, onToggleBar } = props;
      const nb2 = ping && ping.nb2;
      const okPresets = Array.isArray(presets) ? presets.filter((p) => p && p.ok).length : -1;
      const nbConn = notesMeta && notesMeta.connected;
      return h('div', { className: 'mcw-omni' },
        h('div', { className: 'mcw-brand' },
          h(BrandMark, null),
          h('div', null,
            h('div', { className: 'mcw-brand-name' }, 'MARWA CORE'),
            h('div', { className: 'mcw-brand-sub' }, 'غرفة عمليات النجار برنت'))),
        h('div', { className: 'mcw-cmd', onClick: onOpenPalette, role: 'button', tabIndex: 0 },
          '⚡ ',
          h('span', { style: { flex: 1 } }, 'أمر سريع لأي وكيل أو بحث في النوتبوك…'),
          h('kbd', null, 'Ctrl+K')),
        h('span', { className: 'mcw-chip', title: 'Agent Presets الحية المسجلة في DSH' },
          '🧬 Presets: ' + (okPresets >= 0 ? okPresets + '/10' : '...')),
        h('span', { className: 'mcw-chip', title: nbConn ? 'قاعدة notebook.db متصلة عبر الجسر — ' + notesMeta.openCount + ' مفتوحة · ' + notesMeta.pinned + ' مثبتة' : 'تعذّرت قراءة notebook.db عبر الجسر' },
          h('span', { className: 'mcw-dot', style: { background: nbConn ? '#34d399' : '#f87171', boxShadow: nbConn ? '0 0 6px #34d399' : 'none' } }),
          notesMeta ? (nbConn ? 'أفكاري متصل (' + notesMeta.openCount + ' مفتوحة)' : 'أفكاري غير متصل') : 'أفكاري …'),
        nb2 && nb2.up ? h('span', { className: 'mcw-chip', title: 'خدمة أفكاري v2 (الويب + البوت) على المنفذ 8110' },
          h('span', { className: 'mcw-dot', style: { background: '#34d399', boxShadow: '0 0 6px #34d399' } }), 'v2 8110 حي') : null,
        h('span', { className: 'mcw-chip', title: 'استهلاك الرام الفعلي للورشة' },
          '🖥️ ', ram ? (fmtBytes(ram.used) + ' / ' + fmtBytes(ram.total)) : '…',
          h('span', { className: 'mcw-rambar' }, h('i', { style: { width: ram ? Math.min(100, Math.round((ram.used / ram.total) * 100)) + '%' : '0%' } }))),
        h('span', { className: 'mcw-chip' }, '📍 ' + (ping ? ping.node : '…')),
        h('button', { className: 'mcw-btn ghost', style: { opacity: bars && bars.right ? 1 : 0.4 }, title: 'إظهار/إخفاء عمود أفكاري والسياق (يمين)', onClick: () => onToggleBar('right') }, '🗂️'),
        h('button', { className: 'mcw-btn ghost', style: { opacity: bars && bars.left ? 1 : 0.4 }, title: 'إظهار/إخفاء رصيف الوكلاء (يسار)', onClick: () => onToggleBar('left') }, '👥'),
        h('button', { className: 'mcw-btn ghost', onClick: onRefresh, title: 'تحديث البيانات' }, '⟳ ' + (clock || '')));
    }

    function DockRow({ agent, active, unread, delegated, onClick }) {
      return h('div', {
        className: cls('mcw-agent', active && 'on'),
        style: { '--mcw-accent': agent.color },
        onClick: onClick,
      },
        h('span', { className: 'dot', style: { background: agent.color } }),
        h('span', { className: 'nm' },
          h('b', null, agent.emoji + ' ' + agent.name),
          h('span', null, agent.nick)),
        unread > 0 ? h('span', { className: 'mcw-badge' }, unread) :
          (delegated ? h('span', { className: 'mcw-badge think' }, '⏳') : null));
    }

    function AgentDock(props) {
      const { agents, groups, activeId, rooms, onOpen, onOpenDSH, hidden, onCollapse } = props;
      return h('div', { className: cls('mcw-dock', hidden && 'hid') },
        h('div', { style: { display: 'flex', justifyContent: 'flex-end' } },
          h('button', { className: 'mcw-btn ghost', style: { fontSize: 10, padding: '1px 6px' }, title: 'طي رصيف الوكلاء — الغرفة تتمدد', onClick: onCollapse }, '⟪')),
        groups.map((g) => h('div', { key: g.id },
          h('div', { className: 'mcw-group-title' }, h('span', null, g.icon), h('span', null, g.name)),
          agents.filter((a) => a.group === g.id).map((a) => {
            const room = rooms[a.id] || {};
            return h(DockRow, {
              key: a.id, agent: a, active: activeId === a.id,
              unread: room.unread || 0, delegated: !!room.delegated,
              onClick: () => onOpen(a.id),
            });
          }))),
        h('div', { style: { marginTop: 'auto', paddingTop: 8 } },
          h('button', { className: 'mcw-btn', style: { width: '100%' }, onClick: onOpenDSH }, '🗨 فتح شات DSH الأصلي')));
    }

    // --- MsgBubble / ApprovalComposer retired v1.5.0 (native DSH chat now used) ---

    function AgentContextCard({ agent, ctxData }) {
      if (!ctxData) {
        return h('div', { className: 'mcw-foot', style: { padding: '5px 16px', textAlign: 'start' } },
          '🗂 جارٍ سحب ملف ' + agent.name + ' الحي من الدساتير…');
      }
      if (ctxData.error) {
        return h('div', { className: 'mcw-foot', style: { padding: '6px 16px', textAlign: 'start', color: '#f87171' } },
          '🗂 ملف ' + agent.name + ': غير متاح — ' + ctxData.error);
      }
      const p = ctxData.prompt || {};
      const states = ctxData.stateFiles || [];
      const tasks = ctxData.noteTasks || [];
      const inbox = ctxData.inbox || { count: 0, files: [] };
      return h('details', { className: 'mcw-scratch', style: { margin: '0 16px 8px' } },
        h('summary', null,
          '🗂 ملف ' + agent.name + ' الحي — الدستور (' + (p.chars || 0) + ' حرف) · ' + states.length + ' دفاتر · ' +
            ((ctxData.noteTasks || []).length + (inbox.count || 0)) + ' مهام'),
        h('div', { style: { padding: '6px 10px', maxHeight: 260, overflow: 'auto', fontSize: 11 } },
          h('div', { className: 'meta' }, '📜 الدستور: ' + (p.path || 'غير متاح') + (p.chars ? ' · ' + p.chars + ' حرف' : '') + (p.error ? ' · ' + p.error : '')),
          states.map((s, i) => h('div', { key: 'st' + i, style: { marginTop: 6 } },
            h('div', { style: { fontWeight: 700, color: '#ecd58a' } },
              '📄 ' + (s.path || '').split('\\').pop() + ' · آخر تحديث ' + fmtTime(s.mtime) + ' · ' + (s.chars || 0) + ' حرف'),
            h('div', { style: { color: 'rgba(236,231,218,.6)', whiteSpace: 'pre-wrap', maxHeight: 90, overflow: 'hidden', marginTop: 2 } }, (s.head || '').slice(0, 320)))),
          (ctxData.noteTasks || []).length ? h('div', null,
            h('div', { className: 'mcw-group-title', style: { margin: '6px 0 3px' } }, '🧾 المهام الحالية (نوتبوك)'),
            ctxData.noteTasks.map((t) => h('div', { key: t.id, style: { fontSize: 10.5 } },
              '• #' + t.id + ' ' + (t.title || '') + ' — [' + (t.priority || 'normal') + ']' + (t.due_at ? ' · موعد ' + t.due_at : '')))) : null,
          inbox.count ? h('div', { style: { marginTop: 6 } },
            h('div', { className: 'mcw-group-title' }, '📥 صندوق الوارد (' + inbox.count + ')'),
            (inbox.files || []).slice(0, 3).map((f, i) => h('div', { key: f.name, style: { fontSize: 10, color: 'rgba(236,231,218,.55)' } },
              '• ' + f.name + ' · ' + fmtTime(f.mtime)))) : null,
          h('div', { className: 'mcw-foot', style: { textAlign: 'start', padding: '4px 0 0' } }, 'سُحب حياً من الدساتير والدفاتر ' + fmtTime(ctxData.loadedAt))));
    }

    // ------------------------------------------------------------------- غرفة وكيل مبسّطة — هيدر + ملف حقيقي + محادثة DSH الأصلية

    function NativeChatFallback() {
      return h('div', {
        style: {
          flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
          color: 'rgba(236,231,218,.35)', padding: '32px 24px', textAlign: 'center', gap: 14,
        }
      },
        h('div', { style: { fontSize: 40, opacity: 0.4 } }, '💬'),
        h('div', { style: { fontSize: 13 } }, 'الجلسة الحقيقية للوكيل تظهر هنا'),
        h('div', { style: { fontSize: 11, opacity: 0.6 } }, 'اختر وكيلاً من الرصيف الأيسر · أو اضغط «⚡ ربط»'));
    }

    function RoomView(props) {
      const { agent, room, agentCtx, renderFactorySlot, onCopyPrompt, onOpenDSH, onRebind } = props;
      const accent = agent.color;
      return h('div', { className: 'mcw-center' },
        h('div', { className: 'mcw-roomhead', style: { '--mcw-accent': accent } },
          h('div', { className: 'mcw-emoji' }, agent.emoji),
          h('div', null,
            h('h2', null, agent.name + ' ' + (agent.nick ? '— ' + agent.nick : '')),
            h('small', null, agent.role + (agent.external ? ' · مسار خارجي: ' + agent.prompt : ''))),
          h('div', { className: 'mcw-roomacts' },
            room && room.wsTitle ? h('span', { className: 'mcw-chip', title: 'مساحة عمل DSH: ' + room.wsTitle }, '🗂 ' + room.wsTitle) : null,
            room && room.sessionId ? h('span', { className: 'mcw-chip', title: 'جلسة DSH مرتبطة: ' + room.sessionId }, '⚡ DSH #' + String(room.sessionId).slice(0, 8)) : null,
            h('button', { className: 'mcw-btn ghost', title: 'نسخ برومبت تفعيل الشخصية', onClick: () => onCopyPrompt(agent) }, '📋 البرومبت'),
            h('button', { className: 'mcw-btn ghost', onClick: onOpenDSH }, '🗨 ملء الشاشة'),
            h('button', { className: 'mcw-btn', onClick: () => onRebind(agent) }, '⚡ ربط'))),
        h(AgentContextCard, { agent, ctxData: agentCtx }),
        h('div', { className: 'mcw-native', style: { flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 } },
          (renderFactorySlot && room && room.sessionId)
            ? renderFactorySlot('conversation.content', { sessionId: room.sessionId })
            : h(NativeChatFallback)));
    }
    function NoteRow({ n, onPin }) {
      return h('div', { key: n.id, className: 'mcw-note' },
        h('b', null, (n.emoji || '📁') + ' #' + n.id + ' · ' + n.title + (n.status === 'done' ? ' ✓' : '')),
        h('p', null, n.body || ''),
        h('div', { className: 'meta' }, '[' + n.kind + '] ' + n.priority + ' · ' + (n.category || '') + ' · ' + (n.due_at ? 'موعد: ' + n.due_at : '')),
        h('div', { style: { display: 'flex', gap: 4, marginTop: 4 } },
          h('button', { className: 'mcw-btn ghost', onClick: () => onPin(n) }, n.priority === 'high' ? '📌 مثبت' : '📌 تثبيت'),
          h('button', { className: 'mcw-btn ghost', onClick: () => copyText('#قاعدة ' + n.title + '\n' + (n.body || '')) }, 'نسخ كقاعدة')));
    }

    function NotebookPane(props) {
      const { notes, notesMeta, ping, onAddNote, onPin, onRefresh } = props;
      const [title, setTitle] = useState('');
      const [body, setBody] = useState('');
      const [kind, setKind] = useState('note');
      const [priority, setPriority] = useState('normal');
      const nb2 = ping && ping.nb2;
      const conn = notesMeta && notesMeta.connected;
      const all = notes || [];
      const open = all.filter((n) => n.status === 'open');
      const pinned = open.filter((n) => n.priority === 'high' || n.priority === 'urgent');
      const rest = open.filter((n) => !(n.priority === 'high' || n.priority === 'urgent'))
        .concat(all.filter((n) => n.status !== 'open'));
      return h('div', { className: 'mcw-tabpane' },
        h('div', { style: { display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 } },
          h('span', { className: 'mcw-dot', style: { background: conn ? '#34d399' : '#f87171' } }),
          h('span', { style: { fontSize: 11, color: 'rgba(236,231,218,.65)' } },
            conn
              ? 'أفكاري متصل — notebook.db (' + notesMeta.openCount + ' مفتوحة · ' + notesMeta.pinned + ' مثبتة)'
              : 'أفكاري غير متصل — الجسر لم يقرأ notebook.db'),
          nb2 && nb2.up ? h('span', { style: { fontSize: 10, color: '#34d399' } }, ' · v2 8110 حي') : null,
          h('button', { className: 'mcw-btn ghost', onClick: onRefresh, style: { marginInlineStart: 'auto' } }, '⟳')),
        h('div', { style: { border: '1px solid rgba(212,175,55,.3)', borderRadius: 9, padding: 8, marginBottom: 10, background: 'rgba(9,9,11,.4)' } },
          h('input', { placeholder: 'عنوان النوت…', value: title, onChange: (e) => setTitle(e.target.value), style: { width: '100%', marginBottom: 6, background: 'rgba(9,9,11,.7)', border: '1px solid rgba(255,255,255,.12)', borderRadius: 7, color: '#ece7da', padding: '5px 8px', fontFamily: 'inherit' } }),
          h('textarea', { placeholder: 'المحتوى…', value: body, onChange: (e) => setBody(e.target.value), style: { width: '100%', minHeight: 40, marginBottom: 6, background: 'rgba(9,9,11,.7)', border: '1px solid rgba(255,255,255,.12)', borderRadius: 7, color: '#ece7da', padding: '5px 8px', fontFamily: 'inherit', resize: 'vertical' } }),
          h('div', { style: { display: 'flex', gap: 5, alignItems: 'center' } },
            h('select', { value: kind, onChange: (e) => setKind(e.target.value), style: { background: 'rgba(9,9,11,.7)', color: '#ece7da', border: '1px solid rgba(255,255,255,.12)', borderRadius: 7, padding: '4px', fontFamily: 'inherit', fontSize: 11 } },
              h('option', { value: 'note' }, 'نوت'), h('option', { value: 'task' }, 'مهمة'), h('option', { value: 'idea' }, 'فكرة'), h('option', { value: 'reminder' }, 'تذكير')),
            h('select', { value: priority, onChange: (e) => setPriority(e.target.value), style: { background: 'rgba(9,9,11,.7)', color: '#ece7da', border: '1px solid rgba(255,255,255,.12)', borderRadius: 7, padding: '4px', fontFamily: 'inherit', fontSize: 11 } },
              h('option', { value: 'low' }, 'منخفضة'), h('option', { value: 'normal' }, 'عادية'), h('option', { value: 'high' }, 'عالية'), h('option', { value: 'urgent' }, 'عاجلة')),
            h('button', { className: 'mcw-btn', style: { marginInlineStart: 'auto' }, onClick: () => { if (title.trim()) { onAddNote({ title, body, kind, priority }); setTitle(''); setBody(''); } } }, '+ إضافة')),
          h('div', { className: 'mcw-foot', style: { padding: '4px 0 0' } }, 'المخزن: notebook/data/notebook.db (القناة الرسمية store)')),
        (pinned.length ? h('div', { className: 'mcw-group-title' }, '📌 مثبتة (Pinned) — تُحقن في برومبت كل وكيل') : null),
        pinned.map((n) => h(NoteRow, { key: 'p' + n.id, n, onPin })),
        h('div', { className: 'mcw-group-title' }, '🗂 المحفوظة (' + rest.length + ')'),
        rest.map((n) => h(NoteRow, { key: n.id, n, onPin })));
    }

    function VisionPane(props) {
      const { entries, onPreview, preview, onRefresh } = props;
      const [root, setRoot] = useState('all');
      const list = (entries || []).filter((e) => root === 'all' || e.root === root);
      return h('div', { className: 'mcw-tabpane' },
        h('div', { style: { display: 'flex', gap: 5, marginBottom: 8, alignItems: 'center' } },
          h('select', { value: root, onChange: (e) => setRoot(e.target.value), style: { background: 'rgba(9,9,11,.7)', color: '#ece7da', border: '1px solid rgba(255,255,255,.12)', borderRadius: 7, padding: '4px', fontFamily: 'inherit', fontSize: 11 } },
            h('option', { value: 'all' }, 'كل المعمل'),
            ['designs', 'projects', 'ai_templates', 'studies'].map((r) => h('option', { key: r, value: r }, r))),
          h('button', { className: 'mcw-btn ghost', onClick: onRefresh, style: { marginInlineStart: 'auto' } }, '⟳')),
        h('div', { className: 'mcw-foot', style: { textAlign: 'start', padding: '0 0 6px' } }, '👁️ مرسم فيجين — المصدر: Vision-Lab (المرجع الوحيد لفيجن)'),
        h('div', { className: 'mcw-vgrid' },
          list.slice(0, 24).map((e) =>
            h('div', { key: e.path, className: 'mcw-vitem', onClick: () => onPreview(e) },
              e.kind === 'image' ? h('img', { src: '/marwa-core/thumb?path=' + encodeURIComponent(e.path), alt: e.name, onError: (ev) => { ev.currentTarget.style.display = 'none'; } }) :
                h('div', { style: { height: 64, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 26, background: 'rgba(212,175,55,.06)' } }, e.git ? '🗂️' : '📁'),
              h('span', null, (e.kind === 'dir' ? (e.git ? '🔀 ' : '📁 ') : '') + e.name))),
        (preview ? h('div', { className: 'mcw-preview' },
          h('img', { src: preview.dataUrl, alt: preview.name }),
          h('div', { className: 'mcw-foot', style: { textAlign: 'start' } }, preview.path + ' · ' + fmtBytes(preview.size) + ' · ' + fmtTime(preview.mtime))) : null)));
    }

    function ContextPane(props) {
      const { pos, catalog, onRefresh } = props;
      const cards = (pos && pos.cards) || [];
      return h('div', { className: 'mcw-tabpane' },
        h('div', { style: { display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 } },
          h('span', { style: { fontSize: 11, color: 'rgba(236,231,218,.65)' } }, '📊 السياق الحي — مرآة POS المحلية'),
          h('button', { className: 'mcw-btn ghost', onClick: onRefresh, style: { marginInlineStart: 'auto' } }, '⟳')),
        pos && pos.exists === false ? h('div', { className: 'mcw-empty' }, 'مرآة POS غير موجودة محلياً (pos_data.db)') :
          h('div', { className: 'mcw-grid' },
            cards.map((c) => h('div', { key: c.id, className: 'mcw-kart' },
              h('b', null, c._error ? '⚠' : (c.n !== undefined ? String(c.n) : (c.opened_at || c.n || '—'))),
              h('span', null, c.label)))),
        pos && pos.tables ? h('div', null,
          pos.tables.ordersByStatus && pos.tables.ordersByStatus[0] && !pos.tables.ordersByStatus[0]._error ?
            h('div', null,
              h('div', { className: 'mcw-group-title' }, 'الحالات'),
              h('table', { className: 'mcw-tbl' }, h('tbody', null, pos.tables.ordersByStatus.map((r) => h('tr', { key: r.status }, h('td', null, r.status), h('td', null, r.n)))))) : null,
          pos.tables.topProducts && pos.tables.topProducts[0] && !pos.tables.topProducts[0]._error ?
            h('div', null,
              h('div', { className: 'mcw-group-title' }, 'الأكثر مبيعاً'),
              h('table', { className: 'mcw-tbl' }, h('tbody', null, pos.tables.topProducts.map((r, i) => h('tr', { key: i }, h('td', null, r.name), h('td', null, '×' + r.qty)))))) : null,
          pos.tables.lowStock && pos.tables.lowStock[0] && !pos.tables.lowStock[0]._error ?
            h('div', null,
              h('div', { className: 'mcw-group-title' }, 'مخزون منخفض (≤3)'),
              h('table', { className: 'mcw-tbl' }, h('tbody', null, pos.tables.lowStock.map((r, i) => h('tr', { key: i }, h('td', null, r.name), h('td', null, String(r.stock_qty))))))) : null) : null,
        catalog && catalog.headers ?
          h('div', null,
            h('div', { className: 'mcw-group-title' }, 'الكتالوج الماستر — ' + catalog.sheet + ' (' + catalog.total + ' صف)'),
            h('div', { style: { overflow: 'auto', maxHeight: 220 } },
              h('table', { className: 'mcw-tbl' },
                h('thead', null, h('tr', null, catalog.headers.slice(0, 6).map((c2, i) => h('th', { key: i }, c2)))),
                h('tbody', null, catalog.rows.slice(0, 12).map((r, i) => h('tr', { key: i }, r.slice(0, 6).map((c2, j) => h('td', { key: j }, c2)))))))) : null,
        h('div', { className: 'mcw-foot' }, 'آخر تحديث ملفات: POS ' + fmtTime(pos && pos.mtime) + ' · كتالوج ' + fmtTime(catalog && catalog.mtime)));
    }

    function Palette(props) {
      const { open, onClose, agents, notes, onAgent, onAction } = props;
      const [q, setQ] = useState('');
      useEffect(() => {
        if (!open) setQ('');
      }, [open]);
      if (!open) return null;
      const query = q.trim();
      const agentsRes = agents.filter((a) => !query || a.name.includes(query) || a.nick.includes(query) || a.role.includes(query));
      const notesRes = (notes || []).filter((n) => !query || (n.title || '').includes(query)).slice(0, 5);
      return h('div', { className: 'mcw-palette' },
        h('input', { autoFocus: true, placeholder: 'بحث عن وكيل، نوت، أو إجراء…', value: q, onChange: (e) => setQ(e.target.value), onKeyDown: (e) => { if (e.key === 'Escape') onClose(); } }),
        h('div', { className: 'res' },
          agentsRes.map((a) => h('div', { key: a.id, className: 'row', style: { borderInlineStart: '3px solid ' + a.color }, onClick: () => { onAgent(a.id); onClose(); } },
            h('span', null, a.emoji), h('b', null, a.name), h('span', { style: { color: 'rgba(236,231,218,.5)' } }, a.nick))),
          h('div', { className: 'row', style: { color: 'rgba(236,231,218,.5)' }, onClick: () => { onAction('openDSH'); onClose(); } }, '🗨 فتح شات DSH الأصلي'),
          h('div', { className: 'row', style: { color: 'rgba(236,231,218,.5)' }, onClick: () => { onAction('refresh'); onClose(); } }, '⟳ تحديث كل البيانات'),
          notesRes.map((n) => h('div', { key: n.id, className: 'row', onClick: () => { onAction('note', n); onClose(); } },
            h('span', null, n.emoji || '📁'), h('b', null, '#' + n.id + ' ' + n.title)))));
    }

    function Toast({ text }) {
      if (!text) return null;
      return h('div', { className: 'mcw-toast' }, text);
    }

    // ------------------------------------------------------------------- حارس الأخطاء (حتى لا تُفرّغ الفتحة)
    class McwBoundary extends Component {
      constructor(p) { super(p); this.state = { err: null }; }
      static getDerivedStateFromError(e) { return { err: e }; }
      componentDidCatch(e) { try { console.error('[marwa-core]', e); } catch {} }
      render() {
        if (this.state.err) {
          return h('div', { style: { padding: 20, color: '#f2e7c3', fontFamily: 'Cairo, sans-serif', background: '#09090b', height: '100%' } },
            'تعطّل مكوّن غرفة عمليات مروة: ', String(this.state.err && this.state.err.message || this.state.err));
        }
        return this.props.children;
      }
    }

    // ------------------------------------------------------------------- اللوحة الرئيسية (الهيكل الرباعي)
    function Workspace(props) {
      const bridge = useBridge();
      const [ping, setPing] = useState(null);
      const [ram, setRam] = useState(null);
      const [bridgeErr, setBridgeErr] = useState(null);
      const [clock, setClock] = useState('');
      const [activeId, setActiveId] = useState('marwa');
      const [tab, setTab] = useState('nb');
      const [paletteOpen, setPaletteOpen] = useState(false);
      const [notes, setNotes] = useState(null);
      const [nbMeta, setNbMeta] = useState(null);
      const [catalog, setCatalog] = useState(null);
      const [pos, setPos] = useState(null);
      const [entries, setEntries] = useState(null);
      const [preview, setPreview] = useState(null);
      const [presets, setPresets] = useState(null);
      const [agentCtx, setAgentCtx] = useState({});
      const [toast, setToast] = useState(null);
      const [bars, setBars] = useState(() => {
        try { return Object.assign({ left: true, right: true }, JSON.parse(localStorage.getItem('mcw.bars.v1') || '{}')); }
        catch { return { left: true, right: true }; }
      });
      useEffect(() => { try { localStorage.setItem('mcw.bars.v1', JSON.stringify(bars)); } catch {} }, [bars]);
      const toggleBar = useCallback((k) => setBars((b) => Object.assign({}, b, { [k]: !b[k] })), []);
      const [rooms, setRooms] = useState(() => { try { return JSON.parse(localStorage.getItem('mcw.rooms.v1') || '{}'); } catch { return {}; } });
      const [noteDraft, setNoteDraft] = useState('');

      // خدمات DSH المحقونة — إعادة رسم فورية عند وصول الحقن
      const [svcTick, setSvcTick] = useState(0);
      useEffect(() => { const fn = () => setSvcTick((t) => t + 1); svcListeners.add(fn); return () => { svcListeners.delete(fn); }; }, []);
      const layout = useMemo(() => { try { return SVC.layout || undefined; } catch { return undefined; } }, [svcTick]);
      const uiWorkspace = useMemo(() => { try { return SVC.uiWorkspace || undefined; } catch { return undefined; } }, [svcTick]);
      const sessionsSvc = useMemo(() => { try { return SVC.sessions || undefined; } catch { return undefined; } }, [svcTick]);

      const showToast = useCallback((t) => { setToast(t); setTimeout(() => setToast(null), 2600); }, []);

      // حفظ الغرف محلياً
      useEffect(() => { try { localStorage.setItem('mcw.rooms.v1', JSON.stringify(rooms)); } catch {} }, [rooms]);

      // الساعة
      useEffect(() => {
        const t = setInterval(() => { setClock(new Date().toLocaleTimeString('ar-EG', { hour: '2-digit', minute: '2-digit' })); }, 15000);
        return () => clearInterval(t);
      }, []);

      const refresh = useCallback(async () => {
        try {
          const p = await bridge.ping();
          setPing(p);
          setBridgeErr(null);
          const [r, nb, cat, po, vis, pr] = await Promise.all([
            bridge.call('ram', {}).catch(() => null),
            bridge.call('notebook.list', { limit: 120 }).catch(() => null),
            bridge.call('catalog.rows', { maxRows: 300 }).catch(() => null),
            bridge.call('pos.stats', {}).catch(() => null),
            bridge.call('vision.list', {}).catch(() => null),
            bridge.call('presets.status', {}).catch(() => null),
          ]);
          setRam(r);
          if (nb) {
            setNotes(nb.notes || []);
            const openN = (nb.notes || []).filter((n) => n.status === 'open');
            setNbMeta({
              connected: !!nb.exists,
              openCount: nb.openCount || openN.length,
              pinned: openN.filter((n) => n.priority === 'high' || n.priority === 'urgent').length,
              db: nb.db,
            });
          } else { setNbMeta({ connected: false }); }
          if (cat) setCatalog(cat);
          if (po) setPos(po);
          if (vis) setEntries(vis.entries || []);
          if (pr && Array.isArray(pr.presets)) setPresets(pr.presets);
        } catch (err) {
          setBridgeErr(String((err && err.message) || err));
        }
      }, [bridge]);

      useEffect(() => { refresh(); const t = setInterval(refresh, 30000); return () => clearInterval(t); }, [refresh]);

      // إعادة محاولة سريعة تلقائياً عند فشل الجسر (كل 8 ثوانٍ) — يتعافى وحده بعد إقلاع المضيف
      useEffect(() => {
        if (!bridgeErr) return;
        const t = setTimeout(() => { refresh(); }, 8000);
        return () => clearTimeout(t);
      }, [bridgeErr, refresh]);

      // الرام حية كل 5 ثوانٍ — مستقلة عن التحديث الكبير (الشريط العلوي يتنفس)
      useEffect(() => {
        const pull = () => { bridge.call('ram', {}).then((r) => setRam(r)).catch(() => {}); };
        pull();
        const t = setInterval(pull, 5000);
        return () => clearInterval(t);
      }, [bridge]);

      // Ctrl+K
      useEffect(() => {
        function onKey(e) {
          if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
            e.preventDefault();
            setPaletteOpen((v) => !v);
          }
        }
        window.addEventListener('keydown', onKey);
        return () => window.removeEventListener('keydown', onKey);
      }, []);

      function saveRoom(id, patch) {
        setRooms((prev) => {
          const cur = prev[id] || { messages: [], scratch: '', unread: 0, delegated: false, sessionId: null };
          return Object.assign({}, prev, { [id]: Object.assign({}, cur, patch) });
        });
      }
      function pushMsg(id, msg) {
        setRooms((prev) => {
          const cur = prev[id] || { messages: [], scratch: '', unread: 0, delegated: false, sessionId: null };
          const newMsg = Object.assign({ id: 'm' + Date.now() + Math.random().toString(36).slice(2, 6), ts: Date.now() }, msg);
          const unread = id === activeId ? cur.unread : (cur.unread || 0) + 1;
          return Object.assign({}, prev, { [id]: Object.assign({}, cur, { messages: cur.messages.concat([newMsg]), unread }) });
        });
      }

      function onSend(text) {
        const mentions = [];
        AGENTS.forEach((a) => {
          if (a.id === activeId) return;
          a.triggers.concat([a.name, a.nick]).forEach((t) => {
            if (t && text.includes(t)) mentions.push(a.id);
          });
        });
        const mentionSet = Array.from(new Set(mentions));
        pushMsg(activeId, { kind: 'user', text });
        mentionSet.forEach((aid) => {
          const a = AGENT_MAP[aid];
          pushMsg(aid, {
            kind: 'delegation', who: 'استدعاء من غرفة ' + AGENT_MAP[activeId].name,
            text: text + '\n\n(استُدعي ' + a.name + ' للرد في غرفته بفقاعته الملوّنة)',
          });
          saveRoom(aid, { delegated: true });
        });
        if (mentionSet.length > 0) saveRoom(activeId, { delegated: false });
      }

      function onChip(text) {
        pushMsg(activeId, { kind: 'user', text });
      }

      // سياق الوكيل الحي: يُسحب من الدساتير والدفاتر عند فتح غرفته (squad.context عبر الجسر)
      const loadAgentContext = useCallback((id) => {
        bridge.call('squad.context', { agent: id })
          .then((v) => setAgentCtx((prev) => Object.assign({}, prev, { [id]: Object.assign({}, v, { loadedAt: Date.now() }) })))
          .catch((err) => setAgentCtx((prev) => Object.assign({}, prev, { [id]: { agent: id, error: String((err && err.message) || err) } })));
      }, [bridge]);
      useEffect(() => { loadAgentContext(activeId); }, [activeId, loadAgentContext]);

      function onRequestApproval({ title, body, cmd }) {
        pushMsg(activeId, { kind: 'approval', title, text: body, cmd, status: 'pending' });
      }

      function onApprove(msg) {
        saveRoom(activeId, {});
        setRooms((prev) => {
          const cur = prev[activeId] || { messages: [] };
          const msgs = cur.messages.map((m) => (m.id === msg.id ? Object.assign({}, m, { status: 'approved' }) : m));
          return Object.assign({}, prev, { [activeId]: Object.assign({}, cur, { messages: msgs }) });
        });
        const execText = msg.cmd || ((msg.title || '') + '\n' + (msg.text || ''));
        if (msg.cmd) copyText(msg.cmd);
        showToast('✅ اعتمد ✓ — جارٍ التنفيذ في جلسة DSH...');
        sendToSession(activeId, execText)
          .then((sid) => showToast('✅ اعتمد ونُفّذ في جلسة DSH #' + String(sid).slice(0, 8)))
          .catch((err) => showToast((msg.cmd ? '✅ اعتمد ✓ — أمر التنفيذ نُسخ للحافظة' : '✅ اعتمد ✓') + ' · تنفيذ DSH: ' + String((err && err.message) || err)));
        try {
          bridge.call('notebook.add', {
            title: 'اعتماد: ' + (msg.title || 'إجراء'), body: msg.text + (msg.cmd ? '\nالأمر: ' + msg.cmd : ''),
            kind: 'task', priority: 'high', source: 'marwa-core-ui', category: 'قرارات معتمدة',
          }).catch(() => {});
        } catch {}
      }

      function onEditMsg(msg) {
        const edited = window.prompt('✏️ تعديل نص الإجراء:', msg.text || '');
        if (edited === null) return;
        setRooms((prev) => {
          const cur = prev[activeId] || { messages: [] };
          const msgs = cur.messages.map((m) => (m.id === msg.id ? Object.assign({}, m, { text: edited, status: 'edited' }) : m));
          return Object.assign({}, prev, { [activeId]: Object.assign({}, cur, { messages: msgs }) });
        });
      }

      function onAudit(msg) {
        pushMsg('hakim', { kind: 'delegation', who: '🦉 طلب تدقيق من غرفة ' + AGENT_MAP[activeId].name, text: (msg.title || '') + '\n' + (msg.text || '') });
        saveRoom('hakim', { delegated: true });
        setRooms((prev) => {
          const cur = prev[activeId] || { messages: [] };
          const msgs = cur.messages.map((m) => (m.id === msg.id ? Object.assign({}, m, { status: 'auditing' }) : m));
          return Object.assign({}, prev, { [activeId]: Object.assign({}, cur, { messages: msgs }) });
        });
        showToast('🦉 استدعاء حكيم (Preset) للمراجعة...');
        const auditText = 'طلب تدقيق من ' + AGENT_MAP[activeId].name + ' (بوابة اعتماد):\n' + (msg.title || '') + '\n' + (msg.text || '') + '\n\nراجع الحسبة/الاقتراح بصدق وأبلغ المالك بالنتيجة فوراً.';
        ensureAgentSession('hakim')
          .then((r) => sendToSession('hakim', auditText).then(() => showToast('🦉 حكيم يراجع الآن — جلسة #' + String(r.sessionId).slice(0, 8))))
          .catch((err) => showToast('🦉 تعذّر استدعاء حكيم: ' + String((err && err.message) || err)));
      }

      function onSaveNote(msg) {
        try {
          bridge.call('notebook.add', {
            title: msg.title || 'نوت من غرفة ' + AGENT_MAP[activeId].name,
            body: msg.text || msg.details || '', kind: 'note', priority: 'normal', source: 'marwa-core-ui',
          }).then((v) => showToast('📓 حُفظت في النوتبوك #' + v.id)).catch(() => showToast('📓 تعذّر الحفظ — الجسر غير متاح'));
        } catch { showToast('📓 تعذّر الحفظ — الجسر غير متاح'); }
      }

      function onAddNote({ title, body, kind, priority }) {
        try {
          bridge.call('notebook.add', { title, body, kind, priority, source: 'marwa-core-ui' })
            .then((v) => { showToast('📓 أُضيفت النوت #' + v.id); refresh(); })
            .catch(() => showToast('📓 تعذّرت الإضافة'));
        } catch {}
      }

      function onPin(n) {
        try {
          bridge.call('notebook.pin', { id: n.id, pinned: n.priority !== 'high' }).then(refresh).catch(() => {});
        } catch {}
      }

      function onPreview(e) {
        if (e.kind !== 'image') return;
        try {
          bridge.call('vision.file', { path: e.path }).then((v) => {
            setPreview({ dataUrl: 'data:' + v.mime + ';base64,' + v.dataB64, name: v.name, path: v.path, size: v.size, mtime: v.mtime });
          }).catch(() => showToast('👁️ تعذّرت معاينة الملف'));
        } catch {}
      }

      function onCopyPrompt(agent) {
        try {
          bridge.call('squad.prompts', { withText: false }).then((all) => {
            const info = all[agent.id];
            copyText(info && info.path ? 'برومبت ' + agent.name + ' (انسخه في شات DSH مخصص):\nالمسار: ' + info.path + '\n\nافتح: python -m orchestrator.core --message "يا ' + agent.name + ' عرّف نفسك"' : 'مسار البرومبت غير متاح');
            showToast('📋 نُسخ مسار البرومبت');
          }).catch(() => showToast('📋 الجسر غير متاح'));
        } catch {}
      }

      function openDSH() {
        try {
          const sid = (rooms[activeId] || {}).sessionId;
          if (sid && uiWorkspace && uiWorkspace.openSession) uiWorkspace.openSession(sid);
          if (layout && layout.selectPanel) layout.selectPanel('conversation');
          else if (!sid) showToast('لا يمكن فتح شات DSH');
        } catch { showToast('لا يمكن فتح شات DSH'); }
      }

      // ------------------------------------------------ ربط الجلسات التلقائي (Zero-Click) داخل مساحة عمل الوكيل
      const [liveBusy, setLiveBusy] = useState(null);
      const wsSnapRef = useRef(null);
      try { if (props.useWorkspaces) wsSnapRef.current = props.useWorkspaces(); } catch {}
      function currentWorkspaceId() {
        try {
          const snap = wsSnapRef.current;
          return (snap && snap.current && snap.current.id) || (snap && snap.items && snap.items[0] && snap.items[0].id) || null;
        } catch { return null; }
      }
      // مساحة عمل DSH حقيقية لكل وكيل: مجلده الأصلي (orchestrator/squad/<id>…) + عنوان «غرفة عمليات - …».
      // الجلسات الجديدة تُنشأ حصرياً داخلها عبر workspaces.create + connectWorkspace.
      async function ensureAgentWorkspace(agentId) {
        let wss = null;
        try { wss = getSvc('workspaces'); } catch { wss = null; }
        if (!wss || typeof wss.create !== 'function') return null;
        const info = await bridge.call('workspaces.ensure', { agent: agentId }).catch(() => null);
        if (!info || !info.path) return null;
        const norm = (p) => String(p || '').toLowerCase().replace(/\//g, '\\');
        let item = null;
        try { item = (wss.list.getSnapshot().items || []).find((w) => norm(w.path) === norm(info.path)); } catch {}
        if (!item) {
          // مصدر ثاني: snapshot الـhook الخاص بالواجهة (شكل مختلف لنفس المخزن)
          try {
            const snap = wsSnapRef.current;
            const hit = ((snap && snap.items) || []).find((w) => norm(w.path) === norm(info.path));
            if (hit) item = { workspaceId: hit.workspaceId || hit.id, title: hit.title };
          } catch {}
        }
        if (!item) {
          try {
            const created = await wss.create({ path: info.path });
            item = created && created.workspaceId ? created : null;
          } catch { item = null; }
          if (!item) {
            try { item = (wss.list.getSnapshot().items || []).find((w) => norm(w.path) === norm(info.path)); } catch {}
          }
        }
        if (!item) return null;
        try { if (info.title && item.title !== info.title && typeof wss.rename === 'function') await wss.rename(item.workspaceId, info.title); } catch {}
        return { workspaceId: item.workspaceId, title: info.title };
      }
      function buildBootPrompt(agentId, pinned) {
        const a = AGENT_MAP[agentId];
        const presetId = PRESET_ID_MAP[agentId] || agentId;
        const parts = [];
        parts.push('أنت ' + (a ? a.name : agentId) + ' — جلسة DSH تلقائية أنشأتها «غرفة عمليات مروة» عبر Preset: ' + presetId + '. أجب كشخصيتك تماماً حسب دستورك وبصدق تام.');
        if (pinned && pinned.notes && pinned.notes.length) {
          parts.push('📌 قرارات/ملاحظات المالك المثبتة من النوتبوك (اعرفها قبل أي رد):\n' +
            pinned.notes.map((n) => '• [' + (n.kind || 'note') + '] ' + (n.title || '') + (n.body ? ' — ' + String(n.body).slice(0, 260) : '')).join('\n'));
        }
        return parts.join('\n\n').slice(0, 12000);
      }
      function attachLive(agentId, binding) {
        try {
          binding.eventSource.subscribe((frame) => {
            const txt = (frame && (frame.text || frame.content || (frame.message && frame.message.text))) || '';
            if (txt) setRooms((prev) => {
              const cur = prev[agentId] || { messages: [] };
              const msgs = cur.messages.slice();
              const last = msgs[msgs.length - 1];
              if (last && last.live) { msgs[msgs.length - 1] = Object.assign({}, last, { text: txt }); }
              else msgs.push({ id: 'live' + Date.now(), kind: 'agent', who: AGENT_MAP[agentId].name + ' · DSH Live', text: txt, live: true });
              return Object.assign({}, prev, { [agentId]: Object.assign({}, cur, { messages: msgs }) });
            });
          });
        } catch (err) { console.log('[marwa-core] live-subscribe', err); }
      }
      async function ensureAgentSession(agentId) {
        if (!uiWorkspace || !sessionsSvc) throw new Error('خدمات الجلسات غير متاحة');
        const presetId = PRESET_ID_MAP[agentId] || agentId;
        const nav = (targetSid) => { try { if (targetSid && uiWorkspace && typeof uiWorkspace.openSession === 'function') uiWorkspace.openSession(targetSid); } catch {} };
        // 1) جلسة مسجّلة محلياً (localStorage) ما زالت حية؟
        let sid = null;
        try { sid = localStorage.getItem('mcw.sid.' + agentId); } catch {}
        if (sid) {
          try {
            const ref = sessionsSvc.retain(sid, { source: 'controllerOperation' });
            await ref.ready;
            saveRoom(agentId, { sessionId: sid });
            attachLive(agentId, ref.binding);
            nav(sid);
            return { sessionId: sid, created: false };
          } catch { sid = null; }
        }
        // 2) جلسة نشطة مطابقة لنفس الـPreset (فحص حقيقي عبر المضيف)؟
        try {
          const found = await bridge.call('sessions.findForPreset', { presetId });
          if (found && found.sessionId) {
            sid = found.sessionId;
            try { localStorage.setItem('mcw.sid.' + agentId, sid); } catch {}
            const ref = sessionsSvc.retain(sid, { source: 'controllerOperation' });
            await ref.ready;
            saveRoom(agentId, { sessionId: sid });
            attachLive(agentId, ref.binding);
            nav(sid);
            return { sessionId: sid, created: false, found: true };
          }
        } catch {}
        // 3) مساحة الوكيل: عبر الجسر، وإلا اكتشاف أصلي من خدمة workspaces، وإلا إنشاء أصلي — بلا اعتماد إلزامي على الجسر
        let wsInfo = null;
        try { wsInfo = await ensureAgentWorkspace(agentId); } catch { wsInfo = null; }
        let wsId = (wsInfo && wsInfo.workspaceId) || null;
        let boundHit = null;
        // 3-أ) سجل الربط الدائم (الجسر) — أقوى إشارة قبل أي مطابقة اسم/مسار
        if (!wsId) {
          try {
            const b = await bridge.call('binding.get', { agent: agentId });
            const bid = b && b.binding && b.binding.workspaceId;
            if (bid) {
              const wsvc0 = getSvc('workspaces');
              const items0 = (wsvc0 && wsvc0.list && wsvc0.list.getSnapshot) ? (wsvc0.list.getSnapshot().items || []) : [];
              const hit0 = items0.find((w) => (w.workspaceId || w.id) === bid);
              if (hit0) { boundHit = hit0; wsId = hit0.workspaceId || hit0.id || null; }
            }
          } catch {}
        }
        if (!wsId) {
          try {
            const wsvc = getSvc('workspaces');
            const items = (wsvc && wsvc.list && wsvc.list.getSnapshot) ? (wsvc.list.getSnapshot().items || []) : [];
            const names = [String(agentId).toLowerCase(), String((AGENT_MAP[agentId] || {}).name || '').toLowerCase()].filter(Boolean);
            const hit = items.find((w) => names.some((n) => String(w.path || '').toLowerCase().includes('squad/' + n)))
              || items.find((w) => names.some((n) => String(w.title || w.name || '').toLowerCase() === n))
              || items.find((w) => names.some((n) => String(w.path || '').toLowerCase().endsWith('\\\\' + n)));
            if (hit) { boundHit = hit; wsId = hit.workspaceId || hit.id || null; }
          } catch {}
        }
        if (!wsId) {
          try {
            const wsvc = getSvc('workspaces');
            if (wsvc && typeof wsvc.create === 'function') {
              const created = await wsvc.create({ path: 'G:\\ai\\Naggar Print POS Agent\\orchestrator\\squad\\' + agentId });
              wsId = (created && (created.workspaceId || created.id)) || null;
              if (wsId && typeof wsvc.rename === 'function') { try { await wsvc.rename(wsId, (AGENT_MAP[agentId] || {}).name || agentId); } catch {} }
            }
          } catch {}
        }
        // 3-ب) جلسة جاهزة داخل مساحة الوكيل؟ افتحها فوراً بلا إنشاء (تنقّل أصلي)
        if (wsId && !sid) {
          try {
            const wsvc = getSvc('workspaces');
            const items = (wsvc && wsvc.list && wsvc.list.getSnapshot) ? (wsvc.list.getSnapshot().items || []) : [];
            const hit = items.find((w) => (w.workspaceId || w.id) === wsId);
            const sids = (hit && hit.sessionIds) || [];
            if (sids.length) sid = sids[sids.length - 1];
          } catch {}
        }
        if (sid) {
          nav(sid);
          try { localStorage.setItem('mcw.sid.' + agentId, sid); } catch {}
          try {
            const ref = sessionsSvc.retain(sid, { source: 'controllerOperation' });
            await ref.ready;
            saveRoom(agentId, { sessionId: sid });
            attachLive(agentId, ref.binding);
          } catch {}
          try { bridge.call('binding.ensure', { agent: agentId, workspaceId: wsId, workspaceTitle: (boundHit && boundHit.title) || null, workspacePath: (boundHit && boundHit.path) || null, preset: presetId, sessionId: sid }).catch(() => {}); } catch {}
          return { sessionId: sid, created: false, reused: true };
        }
        if (!wsId) throw new Error('لا توجد مساحة عمل للوكيل — شغّل الجسر ثم أعد المحاولة');
        // 4) إنشاء جلسة DSH جديدة داخل مساحة الوكيل + تنقّل أصلي فوري إلى المحادثة
        const sessionId = await uiWorkspace.connectWorkspace(wsId, { agentPreset: presetId });
        nav(sessionId);
        try { localStorage.setItem('mcw.sid.' + agentId, sessionId); } catch {}
        try { bridge.call('binding.ensure', { agent: agentId, workspaceId: wsId, workspaceTitle: (boundHit && boundHit.title) || (wsInfo && wsInfo.title) || null, workspacePath: (boundHit && boundHit.path) || (wsInfo && wsInfo.path) || null, preset: presetId, sessionId: sessionId }).catch(() => {}); } catch {}
        try {
          const ref = sessionsSvc.retain(sessionId, { source: 'controllerOperation' });
          await ref.ready;
          saveRoom(agentId, { sessionId, wsTitle: wsInfo ? wsInfo.title : null });
          attachLive(agentId, ref.binding);
          try {
            const pinned = await bridge.call('notebook.pinned', { limit: 20 }).catch(() => null);
            await ref.binding.session.prompt([{ type: 'text', text: buildBootPrompt(agentId, pinned) }], 'queue');
          } catch {}
        } catch {}
        return { sessionId, created: true, wsTitle: wsInfo ? wsInfo.title : null };
      }
      async function sendToSession(agentId, text) {
        let sid = (rooms[agentId] || {}).sessionId;
        if (!sid) {
          const created = await ensureAgentSession(agentId);
          sid = created.sessionId;
        }
        if (!sid) throw new Error('لا توجد جلسة مرتبطة');
        const ref = sessionsSvc.retain(sid, { source: 'controllerOperation' });
        await ref.ready;
        await ref.binding.session.prompt([{ type: 'text', text }], 'queue');
        return sid;
      }
      async function rebind(agent) {
        setLiveBusy(agent.id);
        try {
          const r = await ensureAgentSession(agent.id);
          showToast('⚡ جلسة DSH #' + String(r.sessionId).slice(0, 8) + (r.wsTitle ? ' في «' + r.wsTitle + '»' : ''));
        } catch (err) {
          showToast('⚡ تعذّر الربط: ' + String((err && err.message) || err));
        } finally { setLiveBusy(null); }
      }

      function openRoom(id) {
        setActiveId(id);
        setRooms((prev) => {
          const cur = prev[id] || { messages: [], scratch: '', unread: 0, delegated: false, sessionId: null };
          return Object.assign({}, prev, { [id]: Object.assign({}, cur, { unread: 0 }) });
        });
        // بذرة فورية من الكاش المحلي — المركز يرسم الشات الأصلي بلا انتظار الجسر
        try {
          const cachedSid = localStorage.getItem('mcw.sid.' + id);
          if (cachedSid) saveRoom(id, { sessionId: cachedSid });
        } catch {}
        // ربط تلقائي (Zero-Click): جلسة مطابقة للـPreset أو إنشاء فوري في الخلفية
        ensureAgentSession(id)
          .then((r) => showToast('⚡ جلسة DSH #' + String(r.sessionId).slice(0, 8) + (r.created ? ' (جديدة)' : ' (موجودة)') + ' — فُتحت المحادثة الأصلية'))
          .catch((err) => showToast('⚠ تعذّر فتح جلسة الوكيل: ' + String((err && err.message) || err)));
      }

      const active = AGENT_MAP[activeId] || AGENTS[0];
      const activeRoom = rooms[activeId] || { messages: [], scratch: '', unread: 0, delegated: false, sessionId: null };

      return h(McwBoundary, null,
        h('div', { className: 'mcw-root' },
          h(OmniBar, { onOpenPalette: () => setPaletteOpen(true), ping, ram, onRefresh: refresh, clock, presets, notesMeta: nbMeta, bars, onToggleBar: toggleBar }),
          h('div', { className: 'mcw-body' },
            h('div', { className: cls('mcw-drawer', !bars.right && 'hid') },
              h('div', { className: 'mcw-tabs' },
                h('button', { className: cls('mcw-tab', tab === 'nb' && 'on'), onClick: () => setTab('nb') }, '📓 أفكاري'),
                h('button', { className: cls('mcw-tab', tab === 'vision' && 'on'), onClick: () => setTab('vision') }, '👁️ مرسم فيجين'),
                h('button', { className: cls('mcw-tab', tab === 'ctx' && 'on'), onClick: () => setTab('ctx') }, '📊 السياق الحي'),
                h('button', { className: 'mcw-btn ghost', style: { alignSelf: 'center', marginInlineEnd: 4, fontSize: 10, padding: '1px 6px', flex: 'none' }, title: 'طي العمود — الغرفة تتمدد', onClick: () => toggleBar('right') }, '⟪')),
              tab === 'nb' ? h(NotebookPane, { notes, notesMeta: nbMeta, ping, onAddNote, onPin, onRefresh: refresh }) :
                tab === 'vision' ? h(VisionPane, { entries, onPreview, preview, onRefresh: refresh }) :
                  h(ContextPane, { pos, catalog, onRefresh: refresh })),
            h(RoomView, {
              key: active.id, agent: active, room: activeRoom, agentCtx: agentCtx[activeId],
              renderFactorySlot: props.renderFactorySlot,
              onCopyPrompt, onOpenDSH: openDSH, onRebind: rebind,
            }),
            h(AgentDock, { agents: AGENTS, groups: GROUPS, activeId, rooms, onOpen: openRoom, onOpenDSH: openDSH, hidden: !bars.left, onCollapse: () => toggleBar('left') })),
          h(Palette, { open: paletteOpen, onClose: () => setPaletteOpen(false), agents: AGENTS, notes, onAgent: openRoom, onAction: (act, n) => { if (act === 'openDSH') openDSH(); else if (act === 'refresh') refresh(); else if (act === 'note' && n) { setTab('nb'); } } }),
          h(Toast, { text: toast }),
          !bridgeErr && !ping ? h('div', { className: 'mcw-toast' }, '⏳ جارٍ الاتصال بجسر مروة…') : null,
          bridgeErr ? h('div', { className: 'mcw-toast', style: { borderColor: '#f87171', cursor: 'pointer' }, onClick: () => refresh(), title: 'اضغط لإعادة المحاولة' }, '⚠ الجسر غير متاح: ' + bridgeErr + ' — اضغط لإعادة المحاولة') : null));
    }

    // ------------------------------------------------------------------- أيقونة الشريط الجانبي
    function PanelIcon(props) {
      const { size, active } = props || {};
      const s = size || 22;
      return h('div', {
        style: {
          width: s, height: s, borderRadius: '30%', display: 'flex', alignItems: 'center', justifyContent: 'center',
          background: active ? 'linear-gradient(135deg,#d4af37,#8a6d1f)' : 'rgba(212,175,55,.12)',
          border: '1px solid ' + (active ? '#d4af37' : 'rgba(212,175,55,.45)'),
          boxShadow: active ? '0 0 10px rgba(212,175,55,.5)' : 'none',
          fontSize: s * 0.55, color: active ? '#09090b' : '#ecd58a',
        },
      }, 'م');
    }

    // ------------------------------------------------------------------- شريحة تحت صندوق الكتابة في الشات الأصلي
    function DockChip() {
      return h('div', { style: { display: 'flex', justifyContent: 'flex-start', padding: '2px 4px' } },
        h('button', {
          className: 'mcw-btn', style: { fontSize: 11 },
          onClick: () => { try { const l = getSvc('layout'); if (l && l.selectPanel) l.selectPanel('marwa-core'); } catch {} },
        }, '🛡️ غرفة عمليات مروة (الوكلاء · النوتبوك · فيجين · السياق)'));
    }

    // ------------------------------------------------------------------- التطبيق
    let ctxRef = null;
    const SVC = {}; // خدمات DSH المحقونة رسمياً عبر inject
    const svcListeners = new Set();
    function getSvc(k) { try { if (SVC[k]) return SVC[k]; } catch {} try { return ctxRef && ctxRef.get ? ctxRef.get(k) : undefined; } catch {} return undefined; }
    return {
      inject: ['slots', 'layout', 'workspaces', 'uiWorkspace', 'sessions'],
      apply(ctx) {
        ctxRef = ctx;
        try {
          const grab = (k) => { try { const v = ctx[k]; if (v) return v; } catch {} try { return ctx.get ? ctx.get(k) : undefined; } catch {} return undefined; };
          for (const k of ['layout', 'workspaces', 'uiWorkspace', 'sessions']) { try { SVC[k] = grab(k); } catch {} }
          for (const fn of Array.from(svcListeners)) { try { fn(); } catch {} }
        } catch {}
        let removeStyles = null;
        try { if (ctx.styles && typeof ctx.styles.insert === 'function') removeStyles = ctx.styles.insert(CSS); } catch {}
        if (!removeStyles) {
          try {
            const el = document.createElement('style');
            el.setAttribute('data-mcw', '1');
            el.textContent = CSS;
            (document.head || document.documentElement).appendChild(el);
            removeStyles = () => { try { el.remove(); } catch {} };
          } catch { removeStyles = () => {}; }
        }
        const disposers = [removeStyles];
        try {
          disposers.push(ctx.slots.inject('sidebar.panellist', () => ctx.slots.register({
            name: 'sidebar.panellist', id: 'marwa-core', order: 20, label: 'غرفة عمليات مروة',
          }, PanelIcon)));
        } catch (err) { console.error('[marwa-core] panellist', err); }
        try {
          disposers.push(ctx.slots.inject('main', () => ctx.slots.register({
            name: 'main', key: 'marwa-core',
          }, Workspace)));
        } catch (err) { console.error('[marwa-core] main', err); }
        try {
          disposers.push(ctx.slots.inject('conversation.composer.dock', () => ctx.slots.register({
            name: 'conversation.composer.dock', id: 'marwa-core-chip', order: 30,
          }, DockChip)));
        } catch (err) { console.error('[marwa-core] dock', err); }
        return function dispose() {
          disposers.forEach((d) => { try { d(); } catch {} });
        };
      },
    };
  },
});
