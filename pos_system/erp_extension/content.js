// content.js - WhatsApp Scraper 2.2 (Viewport Focused)

// Listen for messages from Side Panel
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === "get_chat_info") {
        (async () => {
            const info = getChatInfoSmart();
            const images = await getViewportImages();
            sendResponse({ ...info, images });
        })();
        return true;
    }
    else if (request.action === "get_images_only") {
        (async () => {
            const images = await getViewportImages();
            sendResponse({ images });
        })();
        return true;
    }
    else if (request.action === "get_chat_messages") {
        const messages = getVisibleMessages();
        sendResponse({ messages });
        return true;
    }
});

const _NOT_NAME = new Set([
    'Contact info', 'Profile details', 'WhatsApp', 'Message',
    'معلومات جهة الاتصال', 'تفاصيل الملف الشخصي', 'معلومات الاتصال'
]);

function isPhoneLike(t) {
    const d = (t || '').replace(/\D/g, '');
    return d.length > 9 && d.length >= (t || '').length - 3 && d.length <= 15;
}

function cleanName(t) {
    return (t || '').split('\n')[0].trim();
}

function getChatInfoSmart() {
    let title = "";
    let phone = "";

    // A) Contact-info drawer (يفتح عندما تضغط على اسم المحادثة/البروفايل)
    //    الاسم عادة أول نص بارز، والرقم أو "About" تحته
    const dialog = document.querySelector('div[role="dialog"]');
    if (dialog) {
        const els = dialog.querySelectorAll('span[title], div[title], header span, h1, h2, span[dir="auto"]');
        for (const el of els) {
            const raw = (el.getAttribute && el.getAttribute('title')) || el.innerText || '';
            const t = cleanName(raw);
            if (!t || t.length < 2) continue;
            if (_NOT_NAME.has(t)) continue;
            if (isPhoneLike(t)) { if (!phone) phone = t.replace(/\D/g, ''); continue; }
            if (!title && !/^\d+$/.test(t)) { title = t; }
            if (title && phone) break;
        }
    }

    // B) Header of the OPEN conversation — the saved contact name is always here
    if (!title) {
        for (const sel of ['#main header span[title]', '#main header div[title]', '#main header [title]']) {
            const el = document.querySelector(sel);
            if (!el) continue;
            const t = cleanName(el.getAttribute('title') || '');
            if (!t || t.length < 2 || _NOT_NAME.has(t)) continue;
            if (isPhoneLike(t)) { if (!phone) phone = t.replace(/\D/g, ''); }
            else { title = t; }
            break;
        }
    }

    // C) Phone from any visible pane (side pane / drawer) — strict Egyptian formats
    if (!phone) {
        const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null, false);
        let node;
        while ((node = walker.nextNode())) {
            const txt = node.nodeValue.trim();
            if (txt.match(/^\+20\s?1\d([\s\d]{6,})$/) || txt.match(/^01[0125]\d{8}$/)) {
                phone = txt.replace(/\D/g, '');
                break;
            }
        }
    }

    // D) Name found physically above the phone (side pane layout: Name above Phone)
    if (!title && phone) {
        let phoneNode = null;
        const walker2 = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null, false);
        while ((node = walker2.nextNode())) {
            if (node.nodeValue.replace(/\D/g, '') === phone) { phoneNode = node; break; }
        }
        if (phoneNode) {
            let curr = phoneNode.parentElement;
            for (let up = 0; up < 3 && curr && !title; up++) {
                let prev = curr.previousElementSibling;
                while (prev && !title) {
                    const cand = cleanName(prev.innerText || '');
                    if (cand && cand.length > 1 && !isPhoneLike(cand) && !_NOT_NAME.has(cand)) title = cand;
                    else prev = prev.previousElementSibling;
                }
                curr = curr.parentElement;
            }
        }
    }

    return { title, phone };
}

async function getViewportImages() {
    // Strategy: Get ALL images in #main, filter by visibility and size.
    const main = document.getElementById('main');
    if (!main) return [];

    const allImages = Array.from(main.querySelectorAll('img[src^="blob:"]'));
    const uniqueUrls = new Set();

    // Filter logic
    const candidates = allImages.filter(img => {
        // 1. Size Check (skip stickers/profiles)
        if (img.width < 100 || img.height < 100) return false;

        // 2. Visibility Check (Viewport)
        const rect = img.getBoundingClientRect();
        // Check if image is roughly within the window OR just above/below it (recent history)
        // User wants "Screenshit" basically or "Last sent".
        // Let's take images that are physically in the DOM tree of the message list.
        // We will prioritize those ON SCREEN.
        const inView = (rect.top >= -200 && rect.bottom <= (window.innerHeight + 200));

        return inView;
    });

    // Extract SRCS
    candidates.forEach(img => uniqueUrls.add(img.src));

    // Convert
    const urls = Array.from(uniqueUrls);
    if (urls.length === 0 && candidates.length === 0) {
        // Fallback: If no viewport images found (maybe user scrolled up?), take the LAST 5 from the entire list
        allImages.slice(-5).forEach(img => {
            if (img.width > 100) uniqueUrls.add(img.src);
        });
    }

    const finalUrls = Array.from(uniqueUrls).slice(-10); // Max 10

    if (finalUrls.length === 0) {
        // Debugging feedback
        // console.log("No images found with size > 100px");
    }

    const base64List = [];
    for (const src of finalUrls) {
        try {
            const b64 = await blobUrlToBase64(src);
            base64List.push(b64);
        } catch (e) {
            console.warn("Conversion failed", src);
        }
    }

    return base64List;
}

function getVisibleMessages() {
    const messages = [];
    const msgContainers = document.querySelectorAll('[data-pre-plain-text]');
    
    msgContainers.forEach(msg => {
        // Check if message is in viewport
        const rect = msg.getBoundingClientRect();
        if (rect.top >= 0 && rect.bottom <= window.innerHeight) {
            const text = msg.innerText?.trim();
            if (text) {
                messages.push(text);
            }
        }
    });
    
    // Fallback: Get messages from message bubbles
    if (messages.length === 0) {
        const bubbles = document.querySelectorAll('[data-possible-moved-virtualized-bottom]');
        bubbles.forEach(bubble => {
            const text = bubble.innerText?.trim();
            if (text) {
                messages.push(text);
            }
        });
    }
    
    return messages.slice(-50); // Last 50 messages
}

async function blobUrlToBase64(blobUrl) {
    const response = await fetch(blobUrl);
    const blob = await response.blob();
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onloadend = () => resolve(reader.result);
        reader.onerror = reject;
        reader.readAsDataURL(blob);
    });
}

// Float Icon
function createFloatingIcon() {
    if (document.getElementById('elnagar-pos-floater')) return;
    const btn = document.createElement('button');
    btn.id = 'elnagar-pos-floater';
    btn.innerHTML = '📦';
    btn.title = "Open POS";
    Object.assign(btn.style, {
        position: 'fixed', top: '120px', right: '0px', zIndex: '999999',
        width: '40px', height: '40px', border: 'none', borderRadius: '5px 0 0 5px',
        backgroundColor: '#00a884', color: 'white', fontSize: '20px', cursor: 'pointer'
    });
    btn.onclick = () => chrome.runtime.sendMessage({ action: "open_side_panel" });
    document.body.appendChild(btn);
}
if (document.body) createFloatingIcon();
else window.onload = createFloatingIcon;
