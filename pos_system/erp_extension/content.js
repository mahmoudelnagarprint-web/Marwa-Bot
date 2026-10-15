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
});

function getChatInfoSmart() {
    let title = "";
    let phone = "";

    // 1. Dedicated SIDE PANE Strategy (Anchor: Phone Number)
    // The user screenshot shows Name above Phone. Use Phone as the anchor.
    // Scan all text nodes for the phone format e.g., +20 1x xxxx or 01xxxx

    // Helper to find text node
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null, false);
    let node;
    let phoneNode = null;

    while (node = walker.nextNode()) {
        const txt = node.nodeValue.trim();
        // Strict Phone Check: +20 followed by digits, spaces valid
        if (txt.match(/^\+20\s?1\d([\s\d]{6,})$/) || txt.match(/^01[0125]\d{8}$/)) {
            // Found a phone-like text. Is it in a side pane? 
            // In WA Web, side pane usually has specific classes or is inside a drawer.
            // Let's assume the first valid phone found in the DOM (checking end-to-start or specific container)
            // Actually, if the user just opened Contact Info, it's likely the last one rendered or visible.
            phoneNode = node;
            // Don't break immediately, might find better? usually unique in side pane context.
            // But let's prioritize one that is NOT in the main header (header phone is usually "online" or "last seen", which isn't a phone number).
            // This regex specifically targets KEYS (digits).
        }
    }

    if (phoneNode) {
        phone = phoneNode.nodeValue.trim().replace(/\D/g, ''); // Clean digits

        // Find Name: The element physically ABOVE the phone node.
        // It could be the previous Sibling of the parent, or the parent's previous sibling.
        let curr = phoneNode.parentElement;
        let nameCandidate = "";

        // Go up a few levels to find a block container, then check previous siblings?
        // In the screenshot there is a large gap. Name is likely an h2 or span block.
        // Try Previous Element Sibling of the Phone's Container
        if (curr) {
            // Try 1: Previous Sibling
            let prev = curr.previousElementSibling;
            if (prev) nameCandidate = prev.innerText;
            else {
                // Try 2: Parent's Previous Sibling (if Phone is wrapped tightly)
                let parentPrev = curr.parentElement?.previousElementSibling;
                if (parentPrev) nameCandidate = parentPrev.innerText;
            }
        }

        if (nameCandidate && nameCandidate.length > 1 && !nameCandidate.match(/\d{5}/)) {
            title = nameCandidate.split('\n')[0].trim(); // Take first line if multiple
        }
    }

    // Fallback: Main Header
    if (!title || title === "Contact info" || title === "Profile details") {
        const mainHeader = document.querySelector('#main header');
        if (mainHeader) {
            const titleEl = mainHeader.querySelector('span[title]');
            if (titleEl) title = titleEl.getAttribute('title');
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
