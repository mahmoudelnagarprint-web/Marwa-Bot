/**
 * Marwa Core Workspace — Client half: غرفة عمليات مروة (الهيكل الرباعي).
 *
 * الشاشة الرباعية:
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
      '@media (max-width:1100px){.mcw-dock{width:64px;min-width:56px}.mcw-dock .nm,.mcw-dock .mcw-group-title span{display:none}.mcw-drawer{width:250px}}',
    ].join('\n');

    // ------------------------------------------------------------------- أدوات مساعدة
    function cls() { return Array.prototype.slice.call(arguments).filter(Boolean).join(' '); }

    function fmtBytes(n) {
      if (!n && n !== 0) return '?';
      return (n / 1073741824).toFixed(1) + ' ج.ب';
    }

    function fmtTime(ts) {
      try { return new Date(ts).toLocaleTimeString('ar-EG', { hour: '2-digit', minute: '2-digit' }); } catch { return ''; }
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
      const { onOpenPalette, ping, ram, onRefresh, clock, presets } = props;
      const nb2 = ping && ping.nb2;
      const okPresets = Array.isArray(presets) ? presets.filter((p) => p && p.ok).length : -1;
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
        h('span', { className: 'mcw-chip', title: 'النوتبوك v2 (أفكاري) على المنفذ 8110' },
          h('span', { className: 'mcw-dot', style: { background: nb2 && nb2.up ? '#34d399' : '#f87171', boxShadow: nb2 && nb2.up ? '0 0 6px #34d399' : 'none' } }),
          nb2 ? (nb2.up ? 'أفكاري متصل' : 'أفكاري غير متصل') : 'أفكاري …'),
        h('span', { className: 'mcw-chip', title: 'استهلاك الرام الفعلي للورشة' },
          '🖥️ ', ram ? (fmtBytes(ram.used) + ' / ' + fmtBytes(ram.total)) : '…',
          h('span', { className: 'mcw-rambar' }, h('i', { style: { width: ram ? Math.min(100, Math.round((ram.used / ram.total) * 100)) + '%' : '0%' } }))),
        h('span', { className: 'mcw-chip' }, '📍 ' + (ping ? ping.node : '…')),
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
      const { agents, groups, activeId, rooms, onOpen, onOpenDSH } = props;
      return h('div', { className: 'mcw-dock' },
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

    function MsgBubble({ msg, accent, agentName, onApprove, onEditMsg, onAudit, onSaveNote }) {
      if (msg.kind === 'approval') {
        const approved = msg.status === 'approved';
        return h('div', { className: 'mcw-approval', style: { '--mcw-accent': accent } },
          h('h4', null, (approved ? '✅ ' : '🛡️ ') + (msg.title || 'إجراء بانتظار الاعتماد')),
          h('div', { className: 'det' }, msg.text || msg.details || ''),
          h('div', { className: 'acts' },
            approved ? h('span', { className: 'mcw-chip' }, '✓ تم الاعتماد والتنفيذ') :
              h('button', { className: 'mcw-approve', onClick: () => onApprove(msg) }, '✅ اعتماد وتنفيذ'),
            h('button', { className: 'mcw-editb', onClick: () => onEditMsg(msg) }, '✏️ تعديل'),
            h('button', { className: 'mcw-audit', onClick: () => onAudit(msg) }, '🦉 طلب تدقيق/مراجعة'),
            h('button', { className: 'mcw-savenote', onClick: () => onSaveNote(msg) }, '📓 حفظ في النوتبوك')));
      }
      if (msg.kind === 'note') {
        return h('div', { className: cls('mcw-msg', 'agent'), style: { '--mcw-accent': accent } },
          h('div', { className: 'who' }, '📓 نوت من النوتبوك'),
          renderBlocks(msg.text, accent));
      }
      if (msg.kind === 'system') {
        return h('div', { className: 'mcw-msg', style: { maxWidth: '96%', background: 'rgba(212,175,55,.05)', textAlign: 'center', fontSize: 11, color: 'rgba(236,231,218,.55)' } }, msg.text);
      }
      return h('div', { className: cls('mcw-msg', msg.kind === 'user' ? 'me' : 'agent'), style: { '--mcw-accent': accent } },
        msg.who ? h('div', { className: 'who' }, msg.who) : null,
        renderBlocks(msg.text, accent));
    }

    function ApprovalComposer({ onRequestApproval }) {
      const [open, setOpen] = useState(false);
      const [title, setTitle] = useState('');
      const [body, setBody] = useState('');
      const [cmd, setCmd] = useState('');
      if (!open) return h('button', { className: 'mcw-btn ghost', onClick: () => setOpen(true) }, '🛡️ بوابة اعتماد');
      return h('div', { className: 'mcw-approval', style: { margin: '0 16px 8px' } },
        h('h4', null, '🛡️ إجراء حساس — بانتظار اعتماد المالك'),
        h('input', { placeholder: 'العنوان (مثال: اعتماد سعر #333)', value: title, onChange: (e) => setTitle(e.target.value), style: { width: '100%', marginBottom: 6, background: 'rgba(9,9,11,.7)', border: '1px solid rgba(212,175,55,.3)', borderRadius: 8, color: '#ece7da', padding: '6px 9px', fontFamily: 'inherit' } }),
        h('textarea', { placeholder: 'التفاصيل…', value: body, onChange: (e) => setBody(e.target.value), style: { width: '100%', minHeight: 46, marginBottom: 6, background: 'rgba(9,9,11,.7)', border: '1px solid rgba(212,175,55,.3)', borderRadius: 8, color: '#ece7da', padding: '6px 9px', fontFamily: 'inherit', resize: 'vertical' } }),
        h('input', { placeholder: 'أمر التنفيذ بعد الاعتماد (يُنسخ للحافظة)', value: cmd, onChange: (e) => setCmd(e.target.value), style: { width: '100%', marginBottom: 8, background: 'rgba(9,9,11,.7)', border: '1px solid rgba(212,175,55,.3)', borderRadius: 8, color: '#ece7da', padding: '6px 9px', fontFamily: 'inherit', direction: 'ltr', textAlign: 'left' } }),
        h('div', { className: 'acts' },
          h('button', { className: 'mcw-approve', onClick: () => { onRequestApproval({ title, body, cmd }); setOpen(false); setTitle(''); setBody(''); setCmd(''); } }, 'إرسال للبوابة'),
          h('button', { className: 'mcw-btn ghost', onClick: () => setOpen(false) }, 'إلغاء')));
    }

    function RoomView(props) {
      const { agent, room, notes, bridge, onSend, onChip, onToggleScratch, onApprove, onEditMsg, onAudit, onSaveNote, onRequestApproval, onCopyPrompt, onOpenDSH, onRebind, onInjectNote, openPanel, noteDraft, setNoteDraft, binding } = props;
      const accent = agent.color;
      const msgs = (room && room.messages) || [];
      const [draft, setDraft] = useState('');
      const [mentionOpen, setMentionOpen] = useState(false);
      const [mentionFilter, setMentionFilter] = useState('');
      const [notePick, setNotePick] = useState(false);
      const composerRef = useRef(null);

      function onComposerChange(e) {
        const v = e.target.value;
        setDraft(v);
        const m = v.match(/@([\u0600-\u06FF\w]*)$/);
        setMentionOpen(!!m);
        setMentionFilter(m ? m[1] : '');
      }
      function pickMention(agentId) {
        const a = AGENT_MAP[agentId];
        const v = draft.replace(/@[\u0600-\u06FF\w]*$/, '@' + a.name + ' ');
        setDraft(v);
        setMentionOpen(false);
        if (composerRef.current) composerRef.current.focus();
      }
      function send() {
        if (!draft.trim()) return;
        onSend(draft.trim());
        setDraft('');
        setMentionOpen(false);
      }
      function injectNote(note) {
        setDraft(draft + (draft ? '\n' : '') + '[📓 #' + note.id + '] ' + note.title);
        setNotePick(false);
        if (composerRef.current) composerRef.current.focus();
      }

      return h('div', { className: 'mcw-center' },
        h('div', { className: 'mcw-roomhead', style: { '--mcw-accent': accent } },
          h('div', { className: 'mcw-emoji' }, agent.emoji),
          h('div', null,
            h('h2', null, agent.name + ' ' + (agent.nick ? '— ' + agent.nick : '')),
            h('small', null, agent.role + (agent.external ? ' · مسار خارجي: ' + agent.prompt : ''))),
          h('div', { className: 'mcw-roomacts' },
            room && room.sessionId ? h('span', { className: 'mcw-chip', title: 'جلسة DSH مرتبطة: ' + room.sessionId }, '⚡ DSH #' + String(room.sessionId).slice(0, 8)) : null,
            h('button', { className: 'mcw-btn ghost', title: 'نسخ برومبت تفعيل الشخصية', onClick: () => onCopyPrompt(agent) }, '📋 البرومبت'),
            h('button', { className: 'mcw-btn ghost', onClick: onOpenDSH }, '🗨 فتح في DSH'),
            h('button', { className: 'mcw-btn', onClick: () => onRebind(agent) }, '⚡ ربط جلسة DSH'))),
        h('div', { className: 'mcw-msgs' },
          msgs.length === 0 ?
            h('div', { className: 'mcw-empty' }, 'غرفة ' + agent.name + ' — أرسل تكليفاً أو استخدم الأزرار السريعة. (الردود الحقيقية تُنفَّذ في جلسة DSH الأصلية للوكيل)') :
            msgs.map((m) => h(MsgBubble, {
              key: m.id, msg: m, accent, agentName: agent.name,
              onApprove, onEditMsg, onAudit, onSaveNote,
            }))),
        h('details', { className: 'mcw-scratch' },
          h('summary', null, '🧠 Scratchpad — تفكير ' + agent.name + ' الداخلي' + (room && room.scratch ? ' ✍️' : '')),
          h('textarea', { placeholder: 'ملاحظات تفكير/ذاكرة مؤقتة للوكيل (تُحفظ محلياً)', value: (room && room.scratch) || '', onChange: (e) => onToggleScratch(e.target.value) })),
        h('div', { className: 'mcw-chips' },
          (agent.chips || []).map((c) => h('button', { key: c.label, className: 'mcw-btn', onClick: () => onChip(c.text) }, c.label)),
          h('button', { className: 'mcw-btn ghost', onClick: () => setNotePick(!notePick) }, '# حقن نوت من النوتبوك')),
        (notePick ? h('div', { className: 'mcw-scratch', style: { padding: 8, maxHeight: 160, overflow: 'auto' } },
          (notes || []).filter((n) => n.status === 'open').slice(0, 8).map((n) =>
            h('div', { key: n.id, className: 'mcw-note', style: { cursor: 'pointer' }, onClick: () => injectNote(n) },
              h('b', null, '#' + n.id + ' · ' + n.title),
              h('p', null, n.body || '')))) : null),
        h(ApprovalComposer, { onRequestApproval }),
        h('div', { className: 'mcw-composer' },
          h('textarea', {
            ref: composerRef, value: draft, onChange: onComposerChange,
            placeholder: 'اكتب للوكيل…  ( @اسم_وكيل = استدعاء تعاوني · # = حقن نوت )',
            onKeyDown: (e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); } },
          }),
          h('button', { className: 'mcw-send', onClick: send }, 'إرسال ↵')),
        (mentionOpen ?
          h('div', { className: 'mcw-scratch', style: { position: 'absolute', bottom: 86, insetInline: 40, zIndex: 30, maxHeight: 200, overflow: 'auto' } },
            AGENTS.filter((a) => a.id !== agent.id && (!mentionFilter || a.name.includes(mentionFilter) || a.nick.includes(mentionFilter))).map((a) =>
              h('div', { key: a.id, className: 'mcw-note', style: { cursor: 'pointer', margin: 0, borderInlineStart: '3px solid ' + a.color }, onClick: () => pickMention(a.id) },
                h('b', null, a.emoji + ' ' + a.name + ' — ' + a.nick)))) : null));
    }

    function NotebookPane(props) {
      const { notes, ping, onAddNote, onPin, onRefresh } = props;
      const [title, setTitle] = useState('');
      const [body, setBody] = useState('');
      const [kind, setKind] = useState('note');
      const [priority, setPriority] = useState('normal');
      const nb2 = ping && ping.nb2;
      return h('div', { className: 'mcw-tabpane' },
        h('div', { style: { display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 } },
          h('span', { className: 'mcw-dot', style: { background: nb2 && nb2.up ? '#34d399' : '#f87171' } }),
          h('span', { style: { fontSize: 11, color: 'rgba(236,231,218,.65)' } }, nb2 ? (nb2.up ? 'أفكاري v2 متصل (8110)' : 'أفكاري v2 غير متصل — عرض المخزن المحلي') : '…'),
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
        (notes || []).map((n) => h('div', { key: n.id, className: 'mcw-note' },
          h('b', null, (n.emoji || '📁') + ' #' + n.id + ' · ' + n.title + (n.status === 'done' ? ' ✓' : '')),
          h('p', null, n.body || ''),
          h('div', { className: 'meta' }, '[' + n.kind + '] ' + n.priority + ' · ' + (n.category || '') + ' · ' + (n.due_at ? 'موعد: ' + n.due_at : '')),
          h('div', { style: { display: 'flex', gap: 4, marginTop: 4 } },
            h('button', { className: 'mcw-btn ghost', onClick: () => onPin(n) }, n.priority === 'high' ? '📌 مثبت' : '📌 تثبيت'),
            h('button', { className: 'mcw-btn ghost', onClick: () => copyText('#قاعدة ' + n.title + '\n' + (n.body || '')) }, 'نسخ كقاعدة')))));
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
      const [catalog, setCatalog] = useState(null);
      const [pos, setPos] = useState(null);
      const [entries, setEntries] = useState(null);
      const [preview, setPreview] = useState(null);
      const [presets, setPresets] = useState(null);
      const [toast, setToast] = useState(null);
      const [rooms, setRooms] = useState(() => { try { return JSON.parse(localStorage.getItem('mcw.rooms.v1') || '{}'); } catch { return {}; } });
      const [noteDraft, setNoteDraft] = useState('');

      // خلفيات / خدمات
      const layout = useMemo(() => { try { return ctx.get ? ctx.get('layout') : undefined; } catch { return undefined; } }, []);
      const uiWorkspace = useMemo(() => { try { return ctx.get ? ctx.get('uiWorkspace') : undefined; } catch { return undefined; } }, []);
      const sessionsSvc = useMemo(() => { try { return ctx.get ? ctx.get('sessions') : undefined; } catch { return undefined; } }, []);

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
          if (nb) setNotes(nb.notes || []);
          if (cat) setCatalog(cat);
          if (po) setPos(po);
          if (vis) setEntries(vis.entries || []);
          if (pr && Array.isArray(pr.presets)) setPresets(pr.presets);
        } catch (err) {
          setBridgeErr(String((err && err.message) || err));
        }
      }, [bridge]);

      useEffect(() => { refresh(); const t = setInterval(refresh, 30000); return () => clearInterval(t); }, [refresh]);

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

      // ------------------------------------------------ ربط الجلسات التلقائي (Zero-Click)
      const [liveBusy, setLiveBusy] = useState(null);
      const wsSnapRef = useRef(null);
      try { if (props.useWorkspaces) wsSnapRef.current = props.useWorkspaces(); } catch {}
      function currentWorkspaceId() {
        try {
          const snap = wsSnapRef.current;
          return (snap && snap.current && snap.current.id) || (snap && snap.items && snap.items[0] && snap.items[0].id) || null;
        } catch { return null; }
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
        // 1) جلسة مسجّلة محلياً (localStorage) ما زالت حية؟
        let sid = null;
        try { sid = localStorage.getItem('mcw.sid.' + agentId); } catch {}
        if (sid) {
          try {
            const ref = sessionsSvc.retain(sid, { source: 'controllerOperation' });
            await ref.ready;
            saveRoom(agentId, { sessionId: sid });
            attachLive(agentId, ref.binding);
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
            return { sessionId: sid, created: false, found: true };
          }
        } catch {}
        // 3) إنشاء جلسة DSH جديدة تلقائياً بالـPreset + حقن ملاحظات النوتبوك المثبتة
        const wsId = currentWorkspaceId();
        const sessionId = await uiWorkspace.connectWorkspace(wsId, { agentPreset: presetId });
        try { localStorage.setItem('mcw.sid.' + agentId, sessionId); } catch {}
        const ref = sessionsSvc.retain(sessionId, { source: 'controllerOperation' });
        await ref.ready;
        saveRoom(agentId, { sessionId });
        attachLive(agentId, ref.binding);
        try {
          const pinned = await bridge.call('notebook.pinned', { limit: 20 }).catch(() => null);
          await ref.binding.session.prompt([{ type: 'text', text: buildBootPrompt(agentId, pinned) }], 'queue');
        } catch {}
        return { sessionId, created: true };
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
          showToast('⚡ جلسة DSH مرتبطة #' + String(r.sessionId).slice(0, 8));
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
        // ربط تلقائي (Zero-Click): جلسة مطابقة للـPreset أو إنشاء فوري في الخلفية
        ensureAgentSession(id)
          .then((r) => showToast('⚡ جلسة DSH تلقائية #' + String(r.sessionId).slice(0, 8) + (r.created ? ' (جديدة)' : ' (موجودة)')))
          .catch(() => { /* الغرفة تعمل محلياً؛ الخطأ يظهر عند أول تنفيذ */ });
      }

      const active = AGENT_MAP[activeId] || AGENTS[0];
      const activeRoom = rooms[activeId] || { messages: [], scratch: '', unread: 0, delegated: false, sessionId: null };

      return h(McwBoundary, null,
        h('div', { className: 'mcw-root' },
          h(OmniBar, { onOpenPalette: () => setPaletteOpen(true), ping, ram, onRefresh: refresh, clock, presets }),
          h('div', { className: 'mcw-body' },
            h('div', { className: 'mcw-drawer' },
              h('div', { className: 'mcw-tabs' },
                h('button', { className: cls('mcw-tab', tab === 'nb' && 'on'), onClick: () => setTab('nb') }, '📓 أفكاري'),
                h('button', { className: cls('mcw-tab', tab === 'vision' && 'on'), onClick: () => setTab('vision') }, '👁️ مرسم فيجين'),
                h('button', { className: cls('mcw-tab', tab === 'ctx' && 'on'), onClick: () => setTab('ctx') }, '📊 السياق الحي')),
              tab === 'nb' ? h(NotebookPane, { notes, ping, onAddNote, onPin, onRefresh: refresh }) :
                tab === 'vision' ? h(VisionPane, { entries, onPreview, preview, onRefresh: refresh }) :
                  h(ContextPane, { pos, catalog, onRefresh: refresh })),
            h(RoomView, {
              agent: active, room: activeRoom, notes, bridge,
              onSend, onChip, onToggleScratch: (v) => saveRoom(activeId, { scratch: v }),
              onApprove, onEditMsg, onAudit, onSaveNote, onRequestApproval,
              onCopyPrompt, onOpenDSH: openDSH, onRebind: rebind,
              onInjectNote: null, openPanel: () => { try { if (layout && layout.selectPanel) layout.selectPanel('marwa-core'); } catch {} },
              noteDraft, setNoteDraft,
            }),
            h(AgentDock, { agents: AGENTS, groups: GROUPS, activeId, rooms, onOpen: openRoom, onOpenDSH: openDSH })),
          h(Palette, { open: paletteOpen, onClose: () => setPaletteOpen(false), agents: AGENTS, notes, onAgent: openRoom, onAction: (act, n) => { if (act === 'openDSH') openDSH(); else if (act === 'refresh') refresh(); else if (act === 'note' && n) { setTab('nb'); } } }),
          h(Toast, { text: toast }),
          !bridgeErr && !ping ? h('div', { className: 'mcw-toast' }, '⏳ جارٍ الاتصال بجسر مروة…') : null,
          bridgeErr ? h('div', { className: 'mcw-toast', style: { borderColor: '#f87171' } }, '⚠ الجسر غير متاح: ' + bridgeErr) : null));
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
          onClick: () => { try { const l = ctx.get ? ctx.get('layout') : undefined; if (l && l.selectPanel) l.selectPanel('marwa-core'); } catch {} },
        }, '🛡️ غرفة عمليات مروة (الوكلاء · النوتبوك · فيجين · السياق)'));
    }

    // ------------------------------------------------------------------- التطبيق
    let ctxRef = null;
    return {
      inject: ['slots'],
      apply(ctx) {
        ctxRef = ctx;
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
