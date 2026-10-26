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
 */
import { spawn } from 'node:child_process';
import { existsSync, readFileSync, statSync } from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const DEFAULTS = { repoRoot: 'G:\\Marwa-Bot', routePath: '/api/marwa-core', idleShutdownMs: 300000, nb2Url: 'http://127.0.0.1:8110' };

export function apply(ctx, config) {
  const cfg = Object.assign({}, DEFAULTS, config || {});
  const bridgePath = path.join(path.dirname(new URL(import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1')), 'bridge', 'dsh_bridge.py');

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

  return function dispose() {
    if (idleTimer) clearTimeout(idleTimer);
    if (proc) { try { proc.kill(); } catch {} proc = null; }
    for (const d of disposers) { try { d(); } catch {} }
  };
}
