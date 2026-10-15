// Offline Queue Module - IndexedDB for offline data storage and sync

const DB_NAME = 'RamadanERP_OfflineQueue';
const DB_VERSION = 1;
const STORES = {
    orders: 'pending_orders',
    clients: 'pending_clients',
    attendance: 'pending_attendance'
};

let db = null;

// ========== DATABASE INITIALIZATION ==========
async function initOfflineDB() {
    return new Promise((resolve, reject) => {
        const request = indexedDB.open(DB_NAME, DB_VERSION);
        
        request.onerror = () => {
            console.error('Failed to open offline database');
            reject(request.error);
        };
        
        request.onsuccess = () => {
            db = request.result;
            console.log('Offline database ready');
            resolve(db);
        };
        
        request.onupgradeneeded = (event) => {
            const database = event.target.result;
            
            // Create object stores
            if (!database.objectStoreNames.contains(STORES.orders)) {
                database.createObjectStore(STORES.orders, { keyPath: 'id', autoIncrement: true });
            }
            if (!database.objectStoreNames.contains(STORES.clients)) {
                database.createObjectStore(STORES.clients, { keyPath: 'id', autoIncrement: true });
            }
            if (!database.objectStoreNames.contains(STORES.attendance)) {
                database.createObjectStore(STORES.attendance, { keyPath: 'id', autoIncrement: true });
            }
        };
    });
}

// ========== QUEUE OPERATIONS ==========

// Add item to queue
async function addToQueue(storeName, data) {
    if (!db) await initOfflineDB();
    
    return new Promise((resolve, reject) => {
        const transaction = db.transaction([storeName], 'readwrite');
        const store = transaction.objectStore(storeName);
        
        const item = {
            ...data,
            timestamp: new Date().toISOString(),
            synced: false
        };
        
        const request = store.add(item);
        
        request.onsuccess = () => {
            console.log(`Added to ${storeName} queue:`, item);
            updatePendingBadge();
            resolve(request.result);
        };
        
        request.onerror = () => {
            console.error(`Failed to add to ${storeName}:`, request.error);
            reject(request.error);
        };
    });
}

// Get all pending items from a store
async function getPendingItems(storeName) {
    if (!db) await initOfflineDB();
    
    return new Promise((resolve, reject) => {
        const transaction = db.transaction([storeName], 'readonly');
        const store = transaction.objectStore(storeName);
        const request = store.getAll();
        
        request.onsuccess = () => {
            const pending = request.result.filter(item => !item.synced);
            resolve(pending);
        };
        
        request.onerror = () => reject(request.error);
    });
}

// Mark item as synced
async function markAsSynced(storeName, id) {
    if (!db) await initOfflineDB();
    
    return new Promise((resolve, reject) => {
        const transaction = db.transaction([storeName], 'readwrite');
        const store = transaction.objectStore(storeName);
        const request = store.get(id);
        
        request.onsuccess = () => {
            const item = request.result;
            if (item) {
                item.synced = true;
                store.put(item);
            }
            resolve();
        };
        
        request.onerror = () => reject(request.error);
    });
}

// Delete synced item
async function deleteFromQueue(storeName, id) {
    if (!db) await initOfflineDB();
    
    return new Promise((resolve, reject) => {
        const transaction = db.transaction([storeName], 'readwrite');
        const store = transaction.objectStore(storeName);
        const request = store.delete(id);
        
        request.onsuccess = () => {
            updatePendingBadge();
            resolve();
        };
        request.onerror = () => reject(request.error);
    });
}

// Clear all synced items from a store
async function clearSynced(storeName) {
    const items = await getPendingItems(storeName);
    // Already filtered to non-synced, so nothing to clear
    updatePendingBadge();
}

// ========== SYNC LOGIC ==========

// Check if online (can reach the server)
async function isServerReachable() {
    try {
        // Try to call a simple backend function
        await eel.py_get_network_info()();
        return true;
    } catch (e) {
        return false;
    }
}

// Sync all pending items
async function syncAllPending() {
    if (!await isServerReachable()) {
        console.log('Server not reachable, skipping sync');
        return { success: false, reason: 'offline' };
    }
    
    let syncedCount = 0;
    let errorCount = 0;
    
    // Sync Orders
    const pendingOrders = await getPendingItems(STORES.orders);
    for (const order of pendingOrders) {
        try {
            await eel.py_save_order(order.data)();
            await deleteFromQueue(STORES.orders, order.id);
            syncedCount++;
        } catch (e) {
            console.error('Failed to sync order:', e);
            errorCount++;
        }
    }
    
    // Sync Clients
    const pendingClients = await getPendingItems(STORES.clients);
    for (const client of pendingClients) {
        try {
            await eel.py_add_client(client.name, client.phone, client.type, client.notes)();
            await deleteFromQueue(STORES.clients, client.id);
            syncedCount++;
        } catch (e) {
            console.error('Failed to sync client:', e);
            errorCount++;
        }
    }
    
    // Sync Attendance
    const pendingAttendance = await getPendingItems(STORES.attendance);
    for (const att of pendingAttendance) {
        try {
            await eel.py_log_attendance(att.staff_id, att.action)();
            await deleteFromQueue(STORES.attendance, att.id);
            syncedCount++;
        } catch (e) {
            console.error('Failed to sync attendance:', e);
            errorCount++;
        }
    }
    
    updatePendingBadge();
    
    return {
        success: true,
        synced: syncedCount,
        errors: errorCount
    };
}

// ========== UI HELPERS ==========

// Get total pending count
async function getTotalPendingCount() {
    let total = 0;
    
    try {
        const orders = await getPendingItems(STORES.orders);
        const clients = await getPendingItems(STORES.clients);
        const attendance = await getPendingItems(STORES.attendance);
        
        total = orders.length + clients.length + attendance.length;
    } catch (e) {
        console.error('Error counting pending:', e);
    }
    
    return total;
}

// Update pending badge in UI
async function updatePendingBadge() {
    const count = await getTotalPendingCount();
    const badge = document.getElementById('pending-badge');
    
    if (badge) {
        badge.textContent = count;
        badge.style.display = count > 0 ? 'flex' : 'none';
    }
    
    return count;
}

// Show sync toast
function showSyncToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `sync-toast ${type}`;
    toast.innerHTML = message;
    
    document.body.appendChild(toast);
    
    setTimeout(() => {
        toast.classList.add('show');
    }, 100);
    
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// ========== AUTO SYNC ==========

let syncInterval = null;

function startAutoSync(intervalMs = 10000) {
    if (syncInterval) clearInterval(syncInterval);
    
    syncInterval = setInterval(async () => {
        const count = await getTotalPendingCount();
        if (count > 0) {
            console.log(`Auto-sync: ${count} pending items`);
            const result = await syncAllPending();
            
            if (result.success && result.synced > 0) {
                showSyncToast(`✅ تم مزامنة ${result.synced} عناصر`, 'success');
            }
        }
    }, intervalMs);
    
    console.log('Auto-sync started');
}

function stopAutoSync() {
    if (syncInterval) {
        clearInterval(syncInterval);
        syncInterval = null;
    }
}

// ========== EXPORTS ==========
window.OfflineQueue = {
    init: initOfflineDB,
    add: addToQueue,
    getPending: getPendingItems,
    delete: deleteFromQueue,
    sync: syncAllPending,
    getPendingCount: getTotalPendingCount,
    updateBadge: updatePendingBadge,
    startAutoSync,
    stopAutoSync,
    STORES
};

// Auto-init when loaded
initOfflineDB().then(() => {
    updatePendingBadge();
});
