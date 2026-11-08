// sidepanel.js - Elnagar POS Extension v2.2
// Improvements: dedup (idempotency guard) + draft autosave/restore + connection
// monitor with retry + fetch timeout + debounced rendering + XSS-safe output.

const API_URL = "http://127.0.0.1:7777/api";
const DRAFT_KEY = "elnagar_pos_draft";
const CONN_PING_URL = API_URL + "/products";
const CONN_PING_INTERVAL = 15000;
const CORE = (typeof ElnagarCore !== 'undefined') ? ElnagarCore : null;

// State
let allProducts = [];
let allClients = [];
let allOrders = [];
let allOrdersGrouped = { prep: [], ready: [], done: [] };
let draftTimer = null;          // draft autosave timer (was undeclared -> ReferenceError)
let connFailed = false;         // connection monitor flag (was undeclared)
let selectedImages = [];
let editingOrderId = null;
let allProductsFull = [];
let orderItems = [];
let isSubmitting = false;
let firstLoadDone = false;
let productOptionsHtmlCache = null;
let restoredDraftAt = null;

const escapeHtml = (v) => CORE ? CORE.escapeHtml(v) : String(v == null ? '' : v);
const debounce = (fn, ms) => CORE ? CORE.debounce(fn, ms) : (fn);
const formatDate = (s) => CORE ? CORE.formatDateForDisplay(s) : s;

// --- Initialization ---
document.addEventListener('DOMContentLoaded', () => {
    setupTabs();
    setupListeners();
    setupDragDrop();
    setupConnectionMonitor();
    setupZoomControls();
    initToast();
    restoreDraft();
    loadData();
});

// ================= Zoom Control (تكبير/تصغير الواجهة) =================
const ZOOM_KEY = "elnagar_zoom_level";
let zoomLevel = 100;

function applyZoom() {
    document.body.style.zoom = zoomLevel / 100;
    const el = document.getElementById('zoom-level');
    if (el) el.textContent = zoomLevel + '%';
}

function setZoom(value) {
    zoomLevel = Math.max(70, Math.min(160, Math.round(value / 10) * 10));
    applyZoom();
    if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
        chrome.storage.local.set({ [ZOOM_KEY]: zoomLevel });
    }
}

function setupZoomControls() {
    const zin = document.getElementById('btn-zoom-in');
    const zout = document.getElementById('btn-zoom-out');
    if (zin) zin.addEventListener('click', () => setZoom(zoomLevel + 10));
    if (zout) zout.addEventListener('click', () => setZoom(zoomLevel - 10));
    applyZoom();
    if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
        chrome.storage.local.get(ZOOM_KEY, (d) => {
            if (d && d[ZOOM_KEY]) {
                zoomLevel = Number(d[ZOOM_KEY]) || 100;
                applyZoom();
            }
        });
    }
}

function setupTabs() {
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

            btn.classList.add('active');
            const tab = document.getElementById(btn.dataset.tab);
            if (tab) tab.classList.add('active');

            // Refresh tab-specific data on switch
            if (btn.dataset.tab === 'tab-orders') renderOrdersGrouped();
            if (btn.dataset.tab === 'tab-customers') renderClients(allClients);
            if (btn.dataset.tab === 'tab-financial') loadFinancialData();
            if (btn.dataset.tab === 'tab-ai') resetAIAnalysis();
        });
    });
}

// ================= Toast =================
function initToast() {
    if (!document.getElementById('toast-container')) {
        const c = document.createElement('div');
        c.id = 'toast-container';
        document.body.appendChild(c);
    }
}

function showToast(message, type = 'info', duration = 2800) {
    const container = document.getElementById('toast-container');
    if (!container) return;
    const el = document.createElement('div');
    el.className = 'toast ' + (type || 'info');
    el.textContent = message;
    container.appendChild(el);
    setTimeout(() => {
        el.style.opacity = '0';
        el.style.transition = 'opacity .3s';
        setTimeout(() => el.remove(), 320);
    }, duration);
}

// ================= Connection monitor =================
function setConnectionState(ok, why) {
    const banner = document.getElementById('conn-banner');
    if (!banner) return;
    connFailed = !ok;
    const bannerText = document.getElementById('conn-banner-text');
    if (ok) {
        banner.style.display = 'none';
        banner.className = 'online';
        bannerText.textContent = '';
    } else {
        const reasons = {
            offline: 'الخادم غير متصل — البيانات قد تكون قديمة',
            timeout: 'الخادم بطيء (تجاوز مهلة الانتظار)',
            error: 'خطأ في الاتصال بالخادم'
        };
        banner.style.display = 'flex';
        banner.className = 'offline';
        bannerText.textContent = reasons[why] || reasons.error;
    }
}

function setupConnectionMonitor() {
    const retryBtn = document.getElementById('btn-retry-conn');
    const dismissBtn = document.getElementById('btn-dismiss-banner');
    if (retryBtn) retryBtn.addEventListener('click', () => { loadData(true); });
    if (dismissBtn) dismissBtn.addEventListener('click', () => {
        const b = document.getElementById('conn-banner');
        if (b) b.style.display = 'none';
    });
    // Periodically verify connectivity
    setInterval(async () => {
        try {
            await apiGet('/products', { silent: true });
            setConnectionState(true);
        } catch (e) {
            // keep current banner state; only flip when we had data
            if (firstLoadDone) setConnectionState(false, 'offline');
        }
    }, CONN_PING_INTERVAL);
}

// ================= API helper (with timeout + error normalization) =================
async function apiFetch(url, options, opts) {
    opts = opts || {};
    if (CORE && CORE.fetchWithTimeout) {
        return await CORE.fetchWithTimeout(url, options, opts.timeoutMs);
    }
    return await fetch(url, options);
}

async function apiGet(path, opts) {
    try {
        const res = await apiFetch(API_URL + path, { method: 'GET' });
        if (!res.ok) throw new Error('HTTP ' + res.status);
        return await res.json();
    } catch (err) {
        if (!(opts && opts.silent)) {
            setConnectionState(false, err.name === 'TimeoutError' ? 'timeout'
                : (err && err.message && /Failed to fetch|NetworkError|ECONNREFUSED|Network Error/.test(err.message) ? 'offline' : 'error'));
        }
        throw err;
    }
}

async function apiPostJson(path, body, opts) {
    try {
        const res = await apiFetch(API_URL + path, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body || {})
        }, opts);
        return await res.json();
    } catch (err) {
        if (!(opts && opts.silent)) {
            setConnectionState(false, err.name === 'TimeoutError' ? 'timeout'
                : (err && err.message && /Failed to fetch|NetworkError|ECONNREFUSED/.test(err.message) ? 'offline' : 'error'));
        }
        throw err;
    }
}

async function apiPostForm(path, formData, opts) {
    try {
        const res = await apiFetch(API_URL + path, { method: 'POST', body: formData }, opts);
        return await res.json();
    } catch (err) {
        if (!(opts && opts.silent)) {
            setConnectionState(false, err.name === 'TimeoutError' ? 'timeout'
                : (err && err.message && /Failed to fetch|NetworkError|ECONNREFUSED/.test(err.message) ? 'offline' : 'error'));
        }
        throw err;
    }
}

// ================= Draft (autosave + restore) =================
function collectFormState() {
    return {
        client_name: document.getElementById('client-name').value || '',
        client_phone: document.getElementById('client-phone').value || '',
        client_type: document.getElementById('client-type').value || 'Retail',
        notes: document.getElementById('notes').value || '',
        items: orderItems.map(i => ({
            product_id: i.product_id || null,
            qty: i.qty,
            price: i.price,
            retail_price: i.retail_price,
            wholesale_price: i.wholesale_price,
            name: i.name || '',
            image_count: i.images ? i.images.length : 0
        })),
        global_images: selectedImages.map(f => f._preview || null).filter(Boolean),
        editing_order_id: editingOrderId
    };
}

function scheduleDraftSave() {
    if (draftTimer) clearTimeout(draftTimer);
    draftTimer = setTimeout(() => saveDraft(), 500);
}

function saveDraft() {
    if (!CORE || typeof chrome === 'undefined' || !chrome.storage) return;
    const draft = collectFormState();
    if (!draft.client_name && !draft.notes && draft.items.length === 0 && draft.global_images.length === 0) {
        // Empty -> remove draft
        chrome.storage.local.remove(DRAFT_KEY);
        return;
    }
    const json = CORE.serializeDraft(draft);
    if (json === null) {
        showToast('المسودة كبيرة جدًا — لن تُحفظ الصور', 'warn');
        chrome.storage.local.set({ [DRAFT_KEY]: CORE.serializeDraft(Object.assign({}, draft, { global_images: [] })) });
        return;
    }
    chrome.storage.local.set({ [DRAFT_KEY]: json });
}

function restoreDraft() {
    if (!CORE || typeof chrome === 'undefined' || !chrome.storage) return;
    chrome.storage.local.get(DRAFT_KEY, (data) => {
        if (!data || !data[DRAFT_KEY]) return;
        const d = CORE.parseDraft(data[DRAFT_KEY]);
        if (!d) return;
        restoredDraftAt = d.savedAt || Date.now();
        // Restore form fields
        const nameEl = document.getElementById('client-name');
        if (d.client_name) nameEl.value = d.client_name;
        if (d.client_phone) document.getElementById('client-phone').value = d.client_phone;
        if (d.client_type) document.getElementById('client-type').value = d.client_type;
        if (d.notes) document.getElementById('notes').value = d.notes;
        if (d.editing_order_id) editingOrderId = d.editing_order_id;

        // Restore items
        orderItems = (d.items || []).map(it => ({
            _uid: (Date.now() + Math.random()),
            product_id: it.product_id || '',
            price: it.price || 0,
            qty: it.qty || 1,
            retail_price: it.retail_price || 0,
            wholesale_price: it.wholesale_price || 0,
            images: [],
            name: it.name || ''
        }));

        // Restore images (data URLs -> File objects)
        const imagesArr = (d.global_images || []).slice(0, 16);
        if (imagesArr.length === 0 && orderItems.some(i => i.image_count > 0)) {
            // images were dropped to fit quota; show a notice
            showToast('تمت استعادة المسودة بدون بعض الصور (حجم كبير)', 'warn');
        }
        imagesArr.forEach((b64, idx) => {
            try {
                const holder = new Image();
                holder.src = b64;
                const type = (b64.match(/^data:([^;]+);/) || [])[1] || 'image/jpeg';
                const blob = dataURLToBlob(b64, type);
                if (blob) {
                    const file = new File([blob], 'draft_' + idx + '.jpg', { type });
                    file._preview = b64;
                    selectedImages.push(file);
                }
            } catch (e) { console.warn('draft image skip', e); }
        });

        if (orderItems.length === 0) {
            addOrderItem();
        } else {
            renderOrderRows();
            renderImagePreview();
            updateImageCount();
        }
        let btn = document.querySelector('#sync-form button[type="submit"]');
        if (editingOrderId && btn) {
            btn.textContent = 'حفظ التعديلات (طلب #' + editingOrderId + ')';
            btn.style.background = '#F59E0B';
        }
        showToast('تمت استعادة المسودة المحفوظة 🧹', 'success');
        updateDraftIndicator();
    });
}

function dataURLToBlob(dataUrl, type) {
    try {
        const bin = atob(dataUrl.split(',')[1]);
        const len = bin.length;
        const arr = new Uint8Array(len);
        for (let i = 0; i < len; i++) arr[i] = bin.charCodeAt(i);
        return new Blob([arr], { type: type || 'image/jpeg' });
    } catch (e) {
        return null;
    }
}

function clearDraft() {
    if (typeof chrome === 'undefined' || !chrome.storage) return;
    chrome.storage.local.remove(DRAFT_KEY);
    updateDraftReset(false);
    showToast('تم حذف المسودة', 'info');
}

function updateDraftIndicator() {
    const btn = document.getElementById('btn-clear-draft');
    if (!btn) return;
    // Re-check storage existence is async; keep simple: we saved/removed on state changes.
}

// ================= Setup listeners =================
function setupListeners() {
    // 0. Window Opener
    const winBtn = document.getElementById('btn-open-window');
    if (winBtn) {
        winBtn.addEventListener('click', () => {
            chrome.windows.create({
                url: chrome.runtime.getURL("sidepanel.html"),
                type: "popup",
                width: 400,
                height: 600
            });
        });
    }

    // Clear Draft button
    const clearDraftBtn = document.getElementById('btn-clear-draft');
    if (clearDraftBtn) {
        clearDraftBtn.addEventListener('click', () => {
            if (confirm('حذف المسودة المحفوظة؟')) {
                orderItems = [];
                selectedImages = [];
                editingOrderId = null;
                document.getElementById('sync-form').reset();
                renderOrderRows();
                renderImagePreview();
                updateImageCount();
                clearDraft();
            }
        });
    }

    // 1. Auto Fill
    const btnAutoFill = document.getElementById('btn-autofill');
    if (btnAutoFill) {
        btnAutoFill.addEventListener('click', async () => {
            const data = await sendMessageToContent({ action: "get_chat_info" });
            if (data && (data.title || data.phone)) {
                let title = data.title || "";
                let phone = data.phone || "";

                // If title seems like a phone (mostly digits), use it as phone and clear title
                let d = title.replace(/\D/g, '');
                if (d.length > 9) {
                    if (!phone) phone = title;
                    title = "";
                } else if (CORE) {
                    const norm = CORE.normalizeEgyptianPhone(d);
                    if (norm && CORE.isValidEgyptianPhone(norm)) title = norm;
                }

                const nameEl = document.getElementById('client-name');
                const phoneEl = document.getElementById('client-phone');

                if (title) nameEl.value = title;
                if (phone) phoneEl.value = phone;

                // Lookup by Name first
                let found = false;
                if (title) {
                    try {
                        const json = await apiPostJson('/get_client_details', { name: title });

                        if (json.success && json.found) {
                            found = true;
                            const client = json.client;
                            const typeSel = document.getElementById('client-type');
                            typeSel.value = client.type;

                            if (client.phone) phoneEl.value = client.phone; // Database wins if exists
                            updateAllPricesForClientType();
                            checkLastOrder(client);

                            nameEl.style.borderColor = '#10B981';
                        }
                    } catch (e) { console.error("Lookup Error", e); }
                }

                if (!found && phone) {
                    phoneEl.style.borderColor = '#10B981';
                }
                setTimeout(() => {
                    nameEl.style.borderColor = '';
                    phoneEl.style.borderColor = '';
                }, 2000);
            }
        });
    }

    // 1b. Grab Messages
    const btnGrabMessages = document.getElementById('btn-grab-messages');
    if (btnGrabMessages) {
        btnGrabMessages.addEventListener('click', async () => {
            const data = await sendMessageToContent({ action: "get_chat_messages" });
            if (data && data.messages && data.messages.length > 0) {
                const notesEl = document.getElementById('notes');
                const joined = data.messages.join('\n');
                notesEl.value = notesEl.value ? notesEl.value + '\n\n' + joined : joined;
                scheduleDraftSave();
                showToast('تم لصق ' + data.messages.length + ' رسالة في الملاحظات', 'success');
            } else if (data && data.messages && data.messages.length === 0) {
                showToast('لا توجد رسائل ظاهرة', 'warn');
            }
        });
    }

    // 2. Grab Images
    const btnGrab = document.getElementById('btn-grab-images');
    if (btnGrab) {
        btnGrab.addEventListener('click', async () => {
            const data = await sendMessageToContent({ action: "get_images_only" });
            if (data && data.images && data.images.length > 0) {
                processIncomingImages(data.images);
            } else {
                showToast('لم يتم العثور على صور', 'warn');
            }
        });
    }

    // Clear Images Button
    const btnClearImages = document.getElementById('btn-clear-images');
    if (btnClearImages) {
        btnClearImages.addEventListener('click', () => {
            if (confirm("مسح جميع الصور؟")) {
                selectedImages = [];
                renderImagePreview();
                updateImageCount();
                scheduleDraftSave();
            }
        });
    }

    // 3. Filters (debounced)
    const debouncedProducts = debounce(() => renderProductsGrid(), 150);
    const debouncedClients = debounce(() => renderClients(allClients), 150);

    const searchProductsEl = document.getElementById('search-products');
    const filterCategoryEl = document.getElementById('filter-category');
    const searchClientsEl = document.getElementById('search-clients');
    const sortClientsEl = document.getElementById('sort-clients');
    const refreshOrdersEl = document.getElementById('btn-refresh-orders');

    if (searchProductsEl) searchProductsEl.addEventListener('input', debouncedProducts);
    if (filterCategoryEl) filterCategoryEl.addEventListener('change', renderProductsGrid);
    document.querySelectorAll('input[name="price_mode"]').forEach(r => {
        r.addEventListener('change', renderProductsGrid);
    });

    if (searchClientsEl) searchClientsEl.addEventListener('input', debouncedClients);
    if (sortClientsEl) sortClientsEl.addEventListener('change', () => renderClients(allClients));
    if (refreshOrdersEl) refreshOrdersEl.addEventListener('click', () => loadData(true));

    // 4. Form Actions
    const btnAddRow = document.getElementById('btn-add-row');
    if (btnAddRow) btnAddRow.addEventListener('click', () => addOrderItem());

    const clientTypeEl = document.getElementById('client-type');
    if (clientTypeEl) {
        clientTypeEl.addEventListener('change', () => {
            updateAllPricesForClientType();
            scheduleDraftSave();
        });
    }

    // Quick Add Product
    const btnSaveProd = document.getElementById('btn-save-new-prod');
    if (btnSaveProd) {
        btnSaveProd.addEventListener('click', async () => {
            const name = document.getElementById('new-product-name').value;
            const price_retail = document.getElementById('new-product-price-retail').value;
            const price_wholesale = document.getElementById('new-product-price-wholesale').value;
            const category = document.getElementById('new-product-cat').value;

            if (!name) return showToast('الاسم مطلوب', 'warn');
            try {
                const json = await apiPostJson('/quick_add', {
                    type: 'product',
                    name: name,
                    price_retail: price_retail,
                    price_wholesale: price_wholesale,
                    category: category
                });
                if (json.success) {
                    loadData(true);
                    document.getElementById('new-product-group').style.display = 'none';
                    document.getElementById('new-product-name').value = '';
                    document.getElementById('new-product-price-retail').value = '';
                    document.getElementById('new-product-price-wholesale').value = '';
                    document.getElementById('new-product-cat').value = '';
                    showToast('تمت الإضافة!', 'success');
                } else {
                    showToast(json.message || 'فشل الإضافة', 'error');
                }
            } catch (e) { showToast(e.message, 'error'); }
        });
    }

    // Quick Add Category
    const btnAddCat = document.getElementById('btn-ext-add-cat');
    if (btnAddCat) {
        btnAddCat.addEventListener('click', async () => {
            const name = prompt("أدخل اسم التصنيف الجديد:");
            if (!name) return;
            try {
                const json = await apiPostJson('/quick_add', { type: 'category', name: name });
                if (json.success) {
                    loadData(true);
                    document.getElementById('new-product-cat').value = name;
                    showToast('تم إضافة التصنيف!', 'success');
                } else {
                    showToast(json.message || 'فشل الإضافة', 'error');
                }
            } catch (e) { showToast(e.message, 'error'); }
        });
    }

    const btnQuickToggle = document.getElementById('btn-quick-prod-toggle');
    if (btnQuickToggle) {
        btnQuickToggle.addEventListener('click', () => {
            const div = document.getElementById('new-product-group');
            div.style.display = div.style.display === 'none' ? 'block' : 'none';
        });
    }

    // Form Submit
    const form = document.getElementById('sync-form');
    if (form) {
        form.addEventListener('submit', onFormSubmit);
    }

    // Auto Client Info on name input (debounced save)
    const clientNameEl = document.getElementById('client-name');
    clientNameEl.addEventListener('input', (e) => {
        const val = e.target.value;
        const client = allClients.find(c => c.name === val);
        if (client) {
            if (client.phone) document.getElementById('client-phone').value = client.phone;
            if (client.type) {
                document.getElementById('client-type').value = client.type;
                updateAllPricesForClientType();
            }
            checkLastOrder(client);
        } else {
            const infoDiv = document.getElementById('last-order-info');
            if (infoDiv) infoDiv.style.display = 'none';
        }
        scheduleDraftSave();
    });
    const clientPhoneEl = document.getElementById('client-phone');
    if (clientPhoneEl) clientPhoneEl.addEventListener('input', scheduleDraftSave);
    const notesEl = document.getElementById('notes');
    if (notesEl) notesEl.addEventListener('input', scheduleDraftSave);

    // Delegation for dynamic buttons
    document.addEventListener('click', (e) => {
        const target = e.target;
        if (target.classList.contains('btn-pay-debt')) payDebt(target.dataset.id);
        if (target.classList.contains('btn-delete-client')) {
            if (confirm(`حذف العميل "${target.dataset.name}"؟`)) deleteClient(target.dataset.id);
        }
        if (target.classList.contains('btn-delete-order')) {
            if (confirm(`حذف الطلب #${target.dataset.id}؟`)) deleteOrder(target.dataset.id);
        }
        if (target.closest('.btn-edit-order')) {
            editOrder(target.closest('.btn-edit-order').dataset.id);
        }
        if (target.classList.contains('img-remove-btn')) {
            selectedImages.splice(target.dataset.idx, 1);
            renderImagePreview();
            updateImageCount();
            scheduleDraftSave();
        }
    });

    // Connect Server button (Home tab)
    const btnConnectServer = document.getElementById('btn-connect-server');
    if (btnConnectServer) {
        btnConnectServer.addEventListener('click', () => {
            checkServerStatus();
        });
    }

    // Device image upload (Home tab)
    const imgInput = document.getElementById('img-input');
    if (imgInput) {
        imgInput.addEventListener('change', () => {
            const files = Array.from(imgInput.files || []).filter(f => f.type.startsWith('image/'));
            if (!files.length) return;
            if (selectedImages.length + files.length > 16) {
                showToast('العدد الأقصى 16 صورة', 'warn');
                return;
            }
            files.forEach(f => { f._preview = null; selectedImages.push(f); });
            imgInput.value = '';
            updateImageCount();
            renderImagePreview();
            scheduleDraftSave();
        });
    }

    // Orders search filter (Orders tab)
    const searchOrdersEl = document.getElementById('search-orders');
    if (searchOrdersEl) {
        searchOrdersEl.addEventListener('input', debounce(() => renderOrdersGrouped(), 150));
    }

    // Add new client (Customers tab)
    const btnAddClient = document.getElementById('btn-add-client');
    if (btnAddClient) {
        btnAddClient.addEventListener('click', async () => {
            const name = prompt('اسم العميل الجديد:');
            if (!name) return;
            const phone = prompt('رقم الهاتف (اختياري):') || '';
            const isWholesale = confirm('هل العميل جملة؟\nموافق = جملة\nإلغاء = قطاعي');
            try {
                const json = await apiPostJson('/quick_add', {
                    type: 'client',
                    name: name,
                    phone: phone,
                    client_type: isWholesale ? 'Wholesale' : 'Retail'
                });
                if (json.success) {
                    showToast('تمت إضافة العميل', 'success');
                    loadData(true);
                } else {
                    showToast(json.message || 'فشل الإضافة', 'error');
                }
            } catch (e) { showToast(e.message, 'error'); }
        });
    }

    // Refresh clients (Customers tab)
    const btnRefreshClients = document.getElementById('btn-refresh-clients');
    if (btnRefreshClients) {
        btnRefreshClients.addEventListener('click', () => loadData(true));
    }
}

// ================= Drag & Drop =================
function setupDragDrop() {
    const imgArea = document.getElementById('image-preview-area');
    if (!imgArea) return;

    imgArea.addEventListener('dragover', (e) => { e.preventDefault(); imgArea.style.borderColor = '#10B981'; });
    imgArea.addEventListener('dragleave', (e) => { e.preventDefault(); imgArea.style.borderColor = ''; });
    imgArea.addEventListener('drop', (e) => {
        e.preventDefault();
        imgArea.style.borderColor = '';
        const files = Array.from(e.dataTransfer.files).filter(f => f.type.startsWith('image/'));
        if (files.length > 0) {
            if (selectedImages.length + files.length > 16) return showToast('العدد الأقصى 16 صورة', 'warn');
            selectedImages.push(...files.map(f => (f._preview = null, f)));
            updateImageCount();
            renderImagePreview();
            scheduleDraftSave();
        }
    });
}

// ================= Data Loading =================
async function loadData(force) {
    try {
        setConnectionState(true);
        const [pJson, cJson, oJson, mJson] = await Promise.all([
            apiGet('/products', { silent: force }),
            apiGet('/clients'),
            apiGet('/orders'),
            apiGet('/mobile/orders', { silent: true })
        ]);

        allProducts = (pJson && pJson.success) ? pJson.products : [];
        allProductsFull = allProducts.slice();
        productOptionsHtmlCache = null; // refresh row dropdowns after data reload
        allClients = (cJson && cJson.customers) ? cJson.customers : [];
        allOrders = (oJson && oJson.orders) ? oJson.orders : [];
        // Server-side real status grouping (app.py /api/mobile/orders): prep/ready/done
        allOrdersGrouped = (mJson && Array.isArray(mJson.prep)) ? mJson : { prep: [], ready: [], done: [] };

        renderClients(allClients);
        renderOrdersGrouped();
        if (force) showToast('تم تحديث البيانات', 'success');

        populateClientDatalist(allClients);
        loadCategoriesForExt();

        if (orderItems.length === 0) addOrderItem();
        else renderOrderRows();

        firstLoadDone = true;
    } catch (error) {
        console.error(error);
        setConnectionState(false, error.name === 'TimeoutError' ? 'timeout'
            : (error && error.message && /Failed to fetch|NetworkError|ECONNREFUSED/.test(error.message) ? 'offline' : 'error'));
        showToast('خطأ في الاتصال: ' + (error.message || 'غير معروف'), 'error');
    }
}

// ================= Renderers =================
function populateClientDatalist(clients) {
    const list = document.getElementById('clients-datalist');
    list.innerHTML = '';
    clients.forEach(c => {
        const opt = document.createElement('option');
        opt.value = c.name;
        list.appendChild(opt);
    });
}

function populateCategoryFilter(products) {
    const sel = document.getElementById('filter-category');
    if (!sel) return; // Products grid removed from this UI
    const cats = [...new Set(products.map(p => p.category).filter(Boolean))];
    const currentVal = sel.value;
    sel.innerHTML = '<option value="">كل الأقسام</option>';
    cats.forEach(c => {
        const opt = document.createElement('option');
        opt.value = c;
        opt.textContent = c;
        sel.appendChild(opt);
    });
    if (currentVal) sel.value = currentVal;
}

async function loadCategoriesForExt() {
    try {
        const json = await apiGet('/get_categories', { silent: true });
        if (json.success) {
            const list = document.getElementById('ext-cat-list');
            if (!list) return;
            list.innerHTML = '';
            json.categories.forEach(c => {
                const opt = document.createElement('option');
                opt.value = c.name;
                list.appendChild(opt);
            });
        }
    } catch (e) { console.warn('loadCategoriesForExt', e); }
}

function getClientType() {
    return document.getElementById('client-type')?.value || 'Retail';
}

function renderOrdersGrouped() {
    const prep = document.getElementById('orders-prep');
    const ready = document.getElementById('orders-ready');
    const done = document.getElementById('orders-done');
    if (!prep || !ready || !done) return; // Orders tab not present

    const term = (document.getElementById('search-orders')?.value || '').toLowerCase();
    const countPrep = document.getElementById('count-prep');
    const countReady = document.getElementById('count-ready');
    const countDone = document.getElementById('count-done');

    const matches = (o) => {
        if (!term) return true;
        const client = String(o.client_name || o.client || '').toLowerCase();
        return client.includes(term) || String(o.id).includes(term);
    };

    const renderGroup = (container, list, countEl) => {
        container.innerHTML = '';
        const safeList = Array.isArray(list) ? list : [];
        if (countEl) countEl.textContent = safeList.length;
        const filtered = safeList.filter(matches);
        if (filtered.length === 0) {
            container.innerHTML = '<div class="empty-state">لا يوجد طلبات</div>';
            return;
        }
        filtered.forEach(o => {
            const client = o.client_name || o.client || 'عميل غير معروف';
            const total = (o.total_amount != null) ? o.total_amount : (o.total || 0);
            const items = Array.isArray(o.items) ? o.items : [];
            const itemsHtml = items.length ? `
                <details style="margin-top:6px;">
                    <summary style="cursor:pointer; font-size:11px;">عرض المنتجات (${items.length})</summary>
                    <ul style="font-size:11px; margin:6px 0 0 0; padding-right:16px;">
                        ${items.map(i => `<li>${escapeHtml(i.product_name)} × ${escapeHtml(i.qty)} = ${escapeHtml(i.total)}</li>`).join('')}
                    </ul>
                </details>` : '';
            const div = document.createElement('div');
            div.className = 'card';
            div.innerHTML = `
                <div class="card-header">
                    <span class="card-title">#${escapeHtml(o.id)} - ${escapeHtml(client)}</span>
                    <div style="display:flex; gap:5px;">
                        <button class="btn-edit-order" data-id="${escapeHtml(o.id)}" style="border:none;background:none;cursor:pointer;">✏️</button>
                        <button class="btn-delete-order" data-id="${escapeHtml(o.id)}" style="border:none;background:none;cursor:pointer;">🗑️</button>
                    </div>
                </div>
                <div class="card-subtitle" style="direction:ltr; text-align:right;">${escapeHtml(o.date || '')}</div>
                <div style="font-weight:bold; margin-top:5px;">${escapeHtml(total)}</div>
                ${itemsHtml}
            `;
            container.appendChild(div);
        });
    };

    renderGroup(prep, allOrdersGrouped.prep, countPrep);
    renderGroup(ready, allOrdersGrouped.ready, countReady);
    renderGroup(done, allOrdersGrouped.done, countDone);
}

function renderClients(list) {
    const searchEl = document.getElementById('search-clients');
    const sortEl = document.getElementById('sort-clients');
    const container = document.getElementById('clients-list');
    if (!container) return; // Customers tab not present

    const term = (searchEl?.value || '').toLowerCase();
    const sortMode = sortEl?.value || 'name';

    let filtered = (list || []).filter(c => c.name.toLowerCase().includes(term) || (c.phone && c.phone.includes(term)));

    filtered.sort((a, b) => {
        if (sortMode === 'wholesale') return (a.type === 'Wholesale' && b.type !== 'Wholesale') ? -1 : 1;
        if (sortMode === 'retail') return (a.type === 'Retail' && b.type !== 'Retail') ? -1 : 1;
        if (sortMode === 'debt') return (b.total_debt || 0) - (a.total_debt || 0);
        return a.name.localeCompare(b.name);
    });

    container.innerHTML = '';
    if (filtered.length === 0) {
        container.innerHTML = '<div class="empty-state">لا يوجد عملاء</div>';
        return;
    }

    filtered.forEach(c => {
        const div = document.createElement('div');
        div.className = 'card';
        const debt = Number(c.total_debt) || 0;
        div.innerHTML = `
            <div class="card-header">
                <span class="card-title">${escapeHtml(c.name)}</span>
                ${debt > 0 ? `<span class="debt-indicator">-${escapeHtml(debt)}</span>` : `<span style="color:#34d399">0</span>`}
            </div>
            <div style="font-size:11px;color:#aaa;direction:ltr;text-align:right;">${escapeHtml(c.phone || '')}</div>
            <div class="card-subtitle">
                <span>${c.type === 'Wholesale' ? '⭐️ جملة' : 'قطاعي'}</span>
                <span style="font-size:10px;">#${escapeHtml(c.id)}</span>
            </div>
            <div style="margin-top:8px;display:flex;gap:5px;">
                <button class="btn btn-sm btn-secondary btn-pay-debt" style="flex:1;" data-id="${escapeHtml(c.id)}">تسديد</button>
                <button class="btn btn-sm btn-delete-client" style="background:rgba(239,68,68,.15);color:#f87171;" data-id="${escapeHtml(c.id)}" data-name="${escapeHtml(c.name)}">حذف</button>
            </div>
        `;
        container.appendChild(div);
    });
}

function renderProductsGrid() {
    const container = document.getElementById('products-grid');
    if (!container) return; // Products grid removed from this UI
    const term = (document.getElementById('search-products')?.value || '').toLowerCase();
    const cat = document.getElementById('filter-category')?.value || '';
    const modeEl = document.querySelector('input[name="price_mode"]:checked');
    const mode = modeEl ? modeEl.value : 'retail';

    const filtered = allProducts.filter(p => p.name.toLowerCase().includes(term) && (cat === '' || p.category === cat));
    container.innerHTML = '';

    if (filtered.length === 0) {
        container.innerHTML = '<div class="empty-state">لا يوجد منتجات</div>';
        return;
    }

    filtered.forEach(p => {
        const displayPrice = (mode === 'wholesale' && p.price_wholesale) ? p.price_wholesale : p.price;
        const div = document.createElement('div');
        div.className = 'product-card';
        div.innerHTML = `
            <div class="p-name">${escapeHtml(p.name)}</div>
            <div class="p-cat">${escapeHtml(p.category || 'بدون تصنيف')}</div>
            <div style="margin-top:5px;font-size:11px;display:flex;justify-content:space-between;">
                <span>${mode === 'retail' ? 'قطاعي' : 'جملة'}</span>
                <span class="p-price">${escapeHtml(displayPrice)}</span>
            </div>
            <div style="margin-top:5px;"><span class="stock-badge">مخزون: ${escapeHtml(p.stock)}</span></div>
        `;
        container.appendChild(div);
    });
}

// ================= Order Items =================
function addOrderItem(product = null) {
    const type = getClientType();
    const item = {
        _uid: Date.now() + Math.random(),
        product_id: product ? product.id : "",
        price: product ? (type === 'Wholesale' ? product.price_wholesale : product.price_retail) : 0,
        qty: 1,
        retail_price: product ? product.price_retail : 0,
        wholesale_price: product ? product.price_wholesale : 0,
        images: [],
        name: product ? product.name : ''
    };
    orderItems.push(item);
    renderOrderRows();
    scheduleDraftSave();
}

function assignImagesToItem(uid) {
    const item = orderItems.find(i => String(i._uid) === String(uid));
    if (!item) return;
    if (selectedImages.length === 0) {
        showToast('لا توجد صور محددة! اسحب الصور أولاً ثم اضغط هنا.', 'warn');
        return;
    }
    item.images = [...item.images, ...selectedImages];
    selectedImages = [];
    renderImagePreview();
    updateImageCount();
    renderOrderRows();
    scheduleDraftSave();
    showToast(`✅ تم إرفاق ${item.images.length} صورة للمنتج`, 'success');
}

function removeOrderItem(uid) {
    orderItems = orderItems.filter(i => String(i._uid) !== String(uid));
    renderOrderRows();
    scheduleDraftSave();
}

function updateItemProduct(uid, productId) {
    const item = orderItems.find(i => String(i._uid) === String(uid));
    if (!item) return;
    const product = allProductsFull.find(p => p.id == productId);
    if (product) {
        item.product_id = product.id;
        item.retail_price = product.price_retail;
        item.wholesale_price = product.price_wholesale;
        item.price = getClientType() === 'Wholesale' ? item.wholesale_price : item.retail_price;
        item.name = product.name;
    }
    renderOrderRows();
    scheduleDraftSave();
}

function updateItemField(uid, field, value) {
    const item = orderItems.find(i => i._uid === uid);
    if (item) {
        item[field] = parseFloat(value) || 0;
        calculateTotal();
        scheduleDraftSave();
    }
}

function updateAllPricesForClientType() {
    const type = getClientType();
    orderItems.forEach(item => {
        if (item.product_id) item.price = type === 'Wholesale' ? item.wholesale_price : item.retail_price;
    });
    renderOrderRows();
    calculateTotal();
}

function calculateTotal() {
    const total = CORE ? CORE.computeTotal(orderItems) : orderItems.reduce((s, it) => s + (it.price * it.qty), 0);
    const el = document.getElementById('total-amount');
    if (el) el.textContent = total.toFixed(2);
}

function getProductOptionsHtml() {
    if (productOptionsHtmlCache !== null) return productOptionsHtmlCache;
    productOptionsHtmlCache = allProductsFull.map(p =>
        `<option value="${escapeHtml(p.id)}">${escapeHtml(p.name)}</option>`
    ).join('');
    return productOptionsHtmlCache;
}

function renderOrderRows() {
    const container = document.getElementById('order-items-container');
    if (!container) return;
    container.innerHTML = '';
    orderItems.forEach((item, idx) => {
        const div = document.createElement('div');
        div.className = 'order-row';
        div.dataset.uid = item._uid;

        const options = '<option value="">اختر المنتج...</option>' + getProductOptionsHtml();

        const imgCount = item.images ? item.images.length : 0;
        div.innerHTML = `
            <select class="oi-product" data-uid="${escapeHtml(item._uid)}" style="flex:2; min-width:120px;">${options}</select>
            <input type="number" class="oi-qty" data-uid="${escapeHtml(item._uid)}" value="${escapeHtml(item.qty)}" style="width:45px;">
            <input type="number" class="oi-price" data-uid="${escapeHtml(item._uid)}" value="${escapeHtml(item.price)}" style="width:60px;">
            <button type="button" class="img-btn ${imgCount > 0 ? 'has-images' : ''}" data-uid="${escapeHtml(item._uid)}" title="اضغط لإرفاق الصور المحددة بهذا المنتج">📷 ${imgCount}</button>
            <button type="button" class="del-btn" data-uid="${escapeHtml(item._uid)}">🗑️</button>
        `;

        // Set selected product
        const select = div.querySelector('.oi-product');
        if (item.product_id) select.value = item.product_id;

        container.appendChild(div);
    });
    calculateTotal();
    renderInvoice();
}

// ================= Invoice (فاتورة مراجعة قبل الحفظ) =================
function renderInvoice() {
    const rowsEl = document.getElementById('invoice-rows');
    const totalEl = document.getElementById('invoice-total');
    const imgEl = document.getElementById('invoice-images');
    if (!rowsEl || !totalEl) return;

    rowsEl.innerHTML = '';
    let totalImages = 0;
    let hasInvalid = false;

    orderItems.forEach((it, idx) => {
        const product = allProductsFull.find(p => p.id == it.product_id);
        const name = it.name || (product ? product.name : (it.product_id ? '#' + it.product_id : '— منتج غير محدد —'));
        const qty = Number(it.qty) || 0;
        const price = Number(it.price) || 0;
        const imgs = it.images ? it.images.length : 0;
        totalImages += imgs;
        if (!it.product_id || qty <= 0 || price <= 0) hasInvalid = true;

        const row = document.createElement('div');
        row.className = 'invoice-row' + (hasInvalid && (!it.product_id || qty <= 0 || price <= 0) ? ' invoice-row-warn' : '');
        row.innerHTML = `
            <span class="inv-idx">${idx + 1}</span>
            <span class="inv-name">${escapeHtml(name)}</span>
            <span class="inv-qty">${escapeHtml(qty)}</span>
            <span class="inv-price">${price.toFixed(2)}</span>
            <span class="inv-total">${(qty * price).toFixed(2)}</span>
            ${imgs > 0 ? `<span class="inv-img" title="صور مرفقة">📷${imgs}</span>` : '<span class="inv-img"></span>'}
        `;
        rowsEl.appendChild(row);
    });

    const total = CORE ? CORE.computeTotal(orderItems)
        : orderItems.reduce((s, it) => s + ((Number(it.price) || 0) * (Number(it.qty) || 0)), 0);
    totalEl.textContent = total.toFixed(2);
    if (imgEl) {
        imgEl.textContent = totalImages > 0 ? `📷 إجمالي الصور: ${totalImages}` : '';
    }
    const warnEl = document.getElementById('invoice-warn');
    if (warnEl) {
        warnEl.style.display = (hasInvalid && orderItems.length > 0) ? 'block' : 'none';
    }
}

// Event delegation for order rows (performance: no re-render per keystroke)
document.addEventListener('change', (e) => {
    const t = e.target;
    if (t.classList.contains('oi-product')) updateItemProduct(t.dataset.uid, t.value);
});
document.addEventListener('input', (e) => {
    const t = e.target;
    if (t.classList.contains('oi-qty')) {
        const item = orderItems.find(i => String(i._uid) === String(t.dataset.uid));
        if (item) item.qty = parseFloat(t.value) || 0;
        calculateTotal();
        scheduleDraftSave();
    }
    if (t.classList.contains('oi-price')) {
        const item = orderItems.find(i => String(i._uid) === String(t.dataset.uid));
        if (item) item.price = parseFloat(t.value) || 0;
        calculateTotal();
        scheduleDraftSave();
    }
});
document.addEventListener('click', (e) => {
    const t = e.target;
    if (t.classList.contains('img-btn')) assignImagesToItem(t.dataset.uid);
    if (t.classList.contains('del-btn')) {
        const uidRaw = t.dataset.uid;
        const item = orderItems.find(i => String(i._uid) === String(uidRaw));
        orderItems = orderItems.filter(i => String(i._uid) !== String(uidRaw));
        if (item && item.images && item.images.length) {
            showToast('تم حذف سطر المنتج', 'info');
        }
        renderOrderRows();
        scheduleDraftSave();
    }
});

// ================= Form Submit (with dedup guard) =================
async function onFormSubmit(e) {
    e.preventDefault();
    if (isSubmitting) {
        showToast('يتم الإرسال حاليًا... انتظر', 'warn');
        return;
    }
    const btn = e.target.querySelector('button[type="submit"]');
    const originalText = btn.textContent;
    btn.textContent = "جاري الحفظ...";
    btn.disabled = true;

    try {
        const formData = new FormData(e.target);
        const validItems = CORE ? CORE.buildItemsPayload(orderItems) : orderItems.filter(i => i.product_id || i.price > 0);

        // Fallback for non-core environments
        if (!CORE) {
            // legacy mapping
            const legacy = orderItems.filter(i => i.product_id || i.price > 0).map((i, idx) => ({
                id: i.product_id, qty: i.qty, price: i.price,
                image_count: i.images ? i.images.length : 0, item_index: idx
            }));
            formData.append('items', JSON.stringify(legacy));
        } else {
            formData.append('items', JSON.stringify(validItems));
        }

        if (validItems.length === 0) {
            throw new Error("يجب اختيار منتج واحد على الأقل");
        }

        // Append images with item index prefix for backend matching
        orderItems.forEach((item, idx) => {
            if (item.images && item.images.length > 0) {
                item.images.forEach(file => {
                    formData.append(`images_${idx}`, file);
                });
            }
        });

        // Also append any global selectedImages (for backward compatibility)
        selectedImages.forEach(file => formData.append('images_global', file));

        // Idempotency key: unique per submission. Server ignores unknown field, but let's send it.
        const requestId = CORE ? CORE.makeRequestId() : (Date.now() + '-' + Math.random());
        formData.append('client_request_id', requestId);

        // apiPostForm prepends API_URL itself — pass PATH ONLY
        let url = '/whatsapp_sync';
        if (editingOrderId) {
            url = '/update_order';
            formData.append('order_id', editingOrderId);
        }

        isSubmitting = true;
        // Long timeout: first save may take longer (image upload + WAL + cold start)
        const json = await apiPostForm(url, formData, { timeoutMs: 60000 });

        if (json.success) {
            showToast(editingOrderId ? "تم تعديل الطلب" : "تم إنشاء الطلب #" + json.order_id, 'success');
            e.target.reset();
            selectedImages = [];
            orderItems = [];
            renderImagePreview();
            updateImageCount();
            editingOrderId = null;
            btn.textContent = 'إنشاء الطلب والمزامنة';
            btn.style.background = "";
            // Remove draft after successful submit
            if (chrome && chrome.storage) chrome.storage.local.remove(DRAFT_KEY);
            loadData(true);
        } else {
            showToast('خطأ: ' + (json.message || 'غير معروف'), 'error');
        }
    } catch (err) {
        showToast('خطأ: ' + (err.message || 'غير معروف'), 'error');
    } finally {
        isSubmitting = false;
        btn.textContent = originalText;
        btn.disabled = false;
    }
}

// ================= Action Helpers =================
async function deleteClient(id) {
    try {
        const json = await apiPostJson('/delete_client', { client_id: id });
        if (json.success) { loadData(true); showToast('تم حذف العميل', 'success'); }
    } catch (e) { showToast('Error: ' + e.message, 'error'); }
}

async function deleteOrder(id) {
    try {
        const json = await apiPostJson('/delete_order', { order_id: id });
        if (json.success) { loadData(true); showToast('تم حذف الطلب', 'success'); }
    } catch (e) { showToast('Error: ' + e.message, 'error'); }
}

async function payDebt(id) {
    const amt = prompt("المبلغ:");
    if (!amt) return;
    try {
        const json = await apiPostJson('/pay_debt', { client_id: id, amount: amt });
        if (json.success) { showToast('تم', 'success'); loadData(true); }
        else showToast(json.message || 'فشل', 'error');
    } catch (e) { showToast('Error: ' + e.message, 'error'); }
}

async function editOrder(id) {
    try {
        const json = await apiPostJson('/get_order_details', { order_id: id });
        if (json.success) {
            const { order, client, items } = json.data;
            const homeTabBtn = document.querySelector('[data-tab="tab-home"]');
            if (homeTabBtn) homeTabBtn.click();
            document.getElementById('client-name').value = client.name;
            document.getElementById('client-phone').value = client.phone || '';
            document.getElementById('client-type').value = client.type || 'Retail';
            document.getElementById('notes').value = order.notes || '';

            orderItems = [];
            if (items && items.length) {
                items.forEach(i => {
                    orderItems.push({
                        _uid: Date.now() + Math.random(),
                        product_id: i.product_id,
                        price: i.price,
                        qty: i.qty,
                        retail_price: i.price_retail || i.price,
                        wholesale_price: i.price_wholesale || i.price,
                        images: [],
                        name: ''
                    });
                });
            } else addOrderItem();

            renderOrderRows();
            editingOrderId = id;
            const btn = document.querySelector('#sync-form button[type="submit"]');
            btn.textContent = `حفظ التعديلات (طلب #${id})`;
            btn.style.background = "#F59E0B";
            scheduleDraftSave();
        } else {
            showToast(json.message || 'خطأ في جلب الطلب', 'error');
        }
    } catch (e) { showToast('Edit Error: ' + e.message, 'error'); }
}

async function processIncomingImages(base64List) {
    if (!base64List || base64List.length === 0) return;

    const remainingSlots = 16 - selectedImages.length;
    if (remainingSlots <= 0) {
        showToast("تم الوصول للحد الأقصى (16 صورة). يرجى مسح بعض الصور أولاً.", 'warn');
        return;
    }

    const addingList = base64List.slice(0, remainingSlots);
    updateImageCount(addingList.length);

    try {
        for (const b64 of addingList) {
            try {
                const res = await fetch(b64);
                const blob = await res.blob();
                const type = blob.type.startsWith('image/') ? blob.type : "image/jpeg";
                const file = new File([blob], `img_${Date.now()}_${Math.random().toString(36).substr(2, 5)}.jpg`, { type: type });
                file._preview = b64;
                selectedImages.push(file);
            } catch (err) {
                console.error("Error processing blob:", err);
            }
        }
    } finally {
        renderImagePreview();
        updateImageCount();
        scheduleDraftSave();
    }
}

function updateImageCount(extra) {
    const el = document.getElementById('img-count');
    if (!el) return;
    const total = selectedImages.length + (extra || 0);
    el.textContent = (extra && extra > 0 ? 'جاري المعالجة... ' : '') + (selectedImages.length) + ' صور';
}

async function sendMessageToContent(payload) {
    const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
    if (tabs[0] && tabs[0].url.includes("whatsapp.com")) {
        try {
            return await chrome.tabs.sendMessage(tabs[0].id, payload);
        } catch (e) {
            console.warn(e);
            // Try to inject content script as fallback (already declared in manifest)
            try {
                await chrome.scripting.executeScript({
                    target: { tabId: tabs[0].id },
                    files: ['content.js']
                });
                return await chrome.tabs.sendMessage(tabs[0].id, payload);
            } catch (e2) {
                console.warn('Injection fallback failed', e2);
                showToast('يرجى تحديث صفحة واتساب أولاً!', 'error');
                return null;
            }
        }
    } else {
        showToast('يرجى فتح واتساب ويب أولاً', 'error');
        return null;
    }
}

let objectUrlRegistry = [];
function renderImagePreview() {
    const area = document.getElementById('image-preview-area');
    // Revoke previously created object URLs to avoid leaks
    objectUrlRegistry.forEach(u => { try { URL.revokeObjectURL(u); } catch (e) {} });
    objectUrlRegistry = [];
    area.innerHTML = '';

    selectedImages.forEach((file, idx) => {
        const img = document.createElement('img');

        if (file._preview) {
            img.src = file._preview;
        } else {
            img.src = URL.createObjectURL(file);
            objectUrlRegistry.push(img.src);
        }

        const removeBtn = document.createElement('button');
        removeBtn.className = 'img-remove-btn';
        removeBtn.dataset.idx = idx;
        removeBtn.textContent = 'x';

        const div = document.createElement('div');
        div.style.position = 'relative';
        div.style.display = 'inline-block';
        div.style.width = '60px';
        div.style.height = '60px';
        div.style.margin = '4px';
        div.style.borderRadius = '8px';
        div.style.overflow = 'hidden';
        div.style.border = '1px solid #ccc';

        img.style.width = '100%';
        img.style.height = '100%';
        img.style.objectFit = 'cover';

        div.appendChild(img);
        div.appendChild(removeBtn);
        area.appendChild(div);
    });
}

async function checkLastOrder(client) {
    const infoDiv = document.getElementById('last-order-info');
    const dateSpan = document.getElementById('last-order-date');
    const itemsList = document.getElementById('last-order-items');

    infoDiv.style.display = 'none';
    itemsList.innerHTML = '';

    if (!client || !client.id) return;

    try {
        const json = await apiPostJson('/get_client_last_order', { client_id: client.id }, { silent: true });
        if (json.success && json.order) {
            const o = json.order;
            infoDiv.style.display = 'block';
            dateSpan.textContent = formatDate(o.date);

            const oldBal = document.getElementById('last-order-bal-display');
            if (oldBal) oldBal.remove();
            const balDiv = document.createElement('div');
            balDiv.className = 'bal';
            balDiv.id = 'last-order-bal-display';
            const debt = Number(client.total_debt) || 0;
            balDiv.innerHTML = `الرصيد: <span style="font-weight:bold; color:${debt > 0 ? '#EF4444' : '#10B981'}">${escapeHtml(debt)}</span>`;
            infoDiv.insertBefore(balDiv, itemsList);

            if (o.items && o.items.length > 0) {
                o.items.forEach(item => {
                    const li = document.createElement('li');
                    li.textContent = `${item.qty}x ${item.product_name || 'منتج'}`;
                    itemsList.appendChild(li);
                });
            } else {
                itemsList.innerHTML = '<li>(طلب بدون منتجات)</li>';
            }
        }
    } catch (e) {
        console.error("Failed to check last order", e);
    }
}

// ================= Financial Workspace =================
let currentFinancialData = [];

async function loadFinancialData() {
    try {
        // Load today's transactions
        const stats = await apiGet('/financial/stats');
        const ledger = await apiGet('/financial/ledger?start=' + getTodayDate() + '&end=' + getTodayDate());
        
        // Update summary
        const income = document.getElementById('financial-income');
        const expense = document.getElementById('financial-expense');
        const net = document.getElementById('financial-net');
        
        if (income) income.textContent = formatCurrency(stats.total_income || 0);
        if (expense) expense.textContent = formatCurrency(stats.total_expense || 0);
        if (net) {
            const netValue = (stats.total_income || 0) - (stats.total_expense || 0);
            net.textContent = formatCurrency(netValue);
            net.style.color = netValue >= 0 ? '#10B981' : '#f87171';
        }
        
        // Render transactions list
        const listContainer = document.getElementById('financial-transactions-list');
        if (listContainer) {
            if (ledger && ledger.length > 0) {
                currentFinancialData = ledger;
                listContainer.innerHTML = ledger.map(t => `
                    <div class="card" style="margin-bottom:8px; padding:8px;">
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <div>
                                <span style="font-weight:bold; color:${t.type === 'Income' ? '#10B981' : '#f87171'}">${t.type === 'Income' ? '📈' : '📉'}</span>
                                <span style="margin-right:4px;">${escapeHtml(t.category || t.type)}</span>
                            </div>
                            <div style="font-weight:bold; color:${t.type === 'Income' ? '#10B981' : '#f87171'}">${escapeHtml(t.amount)}</div>
                        </div>
                        <div style="font-size:11px; color:var(--text-sub); margin-top:4px;">${escapeHtml(t.description || '')}</div>
                    </div>
                `).join('');
            } else {
                listContainer.innerHTML = '<div class="empty-state">لا توجد حركات اليوم</div>';
            }
        }
    } catch (e) {
        console.error('Failed to load financial data', e);
    }
}

function getTodayDate() {
    return new Date().toISOString().split('T')[0];
}

function formatCurrency(amount) {
    return parseFloat(amount || 0).toFixed(2);
}

// Setup financial modals
function setupFinancialModals() {
    // Income modal
    const incomeModal = document.getElementById('income-modal');
    const btnAddIncome = document.getElementById('btn-add-income');
    const btnCancelIncome = document.getElementById('btn-cancel-income');
    const btnSaveIncome = document.getElementById('btn-save-income');
    
    if (btnAddIncome) {
        btnAddIncome.addEventListener('click', () => {
            if (incomeModal) incomeModal.style.display = 'flex';
        });
    }
    if (btnCancelIncome) {
        btnCancelIncome.addEventListener('click', () => {
            if (incomeModal) incomeModal.style.display = 'none';
            clearIncomeForm();
        });
    }
    if (btnSaveIncome) {
        btnSaveIncome.addEventListener('click', saveIncomeTransaction);
    }
    
    // Expense modal
    const expenseModal = document.getElementById('expense-modal');
    const btnAddExpense = document.getElementById('btn-add-expense');
    const btnCancelExpense = document.getElementById('btn-cancel-expense');
    const btnSaveExpense = document.getElementById('btn-save-expense');
    
    if (btnAddExpense) {
        btnAddExpense.addEventListener('click', () => {
            if (expenseModal) expenseModal.style.display = 'flex';
        });
    }
    if (btnCancelExpense) {
        btnCancelExpense.addEventListener('click', () => {
            if (expenseModal) expenseModal.style.display = 'none';
            clearExpenseForm();
        });
    }
    if (btnSaveExpense) {
        btnSaveExpense.addEventListener('click', saveExpenseTransaction);
    }
    
    // Obligation modal
    const obligationModal = document.getElementById('obligation-modal');
    const btnAddObligation = document.getElementById('btn-add-obligation');
    const btnCancelObligation = document.getElementById('btn-cancel-obligation');
    const btnSaveObligation = document.getElementById('btn-save-obligation');
    
    if (btnAddObligation) {
        btnAddObligation.addEventListener('click', () => {
            if (obligationModal) obligationModal.style.display = 'flex';
        });
    }
    if (btnCancelObligation) {
        btnCancelObligation.addEventListener('click', () => {
            if (obligationModal) obligationModal.style.display = 'none';
            clearObligationForm();
        });
    }
    if (btnSaveObligation) {
        btnSaveObligation.addEventListener('click', saveObligation);
    }
}

function clearIncomeForm() {
    const amount = document.getElementById('income-amount');
    const note = document.getElementById('income-note');
    if (amount) amount.value = '';
    if (note) note.value = '';
}

function clearExpenseForm() {
    const amount = document.getElementById('expense-amount');
    const note = document.getElementById('expense-note');
    if (amount) amount.value = '';
    if (note) note.value = '';
}

function clearObligationForm() {
    const party = document.getElementById('obligation-party');
    const amount = document.getElementById('obligation-amount');
    const desc = document.getElementById('obligation-description');
    if (party) party.value = '';
    if (amount) amount.value = '';
    if (desc) desc.value = '';
}

async function saveIncomeTransaction() {
    const amount = parseFloat(document.getElementById('income-amount')?.value || 0);
    const type = document.getElementById('income-type')?.value || 'Other';
    const note = document.getElementById('income-note')?.value || '';
    
    if (amount <= 0) {
        showToast('المبلغ يجب أن يكون أكبر من صفر', 'warn');
        return;
    }
    
    try {
        const json = await apiPostJson('/financial/transaction', {
            type: 'Income',
            category: type,
            amount: amount,
            description: note
        });
        if (json.success) {
            showToast('تم تسجيل الدخل بنجاح', 'success');
            document.getElementById('income-modal').style.display = 'none';
            clearIncomeForm();
            loadFinancialData();
        } else {
            showToast(json.message || 'فشل تسجيل الدخل', 'error');
        }
    } catch (e) {
        showToast('خطأ: ' + e.message, 'error');
    }
}

async function saveExpenseTransaction() {
    const amount = parseFloat(document.getElementById('expense-amount')?.value || 0);
    const category = document.getElementById('expense-category')?.value || 'Other';
    const note = document.getElementById('expense-note')?.value || '';
    
    if (amount <= 0) {
        showToast('المبلغ يجب أن يكون أكبر من صفر', 'warn');
        return;
    }
    
    try {
        const json = await apiPostJson('/financial/transaction', {
            type: 'Expense',
            category: category,
            amount: amount,
            description: note
        });
        if (json.success) {
            showToast('تم تسجيل المصروف بنجاح', 'success');
            document.getElementById('expense-modal').style.display = 'none';
            clearExpenseForm();
            loadFinancialData();
        } else {
            showToast(json.message || 'فشل تسجيل المصروف', 'error');
        }
    } catch (e) {
        showToast('خطأ: ' + e.message, 'error');
    }
}

async function saveObligation() {
    const type = document.getElementById('obligation-type')?.value;
    const party = document.getElementById('obligation-party')?.value;
    const amount = parseFloat(document.getElementById('obligation-amount')?.value || 0);
    const desc = document.getElementById('obligation-description')?.value || '';
    
    if (!party || amount <= 0) {
        showToast('الطرف والمبلغ مطلوبان', 'warn');
        return;
    }
    
    try {
        const json = await apiPostJson('/financial/obligations', {
            type: type,
            name: party,
            amount: amount,
            description: desc
        });
        if (json.success) {
            showToast('تم تسجيل الالتزام بنجاح', 'success');
            document.getElementById('obligation-modal').style.display = 'none';
            clearObligationForm();
            loadFinancialData();
        } else {
            showToast(json.message || 'فشل تسجيل الالتزام', 'error');
        }
    } catch (e) {
        showToast('خطأ: ' + e.message, 'error');
    }
}

// ================= AI Analysis =================
let analyzedChatData = null;

function resetAIAnalysis() {
    analyzedChatData = null;
    document.getElementById('ai-analysis-result').style.display = 'none';
    document.getElementById('ai-loading').style.display = 'none';
}

async function analyzeCurrentChat() {
    const resultDiv = document.getElementById('ai-analysis-result');
    const loadingDiv = document.getElementById('ai-loading');
    
    resultDiv.style.display = 'none';
    loadingDiv.style.display = 'block';
    
    try {
        // Get chat info and messages
        const chatInfo = await sendMessageToContent({ action: "get_chat_info" });
        const messages = await sendMessageToContent({ action: "get_chat_messages" });
        const images = await sendMessageToContent({ action: "get_images_only" });
        
        // Analyze messages
        const analysis = analyzeMessages(chatInfo, messages || []);
        
        analyzedChatData = {
            clientName: chatInfo?.title || '',
            clientPhone: chatInfo?.phone || '',
            products: analysis.products,
            missingInfo: analysis.missingInfo,
            messages: messages || [],
            images: images || []
        };
        
        // Render analysis result
        renderAIAnalysisResult(analysis, chatInfo);
        
        loadingDiv.style.display = 'none';
        resultDiv.style.display = 'block';
        
    } catch (e) {
        loadingDiv.style.display = 'none';
        showToast('فشل تحليل المحادثة: ' + e.message, 'error');
    }
}

function analyzeMessages(chatInfo, messages) {
    const products = [];
    const missingInfo = [];
    
    // Simple keyword-based analysis
    const productPatterns = [
        { regex: /(\d+)\s*[xX×]\s*(.+)/, nameIndex: 1 },
        // Add more patterns as needed
    ];
    
    // Keywords for order detection
    const orderKeywords = ['طلب', 'محتاج', 'عايز', 'محتاجة', 'গiri'];
    const priceKeywords = ['سعر', 'بكام', '洗', 'كم الفلوس'];
    const quantityKeywords = ['عدد', 'كمية', 'حبة'];
    
    let hasOrderIntent = false;
    let hasPriceQuery = false;
    
    messages.forEach(msg => {
        if (typeof msg !== 'string') return;
        
        // Check for order intent
        if (orderKeywords.some(k => msg.includes(k))) {
            hasOrderIntent = true;
        }
        
        // Check for price query only
        if (priceKeywords.some(k => msg.includes(k)) && !orderKeywords.some(k => msg.includes(k))) {
            hasPriceQuery = true;
        }
        
        // Try to extract product info
        productPatterns.forEach(pattern => {
            const match = msg.match(pattern.regex);
            if (match) {
                products.push({
                    name: match[pattern.nameIndex] || 'غير محدد',
                    quantity: 1,
                    notes: msg
                });
            }
        });
    });
    
    // Check for missing info
    if (!chatInfo?.title && !chatInfo?.phone) {
        missingInfo.push('اسم العميل أو رقم الهاتف');
    }
    if (products.length === 0 && hasOrderIntent) {
        missingInfo.push('المنتجات المطلوبة');
    }
    if (hasPriceQuery && products.length === 0) {
        missingInfo.push('المنتج للاستعلام عن السعر');
    }
    
    return {
        products: products.length > 0 ? products : [],
        missingInfo: missingInfo,
        hasOrderIntent: hasOrderIntent && !hasPriceQuery,
        isPriceQueryOnly: hasPriceQuery && !hasOrderIntent
    };
}

function renderAIAnalysisResult(analysis, chatInfo) {
    // Client info
    const clientInfoEl = document.getElementById('ai-client-info');
    if (clientInfoEl) {
        clientInfoEl.innerHTML = `
            <div style="margin-bottom:8px;"><strong>الاسم:</strong> ${escapeHtml(chatInfo?.title || 'غير محدد')}</div>
            <div style="margin-bottom:8px;"><strong>الهاتف:</strong> ${escapeHtml(chatInfo?.phone || 'غير محدد')}</div>
            <div style="color:${analysis.hasOrderIntent ? '#10B981' : (analysis.isPriceQueryOnly ? '#F59E0B' : '#b0b0b0')};">
                ${analysis.hasOrderIntent ? '✅ يبدو أنه طلب' : (analysis.isPriceQueryOnly ? '❓ استفسار عن السعر فقط' : '⚠️ لا يوجد طلب واضح')}
            </div>
        `;
    }
    
    // Products list
    const productsListEl = document.getElementById('ai-products-list');
    if (productsListEl) {
        if (analysis.products.length > 0) {
            productsListEl.innerHTML = analysis.products.map(p => `
                <div style="padding:8px; background:var(--input-bg); border-radius:4px; margin-bottom:8px;">
                    <strong>${escapeHtml(p.name)}</strong>
                    ${p.quantity > 1 ? `<span style="color:var(--text-sub);"> × ${p.quantity}</span>` : ''}
                </div>
            `).join('');
        } else {
            productsListEl.innerHTML = '<div style="color:var(--text-sub);">لم يتم استخراج منتجات</div>';
        }
    }
    
    // Missing info
    const missingInfoEl = document.getElementById('ai-missing-info');
    if (missingInfoEl) {
        if (analysis.missingInfo.length > 0) {
            missingInfoEl.innerHTML = '<ul>' + analysis.missingInfo.map(info => `<li>${escapeHtml(info)}</li>`).join('') + '</ul>';
        } else {
            missingInfoEl.innerHTML = '<div style="color:#10B981;">✅ جميع المعلومات متوفرة</div>';
        }
    }
    
    // Notes
    const notesEl = document.getElementById('ai-notes');
    if (notesEl) {
        notesEl.innerHTML = `
            <div style="color:var(--text-sub); font-size:12px;">
                ${analysis.hasOrderIntent ? 'من المحتمل أن العميل يطلب منتجات. راجع المنتجات المستخرجة.' : 
                  (analysis.isPriceQueryOnly ? 'هذا استفسار عن السعر فقط. لا يُنشئ طلب تلقائيًا.' : 
                   'تحليل المحادثة يحتاج مراجعة. لا يوجد طلب واضح.')}
            </div>
        `;
    }
    
    // Update create button visibility
    const createBtn = document.getElementById('btn-create-from-analysis');
    if (createBtn) {
        createBtn.style.display = analysis.hasOrderIntent ? 'inline-block' : 'none';
    }
}

function createOrderFromAnalysis() {
    if (!analyzedChatData) return;
    
    // Fill the main form with analyzed data
    document.getElementById('client-name').value = analyzedChatData.clientName || '';
    document.getElementById('client-phone').value = analyzedChatData.clientPhone || '';
    
    // Add analyzed products to order items
    analyzedChatData.products.forEach(product => {
        const productObj = allProductsFull.find(p => 
            p.name === product.name || 
            p.name.includes(product.name) || 
            product.name.includes(p.name)
        );
        addOrderItem(productObj || null);
        if (!productObj) {
            // If product not found, just add empty item
            const items = document.querySelectorAll('.order-row');
            const lastItem = items[items.length - 1];
            if (lastItem) {
                const qtyInput = lastItem.querySelector('.oi-qty');
                if (qtyInput) qtyInput.value = product.quantity || 1;
            }
        }
    });
    
    // Switch to main tab
    const homeTabBtn = document.querySelector('[data-tab="tab-home"]');
    if (homeTabBtn) homeTabBtn.click();
    
    showToast('تم تعبئة النموذج بالبيانات المستخرجة. راجع وأرسل.', 'success');
}

// Setup AI analysis event listeners
function setupAIAnalysisListeners() {
    const btnAnalyze = document.getElementById('btn-analyze-chat');
    const btnCreate = document.getElementById('btn-create-from-analysis');
    const btnSalma = document.getElementById('btn-ai-assistant-salma');
    const btnBebo = document.getElementById('btn-ai-assistant-bebo');
    
    if (btnAnalyze) btnAnalyze.addEventListener('click', analyzeCurrentChat);
    if (btnCreate) btnCreate.addEventListener('click', createOrderFromAnalysis);
    if (btnSalma) btnSalma.addEventListener('click', () => showToast('مساعد سلمى: اكتب رسالتك للعميل ici', 'info'));
    if (btnBebo) btnBebo.addEventListener('click', () => showToast('مساعد بيبو: تفاصيل التصنيع ici', 'info'));
}

// Initialize additional features
document.addEventListener('DOMContentLoaded', () => {
    setTimeout(() => {
        setupFinancialModals();
        setupAIAnalysisListeners();
        setupServerStatus();
    }, 500);
});

// ================= Server Status Control =================
let serverCheckInterval = null;
let serverStarting = false;

function setupServerStatus() {
    const btnStart = document.getElementById('btn-start-server');
    const btnStartTab = document.getElementById('btn-start-server-tab');
    if (btnStart) {
        btnStart.addEventListener('click', startServer);
    }
    if (btnStartTab) {
        btnStartTab.addEventListener('click', startServer);
    }
    // Start periodic check
    checkServerStatus();
    if (serverCheckInterval) clearInterval(serverCheckInterval);
    serverCheckInterval = setInterval(checkServerStatus, 10000);
}

async function checkServerStatus() {
    const statusEl = document.getElementById('server-status');
    const btnStart = document.getElementById('btn-start-server');
    
    try {
        await apiGet('/products', { silent: true });
        // Server is online
        if (statusEl) {
            statusEl.style.display = 'inline';
            statusEl.style.color = '#10B981';
            statusEl.textContent = '● متصل';
        }
        if (btnStart) btnStart.style.display = 'none';
        setConnectionState(true);
        return true;
    } catch (e) {
        // Server is offline
        if (statusEl) {
            statusEl.style.display = 'inline';
            statusEl.style.color = '#f87171';
            statusEl.textContent = '○ متوقف';
        }
        if (btnStart) btnStart.style.display = 'inline-block';
        if (firstLoadDone) setConnectionState(false, 'offline');
        return false;
    }
}

async function startServer() {
    const btnStart = document.getElementById('btn-start-server');
    if (serverStarting) return;

    serverStarting = true;
    if (btnStart) {
        btnStart.textContent = '⏳ جاري التشغيل...';
        btnStart.disabled = true;
    }
    showToast('بدء تشغيل نظام ERP عبر Native Host...', 'info', 4000);

    try {
        // Already running?
        if (await checkServerStatus()) {
            showToast('✅ النظام يعمل بالفعل!', 'success');
            serverStarting = false;
            if (btnStart) {
                btnStart.textContent = '🚀 تشغيل النظام';
                btnStart.disabled = false;
            }
            return;
        }

        // Send launch command via Native Messaging Host
        let launchResult = null;
        try {
            launchResult = await new Promise((resolve, reject) => {
                const timeout = setTimeout(() => reject(new Error('انتهت مهلة Native Host')), 45000);
                try {
                    chrome.runtime.sendNativeMessage(
                        'com.elnagar.pos.native_host',
                        { action: 'launch_erp' },
                        (response) => {
                            clearTimeout(timeout);
                            if (chrome.runtime.lastError) {
                                reject(new Error(chrome.runtime.lastError.message));
                            } else {
                                resolve(response);
                            }
                        }
                    );
                } catch (err) {
                    clearTimeout(timeout);
                    reject(err);
                }
            });
        } catch (nmError) {
            console.warn('Native Host error:', nmError);
            showToast('⚠️ Native Host غير مسجّل: ' + nmError.message, 'error', 6000);
            showToast('شغّل النظام يدويًا: G:\\ai\\Elnagar POS\\run_app.bat', 'info', 8000);
        }

        if (launchResult && launchResult.success) {
            showToast('✅ ' + (launchResult.message || 'تم تشغيل النظام'), 'success');
            await checkServerStatus();
            loadData(true);
        } else if (launchResult && !launchResult.success) {
            showToast('⚠️ ' + (launchResult.message || 'فشل التشغيل'), 'warn', 6000);
        }

        // Poll for API availability regardless (user may start it manually)
        for (let i = 0; i < 10; i++) {
            await new Promise(r => setTimeout(r, 2000));
            if (await checkServerStatus()) {
                showToast('✅ تم الاتصال بالنظام بنجاح!', 'success');
                loadData(true);
                serverStarting = false;
                if (btnStart) {
                    btnStart.textContent = '🚀 تشغيل النظام';
                    btnStart.disabled = false;
                }
                return;
            }
        }
        showToast('⚠️ لم يستجب النظام. شغّله يدويًا: run_app.bat', 'warn', 6000);
    } catch (e) {
        showToast('فشل التشغيل: ' + e.message, 'error');
    }

    if (btnStart) {
        btnStart.textContent = '🚀 تشغيل النظام';
        btnStart.disabled = false;
    }
    serverStarting = false;
}

// Update connection monitor to use server status
const originalSetConnectionState = setConnectionState;
setConnectionState = function(ok, why) {
    originalSetConnectionState(ok, why);
    // Additional server status indicator update
    const statusEl = document.getElementById('system-status');
    const btnStart = document.getElementById('btn-start-server');
    const btnStartTab = document.getElementById('btn-start-server-tab');
    if (ok) {
        if (statusEl) {
            statusEl.style.display = 'inline';
            statusEl.className = 'status-badge success';
            statusEl.textContent = '● متصل';
        }
        if (btnStart) btnStart.style.display = 'none';
        if (btnStartTab) btnStartTab.style.display = 'none';
    } else {
        if (statusEl) {
            statusEl.style.display = 'inline';
            statusEl.className = 'status-badge error';
            statusEl.textContent = '○ متوقف';
        }
        if (btnStart) btnStart.style.display = 'inline-block';
        if (btnStartTab) btnStartTab.style.display = 'inline-block';
    }
};
