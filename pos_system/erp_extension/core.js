/* core.js - Elnagar POS Extension v2.2 — Pure, testable logic (no Chrome/DOM APIs).
   Loaded from sidepanel.html BEFORE sidepanel.js. Also runnable in Node for tests.
   Exposes global.ElnagarCore */
(function (global) {
  'use strict';

  const Core = {
    VERSION: '2.2',

    // ---- Phone normalization (Egyptian) ----
    // "+20 12 34567890" / "01234567890" / "12034567890" -> "01234567890"
    normalizeEgyptianPhone(input) {
      if (!input) return '';
      const digits = String(input).replace(/\D/g, '');
      if (!digits) return '';
      if (digits.length === 13 && digits.startsWith('20')) return '0' + digits.slice(2);
      if (digits.length === 12 && digits.startsWith('201')) return '0' + digits.slice(2);
      if (digits.length === 10 && digits.startsWith('1')) return '0' + digits;
      return digits;
    },

    isValidEgyptianPhone(phone) {
      return /^01[0125]\d{8}$/.test(String(phone || ''));
    },

    // ---- Request id for idempotency (dedup) ----
    makeRequestId() {
      return (
        Date.now().toString(36) + '-' +
        Math.random().toString(36).slice(2, 10)
      );
    },

    // ---- Order math ----
    computeTotal(items) {
      return items.reduce(
        (sum, it) => sum + (Number(it.price) || 0) * (Number(it.qty) || 0),
        0
      );
    },

    // Build items payload matching backend expectation: id, qty, price, image_count, item_index
    buildItemsPayload(items) {
      return (items || [])
        .filter((i) => i.product_id || Number(i.price) > 0)
        .map((i, idx) => ({
          id: i.product_id,
          qty: Number(i.qty) || 0,
          price: Number(i.price) || 0,
          image_count: i.images ? i.images.length : 0,
          item_index: idx
        }));
    },

    // ---- HTML escaping (XSS safety for innerHTML rendering) ----
    escapeHtml(value) {
      return String(value == null ? '' : value)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
    },

    // ---- Debounce (with cancel/flush) ----
    debounce(fn, ms) {
      let t = null;
      const wrapped = function (...args) {
        const ctx = this;
        clearTimeout(t);
        t = setTimeout(() => fn.apply(ctx, args), ms);
      };
      wrapped.cancel = function () { clearTimeout(t); t = null; };
      wrapped.flush = function () {
        if (t) { clearTimeout(t); fn(); t = null; }
      };
      return wrapped;
    },

    // ---- Idempotency guard (prevents duplicate submission) ----
    createIdempotencyGuard(ttlMs) {
      const ttl = ttlMs || 10000;
      const recently = new Set();
      return {
        // Returns true if this key may proceed (not seen within TTL)
        allow(key) {
          if (!key) return true;
          if (recently.has(key)) return false;
          recently.add(key);
          setTimeout(() => recently.delete(key), ttl);
          return true;
        },
        clear() { recently.clear(); },
        size: () => recently.size
      };
    },

    // ---- Order status classification ----
    classifyStatus(status) {
      const st = String(status || '').toLowerCase();
      if (st.includes('prep') || st.includes('تجهيز')) return 'prep';
      if (st.includes('ready') || st.includes('جاهز')) return 'ready';
      return 'done';
    },

    // ---- Draft (JSON-safe; File objects NOT persisted) ----
    serializeDraft(state) {
      const draft = {
        v: 1,
        savedAt: Date.now(),
        client_name: state.client_name || '',
        client_phone: state.client_phone || '',
        client_type: state.client_type || 'Retail',
        notes: state.notes || '',
        items: (state.items || []).map((i) => ({
          product_id: i.product_id || null,
          qty: Number(i.qty) || 1,
          price: Number(i.price) || 0,
          retail_price: Number(i.retail_price) || 0,
          wholesale_price: Number(i.wholesale_price) || 0,
          name: i.name || ''
        })),
        // Images stored as data URLs so they survive reload (File can't be persisted)
        global_images: (state.global_images || []).slice(0, 16),
        editing_order_id: state.editing_order_id || null
      };
      const json = JSON.stringify(draft);
      if (json.length > 3900000) return null; // ~3.8MB cap (session storage budget ~10MB)
      return json;
    },

    parseDraft(json) {
      if (!json) return null;
      try {
        const d = JSON.parse(json);
        if (!d || d.v !== 1) return null;
        return d;
      } catch (e) {
        return null;
      }
    },

    // ---- Timer-aware fetch (AbortController) ----
    async fetchWithTimeout(url, options, timeoutMs) {
      const timeout = timeoutMs || 8000;
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), timeout);
      try {
        const opts = Object.assign({}, options || {}, { signal: controller.signal });
        return await fetch(url, opts);
      } catch (err) {
        if (err && err.name === 'AbortError') {
          const e = new Error('انتهت مهلة الاتصال بالخادم (8 ثوانٍ)');
          e.name = 'TimeoutError';
          throw e;
        }
        throw err;
      } finally {
        clearTimeout(timer);
      }
    },

    // ---- Formatting helpers ----
    formatDateForDisplay(dateStr) {
      if (!dateStr) return '';
      try {
        const d = new Date(dateStr);
        if (isNaN(d.getTime())) return dateStr;
        return d.toLocaleDateString('ar-EG');
      } catch (e) {
        return dateStr;
      }
    },

    parseMoney(value) {
      const n = parseFloat(value);
      return isNaN(n) ? 0 : n;
    }
  };

  global.ElnagarCore = Core;
  if (typeof module !== 'undefined' && module.exports) module.exports = Core;
})(typeof window !== 'undefined' ? window : globalThis);
