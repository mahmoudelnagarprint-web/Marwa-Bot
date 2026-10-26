/**
 * Marwa Core Workspace — Host half of the native DSH UI plugin.
 *
 * يوفّر مسار POST واحد مُصادق داخل Harness نفسه:  POST /marwa-core/api
 *   body: { endpoint: string, params?: object }
 *   resp: { ok: true, value } | { ok: false, error }
 *
 * نقاط النهاية (بلا أعمال كتابة على قاعدة البرنامج — قراءة فقط):
 *   ping            — هوية العقدة (NODE_ID من .env دون أي أسرار) + مؤشر NB2 8110 + أزمنة الملفات
 *   ram             — استهلاك الرام الفعلي للجهاز (os.totalmem/freemem + rss)
 *   notebook.*      — عبر الجسر (store الرسمي v1)
 *   catalog.rows    — الكتالوج الماستر
 *   pos.stats       — مرآة POS المحلية (قراءة فقط)
 *   vision.*        — معمل فيجن (قراءة فقط)
 *   squad.prompts   — دفاتر تفعيل الشخصيات
 *   presets.status  — حالة الـ10 Agent Presets الحية
 *   presets.rebuild — إعادة بناء الـPresets من الدساتير (تحديث حي)
 *   sessions.findForPreset — إيجاد جلسة DSH نشطة مسجّلة لنفس الـPreset
 */
import { spawn } from 'node:child_process';
import { existsSync, readFileSync, statSync, writeFileSync } from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const DEFAULTS = { repoRoot: 'G:\\Marwa-Bot', routePath: '/api/marwa-core', idleShutdownMs: 300000, nb2Url: 'http://127.0.0.1:8110' };

// ------------------------------------------------------------------- تحديد دليل الحزمة بموثوقية
// import.meta.url قد يكون مساراً وهمياً تحت مُحمّل DSH — نجرّب مرشحين ونثبت بالوجود الفعلي للجسر.
function resolvePluginDir() {
  const candidates = [];
  try {
    const u = String(import.meta.url);
    if (u.startsWith('file:')) {
      const p = new URL(u).pathname.replace(/^\/([A-Za-z]:)/, '$1');
      candidates.push(path.dirname(p));
    }
  } catch {}
  if (process.env.DSH_PROFILE_DIR) {
    candidates.push(path.join(process.env.DSH_PROFILE_DIR, 'node_modules', '@local', 'marwa-core-workspace'));
  }
  candidates.push(path.join(process.cwd(), 'dsh-plugins', 'marwa-core-workspace'));
  candidates.push(path.join(process.cwd(), 'node_modules', '@local', 'marwa-core-workspace'));
  candidates.push('G:\\Marwa-Bot\\dsh-plugins\\marwa-core-workspace');
  for (const c of candidates) {
    try { if (c && existsSync(path.join(c, 'bridge', 'dsh_bridge.py'))) return c; } catch {}
  }
  return candidates[0] || '.';
}

export function apply(ctx, config) {
  const cfg = Object.assign({}, DEFAULTS, config || {});
  const pluginDir = resolvePluginDir();
  const bridgePath = path.join(pluginDir, 'bridge', 'dsh_bridge.py');

  // علامة إقلاع متزامنة — دليل على عمل هذا الجيل من الكود + مكان الكتابة الفعلي
  try {
    writeFileSync(path.join(pluginDir, 'boot.log'),
      JSON.stringify({ at: Date.now(), route: cfg.routePath, cwd: process.cwd(), metaUrl: String(import.meta.url), pluginDir, bridgePath, node: process.version }, null, 2), 'utf8');
  } catch (e) {
    try { writeFileSync(path.join(process.cwd(), 'boot.err.log'), JSON.stringify({ at: Date.now(), err: String((e && e.message) || e), pluginDir }), 'utf8'); } catch {}
  }

  // ------------------------------------------------------------- جسر بايثون (JSON-lines)
  let proc = null;
  let pending = new Map();
  let seq = 0;
  let idleTimer = null;
  let buffer = '';

  function pyExe() {
    const venv = path.join(cfg.repoRoot, '.venv', 'Scripts', 'python.exe');
    return existsSync(venv) ? venv : 'python';
  }

  function ensureBridge() {
    if (proc && !proc.killed && proc.exitCode === null) return proc;
    pending = new Map();
    buffer = '';
    proc = spawn(pyExe(), [bridgePath], {
      cwd: cfg.repoRoot,
      env: Object.assign({}, process.env, { MARWA_REPO_ROOT: cfg.repoRoot, PYTHONIOENCODING: 'utf-8', PYTHONUTF8: '1' }),
      windowsHide: true,
    });
    proc.stdout.setEncoding('utf8');
    proc.stdout.on('data', (chunk) => {
      buffer += chunk;
      let idx;
      while ((idx = buffer.indexOf('\n')) >= 0) {
        const line = buffer.slice(0, idx).trim();
        buffer = buffer.slice(idx + 1);
        if (!line) continue;
        let msg;
        try { msg = JSON.parse(line); } catch { continue; }
        const entry = pending.get(msg.id);
        if (entry) {
          pending.delete(msg.id);
          clearTimeout(entry.timer);
          if (msg.ok) entry.resolve(msg.value);
          else entry.reject(new Error(msg.error || 'bridge failure'));
        }
      }
    });
    proc.on('error', (err) => {
      for (const [, entry] of pending) {
        clearTimeout(entry.timer);
        entry.reject(new Error('bridge spawn: ' + (err && err.message || err)));
      }
      pending = new Map();
      proc = null;
    });
    proc.on('exit', () => {
      for (const [, entry] of pending) {
        clearTimeout(entry.timer);
        entry.reject(new Error('bridge exited'));
      }
      pending = new Map();
      if (proc) { try { proc.kill(); } catch {} }
      proc = null;
    });
    return proc;
  }

  function bumpIdle() {
    if (idleTimer) clearTimeout(idleTimer);
    idleTimer = setTimeout(() => {
      if (proc) { try { proc.kill(); } catch {} proc = null; }
    }, cfg.idleShutdownMs);
    if (idleTimer.unref) idleTimer.unref();
  }

  function bridgeCall(cmd, params, timeoutMs = 25000) {
    ensureBridge();
    bumpIdle();
    const id = 'r' + (++seq);
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        pending.delete(id);
        reject(new Error('bridge timeout: ' + cmd));
      }, timeoutMs);
      pending.set(id, { resolve, reject, timer });
      try {
        proc.stdin.write(JSON.stringify({ id, cmd, params: params || {} }) + '\n');
      } catch (err) {
        clearTimeout(timer);
        pending.delete(id);
        reject(err);
      }
    });
  }

  // ------------------------------------------------------------- نقاط النهاية من جانب Node
  function readNodeId() {
    try {
      const envText = readFileSync(path.join(cfg.repoRoot, '.env'), 'utf8');
      const m = envText.match(/^\s*NODE_ID\s*=\s*"?([A-Za-z0-9_-]+)"?/m);
      return m ? m[1] : 'UNKNOWN';
    } catch {
      return 'UNKNOWN';
    }
  }

  async function probeNb2() {
    try {
      const res = await fetch(cfg.nb2Url, { signal: AbortSignal.timeout(1500) });
      return { up: res.ok || res.status < 500, status: res.status, url: cfg.nb2Url };
    } catch {
      return { up: false, url: cfg.nb2Url };
    }
  }

  function mtimeOf(p) {
    try { return statSync(p).mtimeMs; } catch { return 0; }
  }

  // ------------------------------------------------------------- Agent Presets (10 وكلاء حية)
  // تُبنى عند الإقلاع من دساتير الوكلاء الفعلية (orchestrator/squad + ميثاق مروة + مسارات
  // Notebook v2 / Vision-Lab) وتُسجَّل عبر خدمة agentPresets الرسمية — ربط صفر نقر للغرف.
  const PRESET_SPECS = [
    { id: 'marwa', name: 'مروة — المنسق العام', order: 1,
      prompt: 'AGENT.md',
      refs: ['RULES.md', 'STATUS.md', 'MARWA_CORE.md', 'memory/'],
      tools: [{ name: '@deepseek-ai/dsh-tool-web' }] },
    { id: 'notebook', name: 'أفكاري — الذاكرة الثانية (Notebook v2)', order: 2,
      prompt: 'Vision-Lab/projects/notebook-v2/NB2_CHAT_BOOTSTRAP_PROMPT.md',
      refs: ['Vision-Lab/projects/notebook-v2/', 'notebook/'],
      tools: [] },
    { id: 'rased', name: 'راصد — المراقب الذاتي', order: 3,
      prompt: 'orchestrator/squad/rased/CHAT_BOOTSTRAP_PROMPT.md',
      refs: ['memory/experience_ledger.json'],
      tools: [] },
    { id: 'hakim', name: 'حكيم — طبيب البيانات', order: 4,
      prompt: 'orchestrator/squad/hakim/CHAT_BOOTSTRAP_PROMPT.md',
      refs: ['tools/export_products_excel.py', 'tools/import_products_excel.py', 'pos_data.db'],
      tools: [] },
    { id: 'fares', name: 'فارس — المدير المالي', order: 5,
      prompt: 'orchestrator/squad/fares/CHAT_BOOTSTRAP_PROMPT.md',
      refs: ['FARES_CFO_STATE.md'],
      tools: [] },
    { id: 'salma', name: 'سلمى — علاقات العملاء', order: 6,
      prompt: 'orchestrator/squad/salma/CHAT_BOOTSTRAP_PROMPT.md',
      refs: ['SALMA_CRM_STATE.md'],
      tools: [] },
    { id: 'koko', name: 'كوكو — التسويق والعروض', order: 7,
      prompt: 'orchestrator/squad/koko/CHAT_BOOTSTRAP_PROMPT.md',
      refs: ['KOKO_MARKETING_STATE.md', 'exports/products_catalog_master.xlsx'],
      tools: [{ name: '@deepseek-ai/dsh-tool-web', config: { fetch: true, searchTimeoutMs: 60000 } }] },
    { id: 'bibo', name: 'بيبو — التصنيع والليزر', order: 8,
      prompt: 'orchestrator/squad/bibo/CHAT_BOOTSTRAP_PROMPT.md',
      refs: ['BIBO_MANUFACTURING_STATE.md'],
      tools: [] },
    { id: 'sasa', name: 'مصطفى (صاصا) — التحكم بالكمبيوتر', order: 9,
      prompt: 'orchestrator/squad/sasa/CHAT_BOOTSTRAP_PROMPT.md',
      refs: ['agents/SASA/SASA_LAPTOP_STATE.md', 'agents/SASA/scripts/laptop_health.ps1', 'orchestrator/agents/system_apps.json'],
      tools: [
        { name: '@deepseek-ai/dsh-tool-pwsh', disabled: process.platform !== 'win32' },
        { name: '@deepseek-ai/dsh-tool-bash', disabled: process.platform === 'win32' },
        { name: '@deepseek-ai/dsh-tool-fs' },
      ] },
    { id: 'vision', name: 'فيجن — الكودر والتطوير', order: 10,
      prompt: 'Vision-Lab/SQUAD_BOOTSTRAP_PROMPT.md',
      refs: ['Vision-Lab/', 'Vision-Lab/AGENT.md', 'Vision-Lab/RULES.md', 'memory/experience_ledger.json'],
      tools: [
        { name: '@deepseek-ai/dsh-tool-bash', disabled: process.platform === 'win32' },
        { name: '@deepseek-ai/dsh-tool-pwsh', disabled: process.platform !== 'win32' },
        { name: '@deepseek-ai/dsh-tool-fs' },
        { name: '@deepseek-ai/dsh-tool-fs-search' },
      ] },
  ];
  const presetDisposers = new Map();
  let presetLog = { at: 0, entries: [], error: null, buildMode: 'boot' };
  let presetsRunning = Promise.resolve();

  function writePresetLog() {
    try {
      writeFileSync(path.join(pluginDir, 'presets.last.log'),
        JSON.stringify({ at: Date.now(), buildMode: presetLog.buildMode, error: presetLog.error, entries: presetLog.entries }, null, 2), 'utf8');
    } catch {}
  }

  function readUpTo(p) {
    try { return readFileSync(path.join(cfg.repoRoot, p), 'utf8').trim(); } catch { return null; }
  }

  function composePrompt(spec, pinned) {
    const parts = [];
    const base = readUpTo(spec.prompt);
    parts.push(base && base.length > 0
      ? base
      : ('أنت ' + spec.name + ' — وكيل متخصص في منظومة النجار برنت تحت إدارة مروة. اقرأ مراجعك وأجب بصدق، ولا تختلق أرقاماً أبداً.'));
    if (spec.refs && spec.refs.length) {
      parts.push('🗂️ مراجعك الرسمية (من داخل مستودع G:\\Marwa-Bot):\n' + spec.refs.map((r) => '• ' + r).join('\n'));
    }
    if (pinned && pinned.notes && pinned.notes.length) {
      const txt = pinned.notes.map((n) => '• [' + (n.kind || 'note') + '] ' + (n.title || '') + (n.body ? ' — ' + String(n.body).slice(0, 260) : '')).join('\n');
      parts.push('📌 قرارات/ملاحظات المالك المثبتة من النوتبوك (اعرفها قبل أي رد):\n' + txt);
    }
    return parts.join('\n\n').slice(0, 14000);
  }

  function withTimeout(promise, ms) {
    return Promise.race([
      Promise.resolve(promise),
      new Promise((_, rej) => setTimeout(() => rej(new Error('timeout ' + ms + 'ms')), ms)),
    ]);
  }

  async function ensurePresets(mode) {
    presetLog = { at: 0, entries: [], error: null, buildMode: mode || 'boot' };
    const reg = ctx.get ? ctx.get('agentPresets') : undefined;
    if (!reg || typeof reg.register !== 'function') {
      presetLog.error = 'خدمة agentPresets غير متاحة في هذا المضيف';
      writePresetLog();
      return presetLog;
    }
    let pinned = null;
    try { pinned = await withTimeout(bridgeCall('notebook.pinned', { limit: 20 }), 15000); }
    catch (e) { presetLog.error = 'notebook.pinned: ' + String((e && e.message) || e); }
    // حارس تخطٍّ: لا نسجّل Preset موجوداً وسليماً (تجنب «Duplicate» مع الصفوف الثابتة/الموجودة)
    let roster = [];
    try { roster = await withTimeout(reg.list(), 10000); } catch {}
    const results = [];
    for (const spec of PRESET_SPECS) {
      try {
        const existing = roster.find((r) => r && r.id === spec.id && !r.broken);
        if (existing) {
          results.push({ id: spec.id, ok: true, existing: true });
          continue;
        }
        const plugins = [{ name: '@deepseek-ai/dsh-persona', config: { prefix: composePrompt(spec, pinned) } }].concat(spec.tools);
        const dispose = await withTimeout(reg.register({
          id: spec.id,
          name: spec.name,
          order: spec.order,
          description: 'Preset تلقائي من دساتير منظومة مروة — ' + spec.name,
          plugins,
        }), 20000);
        presetDisposers.set(spec.id, dispose);
        results.push({ id: spec.id, ok: true });
      } catch (err) {
        const msg = String((err && err.message) || err);
        if (msg.includes('Duplicate')) {
          // مسجّل سابقاً (بقايا دورة قديمة لم يُتخلَّص منها بعد) — نتسامح ونكمل:
          try {
            const existing = await withTimeout(reg.resolve(spec.id), 5000);
            if (existing && existing.id === spec.id) {
              results.push({ id: spec.id, ok: true, existing: true });
              continue;
            }
          } catch {}
        }
        results.push({ id: spec.id, ok: false, error: msg });
      }
    }
    presetLog.at = Date.now();
    presetLog.entries = results;
    writePresetLog();
    return presetLog;
  }

  async function dispatch(endpoint, params) {
    switch (endpoint) {
      case 'ping': {
        const [nb2] = await Promise.all([probeNb2()]);
        return {
          ok: true,
          node: readNodeId(),
          repoRoot: cfg.repoRoot,
          time: Date.now(),
          nb2,
          files: {
            posDb: mtimeOf(path.join(cfg.repoRoot, 'pos_data.db')),
            catalog: mtimeOf(path.join(cfg.repoRoot, 'exports', 'products_catalog_master.xlsx')),
            notebook: mtimeOf(path.join(cfg.repoRoot, 'notebook', 'data', 'notebook.db')),
          },
        };
      }
      case 'ram':
        return {
          total: os.totalmem(), free: os.freemem(),
          used: os.totalmem() - os.freemem(),
          rss: process.memoryUsage ? process.memoryUsage().rss : 0,
          platform: os.platform(), cpus: os.cpus ? os.cpus().length : 0,
        };
      case 'presets.status':
        return {
          presets: PRESET_SPECS.map((s) => {
            const e = (presetLog.entries || []).find((x) => x.id === s.id);
            return { id: s.id, name: s.name, ok: !!(e && e.ok), error: e && e.error };
          }),
          log: { at: presetLog.at, buildMode: presetLog.buildMode, error: presetLog.error },
        };
      case 'presets.rebuild':
        presetsRunning = ensurePresets('manual');
        await presetsRunning;
        return presetLog;
      case 'sessions.findForPreset': {
        const presetId = params && typeof params.presetId === 'string' ? params.presetId : '';
        const sessionsSvc = ctx.get ? ctx.get('sessions') : undefined;
        if (!sessionsSvc || typeof sessionsSvc.list !== 'function') {
          return { sessionId: null, available: false, liveCount: -1 };
        }
        const all = sessionsSvc.list();
        const match = all.find((s) => s && s.header && s.header.agentPreset === presetId);
        return { sessionId: match ? match.id : null, available: true, liveCount: all.length };
      }
      default:
        return bridgeCall(endpoint, params);
    }
  }

  // ------------------------------------------------------------- مسار الـAPI المُصادق
  async function handler(request) {
    let body = null;
    try { body = await request.json(); } catch { body = null; }
    const endpoint = body && typeof body.endpoint === 'string' ? body.endpoint : '';
    const params = body && body.params && typeof body.params === 'object' ? body.params : {};
    if (!endpoint) return Response.json({ ok: false, error: 'endpoint required' });
    try {
      const value = await dispatch(endpoint, params);
      return Response.json({ ok: true, value });
    } catch (err) {
      return Response.json({ ok: false, error: String((err && err.message) || err) });
    }
  }

  const disposers = [];
  const connection = ctx.get ? ctx.get('connection') : undefined;
  if (connection && connection.fetch && typeof connection.fetch.register === 'function') {
    const un = connection.fetch.register({
      path: cfg.routePath,
      methods: ['POST'],
      requestBody: 'buffered',
      fetch: (request) => handler(request),
    });
    disposers.push(() => Promise.resolve(un).catch(() => {}));
  }
  const webServer = ctx.get ? ctx.get('webServer') : undefined;
  if (!connection && webServer && typeof webServer.register === 'function') {
    const un = webServer.register({ path: cfg.routePath, methods: ['POST'], fetch: (request) => handler(request) });
    disposers.push(() => Promise.resolve(un).catch(() => {}));
  }

  // بناء الـ10 Agent Presets الحية من الدساتير عند الإقلاع (لا يحجب تفعيل الصف)
  presetsRunning = ensurePresets('boot').catch((err) => {
    presetLog.error = String((err && err.message) || err);
    writePresetLog();
  });

  return function dispose() {
    if (idleTimer) clearTimeout(idleTimer);
    if (proc) { try { proc.kill(); } catch {} proc = null; }
    for (const [, disposePreset] of presetDisposers) {
      try { Promise.resolve(disposePreset()).catch(() => {}); } catch {}
    }
    presetDisposers.clear();
    for (const d of disposers) { try { d(); } catch {} }
  };
}
