const API_URL = "http://127.0.0.1:7777/api";

// State
let allProducts = [];
let allClients = [];
let allOrders = [];
let selectedImages = [];
let editingOrderId = null;
let allProductsFull = [];
let orderItems = [];

// --- Initialization ---
document.addEventListener('DOMContentLoaded', () => {
    loadData();
    setupTabs();
    setupListeners();
    setupDragDrop();
});

function setupTabs() {
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

            btn.classList.add('active');
            document.getElementById(btn.dataset.tab).classList.add('active');

            // Auto-load laser queue when switching to laser tab
            if (btn.dataset.tab === 'tab-laser') {
                loadLaserQueue();
            }
        });
    });
}

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
                    // Likely a phone number
                    if (!phone) phone = title;
                    title = ""; // Reset title so we don't put a phone number as name
                } else {
                    // Normalization logic for Egyptian numbers (simplification)
                    if (match = d.match(/20(1[0125]\d{8})/)) title = '0' + match[1];
                    else if (match = d.match(/(1[0125]\d{8})/)) title = '0' + match[1];
                }

                const nameEl = document.getElementById('client-name');
                const phoneEl = document.getElementById('client-phone');

                if (title) nameEl.value = title;
                if (phone) phoneEl.value = phone;

                // Lookup by Name first
                let found = false;
                if (title) {
                    try {
                        const res = await fetch(`${API_URL}/get_client_details`, {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ name: title })
                        });
                        const json = await res.json();

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

                // Visual feedback
                if (!found && phone) {
                    // If new client but phone found, flash phone
                    phoneEl.style.borderColor = '#10B981';
                }
                setTimeout(() => {
                    nameEl.style.borderColor = '';
                    phoneEl.style.borderColor = '';
                }, 2000);
            }
            // User requested NO images on this button (Fetch Data Only)
            // if (data && data.images && data.images.length > 0) {
            //    processIncomingImages(data.images);
            // }
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
                alert("لم يتم العثور على صور");
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
                document.getElementById('img-count').textContent = "0 صور";
            }
        });
    }

    // 3. Filters
    document.getElementById('product-filter')?.addEventListener('input', (e) => {
        // Legacy
    });

    document.getElementById('search-products').addEventListener('keyup', renderProductsGrid);
    document.getElementById('filter-category').addEventListener('change', renderProductsGrid);
    document.querySelectorAll('input[name="price_mode"]').forEach(r => {
        r.addEventListener('change', renderProductsGrid);
    });

    document.getElementById('search-clients').addEventListener('keyup', () => renderClients(allClients));
    document.getElementById('sort-clients').addEventListener('change', () => renderClients(allClients));
    document.getElementById('btn-refresh-orders').addEventListener('click', loadData);


    // 4. Form Actions
    const btnAddRow = document.getElementById('btn-add-row');
    if (btnAddRow) btnAddRow.addEventListener('click', () => addOrderItem());

    const clientTypeEl = document.getElementById('client-type');
    if (clientTypeEl) {
        clientTypeEl.addEventListener('change', () => {
            updateAllPricesForClientType();
        });
    }

    // Quick Add Product
    const btnSaveProd = document.getElementById('btn-save-new-prod');
    if (btnSaveProd) {
        btnSaveProd.addEventListener('click', async () => {
            const name = document.getElementById('new-product-name').value;
            const price_retail = document.getElementById('new-product-price-retail').value;
            const price_wholesale = document.getElementById('new-product-price-wholesale').value;
            const category = document.getElementById('new-product-cat').value; // Get Category
            
            if (!name) return alert("الاسم مطلوب");
            try {
                const res = await fetch(`${API_URL}/quick_add`, {
                    headers: { 'Content-Type': 'application/json' },
                    method: 'POST',
                    body: JSON.stringify({ 
                        type: 'product', 
                        name: name, 
                        price_retail: price_retail, 
                        price_wholesale: price_wholesale,
                        category: category 
                    })
                });
                const json = await res.json();
                if (json.success) {
                    loadData();
                    document.getElementById('new-product-group').style.display = 'none';
                    // Clear fields
                    document.getElementById('new-product-name').value = '';
                    document.getElementById('new-product-price-retail').value = '';
                    document.getElementById('new-product-price-wholesale').value = '';
                    document.getElementById('new-product-cat').value = '';
                    alert("تمت الإضافة!");
                } else {
                    alert(json.message);
                }
            } catch (e) { alert(e.message); }
        });
    }

    // Quick Add Category
    const btnAddCat = document.getElementById('btn-ext-add-cat');
    if (btnAddCat) {
        btnAddCat.addEventListener('click', async () => {
             const name = prompt("أدخل اسم التصنيف الجديد:");
             if(!name) return;
             try {
                const res = await fetch(`${API_URL}/quick_add`, {
                    headers: { 'Content-Type': 'application/json' },
                    method: 'POST',
                    body: JSON.stringify({ type: 'category', name: name })
                });
                const json = await res.json();
                if(json.success) {
                    loadData(); // Refresh lists
                     document.getElementById('new-product-cat').value = name;
                     alert("تم إضافة التصنيف!");
                } else {
                    alert(json.message);
                }
             } catch(e) { alert(e.message); }
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
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            const btn = e.target.querySelector('button[type="submit"]');
            const originalText = btn.textContent;
            btn.textContent = "جاري الحفظ...";
            btn.disabled = true;

            try {
                const formData = new FormData(e.target);
                const validItems = orderItems.filter(i => i.product_id || i.price > 0);
                if (validItems.length === 0) throw new Error("يجب اختيار منتج واحد على الأقل");

                // NEW: Build items_with_images - each item has its own images
                const itemsPayload = validItems.map((i, idx) => ({
                    id: i.product_id, 
                    qty: i.qty, 
                    price: i.price,
                    image_count: i.images ? i.images.length : 0,
                    item_index: idx  // Used to match images on backend
                }));
                formData.append('items', JSON.stringify(itemsPayload));

                // NEW: Append images with item index prefix for backend matching
                validItems.forEach((item, idx) => {
                    if (item.images && item.images.length > 0) {
                        item.images.forEach(file => {
                            formData.append(`images_${idx}`, file);
                        });
                    }
                });

                // Also append any global selectedImages (for backward compatibility)
                selectedImages.forEach(file => formData.append('images_global', file));

                let url = `${API_URL}/whatsapp_sync`;
                if (editingOrderId) {
                    url = `${API_URL}/update_order`;
                    formData.append('order_id', editingOrderId);
                }

                const res = await fetch(url, { method: 'POST', body: formData });
                const json = await res.json();

                if (json.success) {
                    alert(editingOrderId ? "تم تعديل الطلب" : "تم إنشاء الطلب " + json.order_id);
                    e.target.reset();
                    selectedImages = [];
                    orderItems = [];
                    addOrderItem();
                    renderImagePreview();
                    editingOrderId = null;
                    btn.style.background = "";
                    loadData();
                } else {
                    alert("خطأ: " + json.message);
                }
            } catch (err) {
                alert("خطأ: " + err.message);
            } finally {
                btn.textContent = originalText;
                btn.disabled = false;
            }
        });
    }

    // 5. Delegation
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
            document.getElementById('img-count').textContent = `${selectedImages.length} صور`;
        }
    });

    // Auto Client Info
    document.getElementById('client-name').addEventListener('input', (e) => {
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
            document.getElementById('last-order-info').style.display = 'none';
        }
    });
}

function setupDragDrop() {
    const imgArea = document.getElementById('image-preview-area');
    if (!imgArea) return;

    imgArea.addEventListener('dragover', (e) => { e.preventDefault(); imgArea.style.borderColor = '#10B981'; imgArea.style.background = '#ecfdf5'; });
    imgArea.addEventListener('dragleave', (e) => { e.preventDefault(); imgArea.style.borderColor = '#ccc'; imgArea.style.background = 'transparent'; });
    imgArea.addEventListener('drop', (e) => {
        e.preventDefault();
        imgArea.style.borderColor = '#ccc';
        imgArea.style.background = 'transparent';
        const files = Array.from(e.dataTransfer.files).filter(f => f.type.startsWith('image/'));
        if (files.length > 0) {
            if (selectedImages.length + files.length > 16) return alert("العدد الأقصى 16 صورة");
            selectedImages.push(...files);
            document.getElementById('img-count').textContent = `${selectedImages.length} صور`;
            renderImagePreview();
        }
    });
}

// --- Data Loading ---
async function loadData() {
    try {
        const [productsRes, clientsRes, ordersRes] = await Promise.all([
            fetch(`${API_URL}/products`),
            fetch(`${API_URL}/clients`),
            fetch(`${API_URL}/orders`)
        ]);

        const pJson = await productsRes.json();
        const cJson = await clientsRes.json();
        const oJson = await ordersRes.json();

        if (pJson.success) {
            allProducts = pJson.products;
            allProductsFull = allProducts; // Keep full list
        } else {
            allProducts = [];
            allProductsFull = [];
        }

        allClients = cJson.customers || [];
        allOrders = oJson.orders || [];

        renderClients(allClients);
        renderOrdersGrouped(allOrders); // Assuming renderOrdersGrouped is the correct function
        // renderProducts(); // This function is not defined in the provided context, commenting out.
        
        // Populate Laser Datalist
        const laserList = document.getElementById('laser-products-list');
        if (laserList) {
            laserList.innerHTML = allProducts.map(p => `<option value="${p.name}">`).join('');
        }
        
        populateClientDatalist(allClients);
        populateCategoryFilter(allProducts);
        loadCategoriesForExt(); // Load Datalist for adding product

        if (orderItems.length === 0) addOrderItem();
        else renderOrderRows();

    } catch (error) {
        console.error(error);
        const errDiv = document.createElement('div');
        errDiv.style.background = '#fee2e2';
        errDiv.style.color = 'red';
        errDiv.style.padding = '10px';
        errDiv.textContent = `خطأ في الاتصال: ${error.message}. تأكد من تشغيل البرنامج.`;
        document.body.prepend(errDiv);
    }
}

// --- Renderers ---
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
    const cats = [...new Set(products.map(p => p.category).filter(Boolean))];
    const sel = document.getElementById('filter-category');
    const currentVal = sel.value;
    sel.innerHTML = '<option value="">الكل</option>';
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
        const res = await fetch(`${API_URL}/get_categories`);
        const json = await res.json();
        if(json.success) {
            const list = document.getElementById('ext-cat-list');
            list.innerHTML = '';
            json.categories.forEach(c => {
                const opt = document.createElement('option');
                opt.value = c.name;
                list.appendChild(opt);
            });
        }
    } catch(e) { console.error(e); }
}

function getClientType() {
    return document.getElementById('client-type')?.value || 'Retail';
}

function renderOrdersGrouped(list) {
    const prep = document.getElementById('orders-prep');
    const ready = document.getElementById('orders-ready');
    const done = document.getElementById('orders-done');
    prep.innerHTML = ''; ready.innerHTML = ''; done.innerHTML = '';

    if (list.length === 0) {
        prep.innerHTML = '<div style="color:#999; text-align:center;">لا يوجد طلبات</div>';
        return;
    }

    list.forEach(o => {
        const div = document.createElement('div');
        div.className = 'card';
        div.innerHTML = `
            <div class="card-header">
                <span class="card-title">#${o.id} - ${o.client}</span>
                <div style="display:flex; gap:5px;">
                    <button class="btn-edit-order" data-id="${o.id}" style="border:none;background:none;cursor:pointer;">✏️</button>
                    <button class="btn-delete-order" data-id="${o.id}" style="border:none;background:none;cursor:pointer;">🗑️</button>
                </div>
            </div>
            <div class="card-subtitle" style="direction:ltr; text-align:right;">${o.date}</div>
            <div style="font-weight:bold; margin-top:5px;">${o.total}</div>
        `;
        const st = (o.status || '').toLowerCase();
        if (st.includes('prep') || st.includes('تجهيز')) prep.appendChild(div);
        else if (st.includes('ready') || st.includes('جاهز')) ready.appendChild(div);
        else done.appendChild(div);
    });
}

function renderClients(list) {
    const term = document.getElementById('search-clients').value.toLowerCase();
    const sortMode = document.getElementById('sort-clients').value;

    let filtered = list.filter(c => c.name.toLowerCase().includes(term) || (c.phone && c.phone.includes(term)));

    filtered.sort((a, b) => {
        if (sortMode === 'wholesale') return (a.type === 'Wholesale' && b.type !== 'Wholesale') ? -1 : 1;
        if (sortMode === 'retail') return (a.type === 'Retail' && b.type !== 'Retail') ? -1 : 1;
        if (sortMode === 'debt') return b.total_debt - a.total_debt;
        return a.name.localeCompare(b.name);
    });

    const container = document.getElementById('clients-list');
    container.innerHTML = '';
    if (filtered.length === 0) return container.innerHTML = '<div style="text-align:center;padding:20px;">لا يوجد عملاء</div>';

    filtered.forEach(c => {
        const div = document.createElement('div');
        div.className = 'card';
        div.innerHTML = `
            <div class="card-header">
                <span class="card-title">${c.name}</span>
                ${c.total_debt > 0 ? `<span class="debt-indicator">-${c.total_debt}</span>` : `<span style="color:#4caf50">0</span>`}
            </div>
            <div style="font-size:11px;color:#aaa;direction:ltr;text-align:right;">${c.phone || ''}</div>
            <div class="card-subtitle">
                <span>${c.type === 'Wholesale' ? '⭐️ جملة' : 'قطاعي'}</span>
                <span style="font-size:10px;">#${c.id}</span>
            </div>
            <div style="margin-top:8px;display:flex;gap:5px;">
                <button class="btn btn-sm btn-secondary btn-pay-debt" style="flex:1;" data-id="${c.id}">تسديد</button>
                <button class="btn btn-sm btn-delete-client" style="background:#fee2e2;color:#ef4444;" data-id="${c.id}" data-name="${c.name}">حذف</button>
            </div>
        `;
        container.appendChild(div);
    });
}

function renderProductsGrid() {
    const term = document.getElementById('search-products').value.toLowerCase();
    const cat = document.getElementById('filter-category').value;
    const mode = document.querySelector('input[name="price_mode"]:checked').value;

    const filtered = allProducts.filter(p => p.name.toLowerCase().includes(term) && (cat === '' || p.category === cat));
    const container = document.getElementById('products-grid');
    container.innerHTML = '';

    if (filtered.length === 0) return container.innerHTML = '<div style="padding:20px;text-align:center;">لا يوجد منتجات</div>';

    filtered.forEach(p => {
        const displayPrice = (mode === 'wholesale' && p.price_wholesale) ? p.price_wholesale : p.price;
        const div = document.createElement('div');
        div.className = 'card';
        div.innerHTML = `
            <div style="font-weight:bold;font-size:12px;">${p.name}</div>
            <div style="font-size:11px;color:var(--text-sub)">${p.category || 'بدون تصنيف'}</div>
            <div style="margin-top:5px;font-size:11px;display:flex;justify-content:space-between;">
                <span>${mode === 'retail' ? 'قطاعي' : 'جملة'}</span>
                <span style="font-weight:bold;color:#2563EB;">${displayPrice}</span>
            </div>
            <div style="margin-top:5px;"><span class="stock-badge">مخزون: ${p.stock}</span></div>
        `;
        container.appendChild(div);
    });
}

// --- Order Items ---
function addOrderItem(product = null) {
    const item = {
        _uid: Date.now() + Math.random(),
        product_id: product ? product.id : "",
        price: product ? (getClientType() === 'Wholesale' ? product.price_wholesale : product.price_retail) : 0,
        qty: 1,
        retail_price: product ? product.price_retail : 0,
        wholesale_price: product ? product.price_wholesale : 0,
        images: []  // NEW: صور هذا المنتج
    };
    orderItems.push(item);
    renderOrderRows();
}

// NEW: Assign current selected images to a specific product item
function assignImagesToItem(uid) {
    const item = orderItems.find(i => i._uid === uid);
    if (!item) return;
    if (selectedImages.length === 0) {
        alert("لا توجد صور محددة! اسحب الصور أولاً ثم اضغط هنا.");
        return;
    }
    // Append to existing images (don't replace)
    item.images = [...item.images, ...selectedImages];
    selectedImages = []; // Clear global selection
    renderImagePreview(); // Clear preview
    document.getElementById('img-count').textContent = "0 صور";
    renderOrderRows();
    alert(`✅ تم إرفاق ${item.images.length} صورة للمنتج`);
}

function removeOrderItem(uid) {
    orderItems = orderItems.filter(i => i._uid !== uid);
    renderOrderRows();
}

function updateItemProduct(uid, productId) {
    const item = orderItems.find(i => i._uid === uid);
    if (!item) return;
    const product = allProductsFull.find(p => p.id == productId);
    if (product) {
        item.product_id = product.id;
        item.retail_price = product.price_retail;
        item.wholesale_price = product.price_wholesale;
        item.price = getClientType() === 'Wholesale' ? item.wholesale_price : item.retail_price;
    }
    renderOrderRows();
}

function updateItemField(uid, field, value) {
    const item = orderItems.find(i => i._uid === uid);
    if (item) {
        item[field] = parseFloat(value) || 0;
        calculateTotal();
    }
}

function updateAllPricesForClientType() {
    const type = getClientType();
    orderItems.forEach(item => {
        if (item.product_id) item.price = type === 'Wholesale' ? item.wholesale_price : item.retail_price;
    });
    renderOrderRows();
}

function calculateTotal() {
    const total = orderItems.reduce((sum, item) => sum + (item.price * item.qty), 0);
    document.getElementById('total-amount').textContent = total.toFixed(2);
}

function renderOrderRows() {
    const container = document.getElementById('order-items-container');
    container.innerHTML = '';
    orderItems.forEach((item, idx) => {
        const div = document.createElement('div');
        div.className = 'order-row';
        div.style.cssText = 'display:flex;gap:5px;background:#fff;padding:8px;border:1px solid #eee;border-radius:5px;align-items:center;margin-bottom:5px;flex-wrap:wrap;';

        // Product Select
        const select = document.createElement('select');
        select.style.flex = '2';
        select.style.minWidth = '120px';
        select.innerHTML = '<option value="">اختر المنتج...</option>';
        allProductsFull.forEach(p => {
            const opt = document.createElement('option');
            opt.value = p.id;
            opt.textContent = p.name;
            if (p.id == item.product_id) opt.selected = true;
            select.appendChild(opt);
        });
        select.addEventListener('change', (e) => updateItemProduct(item._uid, e.target.value));

        // Qty Input
        const qtyInput = document.createElement('input');
        qtyInput.type = 'number';
        qtyInput.value = item.qty;
        qtyInput.style.width = '45px';
        qtyInput.addEventListener('input', (e) => updateItemField(item._uid, 'qty', e.target.value));

        // Price Input
        const priceInput = document.createElement('input');
        priceInput.type = 'number';
        priceInput.value = item.price;
        priceInput.style.width = '60px';
        priceInput.addEventListener('input', (e) => updateItemField(item._uid, 'price', e.target.value));

        // NEW: Image Button with Count
        const imgBtn = document.createElement('button');
        imgBtn.type = 'button';
        const imgCount = item.images ? item.images.length : 0;
        imgBtn.innerHTML = `📷 ${imgCount}`;
        imgBtn.title = 'اضغط لإرفاق الصور المحددة بهذا المنتج';
        imgBtn.style.cssText = `border:1px solid ${imgCount > 0 ? '#10B981' : '#ccc'};background:${imgCount > 0 ? '#ECFDF5' : '#f9f9f9'};cursor:pointer;padding:5px 8px;border-radius:5px;font-size:12px;`;
        imgBtn.addEventListener('click', () => assignImagesToItem(item._uid));

        // Delete Button
        const delBtn = document.createElement('button');
        delBtn.type = 'button';
        delBtn.textContent = '🗑️';
        delBtn.style.cssText = 'border:none;background:transparent;cursor:pointer;color:#ef4444;';
        delBtn.addEventListener('click', () => removeOrderItem(item._uid));

        div.append(select, qtyInput, priceInput, imgBtn, delBtn);
        container.appendChild(div);
    });
    calculateTotal();
}

// --- Action Helpers (Async) ---
async function deleteClient(id) {
    try {
        const res = await fetch(`${API_URL}/delete_client`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ client_id: id }) });
        if ((await res.json()).success) loadData();
    } catch (e) { alert("Error: " + e.message); }
}

async function deleteOrder(id) {
    try {
        const res = await fetch(`${API_URL}/delete_order`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ order_id: id }) });
        if ((await res.json()).success) loadData();
    } catch (e) { alert("Error: " + e.message); }
}

async function payDebt(id) {
    const amt = prompt("المبلغ:");
    if (!amt) return;
    try {
        const res = await fetch(`${API_URL}/pay_debt`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ client_id: id, amount: amt }) });
        if ((await res.json()).success) { alert("تم"); loadData(); }
    } catch (e) { alert("Error: " + e.message); }
}

async function editOrder(id) {
    try {
        const res = await fetch(`${API_URL}/get_order_details`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ order_id: id }) });
        const json = await res.json();
        if (json.success) {
            const { order, client, items } = json.data;
            document.querySelector('[data-tab="tab-start"]').click();
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
                        wholesale_price: i.price_wholesale || i.price
                    });
                });
            } else addOrderItem();

            renderOrderRows();
            editingOrderId = id;
            const btn = document.querySelector('#sync-form button[type="submit"]');
            btn.textContent = `حفظ التعديلات (طلب #${id})`;
            btn.style.background = "#F59E0B";
        }
    } catch (e) { alert("Edit Error: " + e.message); }
}

async function processIncomingImages(base64List) {
    if (!base64List || base64List.length === 0) return;

    // Limit total to 16
    const remainingSlots = 16 - selectedImages.length;
    if (remainingSlots <= 0) {
        alert("تم الوصول للحد الأقصى (16 صورة). يرجى مسح بعض الصور أولاً.");
        return;
    }

    // Take only what fits
    const addingList = base64List.slice(0, remainingSlots);

    document.getElementById('img-count').textContent = "جاري المعالجة...";

    try {
        for (const b64 of addingList) {
            try {
                // b64 should look like "data:image/jpeg;base64,..."
                const res = await fetch(b64);
                const blob = await res.blob();

                const type = blob.type.startsWith('image/') ? blob.type : "image/jpeg";
                const file = new File([blob], `img_${Date.now()}_${Math.random().toString(36).substr(2, 5)}.jpg`, { type: type });

                // SAVE PREVIEW DIRECTLY to avoid ObjectURL issues
                file._preview = b64;

                selectedImages.push(file);
            } catch (err) {
                console.error("Error processing blob:", err);
            }
        }
    } finally {
        renderImagePreview();
        document.getElementById('img-count').textContent = `${selectedImages.length} صور`;
    }
}

async function sendMessageToContent(payload) {
    const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
    if (tabs[0] && tabs[0].url.includes("whatsapp.com")) {
        try {
            return await chrome.tabs.sendMessage(tabs[0].id, payload);
        } catch (e) {
            console.warn(e);
            alert("يرجى تحديث صفحة واتساب أولاً!");
            return null;
        }
    } else {
        alert("يرجى فتح واتساب ويب أولاً");
    }
}

function renderImagePreview() {
    const area = document.getElementById('image-preview-area');
    area.innerHTML = '';

    if (selectedImages.length === 0) {
        // Optional: placeholder
    }

    selectedImages.forEach((file, idx) => {
        const img = document.createElement('img');

        // Use direct base64 if available (Robustness)
        if (file._preview) {
            img.src = file._preview;
        } else {
            img.src = URL.createObjectURL(file);
        }

        const removeBtn = document.createElement('button');
        removeBtn.className = 'img-remove-btn';
        removeBtn.dataset.idx = idx;
        removeBtn.textContent = 'x';
        
        const div = document.createElement('div');
        div.style.position = 'relative'; 
        // Thumbnail Styles
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
    
    // Clear previous
    infoDiv.style.display = 'none';
    itemsList.innerHTML = '';
    
    if (!client || !client.id) return;

    try {
        const res = await fetch(`${API_URL}/get_client_last_order`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ client_id: client.id })
        });
        const json = await res.json();
        
        if (json.success && json.order) {
            const o = json.order;
            // Only show if there are items or meaningful info
            infoDiv.style.display = 'block';
            
            // Format Date safely
            let safeDate = o.date;
            try { 
                const d = new Date(o.date); 
                if(!isNaN(d)) safeDate = d.toLocaleDateString('ar-EG');
            } catch(e){}
            
            dateSpan.textContent = safeDate;

            // Add Balance Info (New Request)
            const oldBal = document.getElementById('last-order-bal-display');
            if(oldBal) oldBal.remove();
            
            const balDiv = document.createElement('div');
            balDiv.id = 'last-order-bal-display';
            balDiv.style.marginTop = '4px';
            balDiv.style.fontSize = '0.9em';
            let debt = client.total_debt || 0;
            balDiv.innerHTML = `الرصيد: <span style="font-weight:bold; color:${debt > 0 ? '#EF4444' : '#10B981'}">${debt}</span>`;
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

// ═══════════════════════════════════════════════════════════════════
// 🔴 LASER OPS CENTER
// ═══════════════════════════════════════════════════════════════════

// ═══════════════════════════════════════════════════════════════════
// 🔴 LASER OPS CENTER
// ═══════════════════════════════════════════════════════════════════

async function loadLaserQueue() {
    const queueList = document.getElementById('laser-queue-list');
    const manualDatalist = document.getElementById('laser-products-list');
    const defectSelect = document.getElementById('defect-product-select');
    
    if (!queueList) return;

    queueList.innerHTML = '<div style="text-align:center; padding:10px; color:#999;">جاري التحميل...</div>';
    
    try {
        // Fetch aggregated products (NOW FILTERED by 'Under Preparation')
        const res = await fetch(`${API_URL}/laser_queue`);
        const data = await res.json();

        // Clear Lists
        queueList.innerHTML = '';
        if (manualDatalist) manualDatalist.innerHTML = '';
        if (defectSelect) defectSelect.innerHTML = '<option value="">اختر المنتج الناقص...</option>';

        if (data.aggregated && data.aggregated.length > 0) {
            data.aggregated.forEach(item => {
                // 1. Render Queue Item
                const card = document.createElement('div');
                card.className = 'order-card';
                card.style.cssText = 'display:flex; justify-content:space-between; align-items:center; padding:8px 10px; border-bottom:1px solid #eee; background:white; border-radius:4px;';
                card.innerHTML = `
                    <div style="display:flex; flex-direction:column;">
                        <span style="font-weight:bold; font-size:12px; color:#333;">${item.product_name}</span>
                        <span style="font-size:10px; color:#666;">${item.order_count || 0} طلبات</span>
                    </div>
                    <span style="background:#DC2626; color:white; padding:2px 8px; border-radius:12px; font-weight:bold; font-size:12px;">
                        ${item.total_qty}
                    </span>
                `;
                queueList.appendChild(card);

                // 2. Populate Manual Datalist
                if (manualDatalist) {
                    const opt = document.createElement('option');
                    opt.value = item.product_name;
                    manualDatalist.appendChild(opt);
                }

                // 3. Populate Defect Dropdown
                if (defectSelect) {
                    const opt = document.createElement('option');
                    opt.value = item.product_name;
                    opt.textContent = `${item.product_name} (متبقي: ${item.total_qty})`;
                    defectSelect.appendChild(opt);
                }
            });
        } else {
            queueList.innerHTML = '<div style="text-align:center; padding:20px; color:#10B981;">✅ لا يوجد طلبات تحت التجهيز</div>';
        }
        
    } catch (e) {
        console.error('Laser queue error:', e);
        queueList.innerHTML = '<div style="text-align:center; padding:10px; color:#ef4444;">خطأ في الاتصال</div>';
    }
}

// --- SUB TABS LOGIC ---
document.addEventListener('DOMContentLoaded', () => {
    const subListBtn = document.getElementById('subtab-laser-list');
    const subDefectBtn = document.getElementById('subtab-laser-defect');
    const viewList = document.getElementById('view-laser-list');
    const viewDefect = document.getElementById('view-laser-defect');

    if (subListBtn && subDefectBtn) {
        subListBtn.addEventListener('click', () => {
            subListBtn.classList.add('active');
            subDefectBtn.classList.remove('active');
            viewList.style.display = 'block';
            viewDefect.style.display = 'none';
        });

        subDefectBtn.addEventListener('click', () => {
            subDefectBtn.classList.add('active');
            subListBtn.classList.remove('active');
            viewList.style.display = 'none';
            viewDefect.style.display = 'block';
        });
    }

    // Refresh Button
    const btnRefresh = document.getElementById('btn-refresh-laser');
    if (btnRefresh) btnRefresh.addEventListener('click', loadLaserQueue);

    // Initial Load if on Laser Tab (handled by main tab switcher)
    
    // --- DEFECT REPORT LOGIC ---
    setupDefectReporting();
    setupManualLaserTask(); // Existing logic refactored below
});

function setupDefectReporting() {
    const btnSend = document.getElementById('btn-send-defect');
    const productSelect = document.getElementById('defect-product-select');
    const notesInput = document.getElementById('defect-notes');
    const dropZone = document.getElementById('defect-drop-zone');
    const previewContainer = document.getElementById('defect-preview-container');
    
    let defectFile = null;

    // Paste / Drop Logic for Defect
    if (dropZone) {
       dropZone.addEventListener('paste', handlePaste); // Global paste might need focus? No, usually element based.
       // Actually paste works on document usually, but let's try focused element or click to focus.
       // For simplicity, click to browse or drag drop.
       dropZone.addEventListener('click', () => {
           // Create temp input
           const input = document.createElement('input');
           input.type = 'file';
           input.accept = 'image/*';
           input.onchange = e => {
               if(e.target.files[0]) handleDefectFile(e.target.files[0]);
           };
           input.click();
       });
       
       document.addEventListener('paste', e => {
           // Only if defect tab is visible
           if (document.getElementById('view-laser-defect').style.display === 'none') return;
           if (e.clipboardData && e.clipboardData.files.length > 0) {
               handleDefectFile(e.clipboardData.files[0]);
               e.preventDefault();
           }
       });
    }

    function handleDefectFile(file) {
        if (!file.type.startsWith('image/')) return;
        defectFile = file;
        const reader = new FileReader();
        reader.onload = e => {
            previewContainer.innerHTML = `<img src="${e.target.result}" style="max-height:80px; border-radius:4px;">`;
        };
        reader.readAsDataURL(file);
    }

    if (btnSend) {
        btnSend.addEventListener('click', async () => {
             const productName = productSelect.value;
             if (!productName) {
                 alert("يرجى اختيار المنتج الناقص!");
                 return;
             }
             
             btnSend.disabled = true;
             btnSend.textContent = "جاري الإرسال...";
             
             try {
                 let b64 = null;
                 if (defectFile) {
                    const reader = new FileReader();
                    b64 = await new Promise(resolve => {
                        reader.onload = e => resolve(e.target.result);
                        reader.readAsDataURL(defectFile);
                    });
                 }
                 
                 const payload = {
                     product_name: productName,
                     notes: notesInput.value,
                     image_base64: b64
                 };
                 
                 const res = await fetch(`${API_URL}/upload_defect`, {
                     method: 'POST',
                     headers: {'Content-Type': 'application/json'},
                     body: JSON.stringify(payload)
                 });
                 const json = await res.json();
                 
                 if (json.success) {
                     alert("✅ تم إرسال البلاغ لقسم الليزر");
                     // Reset
                     productSelect.value = "";
                     notesInput.value = "";
                     previewContainer.innerHTML = "";
                     defectFile = null;
                     // Switch to List?
                 } else {
                     alert("خطأ: " + json.message);
                 }
             } catch (e) {
                 console.error(e);
                 alert("فشل الاتصال");
             } finally {
                 btnSend.disabled = false;
                 btnSend.textContent = "🚀 إرسال بلاغ عاجل";
             }
        });
    }
}

function setupManualLaserTask() {
    const addBtn = document.getElementById('btn-add-laser-task');
    const noteInput = document.getElementById('laser-manual-note');
    const pieceInput = document.getElementById('laser-piece-type');
    const dropZone = document.getElementById('laser-drop-zone');
    const previewContainer = document.getElementById('laser-preview-container');
    const fileInput = document.getElementById('laser-upload-input');
    
    let manualFile = null;

    if (!addBtn) return;

    // File Handling
    if(dropZone) {
        dropZone.addEventListener('click', () => fileInput.click());
        fileInput.addEventListener('change', e => {
            if(e.target.files[0]) handleManualFile(e.target.files[0]);
        });
        document.addEventListener('paste', e => {
           if (document.getElementById('view-laser-list').style.display === 'none') return;
           if (e.clipboardData && e.clipboardData.files.length > 0) {
               handleManualFile(e.clipboardData.files[0]);
               e.preventDefault();
           }
        });
    }

    function handleManualFile(file) {
        if (!file.type.startsWith('image/')) return;
        manualFile = file;
        const reader = new FileReader();
        reader.onload = e => {
            previewContainer.innerHTML = `<img src="${e.target.result}" style="max-height:80px; border-radius:4px;">`;
        };
        reader.readAsDataURL(file);
    }

    addBtn.addEventListener('click', async () => {
        const note = noteInput.value.trim();
        const product = pieceInput.value.trim();
        
        if (!note && !manualFile && !product) {
            alert("أدخل بيانات!");
            return;
        }

        // Combine logic: Note = [Product] + Manual Note
        let finalNote = note;
        if (product) finalNote = `[${product}] ${note}`;

        const formData = new FormData();
        formData.append('notes', finalNote);
        formData.append('type', 'manual');
        if (manualFile) formData.append('image', manualFile);

        addBtn.disabled = true;
        addBtn.textContent = '...';

        try {
            const res = await fetch(`${API_URL}/laser_queue/upload`, {
                method: 'POST',
                body: formData
            });
            const data = await res.json();
            if (data.success) {
                alert("✅ تم الإرسال");
                noteInput.value = '';
                pieceInput.value = '';
                manualFile = null;
                previewContainer.innerHTML = '';
            } else {
                alert("خطأ: " + data.message);
            }
        } catch (e) {
            alert("فشل الاتصال");
        } finally {
            addBtn.disabled = false;
            addBtn.textContent = "إرسال للمعمل 🚀";
        }
    }); 
}
