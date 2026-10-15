// Mobile App JavaScript

// ========== API CONFIGURATION ==========
// Auto-detect if running on Eel or Flask
const API_BASE = window.eel ? '' : (window.location.origin || '');
const USE_EEL = typeof window.eel !== 'undefined';

// API Helper - works with both Eel and Flask
async function apiCall(endpoint, data = null) {
    if (USE_EEL) {
        // Use Eel for desktop
        try {
            return await window.eel[endpoint](data)();
        } catch(e) {
            console.error('Eel call failed:', e);
            throw e;
        }
    } else {
        // Use Flask API for mobile
        const url = `${API_BASE}/api/mobile/${endpoint}`;
        const options = {
            method: data ? 'POST' : 'GET',
            headers: { 'Content-Type': 'application/json' }
        };
        if (data) options.body = JSON.stringify(data);
        
        const response = await fetch(url, options);
        return await response.json();
    }
}

// ========== STATE ==========
let currentUser = null;
let currentPage = 'orders';
let currentOrderTab = 'prep';
let allOrders = { prep: [], ready: [], done: [] };
let allProducts = [];
let allClients = [];
let cart = [];
let selectedClient = null;

// ========== INITIALIZATION ==========
document.addEventListener('DOMContentLoaded', async () => {
    // Check for stored session
    const stored = localStorage.getItem('mobile_user');
    if (stored) {
        currentUser = JSON.parse(stored);
        showApp();
    }
});

// ========== LOGIN ==========
let pin = '';

function enterPin(digit) {
    if (pin.length >= 4) return;
    pin += digit;
    updatePinDisplay();
    
    if (pin.length === 4) {
        attemptLogin();
    }
}

function deletePin() {
    pin = pin.slice(0, -1);
    updatePinDisplay();
}

function updatePinDisplay() {
    const dots = document.querySelectorAll('.pin-display .dot');
    dots.forEach((dot, i) => {
        dot.classList.toggle('filled', i < pin.length);
    });
}

async function attemptLogin() {
    const errorMsg = document.getElementById('login-error');
    errorMsg.textContent = 'جاري الاتصال...';
    errorMsg.style.color = '#3B82F6'; // Blue text for status
    
    try {
        let result;
        
        if (USE_EEL) {
            result = await eel.py_mobile_login(pin)();
        } else {
            // Use Flask API
            const response = await fetch(`${API_BASE}/api/mobile/login`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ pin: pin })
            });
            if (!response.ok) {
                throw new Error(`HTTP Error: ${response.status}`);
            }
            result = await response.json();
        }
        
        if (result.success) {
            currentUser = result.staff;
            localStorage.setItem('mobile_user', JSON.stringify(currentUser));
            showApp();
        } else {
            errorMsg.style.color = 'var(--danger)';
            errorMsg.textContent = result.error || 'رمز خاطئ';
            pin = '';
            updatePinDisplay();
            
            // Shake animation
            const keypad = document.querySelector('.keypad');
            keypad.style.animation = 'shake 0.3s';
            setTimeout(() => keypad.style.animation = '', 300);
        }
    } catch (e) {
        console.error(e);
        errorMsg.style.color = 'var(--danger)';
        errorMsg.textContent = 'فشل الاتصال بالسيرفر. تأكد من تشغيل البرنامج على الكمبيوتر والاتصال بنفس الشبكة.';
        pin = '';
        updatePinDisplay();
    }
}

function logout() {
    localStorage.removeItem('mobile_user');
    currentUser = null;
    pin = '';
    updatePinDisplay();
    document.getElementById('login-screen').classList.add('active');
    document.getElementById('app-screen').classList.remove('active');
}

// ========== APP NAVIGATION ==========
function showApp() {
    document.getElementById('login-screen').classList.remove('active');
    document.getElementById('app-screen').classList.add('active');
    
    // Update header
    const initials = currentUser.name ? currentUser.name.charAt(0).toUpperCase() : '?';
    document.getElementById('header-avatar').textContent = initials;
    document.getElementById('header-name').textContent = currentUser.name;
    document.getElementById('header-role').textContent = currentUser.role;
    
    // Load initial data
    loadOrders();
    loadProducts();
    loadClients();
}

function navigateTo(page) {
    currentPage = page;
    
    // Update nav buttons
    document.querySelectorAll('.nav-item').forEach(btn => btn.classList.remove('active'));
    document.querySelector(`.nav-item[onclick="navigateTo('${page}')"]`).classList.add('active');
    
    // Update pages
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    document.getElementById(`page-${page}`).classList.add('active');
    
    // Load page-specific data
    if (page === 'orders') loadOrders();
    if (page === 'products') loadProducts();
    if (page === 'profile') loadProfile();
}

// ========== ORDERS ==========
async function loadOrders() {
    try {
        if (USE_EEL) {
            allOrders = await eel.py_get_orders_mobile()();
        } else {
            const response = await fetch(`${API_BASE}/api/mobile/orders`);
            allOrders = await response.json();
        }
        
        // Update badges
        document.getElementById('badge-prep').textContent = allOrders.prep.length;
        document.getElementById('badge-ready').textContent = allOrders.ready.length;
        document.getElementById('badge-done').textContent = allOrders.done.length;
        
        renderOrders();
    } catch (e) {
        console.error('Failed to load orders:', e);
    }
}

function switchOrderTab(tab) {
    currentOrderTab = tab;
    
    document.querySelectorAll('.tabs-container .tab').forEach(t => t.classList.remove('active'));
    document.querySelector(`.tab[data-tab="${tab}"]`).classList.add('active');
    
    renderOrders();
}

function renderOrders() {
    const list = document.getElementById('orders-list');
    const orders = allOrders[currentOrderTab] || [];
    
    if (orders.length === 0) {
        list.innerHTML = '<p style="text-align:center; color:var(--text-muted); padding:40px;">لا توجد طلبات</p>';
        return;
    }
    
    list.innerHTML = orders.map(order => {
        // Build items list
        let itemsHtml = '';
        if (order.items && order.items.length > 0) {
            itemsHtml = order.items.map(i => `
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px; border-bottom:1px solid rgba(255,255,255,0.1); padding-bottom:4px;">
                    <span style="font-size:15px; font-weight:800; color:#eff6ff;">${i.product_name} <span style="font-size:13px; font-weight:normal; color:#cbd5e1;">(x${i.qty})</span></span>
                    <span style="font-weight:bold; color:#fbbf24; font-size:14px;">${i.total}</span>
                </div>
            `).join('');
        } else {
            itemsHtml = `<div style="color:var(--text-secondary); font-style:italic;">${order.items_summary || order.notes || 'بدون تفاصيل'}</div>`;
        }

        const date = order.date ? new Date(order.date).toLocaleString('ar-EG') : '';
        
        let actions = '';
        if (currentOrderTab === 'prep') {
            actions = '<button class="btn-action ready" onclick="updateOrderStatus(' + order.id + ', \'Ready\')">جاهز ✓</button>';
        } else if (currentOrderTab === 'ready') {
            actions = '<button class="btn-action deliver" onclick="updateOrderStatus(' + order.id + ', \'Delivered\')">تم التسليم 🚀</button>';
        }
        
        return `
            <div class="order-card" onclick="showOrderDetails(${order.id})" style="cursor:pointer;">
                <div class="order-header">
                    <span class="order-id">#${order.id}</span>
                    <span class="order-time">${date}</span>
                </div>
                <div class="order-client">${order.client_name || 'عميل نقدي'}</div>
                <div class="order-items" style="margin-top:8px;">${itemsHtml}</div>
                <div class="order-footer">
                    <span class="order-total">${order.total_amount || 0} ج.م</span>
                    <div class="order-actions" onclick="event.stopPropagation();">${actions}</div>
                </div>
            </div>
        `;
    }).join('');
}

async function updateOrderStatus(orderId, newStatus) {
    try {
        await eel.py_update_order_status(orderId, newStatus, 0, null)();
        loadOrders();
    } catch (e) {
        console.error('Failed to update order:', e);
    }
}

// ========== PRODUCTS ==========
async function loadProducts() {
    try {
        if (USE_EEL) {
            allProducts = await eel.py_get_products_mobile()();
        } else {
            const response = await fetch(`${API_BASE}/api/mobile/products`);
            allProducts = await response.json();
        }
        renderProducts(allProducts);
    } catch (e) {
        console.error('Failed to load products:', e);
    }
}

function renderProducts(products) {
    const grid = document.getElementById('products-grid');
    
    if (!products || products.length === 0) {
        grid.innerHTML = '<p style="text-align:center; color:var(--text-muted); padding:40px; grid-column:1/-1;">لا توجد منتجات</p>';
        return;
    }
    
    grid.innerHTML = products.map(p => {
        const price = p.price_retail !== undefined ? p.price_retail : (p.retail_price || 0);
        const stock = p.stock_qty !== undefined ? p.stock_qty : (p.stock || 0);
        const stockClass = stock < 5 ? 'color:var(--danger)' : '';
        
        return `
            <div class="product-card" onclick="addToCart(${p.id})">
                <div class="product-img">
                    ${p.image_path ? `<img src="${p.image_path}" alt="${p.name}">` : '📦'}
                </div>
                <div class="product-info">
                    <div class="product-name">${p.name}</div>
                    <div class="product-price">${price} ج.م</div>
                    <div class="product-stock" style="${stockClass}">المخزون: ${stock}</div>
                </div>
            </div>
        `;
    }).join('');
}

function filterProducts(query) {
    const filtered = allProducts.filter(p => 
        p.name.toLowerCase().includes(query.toLowerCase()) ||
        (p.category && p.category.toLowerCase().includes(query.toLowerCase()))
    );
    renderProducts(filtered);
}

// ========== POS / NEW ORDER ==========
async function loadClients() {
    try {
        if (USE_EEL) {
            allClients = await eel.py_get_clients()();
        } else {
            const response = await fetch(`${API_BASE}/api/mobile/clients`);
            allClients = await response.json();
        }
    } catch (e) {
        console.error('Failed to load clients:', e);
    }
}

function searchClients(query) {
    const results = document.getElementById('client-results');
    
    if (!query || query.length < 2) {
        results.classList.remove('show');
        return;
    }
    
    const filtered = allClients.filter(c => 
        c.name.toLowerCase().includes(query.toLowerCase()) ||
        (c.phone && c.phone.includes(query))
    ).slice(0, 5);
    
    if (filtered.length === 0) {
        results.classList.remove('show');
        return;
    }
    
    results.innerHTML = filtered.map(c => `
        <div class="dropdown-item" onclick="selectClient(${c.id})">
            <strong>${c.name}</strong> - ${c.phone || ''}
        </div>
    `).join('');
    results.classList.add('show');
}

function selectClient(clientId) {
    const client = allClients.find(c => c.id === clientId);
    if (!client) return;
    
    selectedClient = client;
    document.getElementById('client-results').classList.remove('show');
    document.getElementById('pos-client-search').value = '';
    
    const display = document.getElementById('selected-client');
    display.style.display = 'flex';
    display.innerHTML = `
        <span>${client.name}</span>
        <button onclick="clearClient()">×</button>
    `;
}

function clearClient() {
    selectedClient = null;
    document.getElementById('selected-client').style.display = 'none';
}

// Improved Product Search
async function searchProducts(query) {
    const results = document.getElementById('product-results');
    
    // Ensure products are loaded
    if (allProducts.length === 0) {
        await loadProducts();
    }
    
    if (!query) {
        results.classList.remove('show');
        return;
    }
    
    const filtered = allProducts.filter(p => 
        p.name.toLowerCase().includes(query.toLowerCase())
    ).slice(0, 10);
    
    results.innerHTML = filtered.map(p => `
        <div class="dropdown-item" onclick="addToCart(${p.id})">
            <div>
                <strong>${p.name}</strong>
                <div style="font-size:0.8em; color:#888;">${p.price_retail || p.retail_price} ج.م | المخزون: ${p.stock || p.stock_qty}</div>
            </div>
            <i class="fa-solid fa-plus-circle"></i>
        </div>
    `).join('');
    
    if (filtered.length > 0) {
        results.classList.add('show');
    } else {
        results.classList.remove('show');
    }
}
    


function addToCart(productId) {
    const product = allProducts.find(p => p.id === productId);
    if (!product) return;
    
    document.getElementById('product-results').classList.remove('show');
    document.getElementById('pos-product-search').value = '';
    
    // Check if already in cart
    const existing = cart.find(item => item.id === productId);
    if (existing) {
        existing.qty++;
    } else {
        cart.push({
            id: product.id,
            name: product.name,
            price: product.retail_price || 0,
            qty: 1
        });
    }
    
    renderCart();
}

function renderCart() {
    const container = document.getElementById('cart-items');
    
    if (cart.length === 0) {
        container.innerHTML = '<p class="empty-cart">السلة فارغة</p>';
        document.getElementById('cart-subtotal').textContent = '0';
        document.getElementById('cart-total').textContent = '0';
        return;
    }
    
    container.innerHTML = cart.map((item, idx) => `
        <div class="cart-item">
            <div>
                <strong>${item.name}</strong>
                <div style="color:var(--text-muted); font-size:12px;">${item.price} × ${item.qty}</div>
            </div>
            <div style="display:flex; align-items:center; gap:10px;">
                <span style="font-weight:bold;">${item.price * item.qty}</span>
                <button onclick="removeFromCart(${idx})" style="background:var(--danger); color:white; border:none; width:25px; height:25px; border-radius:5px; cursor:pointer;">×</button>
            </div>
        </div>
    `).join('');
    
    updateCartTotal();
}

function removeFromCart(index) {
    cart.splice(index, 1);
    renderCart();
}

function updateCartTotal() {
    const subtotal = cart.reduce((sum, item) => sum + (item.price * item.qty), 0);
    const discount = parseFloat(document.getElementById('cart-discount').value) || 0;
    const total = subtotal - discount;
    
    document.getElementById('cart-subtotal').textContent = subtotal;
    document.getElementById('cart-total').textContent = total;
}

async function saveOrder() {
    if (cart.length === 0) {
        alert('السلة فارغة');
        return;
    }
    
    const discount = parseFloat(document.getElementById('cart-discount').value) || 0;
    const subtotal = cart.reduce((sum, item) => sum + (item.price * item.qty), 0);
    
    const orderData = {
        client_id: selectedClient ? selectedClient.id : null,
        client_name: selectedClient ? selectedClient.name : 'عميل نقدي',
        items: cart,
        items_summary: cart.map(i => `${i.name} x${i.qty}`).join(', '),
        discount: discount,
        subtotal: subtotal,
        total: subtotal - discount,
        paid: 0,
        status: 'Under Preparation',
        payment_method: 'Cash',
        created_by: currentUser ? currentUser.id : null
    };
    
    try {
        // Try to save directly first
        await eel.py_save_order(orderData)();
        
        // Clear cart
        clearCart();
        showSyncToast('✅ تم حفظ الطلب بنجاح', 'success');
        navigateTo('orders');
        
    } catch (e) {
        console.log('Server unreachable, saving to offline queue');
        
        // Save to offline queue
        if (window.OfflineQueue) {
            await window.OfflineQueue.add(window.OfflineQueue.STORES.orders, { data: orderData });
            clearCart();
            showSyncToast('📦 تم حفظ الطلب (في انتظار المزامنة)', 'info');
            navigateTo('orders');
        } else {
            alert('خطأ في حفظ الطلب');
        }
    }
}

function clearCart() {
    cart = [];
    selectedClient = null;
    document.getElementById('cart-discount').value = 0;
    document.getElementById('selected-client').style.display = 'none';
    renderCart();
}

// ========== SYNC ==========
async function manualSync() {
    if (!window.OfflineQueue) return;
    
    const btn = document.querySelector('.sync-btn i');
    btn.classList.add('fa-spin');
    
    try {
        const result = await window.OfflineQueue.sync();
        
        if (result.success && result.synced > 0) {
            showSyncToast(`✅ تم مزامنة ${result.synced} عناصر`, 'success');
            loadOrders(); // Refresh orders list
        } else if (result.synced === 0) {
            showSyncToast('لا توجد عناصر للمزامنة', 'info');
        }
    } catch (e) {
        showSyncToast('❌ فشل في المزامنة', 'error');
    }
    
    btn.classList.remove('fa-spin');
}

// ========== PROFILE ==========
async function loadProfile() {
    if (!currentUser) return;
    
    const initials = currentUser.name ? currentUser.name.charAt(0).toUpperCase() : '?';
    document.getElementById('profile-avatar').textContent = initials;
    document.getElementById('profile-name').textContent = currentUser.name;
    document.getElementById('profile-role').textContent = currentUser.role;
    
    try {
        const stats = await eel.py_get_employee_stats(currentUser.id)();
        document.getElementById('stat-days').textContent = stats.days_present || 0;
        document.getElementById('stat-late').textContent = stats.late_count || 0;
        document.getElementById('stat-orders').textContent = stats.orders_count || 0;
        document.getElementById('stat-comm').textContent = stats.commission_earned || 0;
    } catch (e) {
        console.error('Failed to load stats:', e);
    }
}

async function checkInOut(action) {
    if (!currentUser) return;
    
    try {
        if (USE_EEL) {
            await eel.py_log_attendance(currentUser.id, action)();
        } else {
            // Flask API Support for Attendance (Add to app.py later if needed or via queue)
            // For now simple offline support
             if (window.OfflineQueue) {
                 await window.OfflineQueue.add(window.OfflineQueue.STORES.attendance, { 
                     staff_id: currentUser.id, 
                     action: action 
                 });
             }
        }
        alert(action === 'check_in' ? 'تم تسجيل الحضور ✓' : 'تم تسجيل الانصراف ✓');
        loadProfile();
    } catch (e) {
        console.error('Failed to log attendance:', e);
        alert('خطأ في التسجيل');
    }
}

// ========== CSS Animation ==========
const style = document.createElement('style');
style.textContent = `
    @keyframes shake {
        0%, 100% { transform: translateX(0); }
        25% { transform: translateX(-10px); }
        75% { transform: translateX(10px); }
    }
`;
document.head.appendChild(style);

// ========== MODALS ==========
function openNewClientModal() {
    document.getElementById('new-client-name').value = '';
    document.getElementById('new-client-phone').value = '';
    document.getElementById('modal-client').classList.add('active');
}

function closeModal(modalId) {
    document.getElementById(modalId).classList.remove('active');
}

async function saveNewClient() {
    const name = document.getElementById('new-client-name').value;
    const phone = document.getElementById('new-client-phone').value;
    
    if (!name) {
        alert('الاسم مطلوب');
        return;
    }
    
    try {
        let result;
        if (USE_EEL) {
            result = await eel.py_add_client(name, phone, 'Retail', 'Added from Mobile')();
        } else {
            // Use Flask Quick Add
            const response = await fetch(`${API_BASE}/api/quick_add`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    type: 'client',
                    name: name,
                    phone: phone,
                    client_type: 'Retail'
                })
            });
            result = await response.json();
        }
        
        if (result.success) {
            // Add to local list and select
            const newClient = { id: result.id, name: name, phone: phone };
            allClients.push(newClient);
            selectClient(newClient.id);
            
            closeModal('modal-client');
            alert('تم إضافة العميل بنجاح');
        } else {
            alert('فشل إضافة العميل: ' + (result.message || result.error));
        }
    } catch (e) {
        console.error('Add Client Error:', e);
        // Offline support
        if (window.OfflineQueue) {
            const tempId = 'temp_' + Date.now();
            const offlineClient = { id: tempId, name: name, phone: phone, type: 'Retail', notes: 'Offline Mobile', data: { name, phone, type: 'Retail' } };
            
            await window.OfflineQueue.add(window.OfflineQueue.STORES.clients, offlineClient);
            
            allClients.push(offlineClient);
            selectClient(tempId);
            
            closeModal('modal-client');
            showSyncToast('تم إضافة العميل (Offline)', 'info');
        } else {
            alert('خطأ في الاتصال');
        }
    }
}

// ========== CLIENTS PAGE ==========
function renderClientsPage(clients) {
    const list = document.getElementById('clients-list-page');
    if (!clients || clients.length === 0) {
        list.innerHTML = '<p style="text-align:center; padding:20px;">لا يوجد عملاء</p>';
        return;
    }
    
    list.innerHTML = clients.map(c => {
        const bal = c.balance || 0;
        let balClass = 'bg-gray';
        let balText = '0';
        
        if (bal > 0) { balClass = 'bg-red'; balText = `مدين: ${bal}`; }
        else if (bal < 0) { balClass = 'bg-green'; balText = `دائن: ${Math.abs(bal)}`; }
        
        return `
            <div class="client-card" onclick="openClientStatementMobile(${c.id})">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <div>
                        <div style="font-weight:bold;">${c.name}</div>
                        <div style="font-size:12px; color:var(--text-secondary);">${c.phone || '-'}</div>
                    </div>
                    <div class="client-balance ${balClass}">${balText}</div>
                </div>
                <div style="margin-top:10px; padding-top:10px; border-top:1px solid rgba(255,255,255,0.1); display:flex; justify-content:flex-end;">
                     <button class="btn-action" style="background:var(--primary); color:white; padding:8px 20px; border-radius:15px; font-size:13px; border:none; cursor:pointer; display:flex; align-items:center; gap:5px;" 
                     onclick="handleStatementClick(event, ${c.id})">
                        <i class="fa-solid fa-file-invoice-dollar"></i> كشف حساب
                     </button>
                </div>
            </div>
        `;
    }).join('');
}

function handleStatementClick(event, clientId) {
    if (event) event.stopPropagation();
    openClientStatementMobile(clientId);
}

function filterClientsPage(query) {
    if (!query) {
        renderClientsPage(allClients); // allClients loaded by app init
        return;
    }
    const filtered = allClients.filter(c => 
        c.name.toLowerCase().includes(query.toLowerCase()) || 
        (c.phone && c.phone.includes(query))
    );
    renderClientsPage(filtered);
}

// ========== TASKS ==========
let allTasks = [];
let currentTaskTab = 'pending';

async function loadTasks() {
    try {
        let tasks = [];
        if (USE_EEL) {
            tasks = await eel.py_get_tasks(currentUser.name)();
        } else {
            const res = await fetch(`${API_BASE}/api/mobile/tasks?staff_name=${encodeURIComponent(currentUser.name)}`);
            tasks = await res.json();
        }
        allTasks = tasks;
        renderTasks();
    } catch (e) { console.error(e); }
}

function switchTaskTab(tab) {
    currentTaskTab = tab;
    document.querySelectorAll('#page-tasks .tab').forEach(t => t.classList.remove('active'));
    document.querySelector(`#page-tasks .tab[data-tab="${tab}"]`).classList.add('active');
    renderTasks();
}

function renderTasks() {
    const list = document.getElementById('tasks-list');
    const filtered = allTasks.filter(t => currentTaskTab === 'pending' ? t.status !== 'done' : t.status === 'done');
    
    if (filtered.length === 0) {
        list.innerHTML = '<p style="text-align:center; padding:20px;">لا يوجد مهام</p>';
        return;
    }
    
    list.innerHTML = filtered.map(t => `
        <div class="task-card ${t.status === 'done' ? 'done' : ''}">
            <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
                <h3 style="font-size:16px;">${t.title}</h3>
                <span style="font-size:11px; color:var(--text-muted);">${new Date(t.created_at).toLocaleDateString()}</span>
            </div>
            <p style="color:var(--text-secondary); font-size:13px; margin-bottom:10px;">${t.description || ''}</p>
            ${t.image_path ? `<img src="${t.image_path.replace(/\\/g, '/')}" class="task-img-preview" onclick="viewImageFull(this.src)">` : ''}
            
            ${t.status !== 'done' ? `
            <div class="task-actions">
                <button class="btn-action ready" onclick="markTaskDone(${t.id})" style="width:100%;">✅ تم الإنجاز</button>
            </div>` : ''}
        </div>
    `).join('');
}

async function markTaskDone(taskId) {
    if (!confirm('تأكيد إنجاز المهمة؟')) return;
    try {
        if (USE_EEL) await eel.py_update_task_status(taskId, 'done')();
        else {
             await fetch(`${API_BASE}/api/mobile/tasks/update`, {
                 method: 'POST',
                 headers: {'Content-Type': 'application/json'},
                 body: JSON.stringify({id: taskId, status: 'done'})
             });
        }
        loadTasks();
    } catch (e) { alert('خطأ'); }
}

// ========== CHAT ==========
let chatPollInterval = null;

async function loadChat() {
    await fetchChat();
    if (!chatPollInterval) chatPollInterval = setInterval(fetchChat, 5000);
}

async function fetchChat() {
    try {
        let msgs = [];
        if (USE_EEL) msgs = await eel.py_get_chat_messages(50)();
        else {
            const res = await fetch(`${API_BASE}/api/mobile/chat?limit=50`);
            msgs = await res.json();
        }
        renderChat(msgs);
    } catch(e) {}
}

function renderChat(msgs) {
    const div = document.getElementById('chat-messages');
    // Simple render: if diff count, update all. Optimizing scroll
    const wasAtBottom = div.scrollHeight - div.scrollTop === div.clientHeight;
    
    div.innerHTML = msgs.map(m => {
        const isMe = m.sender === currentUser.name;
        // Fix image path for web
        let imgTag = '';
        if (m.image_path) {
             // If web, ensure relative path or API serve
             // Assuming path is like 'pos_images/chat/...'
             // If absolute path from backend, need conversion?
             // Flask serves static 'pos_images' via route? No, we need a route for images if they are outside 'web'.
             // Assuming app.py serves images or returns relative. 
             // Backend returns what is stored.
             imgTag = `<img src="${m.image_path}" class="msg-img">`; 
        }
        
        return `
            <div class="message-bubble ${isMe ? 'msg-out' : 'msg-in'}">
                ${!isMe ? `<div style="font-size:10px; font-weight:bold; margin-bottom:2px;">${m.sender}</div>` : ''}
                ${m.message}
                ${imgTag}
                <div style="font-size:9px; opacity:0.7; text-align:right; margin-top:2px;">
                    ${new Date(m.timestamp).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}
                </div>
            </div>
        `;
    }).join('');
    
    if (wasAtBottom) div.scrollTop = div.scrollHeight;
}

let chatImgFile = null;
function previewChatImage(input) {
    if (input.files && input.files[0]) {
        chatImgFile = input.files[0];
        const reader = new FileReader();
        reader.onload = function(e) {
            document.getElementById('chat-img-preview').src = e.target.result;
            document.getElementById('chat-img-preview-container').style.display = 'block';
        }
        reader.readAsDataURL(input.files[0]);
    }
}
function clearChatImage() {
    chatImgFile = null;
    document.getElementById('chat-img-upload').value = '';
    document.getElementById('chat-img-preview-container').style.display = 'none';
}

async function sendChatMessage() {
    const txt = document.getElementById('chat-input').value;
    if (!txt && !chatImgFile) return;
    
    const sender = currentUser.name;
    
    try {
        if (USE_EEL) {
            // Eel text only for now unless we implement file upload via Eel base64
            // User requested WhatsApp style. 
            // We can pass path if file exists? No.
            // Simplified: Text only for Eel, or Base64 (Heavy).
            // Let's assume Flask for image upload usually.
            await eel.py_add_chat_message(sender, txt, null)();
            document.getElementById('chat-input').value = '';
        } else {
            const formData = new FormData();
            formData.append('sender', sender);
            formData.append('message', txt);
            if (chatImgFile) formData.append('image', chatImgFile);
            
            await fetch(`${API_BASE}/api/mobile/chat/send`, {
                method: 'POST',
                body: formData
            });
            document.getElementById('chat-input').value = '';
            clearChatImage();
        }
        fetchChat();
    } catch(e) { alert('فشل الإرسال'); }
}

// ========== PRODUCTION ==========
async function loadProduction() {
    try {
        let summary = [];
        if (USE_EEL) summary = await eel.py_get_production_summary()();
        else {
            const res = await fetch(`${API_BASE}/api/mobile/production`);
            summary = await res.json();
        }
        renderProduction(summary);
    } catch(e) {}
}

function renderProduction(list) {
    const container = document.getElementById('production-list');
    if (!list || list.length === 0) {
        container.innerHTML = '<p style="text-align:center; padding:20px;">لا يوجد نواقص (كله تمام)</p>';
        return;
    }
    
    container.innerHTML = list.map(item => `
        <div class="prod-item">
            <div>
                <div style="font-weight:bold;">${item.product_name}</div>
            </div>
            <div style="display:flex; gap:10px; align-items:center;">
                <span class="prod-qty-badge">مطلوب: ${item.total_qty}</span>
                <button class="btn-decrement" onclick="decrementProduction(${item.product_id})">-1</button>
            </div>
        </div>
    `).join('');
}

async function decrementProduction(pid) {
    try {
        if (USE_EEL) await eel.py_decrement_production_item(pid, 1)();
        else {
             await fetch(`${API_BASE}/api/mobile/production/decrement`, {
                 method: 'POST',
                 headers: {'Content-Type': 'application/json'},
                 body: JSON.stringify({product_id: pid, qty: 1})
             });
        }
        // Optimistic UI update or refresh
        loadProduction();
    } catch(e) { alert('خطأ'); }
}

// ========== SUMMON ==========
async function summonStaff() {
    if (!confirm('هل تريد استدعاء المدير/الموظفين حالاً؟')) return;
    try {
        // Send call
        if (USE_EEL) await eel.py_add_staff_call(currentUser.name, 'all', 'summon')();
        else {
             await fetch(`${API_BASE}/api/mobile/calls/add`, {
                 method: 'POST',
                 headers: {'Content-Type': 'application/json'},
                 body: JSON.stringify({caller: currentUser.name, target: 'all', type: 'summon'})
             });
        }
        alert('🔔 تم إرسال الاستدعاء!');
    } catch(e) { alert('خطأ في الإرسال'); }
}

// Helper to open full image
function viewImageFull(src) {
    // Implement simple lightbox or open in new tab
    window.open(src, '_blank');
}

// Hook into navigateTo to load data
const originalNavigateTo = navigateTo;
navigateTo = function(page) {
    originalNavigateTo(page);
    if (page === 'clients') { renderClientsPage(allClients); } // Filter reset
    if (page === 'tasks') loadTasks();
    if (page === 'chat') loadChat();
    else clearInterval(chatPollInterval); // Stop poll if leaving chat
    if (page === 'production') loadProduction();
    if (page === 'inventory') loadInventory();
    if (page === 'laser') loadLaserOps();
}

// ========== ORDER DETAILS ==========
async function showOrderDetails(orderId) {
    try {
        const response = await fetch(`${API_BASE}/api/mobile/order_details/${orderId}`);
        const result = await response.json();
        
        if (!result.success) {
            alert(result.message || 'فشل جلب التفاصيل');
            return;
        }
        
        const data = result.data;
        const order = data.order;
        const items = data.items || [];
        const client = data.client || {};
        
        document.getElementById('order-modal-title').textContent = `طلب #${order.id}`;
        
        let html = `
            <div style="background:var(--bg-tertiary); padding:12px; border-radius:8px; margin-bottom:15px;">
                <div style="font-weight:bold; margin-bottom:5px;">${client.name || 'عميل نقدي'}</div>
                <div style="font-size:12px; color:var(--text-secondary);">${client.phone || ''}</div>
                <div style="font-size:12px; color:var(--text-muted);">${order.date ? new Date(order.date).toLocaleString('ar-EG') : ''}</div>
            </div>
            
            <h4 style="margin-bottom:10px;">المنتجات:</h4>
            <div style="border:1px solid var(--border-color); border-radius:8px; overflow:hidden;">
        `;
        
        if (items.length === 0) {
            html += `<div style="padding:15px; text-align:center; color:var(--text-muted);">لا توجد منتجات</div>`;
        } else {
            items.forEach((item, idx) => {
                html += `
                    <div style="display:flex; justify-content:space-between; padding:10px 12px; ${idx < items.length - 1 ? 'border-bottom:1px solid var(--border-color);' : ''}">
                        <div>
                            <div style="font-weight:500;">${item.product_name}</div>
                            <div style="font-size:12px; color:var(--text-secondary);">${item.qty} × ${item.price} ج.م</div>
                        </div>
                        <div style="font-weight:bold; color:var(--primary);">${item.total || (item.qty * item.price)} ج.م</div>
                    </div>
                `;
            });
        }
        
        html += `</div>
            <div style="margin-top:15px; padding:12px; background:var(--primary); color:white; border-radius:8px; display:flex; justify-content:space-between;">
                <span>الإجمالي:</span>
                <span style="font-weight:bold;">${order.total_amount || 0} ج.م</span>
            </div>
        `;
        
        document.getElementById('order-details-content').innerHTML = html;
        document.getElementById('modal-order-details').classList.add('active');
        
    } catch (e) {
        console.error(e);
        alert('فشل جلب التفاصيل');
    }
}

// ========== CLIENT STATEMENT ==========
async function openClientStatementMobile(clientId) {
    try {
        const response = await fetch(`${API_BASE}/api/mobile/client_statement/${clientId}`);
        const result = await response.json();
        
        if (!result.success) {
            alert(result.message || 'فشل جلب كشف الحساب');
            return;
        }
        
        const data = result.data;
        const client = data.client;
        const summary = data.summary;
        const groups = data.grouped_items || {};
        
        document.getElementById('statement-modal-title').textContent = `كشف حساب: ${client.name}`;
        
        let html = `
            <!-- Summary Cards -->
            <div style="display:grid; grid-template-columns:repeat(2, 1fr); gap:10px; margin-bottom:15px;">
                <div style="background:linear-gradient(135deg, #ef4444, #dc2626); padding:12px; border-radius:10px; color:white; text-align:center;">
                    <div style="font-size:11px; opacity:0.9;">إجمالي المديونية</div>
                    <div style="font-size:18px; font-weight:bold;">${summary.total_debt || 0} ج.م</div>
                </div>
                <div style="background:linear-gradient(135deg, #22c55e, #16a34a); padding:12px; border-radius:10px; color:white; text-align:center;">
                    <div style="font-size:11px; opacity:0.9;">إجمالي المدفوع</div>
                    <div style="font-size:18px; font-weight:bold;">${summary.total_paid || 0} ج.م</div>
                </div>
                <div style="background:linear-gradient(135deg, #f59e0b, #d97706); padding:12px; border-radius:10px; color:white; text-align:center;">
                    <div style="font-size:11px; opacity:0.9;">جاري التجهيز</div>
                    <div style="font-size:18px; font-weight:bold;">${summary.processing_debt || 0} ج.م</div>
                </div>
                <div style="background:linear-gradient(135deg, #3b82f6, #2563eb); padding:12px; border-radius:10px; color:white; text-align:center;">
                    <div style="font-size:11px; opacity:0.9;">جاهز للتسليم</div>
                    <div style="font-size:18px; font-weight:bold;">${summary.executed_debt || 0} ج.م</div>
                </div>
            </div>
        `;
        
        // Under Preparation
        if (groups.under_prep && groups.under_prep.length > 0) {
            html += renderItemsSection('⏳ جاري التجهيز', groups.under_prep, '#f59e0b');
        }
        
        // Ready
        if (groups.ready && groups.ready.length > 0) {
            html += renderItemsSection('✅ جاهز للتسليم', groups.ready, '#22c55e');    
        }
        
        // Delivered (last 10)
        if (groups.delivered && groups.delivered.length > 0) {
            html += renderItemsSection('📦 تم التسليم', groups.delivered.slice(0, 10), '#6b7280');
        }
        
        document.getElementById('client-statement-content').innerHTML = html;
        document.getElementById('modal-client-statement').classList.add('active');
        
    } catch (e) {
        console.error(e);
        alert('فشل جلب كشف الحساب');
    }
}

function renderItemsSection(title, items, color) {
    let html = `
        <div style="margin-bottom:15px;">
            <h4 style="color:${color}; margin-bottom:8px; display:flex; align-items:center; gap:5px;">
                ${title} <span style="font-size:12px; background:${color}22; color:${color}; padding:2px 8px; border-radius:10px;">${items.length}</span>
            </h4>
            <div style="border:1px solid var(--border-color); border-radius:8px; overflow:hidden;">
    `;
    
    items.forEach((item, idx) => {
        const borderStyle = idx < items.length - 1 ? 'border-bottom:1px solid var(--border-color);' : '';
        html += `
            <div style="display:flex; justify-content:space-between; padding:10px 12px; ${borderStyle}">
                <div>
                    <div style="font-weight:500;">${item.product_name}</div>
                    <div style="font-size:12px; color:var(--text-secondary);">${item.qty} قطعة × ${item.unit_price} ج.م</div>
                </div>
                <div style="font-weight:bold;">${item.total} ج.م</div>
            </div>
        `;
    });
    
    html += `</div></div>`;
    return html;
}

// ========== INVENTORY ==========
let inventoryProducts = [];

async function loadInventory() {
    try {
        const response = await fetch(`${API_BASE}/api/mobile/inventory`);
        inventoryProducts = await response.json();
        renderInventory(inventoryProducts);
    } catch(e) {
        console.error('Failed to load inventory:', e);
        document.getElementById('inventory-list').innerHTML = '<p style="text-align:center; padding:20px;">فشل تحميل المنتجات</p>';
    }
}

function filterInventory(query) {
    if (!query) {
        renderInventory(inventoryProducts);
        return;
    }
    const filtered = inventoryProducts.filter(p => 
        p.name.toLowerCase().includes(query.toLowerCase()) ||
        (p.category && p.category.toLowerCase().includes(query.toLowerCase()))
    );
    renderInventory(filtered);
}

function renderInventory(products) {
    const container = document.getElementById('inventory-list');
    
    if (!products || products.length === 0) {
        container.innerHTML = '<p style="text-align:center; padding:20px; color:var(--text-muted);">لا توجد منتجات</p>';
        return;
    }
    
    container.innerHTML = products.map(p => `
        <div class="inventory-item" style="background:var(--bg-surface); border-radius:12px; padding:15px; display:flex; flex-direction:column; gap:10px;">
            <div style="display:flex; justify-content:space-between; align-items:flex-start;">
                <div>
                    <div style="font-weight:bold; font-size:15px;">${p.name}</div>
                    <div style="font-size:12px; color:var(--text-secondary);">${p.category || ''}</div>
                </div>
                <div style="background:var(--primary); color:white; padding:4px 12px; border-radius:15px; font-size:13px;">
                    بالنظام: ${p.system_qty || 0}
                </div>
            </div>
            <div style="display:flex; gap:10px; align-items:center;">
                <input type="number" 
                       id="count-${p.id}" 
                       placeholder="الكمية المجرودة" 
                       style="flex:1; padding:10px; border:1px solid var(--border-color); border-radius:8px; background:var(--bg-tertiary); color:var(--text-primary); font-size:14px;"
                       min="0">
                <button onclick="saveInventoryCount(${p.id})" 
                        style="background:var(--accent); color:white; border:none; padding:10px 20px; border-radius:8px; font-weight:bold; cursor:pointer;">
                    حفظ
                </button>
            </div>
        </div>
    `).join('');
}

async function saveInventoryCount(productId) {
    const input = document.getElementById(`count-${productId}`);
    const countedQty = parseInt(input.value);
    
    if (isNaN(countedQty) || countedQty < 0) {
        alert('أدخل كمية صحيحة');
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/api/mobile/inventory/count`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                product_id: productId,
                counted_qty: countedQty,
                staff_id: currentUser ? currentUser.id : null,
                notes: ''
            })
        });
        
        const result = await response.json();
        
        if (result.success) {
            // Visual feedback
            input.style.borderColor = '#22c55e';
            input.style.backgroundColor = '#22c55e22';
            
            let diffMsg = '';
            if (result.difference > 0) {
                diffMsg = ` (زيادة: +${result.difference})`;
            } else if (result.difference < 0) {
                diffMsg = ` (نقص: ${result.difference})`;
            } else {
                diffMsg = ' (مطابق ✓)';
            }
            
            showSyncToast(`✅ تم حفظ الجرد${diffMsg}`, 'success');
            
            // Reset after a moment
            setTimeout(() => {
                input.style.borderColor = '';
                input.style.backgroundColor = '';
            }, 2000);
            
        } else {
            alert(result.message || 'فشل حفظ الجرد');
        }
    } catch(e) {
        console.error(e);
        alert('فشل الاتصال');
    }
}

// ========== LASER OPS CENTER ==========
async function loadLaserOps() {
    const prodContainer = document.getElementById('laser-ops-products');
    const imgContainer = document.getElementById('laser-ops-images');
    if (!prodContainer || !imgContainer) return;

    prodContainer.innerHTML = '<p style="text-align:center; padding:10px; color:var(--text-muted);">جاري التحميل...</p>';
    imgContainer.innerHTML = '';

    try {
        // Aggregated products
        const res = await fetch(`${API_BASE}/api/laser_queue`);
        const data = await res.json();

        prodContainer.innerHTML = '';
        if (data.aggregated && data.aggregated.length > 0) {
            data.aggregated.forEach(item => {
                prodContainer.innerHTML += `
                    <div style="background:var(--bg-surface); padding:12px; border-radius:10px; display:flex; justify-content:space-between; align-items:center;">
                        <span style="font-weight:bold;">${item.product_name}</span>
                        <div style="display:flex; gap:8px; align-items:center;">
                            <span style="font-size:11px; color:var(--text-muted);">${item.order_count || ''} طلب</span>
                            <span style="background:#DC2626; color:white; padding:3px 12px; border-radius:12px; font-weight:bold;">${item.total_qty}</span>
                        </div>
                    </div>
                `;
            });
        } else {
            prodContainer.innerHTML = '<p style="text-align:center; padding:15px; color:#10B981;">✅ لا يوجد طلبات تحت التجهيز</p>';
        }

        // Images
        const imgRes = await fetch(`${API_BASE}/api/laser_queue/images`);
        const imgData = await imgRes.json();

        imgContainer.innerHTML = '';
        if (imgData.images && imgData.images.length > 0) {
            imgData.images.forEach(img => {
                imgContainer.innerHTML += `
                    <div style="background:var(--bg-surface); padding:10px; border-radius:10px; display:flex; align-items:center; gap:10px;">
                        <img src="${API_BASE}/api/laser_queue/file/${img.filename}" 
                             style="width:60px; height:50px; object-fit:cover; border-radius:6px;" 
                             onclick="viewImageFull(this.src)">
                        <span style="flex:1; font-size:12px; color:var(--text-secondary); overflow:hidden; text-overflow:ellipsis;">${img.filename}</span>
                        <button onclick="laserDoneMobile('${img.filename}')" 
                                style="background:#10B981; color:white; border:none; padding:8px 16px; border-radius:8px; font-weight:bold; cursor:pointer;">
                            ✅ تم
                        </button>
                    </div>
                `;
            });
        } else {
            imgContainer.innerHTML = '<p style="text-align:center; padding:15px; color:var(--text-muted);">📂 لا يوجد صور</p>';
        }
    } catch (e) {
        console.error('Laser ops error:', e);
        prodContainer.innerHTML = '<p style="text-align:center; padding:10px; color:var(--danger);">خطأ في الاتصال</p>';
    }
}

async function laserDoneMobile(filename) {
    if (!confirm('تأكيد: تمت القطع؟')) return;
    try {
        await fetch(`${API_BASE}/api/laser_queue/done/${filename}`, { method: 'POST' });
        showSyncToast('✅ تم', 'success');
        loadLaserOps();
    } catch (e) {
        alert('خطأ');
    }
}

async function uploadLaserImage(input) {
    if (!input.files || !input.files[0]) return;
    const file = input.files[0];

    const formData = new FormData();
    formData.append('image', file);
    formData.append('notes', 'تصوير من الموبايل');
    formData.append('quantity', '1');

    try {
        const res = await fetch(`${API_BASE}/api/laser_queue/upload`, {
            method: 'POST',
            body: formData
        });
        const data = await res.json();
        if (data.success) {
            showSyncToast('📸 تم رفع الصورة', 'success');
            loadLaserOps();
        } else {
            alert(data.message || 'فشل الرفع');
        }
    } catch (e) {
        alert('خطأ في رفع الصورة');
    }
    input.value = ''; // Reset file input
}
