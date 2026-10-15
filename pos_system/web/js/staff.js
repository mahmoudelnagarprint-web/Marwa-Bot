// Staff Management Logic

let allStaff = [];
let currentTab = 'team';
let currentPayrollStaffId = null;

// --- Initialization ---
document.addEventListener('DOMContentLoaded', async () => {
    await loadStaff();
    initSecurityGate();
    
    // Initial Load
    renderLeaderboard();
});

// --- Tab System ---
function switchTab(tabId) {
    currentTab = tabId;
    
    // Hide all tabs
    document.querySelectorAll('.tab-content').forEach(c => c.style.display = 'none');
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    
    // Show selected tab
    document.getElementById(`tab-${tabId}`).style.display = 'block';
    document.getElementById(`tabBtn_${tabId}`).classList.add('active');
    
    // Load Data based on Tab
    if (tabId === 'team') loadStaff();
    if (tabId === 'attendance') loadAttendance();
    if (tabId === 'payroll') renderPayrollStaffList();
    if (tabId === 'requests') loadRequests();
    if (tabId === 'chat') startChatPolling();
    if (tabId === 'security') startQRTimer();
}

// --- Team Tab ---
async function loadStaff() {
    try {
        allStaff = await eel.py_get_all_staff(false)();
        renderStaffGrid(allStaff);
        renderLeaderboard();
    } catch (e) {
        console.error("Failed to load staff:", e);
    }
}

function renderStaffGrid(staffList) {
    const grid = document.getElementById('staff-grid');
    grid.innerHTML = '';
    
    if (!staffList || staffList.length === 0) {
        grid.innerHTML = '<p style="text-align:center; color:#94A3B8; grid-column: 1/-1; padding:50px;">لا يوجد موظفين. أضف موظف جديد!</p>';
        return;
    }
    
    staffList.forEach(s => {
        if (!s.is_active) return; // Skip inactive in grid
        
        const initials = s.name ? s.name.charAt(0).toUpperCase() : '?';
        
        const card = document.createElement('div');
        card.className = 'staff-card';
        card.innerHTML = `
            <div class="staff-avatar">
                ${s.photo_path ? `<img src="${s.photo_path}" alt="${s.name}">` : initials}
                <div class="staff-status online"></div>
            </div>
            <div class="staff-details">
                <h4>${s.name}</h4>
                <span>${s.role}</span>
            </div>
            
            <div class="staff-stats">
                <div class="stat-item">
                    <span class="stat-val">0</span>
                    <span class="stat-label">بيع</span>
                </div>
                <div class="stat-item">
                    <span class="stat-val">${s.commission_rate || 0}%</span>
                    <span class="stat-label">عمولة</span>
                </div>
            </div>
            
            <div class="staff-actions">
                <button onclick="openEditStaff(${s.id})" title="تعديل">✏️</button>
                <button onclick="logAttendance(${s.id}, 'check_in')" title="تسجيل حضور">⏰</button>
                <button class="danger" onclick="deleteStaff(${s.id})" title="حذف">🗑️</button>
            </div>
        `;
        grid.appendChild(card);
    });
}

function renderLeaderboard() {
    const top = allStaff.filter(s => s.is_active).slice(0, 2);
    const container = document.getElementById('leaderboard-container');
    container.innerHTML = '';
    
    if (top.length > 0) {
        container.innerHTML += createLeaderCard(top[0], 'gold', 1);
    }
    if (top.length > 1) {
        container.innerHTML += createLeaderCard(top[1], 'silver', 2);
    }
}

function createLeaderCard(staff, type, rank) {
    const initials = staff.name ? staff.name.charAt(0).toUpperCase() : '?';
    return `
        <div class="lb-card ${type}">
            <div class="lb-rank">#${rank}</div>
            <div class="staff-avatar" style="width:60px; height:60px; font-size:1.5em;">
                ${staff.photo_path ? `<img src="${staff.photo_path}" alt="${staff.name}">` : initials}
            </div>
            <div class="lb-info">
                <h3>${staff.name}</h3>
                <p>Top Performer</p>
                <div class="lb-prize">🏆 جائزة الشهر</div>
            </div>
        </div>
    `;
}

function filterStaff(query) {
    const filtered = allStaff.filter(s => s.name.toLowerCase().includes(query.toLowerCase()));
    renderStaffGrid(filtered);
}

// --- Attendance Tab ---
async function loadAttendance() {
    const from = document.getElementById('att-date-from').value;
    const to = document.getElementById('att-date-to').value;
    
    try {
        const logs = await eel.py_get_attendance_log(null, from, to)();
        const tbody = document.getElementById('attendance-table-body');
        tbody.innerHTML = '';
        
        if (!logs || logs.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; color:#94A3B8;">لا توجد سجلات</td></tr>';
            return;
        }
        
        logs.forEach(log => {
            let duration = '-';
            if (log.check_in && log.check_out) {
                const start = new Date(log.check_in);
                const end = new Date(log.check_out);
                const diffHours = (end - start) / (1000 * 60 * 60);
                duration = diffHours.toFixed(1) + ' س';
            }
            
            const checkInTime = log.check_in ? new Date(log.check_in).toLocaleTimeString('ar-EG') : '-';
            const checkOutTime = log.check_out ? new Date(log.check_out).toLocaleTimeString('ar-EG') : '-';
            
            let statusClass = '';
            if (log.status === 'Absent') statusClass = 'color:#DC2626';
            if (log.status === 'Late') statusClass = 'color:#F59E0B';
            if (log.status === 'Present') statusClass = 'color:#10B981';
            
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>${log.date}</td>
                <td>${log.name || 'Unknown'}</td>
                <td>${checkInTime}</td>
                <td>${checkOutTime}</td>
                <td style="${statusClass}">${translateStatus(log.status)}</td>
                <td>${duration}</td>
            `;
            tbody.appendChild(tr);
        });
    } catch (e) {
        console.error("Failed to load attendance:", e);
    }
}

function translateStatus(s) {
    if (s === 'Present') return 'حاضر';
    if (s === 'Late') return 'متأخر';
    if (s === 'Absent') return 'غائب';
    return s || '-';
}

// --- Payroll Tab ---
function renderPayrollStaffList() {
    const list = document.getElementById('payroll-staff-list');
    list.innerHTML = '';
    allStaff.filter(s => s.is_active).forEach(s => {
        const btn = document.createElement('button');
        btn.className = 'btn btn-outline';
        btn.style = "width:100%; text-align:right; margin-bottom:5px;";
        btn.innerText = s.name;
        btn.onclick = () => loadPayrollDetails(s.id);
        list.appendChild(btn);
    });
}

async function loadPayrollDetails(staffId) {
    currentPayrollStaffId = staffId;
    document.getElementById('payroll-empty-state').style.display = 'none';
    document.getElementById('payroll-details-view').style.display = 'block';
    
    try {
        const draft = await eel.py_get_payroll_draft(staffId)();
        if (draft) {
            document.getElementById('pay-staff-name').innerText = draft.staff_name;
            document.getElementById('pay-base').innerText = draft.base_salary;
            document.getElementById('pay-comm').innerText = draft.commission;
            
            const wallet = draft.bonuses - draft.deductions;
            const wEl = document.getElementById('pay-wallet');
            wEl.innerText = wallet;
            wEl.className = wallet >= 0 ? 'kpi-value positive' : 'kpi-value negative';
            
            document.getElementById('pay-net').innerText = draft.net_salary;
        }
    } catch (e) {
        console.error("Failed to load payroll:", e);
    }
}

function openTransactionModal(type) {
    if (!currentPayrollStaffId) return;
    document.getElementById('modal-txn').classList.add('active');
    document.getElementById('txn-type').value = type;
    document.getElementById('txn-title').innerText = type === 'Bonus' ? 'إضافة مكافأة' : 'إضافة خصم';
}

async function submitTransaction() {
    const type = document.getElementById('txn-type').value;
    const amount = parseFloat(document.getElementById('txn-amount').value);
    const reason = document.getElementById('txn-reason').value;
    
    if (!amount) return;
    
    await eel.py_add_payroll_txn(currentPayrollStaffId, type, amount, reason)();
    closeModal('modal-txn');
    loadPayrollDetails(currentPayrollStaffId);
}

async function openPayoutModal() {
    if (!currentPayrollStaffId) return;
    if(confirm('هل تريد تأكيد صرف كافة المستحقات لهذا الموظف؟ يتم الحساب تلقائياً.')) {
        await eel.py_confirm_payout(currentPayrollStaffId)();
        loadPayrollDetails(currentPayrollStaffId);
        alert('تم صرف المرتب بنجاح');
    }
}

// --- Requests Tab ---
async function loadRequests() {
    try {
        const reqs = await eel.py_get_requests()();
        const tbody = document.getElementById('requests-table-body');
        tbody.innerHTML = '';
        
        const pending = reqs.filter(r => r.status === 'Pending');
        document.getElementById('req-badge').innerText = pending.length;
        document.getElementById('req-badge').style.display = pending.length > 0 ? 'inline-block' : 'none';
        
        if (!reqs || reqs.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; color:#94A3B8;">لا توجد طلبات</td></tr>';
            return;
        }
        
        reqs.forEach(r => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>${r.staff_name || 'Unknown'}</td>
                <td>${r.type}</td>
                <td>${r.details}</td>
                <td>${new Date(r.date).toLocaleDateString()}</td>
                <td><span class="badge ${r.status.toLowerCase()}">${r.status}</span></td>
                <td>
                     ${r.status === 'Pending' ? `
                     <button class="btn btn-success" style="padding:5px 10px;" onclick="updateReq(${r.id}, 'Approved')">✔</button>
                     <button class="btn btn-danger" style="padding:5px 10px;" onclick="updateReq(${r.id}, 'Rejected')">✖</button>
                     ` : '-'}
                </td>
            `;
            tbody.appendChild(tr);
        });
    } catch (e) {
        console.error("Failed to load requests:", e);
    }
}

async function updateReq(id, status) {
    await eel.py_update_request_status(id, status)();
    loadRequests();
}

// --- Chat Tab ---
let chatInterval = null;
function startChatPolling() {
    loadChatMessages();
    if (!chatInterval) chatInterval = setInterval(loadChatMessages, 3000);
}

async function loadChatMessages() {
    try {
        const msgs = await eel.py_get_chat_messages(50)();
        const box = document.getElementById('chat-box');
        box.innerHTML = '';
        
        if (!msgs || msgs.length === 0) {
            box.innerHTML = '<p style="text-align:center; color:#94A3B8;">لا توجد رسائل</p>';
            return;
        }
        
        msgs.forEach(m => {
            const div = document.createElement('div');
            div.className = `chat-bubble ${m.sender_id ? 'others' : 'mine'}`;
            
            div.innerHTML = `
                <strong>${m.sender_name || 'Admin'}</strong><br>
                ${m.message}
                <div style="font-size:0.7em; opacity:0.7; text-align:left; margin-top:5px;">${new Date(m.timestamp).toLocaleTimeString()}</div>
            `;
            box.appendChild(div);
        });
        box.scrollTop = box.scrollHeight;
    } catch (e) {
        console.error("Failed to load chat:", e);
    }
}

async function sendMessage() {
    const msg = document.getElementById('chat-input').value;
    const recipient = document.getElementById('chat-recipient').value;
    
    if (!msg) return;
    
    const recId = recipient === 'broadcast' ? null : parseInt(recipient);
    
    await eel.py_send_chat(null, recId, msg)();
    document.getElementById('chat-input').value = '';
    loadChatMessages();
}

// --- Security Tab ---
let qrTimer = null;
let networkUrl = '';

function startQRTimer() {
    // Load network info first, then generate QR with the URL
    loadNetworkInfo().then(() => {
        refreshQR();
    });
}

async function refreshQR() {
    const container = document.getElementById('qrcode');
    
    // Check if QRCode library is loaded
    if (typeof QRCode === 'undefined') {
        container.innerHTML = '<p style="color:red;">خطأ: مكتبة QR غير محملة</p>';
        console.error("QRCode library not loaded");
        return;
    }
    
    try {
        // Use network URL if available, otherwise use token
        let qrContent = networkUrl;
        
        if (!qrContent) {
            const data = await eel.py_get_security_token()();
            qrContent = JSON.stringify(data);
        }
        
        container.innerHTML = '';
        new QRCode(container, {
            text: qrContent,
            width: 200,
            height: 200,
            colorDark: "#1E293B",
            colorLight: "#ffffff"
        });
        
    } catch (e) {
        console.error("Failed to generate QR:", e);
        container.innerHTML = '<p style="color:red;">خطأ في توليد الكود</p>';
    }
}

async function loadNetworkInfo() {
    try {
        const info = await eel.py_get_network_info()();
        
        document.getElementById('network-ip').innerText = info.ip || 'غير متاح';
        document.getElementById('network-url').innerText = info.url || 'غير متاح';
        networkUrl = info.url || '';
        
        return info;
        
    } catch (e) {
        console.error("Failed to get network info:", e);
        document.getElementById('network-ip').innerText = 'غير متاح';
        document.getElementById('network-url').innerText = 'أعد تشغيل التطبيق';
        return null;
    }
}

function copyNetworkLink() {
    if (!networkUrl) {
        alert('الرابط غير متاح');
        return;
    }
    
    navigator.clipboard.writeText(networkUrl).then(() => {
        alert('تم نسخ الرابط! 📋\n\n' + networkUrl);
    }).catch(e => {
        // Fallback for older browsers
        const textarea = document.createElement('textarea');
        textarea.value = networkUrl;
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand('copy');
        document.body.removeChild(textarea);
        alert('تم نسخ الرابط! 📋\n\n' + networkUrl);
    });
}

function openNetworkLink() {
    if (!networkUrl) {
        loadNetworkInfo();
        return;
    }
    window.open(networkUrl, '_blank');
}

// --- Modals ---
function openAddStaffModal() {
    document.getElementById('staff-id').value = '';
    document.getElementById('staff-name').value = '';
    document.getElementById('staff-role').value = 'Employee';
    document.getElementById('staff-base').value = '';
    document.getElementById('staff-comm').value = '';
    document.getElementById('staff-pin').value = '';
    document.getElementById('modal-staff-title').innerText = 'إضافة موظف';
    document.getElementById('modal-staff').classList.add('active');
}

function openEditStaff(id) {
    const staff = allStaff.find(s => s.id === id);
    if (!staff) return;
    
    document.getElementById('staff-id').value = staff.id;
    document.getElementById('staff-name').value = staff.name;
    document.getElementById('staff-role').value = staff.role;
    document.getElementById('staff-base').value = staff.base_salary;
    document.getElementById('staff-comm').value = staff.commission_rate;
    document.getElementById('staff-pin').value = '';
    document.getElementById('modal-staff-title').innerText = 'تعديل موظف';
    document.getElementById('modal-staff').classList.add('active');
}

function closeModal(id) {
    document.getElementById(id).classList.remove('active');
}

async function saveStaff() {
    const data = {
        id: document.getElementById('staff-id').value || null,
        name: document.getElementById('staff-name').value,
        role: document.getElementById('staff-role').value,
        base_salary: parseFloat(document.getElementById('staff-base').value) || 0,
        commission_rate: parseFloat(document.getElementById('staff-comm').value) || 0,
        pin: document.getElementById('staff-pin').value
    };
    
    if (!data.name) {
        alert('يرجى إدخال اسم الموظف');
        return;
    }
    
    await eel.py_save_staff(data)();
    closeModal('modal-staff');
    loadStaff();
}

async function deleteStaff(id) {
    if(confirm('هل أنت متأكد من حذف هذا الموظف؟')) {
        await eel.py_delete_staff(id)();
        loadStaff();
    }
}

async function logAttendance(staffId, action) {
    await eel.py_log_attendance(staffId, action)();
    alert('تم تسجيل الحضور');
}

function initSecurityGate() {
    // Populate Chat Recipient Dropdown with staff
    const chatSel = document.getElementById('chat-recipient');
    if (!chatSel) return;
    
    // Clear first (keep broadcast)
    chatSel.innerHTML = '<option value="broadcast">📢 الكل (Broadcast)</option>';
    
    allStaff.filter(s => s.is_active).forEach(s => {
        const opt = document.createElement('option');
        opt.value = s.id;
        opt.textContent = s.name;
        chatSel.appendChild(opt);
    });
}

// ========== ALARM SYSTEM ==========
function openAlarmModal() {
    document.getElementById('alarm-note').value = '';
    document.getElementById('modal-alarm').classList.add('active');
}

function triggerAlarm() {
    const note = document.getElementById('alarm-note').value || 'عميل';
    closeModal('modal-alarm');
    
    // Play Sound
    playAlarmSound();
    
    // Visual Alert
    setTimeout(() => {
        alert(`⚠️ تنبيه للمدير!\n\n مطلوب: ${note}\n\nيرجى الحضور فوراً.`);
    }, 100);
}

function playAlarmSound() {
    try {
        const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        const oscillator = audioCtx.createOscillator();
        const gainNode = audioCtx.createGain();
        
        oscillator.connect(gainNode);
        gainNode.connect(audioCtx.destination);
        
        // "Normal Long Sound" - Low frequency square wave
        oscillator.type = 'square';
        oscillator.frequency.value = 600; // Hz
        gainNode.gain.value = 0.3;
        
        oscillator.start();
        
        // Stop after 3 seconds
        setTimeout(() => {
            oscillator.stop();
            audioCtx.close();
        }, 3000);
        
    } catch (e) {
        console.error('Audio Error:', e);
        alert('🔊 بيب بيب بيب (تعذر تشغيل الصوت)');
    }
}

// ========== TASKS LOGIC (NEW) ==========
async function loadTasksAdmin() {
    try {
        const tasks = await eel.py_get_tasks()();
        const tbody = document.getElementById('tasks-table-body');
        if (!tbody) return;
        
        tbody.innerHTML = '';
        if(!tasks || tasks.length === 0) { 
            tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; color:#94A3B8;">لا يوجد مهام</td></tr>'; 
            return; 
        }
        
        tasks.forEach(t => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>${t.title}</td>
                <td>${t.assigned_to}</td>
                <td><span class="badge ${t.status === 'done' ? 'success' : 'warning'}" style="${t.status === 'done' ? 'background:#DCFCE7; color:#166534;' : 'background:#FEF9C3; color:#854D0E;'}">${t.status === 'done' ? 'مكتملة' : 'قيد التنفيذ'}</span></td>
                <td>${new Date(t.created_at).toLocaleDateString()}</td>
                <td>${t.image_path ? '📷' : '-'}</td>
                <td>
                    ${t.status !== 'done' ? `<button class="btn btn-sm btn-success" style="padding:5px 10px;" onclick="adminCompleteTask(${t.id})">✔ إنجاز</button>` : '✅'}
                </td>
            `;
            tbody.appendChild(tr);
        });
    } catch(e) { console.error(e); }
}

function openAddTaskModal() {
    document.getElementById('task-title').value = '';
    document.getElementById('task-desc').value = '';
    document.getElementById('task-img').value = '';
    
    // Populate Assignee
    const sel = document.getElementById('task-assignee');
    sel.innerHTML = '<option value="All">الجميع (عام)</option>';
    allStaff.forEach(s => {
        if (!s.is_active) return;
        const opt = document.createElement('option');
        opt.value = s.name;
        opt.textContent = s.name;
        sel.appendChild(opt);
    });
    
    document.getElementById('modal-task').classList.add('active');
}

async function saveTask() {
    const title = document.getElementById('task-title').value;
    const desc = document.getElementById('task-desc').value;
    const assign = document.getElementById('task-assignee').value;
    const img = document.getElementById('task-img').value;
    
    if(!title) { alert('العنوان مطلوب'); return; }
    
    await eel.py_add_task(title, desc, assign, null, img)();
    closeModal('modal-task');
    loadTasksAdmin();
}

async function adminCompleteTask(id) {
    if(confirm('هل تم إنجاز المهمة؟')) {
        await eel.py_update_task_status(id, 'done')();
        loadTasksAdmin();
    }
}

async function selectTaskImage() {
    // Simple alert for now as dragging is supported by OS to text input often
    alert('قم بنسخ مسار الصورة ولصقه هنا (Copy as Path)');
}

// Updated Switch Tab to load Tasks
const originalSwitchTab = switchTab;
switchTab = function(tabId) {
    originalSwitchTab(tabId);
    if(tabId === 'tasks') loadTasksAdmin();
}

// Updated Trigger Alarm to log to DB
const originalTriggerAlarm = triggerAlarm;
triggerAlarm = async function() {
    const note = document.getElementById('alarm-note').value || 'عميل';
    if(confirm('إطلاق نداء للمدير؟')) {
        originalTriggerAlarm(); // Play sound locally
        // Log to DB so mobile gets it
        await eel.py_add_staff_call('Admin', 'Manager', `Summon: ${note}`)();
    }
}
