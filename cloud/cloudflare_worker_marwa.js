// Marwa Telegram Webhook — Cloudflare Worker (مجاني)
// ============================================================
// بديل سيرفر Replit النائم — عقل استقبال السحابة لبوت @Marwty_bot.
// الفلسفة (قرار المالك 2026-10-13): الويب هوك = طابور استقبال فقط.
//
// التدفق لكل رسالة:
//   1) تحقق أن الطلب من تليجرام فعلاً (X-Telegram-Bot-Api-Secret-Token)
//   2) تحقق أن المرسل هو المالك فقط (OWNER_ID) — غيره يُتجاهل بـ200
//   3) أمر نظام (لقطة/إطفاء/إعادة تشغيل) → commands (action=system_command)
//   4) أي كلام آخر → commands (action=orchestrate) — منسق الورشة يوجهه للوكيل الصح
//   5) رد فوري صادق على تليجرام
//
// الأسرار كلها في متغيرات البيئة بتاعة الـWorker (Settings → Variables):
//   SUPABASE_URL, SUPABASE_KEY (service), TELEGRAM_TOKEN, OWNER_ID, WEBHOOK_SECRET
// لا سر في الكود — لا سر في git — لا سر في الذاكرة.

export default {
  async fetch(request, env) {
    if (request.method !== "POST") {
      return json({ ok: true, service: "marwa-webhook", hint: "POST /webhook" });
    }

    // 1) تحقق سر تليجرام (يتظبط مع setWebhook secret_token)
    const secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token") || "";
    if (!env.WEBHOOK_SECRET || secret !== env.WEBHOOK_SECRET) {
      return json({ ok: false, error: "bad secret token" }, 401);
    }

    const update = await request.json().catch(() => ({}));
    const msg = update.message || {};
    const fromId = String((msg.from || {}).id || "");
    const chatId = String((msg.chat || {}).id || "");
    const text = String(msg.text || "").trim();

    // 2) المالك فقط — الرد 200 عشان تليجرام تعمل stop retrying
    if (!chatId || !text) return json({ ok: true, ignored: "empty" });
    if (String(env.OWNER_ID) !== fromId) return json({ ok: true, ignored: "not owner" });

    // 3) تصنيف: أمر نظام أم رسالة عادية (نفس كلمات النسخة البايثون)
    const sys = detectSystemCommand(text);
    let action, payload, reply;
    if (sys) {
      action = "system_command";
      payload = { cmd: sys };
      reply =
        sys === "screenshot"
          ? "تمام 📸 سجلت أمر اللقطة — الورشة تنفذه وتبعته أول ما الدايمون يشتغل."
          : sys === "reboot"
          ? "تمام 🔄 سجلت إعادة التشغيل — هتتنفذ لما الدايمون يشتغل."
          : "تمام 😴 سجلت أمر الإطفاء — هيتنفذ لما الدايمون يشتغل.";
    } else {
      action = "orchestrate";
      payload = { text: text };
      reply = "وصلتني رسالتك وسجلتها في الطابور ✅ — الورشة تعالجها أول ما الدايمون يشتغل.";
    }

    // 4) إدراج في طابور Supabase
    const queued = await enqueue(env, action, payload);

    // 5) رد صادق — نجاح أو فشل بالاسم
    const finalReply = queued
      ? reply
      : "⚠️ وصلني طلبك لكن فشل الإدراج في الطابور — راجع متغيرات الـWorker (SUPABASE_URL / SUPABASE_KEY).";
    await tgSend(env, chatId, finalReply);

    return json({ ok: true, queued, action });
  },
};

// نفس قوائم الكلمات من cloud_webhook_server.py — الإطفاء الأول (أولوية)
function detectSystemCommand(text) {
  const t = text.toLowerCase();
  const has = (arr) => arr.some((k) => t.includes(k));
  if (has(["اغلق الجهاز", "اقفل الجهاز", "اطفئ", "اطفي", "إطفاء", "اغلاق", "shutdown", "power off"])) return "shutdown";
  if (has(["أعد التشغيل", "اعادة تشغيل", "اعيد التشغيل", "reset", "restart", "reboot"])) return "reboot";
  if (has(["لقطة", "لقطه", "سكرين", "شاشة", "شاشه", "screenshot", "capture"])) return "screenshot";
  return null;
}

async function enqueue(env, action, payload) {
  const row = {
    action,
    payload,
    status: "pending",
    idempotency_key: crypto.randomUUID(),
    created_at: new Date().toISOString(),
  };
  try {
    const r = await fetch(`${env.SUPABASE_URL}/rest/v1/commands`, {
      method: "POST",
      headers: {
        apikey: env.SUPABASE_KEY,
        Authorization: `Bearer ${env.SUPABASE_KEY}`,
        "Content-Type": "application/json",
        Prefer: "return=minimal",
      },
      body: JSON.stringify(row),
    });
    return r.ok;
  } catch (e) {
    return false;
  }
}

async function tgSend(env, chatId, text) {
  try {
    await fetch(`https://api.telegram.org/bot${env.TELEGRAM_TOKEN}/sendMessage`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ chat_id: chatId, text: text.slice(0, 4000) }),
    });
  } catch (e) {
    /* صامت — تليجرام هيعيد المحاولة لو فشلت التسليم */
  }
}

function json(obj, status) {
  return new Response(JSON.stringify(obj), {
    status: status || 200,
    headers: { "content-type": "application/json" },
  });
}
