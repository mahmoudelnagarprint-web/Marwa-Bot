/**
 * Laser Ops Dashboard Logic
 * Renders the MES Kanban board inside the main web/Eel dashboard.
 */

const API_BASE = window.location.port === "7777" ? "" : "http://127.0.0.1:7777";
const WORKSTATION_OPTIONS = [
    "⚡ ليزر (قص/حفر)",
    "🖨️ طباعة سبليميشن",
    "🖨️ طباعة فوتو",
    "🧵 تجميع وتشطيب",
    "❓ غير مصنف (Uncategorized)",
];
const MATERIAL_OPTIONS = [
    "أكريليك",
    "أكريليك - شفاف",
    "أكريليك - مراية",
    "خشب",
    "خشب - هافان",
    "خشب - بني",
    "خشب - دهبي",
    "خشب - فضي",
    "جلد",
    "غير محدد",
];

let laserAutoRefreshInterval = null;
let activeMaterialFilter = "الكل";

function escapeHtml(value) {
    return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");
}

function safeId(value) {
    return String(value ?? "").replace(/[^a-zA-Z0-9_-]/g, "_");
}

async function loadLaserData() {
    try {
        const [boardRes, imgRes] = await Promise.all([
            fetch(`${API_BASE}/api/laser_ops_board`),
            fetch(`${API_BASE}/api/laser_queue/images`),
        ]);

        if (!boardRes.ok) throw new Error(`HTTP Error: ${boardRes.status}`);
        if (!imgRes.ok) throw new Error(`HTTP Error: ${imgRes.status}`);

        const boardData = await boardRes.json();
        const imgData = await imgRes.json();

        if (!boardData.success) {
            throw new Error(boardData.message || "Board API failed");
        }

        renderLaserKanban(boardData.board || []);
        updateLaserStats(boardData.board || [], boardData.stats || {});
        renderLaserTasks(imgData.images || []);
        loadLaserProductsDropdown();
    } catch (error) {
        console.error("Error loading MES laser board:", error);
        const board = document.getElementById("laser-kanban-board");
        const empty = document.getElementById("laserProductEmpty");
        if (board) board.innerHTML = "";
        if (empty) {
            empty.style.display = "block";
            empty.textContent = `تعذر تحميل لوحة التشغيل: ${error.message || error}`;
        }
    }
}

function updateLaserStats(board, stats) {
    let laserQty = 0;
    let printQty = 0;
    let assemblyQty = 0;
    let uncategorizedQty = 0;

    (board || []).forEach(column => {
        const ws = column.workstation || "";
        const qty = column.total_qty || 0;
        if (ws.includes("ليزر")) {
            laserQty += qty;
        } else if (ws.includes("طباعة")) {
            printQty += qty;
        } else if (ws.includes("تجميع") || ws.includes("تشطيب")) {
            assemblyQty += qty;
        } else if (ws.includes("غير مصنف") || ws.includes("Uncategorized")) {
            uncategorizedQty += qty;
        }
    });

    const elLaser = document.getElementById("laser-stat-laser");
    const elPrint = document.getElementById("laser-stat-print");
    const elAssembly = document.getElementById("laser-stat-assembly");
    const elSorting = document.getElementById("laser-stat-sorting");

    if (elLaser) elLaser.innerText = laserQty;
    if (elPrint) elPrint.innerText = printQty;
    if (elAssembly) elAssembly.innerText = assemblyQty;
    if (elSorting) elSorting.innerText = uncategorizedQty;
}

function switchLaserTab(tabId, btn) {
    document.querySelectorAll("#laser-page .tab-content").forEach((el) => el.classList.remove("active"));
    document.querySelectorAll("#laser-page .tab-link").forEach((el) => el.classList.remove("active"));
    document.getElementById(tabId).classList.add("active");
    btn.classList.add("active");
}

function renderLaserKanban(board) {
    const boardEl = document.getElementById("laser-kanban-board");
    const emptyEl = document.getElementById("laserProductEmpty");
    if (!boardEl || !emptyEl) return;

    // Render material quick navigation filter chips
    renderFilterChips(board);

    boardEl.innerHTML = "";

    if (!board || board.length === 0) {
        emptyEl.style.display = "block";
        return;
    }

    emptyEl.style.display = "none";

    board.forEach((column) => {
        const col = document.createElement("div");
        col.className = "laser-kanban-col";
        col.innerHTML = `
            <div class="laser-kanban-head">
                <div class="laser-kanban-title">${escapeHtml(column.workstation)}</div>
                <div class="laser-kanban-meta">${escapeHtml(column.total_qty || 0)} قطعة</div>
            </div>
            <div class="laser-kanban-body">
                ${(column.materials || []).map((material) => renderMaterialGroup(column.workstation, material)).join("")}
            </div>
        `;
        boardEl.appendChild(col);
    });

    // Apply the active filter
    filterBoardByMaterial(activeMaterialFilter);

    // Initialize 3D tactile Drag and Drop
    initDragAndDrop();
}

function renderMaterialGroup(workstation, materialGroup) {
    return `
        <div class="laser-material-group" data-material="${escapeHtml(materialGroup.material)}">
            <div class="laser-material-header">
                <div class="laser-material-title">${escapeHtml(materialGroup.material)}</div>
                <div class="laser-material-total">إجمالي: ${escapeHtml(materialGroup.total_qty || 0)}</div>
            </div>
            <div class="laser-card-list">
                ${(materialGroup.items || []).map((item) => renderJobCard(workstation, item)).join("")}
            </div>
        </div>
    `;
}

function renderJobCard(workstation, item) {
    const notes = Array.isArray(item.custom_notes) ? item.custom_notes.filter(Boolean) : [];
    const orders = Array.isArray(item.orders) ? item.orders : [];
    const badges = [];

    if (item.is_urgent) badges.push(`<span class="laser-badge urgent">🚨 عاجل</span>`);
    if (item.is_scrap_friendly) badges.push(`<span class="laser-badge scrap">♻️ قصاقيص</span>`);
    if (item.source === "memory") badges.push(`<span class="laser-badge memory">🧠 متعلم</span>`);

    // Add translucent stages and material badges to visualize multi-stage products
    (item.workstations || []).forEach(ws => {
        const shortName = ws.replace(/[⚡🖨️🧵❓]\s*/g, "").split(" ")[0];
        badges.push(`<span class="laser-badge stage" style="background:rgba(37,99,235,0.1); color:#2563EB; border:1px solid rgba(37,99,235,0.25);">📍 ${escapeHtml(shortName)}</span>`);
    });
    (item.materials || []).forEach(mat => {
        badges.push(`<span class="laser-badge material-tag" style="background:rgba(100,116,139,0.1); color:#475569; border:1px solid rgba(100,116,139,0.25);">🏷️ ${escapeHtml(mat)}</span>`);
    });

    const cardId = safeId(`${workstation}-${item.product_name}-${item.size || "na"}`);
    const encodedProductName = encodeURIComponent(item.product_name || "");
    const orderSummary = orders.length
        ? `<div class="laser-job-orders">${orders.map((order) => `#${escapeHtml(order.order_id)} - ${escapeHtml(order.client_name || "عميل")} (${escapeHtml(order.qty || 0)})`).join("<br>")}</div>`
        : "";

    return `
        <div class="laser-job-card ${item.is_urgent ? "urgent" : ""}" data-product-name="${escapeHtml(item.product_name)}" draggable="true">
            <div class="laser-job-header">
                <div class="laser-job-title">${escapeHtml(item.display_name || item.product_name)}</div>
                <div class="laser-qty-pill">${escapeHtml(item.total_qty || 0)}</div>
            </div>
            ${badges.length ? `<div class="laser-badges">${badges.join("")}</div>` : ""}
            <div class="laser-job-meta">
                <div>الخامة: ${escapeHtml(item.material || "غير محدد")}</div>
                <div>عدد الطلبات: ${escapeHtml(item.order_count || 0)}</div>
                <div>تاريخ التسليم: ${escapeHtml(item.delivery_date || "غير محدد")}</div>
            </div>
            ${notes.length ? `<div class="laser-job-notes">📝 ${escapeHtml(notes.join(" | "))}</div>` : ""}
            ${orderSummary}
            ${workstation.includes("غير مصنف") || workstation.includes("Uncategorized") ? renderResolverButton(cardId, item, encodedProductName) : ""}
        </div>
    `;
}

function renderResolverButton(cardId, item, encodedProductName) {
    const encodedItem = encodeURIComponent(JSON.stringify(item));
    return `
        <button class="btn btn-primary" style="width:100%; margin-top:10px; font-size: 0.9em; border-radius: 8px; padding: 8px;" onclick="openLaserResolverModal('${cardId}', '${encodedProductName}', '${encodedItem}')">
            ⚙️ تحديد وتصنيف المسار
        </button>
    `;
}

function openLaserResolverModal(cardId, encodedProductName, encodedItem) {
    const item = JSON.parse(decodeURIComponent(encodedItem));
    const activeWorkstations = item.workstations || ["⚡ ليزر (قص/حفر)"];
    const activeMaterials = item.materials || [item.material || "غير محدد"];
    
    let wsHtml = WORKSTATION_OPTIONS.map((option) => {
        const isChecked = activeWorkstations.includes(option) ? "checked" : "";
        return `
            <label class="laser-resolver-row" style="margin:0 !important; display:flex !important; align-items:center; gap:8px;">
                <input type="checkbox" data-role="workstation-chk" value="${escapeHtml(option)}" ${isChecked} style="width:auto !important; margin:0 !important;">
                <span style="font-size:0.9em; font-weight:700; color:var(--text-primary);">${escapeHtml(option)}</span>
            </label>
        `;
    }).join("");

    let matHtml = MATERIAL_OPTIONS.map((option) => {
        const isChecked = activeMaterials.includes(option) ? "checked" : "";
        return `
            <label class="laser-resolver-row" style="margin:0 !important; display:flex !important; align-items:center; gap:8px;">
                <input type="checkbox" data-role="material-chk" value="${escapeHtml(option)}" ${isChecked} style="width:auto !important; margin:0 !important;">
                <span style="font-size:0.9em; font-weight:700; color:var(--text-primary);">${escapeHtml(option)}</span>
            </label>
        `;
    }).join("");
    
    const isScrap = item.is_scrap_friendly ? "checked" : "";

    const formHtml = `
        <div id="resolver-${cardId}">
            <div style="margin-bottom:15px;">
                <label style="font-weight:800; margin-bottom:8px; display:block; color:var(--text-primary);">محطات التشغيل (تحديد متعدد)</label>
                <div style="display:flex; flex-direction:column; gap:6px; background:var(--bg-main, rgba(0,0,0,0.02)); padding:10px; border-radius:8px; border:1px solid var(--border-color, #e2e8f0);">
                    ${wsHtml}
                </div>
            </div>
            <div style="margin-bottom:15px;">
                <label style="font-weight:800; margin-bottom:8px; display:block; color:var(--text-primary);">الخامات المطلوبة (تحديد متعدد)</label>
                <div style="display:flex; flex-direction:column; gap:6px; background:var(--bg-main, rgba(0,0,0,0.02)); padding:10px; border-radius:8px; border:1px solid var(--border-color, #e2e8f0);">
                    ${matHtml}
                </div>
            </div>
            <label class="laser-resolver-row" style="display:flex !important; align-items:center; gap:8px; cursor:pointer;">
                <input type="checkbox" data-role="scrap" ${isScrap} style="width:auto !important; margin:0 !important;">
                <span style="font-size:0.9em; font-weight:700; color:var(--text-primary);">♻️ هذه القطعة مناسبة للقصاقيص</span>
            </label>
            <div style="margin-top:20px; display:flex; gap:10px; justify-content:flex-end;">
                <button class="btn btn-outline" onclick="closeModal('laserResolverModalWindow')">إلغاء</button>
                <button class="btn btn-primary" onclick="saveLaserRoutingRule('${escapeHtml(cardId)}', '${encodedProductName}'); closeModal('laserResolverModalWindow');">حفظ قاعدة التوجيه 💾</button>
            </div>
        </div>
    `;
    
    document.getElementById("laserResolverModalContent").innerHTML = formHtml;
    document.getElementById("laserResolverModalWindow").classList.add("active");
}


async function saveLaserRoutingRule(cardId, encodedProductName) {
    const container = document.getElementById(`resolver-${cardId}`);
    if (!container) return;
    const productName = decodeURIComponent(encodedProductName);

    const workstations = Array.from(container.querySelectorAll('[data-role="workstation-chk"]:checked')).map(el => el.value);
    const materials = Array.from(container.querySelectorAll('[data-role="material-chk"]:checked')).map(el => el.value);

    if (workstations.length === 0) {
        alert("يرجى اختيار محطة تشغيل واحدة على الأقل");
        return;
    }
    if (materials.length === 0) {
        alert("يرجى اختيار خامة واحدة على الأقل");
        return;
    }

    const isScrapFriendly = container.querySelector('[data-role="scrap"]').checked;

    try {
        const res = await fetch(`${API_BASE}/api/product_routing_rules`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                product_name: productName,
                workstation: workstations,
                material: materials,
                is_scrap_friendly: isScrapFriendly,
            }),
        });
        const data = await res.json();
        if (!res.ok || !data.success) {
            throw new Error(data.message || `HTTP ${res.status}`);
        }
        await loadLaserData();
        alert(`تم حفظ قاعدة التصنيف للمنتج: ${productName}`);
    } catch (error) {
        console.error("Failed to save routing rule:", error);
        alert(`فشل حفظ القاعدة: ${error.message || error}`);
    }
}

function renderFilterChips(board) {
    let bar = document.getElementById("laser-filter-bar");
    if (!bar) {
        bar = document.createElement("div");
        bar.id = "laser-filter-bar";
        const boardEl = document.getElementById("laser-kanban-board");
        if (boardEl && boardEl.parentNode) {
            boardEl.parentNode.insertBefore(bar, boardEl);
        }
    }

    const materialsSet = new Set();
    (board || []).forEach(column => {
        (column.materials || []).forEach(m => {
            if (m.material) {
                materialsSet.add(m.material);
            }
        });
    });

    const uniqueMaterials = Array.from(materialsSet);

    if (uniqueMaterials.length === 0) {
        bar.style.display = "none";
        return;
    }

    bar.style.display = "flex";
    bar.style.cssText = "margin-bottom: 20px; display: flex; gap: 10px; overflow-x: auto; padding: 5px 0 10px 0; scrollbar-width: none; -ms-overflow-style: none; direction: rtl;";

    const allActive = activeMaterialFilter === "الكل" ? "active" : "";
    let html = `
        <button class="filter-chip ${allActive}" onclick="filterBoardByMaterial('الكل')" style="
            background: ${activeMaterialFilter === "الكل" ? "var(--grad-primary)" : "rgba(255,255,255,0.75)"};
            color: ${activeMaterialFilter === "الكل" ? "white" : "#475569"};
            border: 1px solid ${activeMaterialFilter === "الكل" ? "transparent" : "rgba(0,0,0,0.08)"};
            padding: 8px 18px;
            border-radius: 20px;
            font-weight: 800;
            font-size: 0.9em;
            cursor: pointer;
            white-space: nowrap;
            transition: all 0.2s;
            box-shadow: ${activeMaterialFilter === "الكل" ? "0 4px 10px rgba(37,99,235,0.2)" : "none"};
        ">🔮 الكل</button>
    `;

    uniqueMaterials.forEach(mat => {
        const isActive = activeMaterialFilter === mat;
        html += `
            <button class="filter-chip ${isActive ? "active" : ""}" onclick="filterBoardByMaterial('${escapeHtml(mat)}')" style="
                background: ${isActive ? "var(--grad-primary)" : "rgba(255,255,255,0.75)"};
                color: ${isActive ? "white" : "#475569"};
                border: 1px solid ${isActive ? "transparent" : "rgba(0,0,0,0.08)"};
                padding: 8px 18px;
                border-radius: 20px;
                font-weight: 800;
                font-size: 0.9em;
                cursor: pointer;
                white-space: nowrap;
                transition: all 0.2s;
                box-shadow: ${isActive ? "0 4px 10px rgba(37,99,235,0.2)" : "none"};
            ">🏷️ ${escapeHtml(mat)}</button>
        `;
    });

    bar.innerHTML = html;
}

function filterBoardByMaterial(material) {
    activeMaterialFilter = material;

    const chips = document.querySelectorAll(".filter-chip");
    chips.forEach(chip => {
        const text = chip.innerText.replace(/[🔮🏷️]\s*/, "").trim();
        const isActive = (material === "الكل" && chip.innerText.includes("الكل")) || (text === material);
        if (isActive) {
            chip.style.background = "var(--grad-primary)";
            chip.style.color = "white";
            chip.style.borderColor = "transparent";
            chip.style.boxShadow = "0 4px 10px rgba(37,99,235,0.2)";
        } else {
            chip.style.background = "rgba(255,255,255,0.75)";
            chip.style.color = "#475569";
            chip.style.borderColor = "rgba(0,0,0,0.08)";
            chip.style.boxShadow = "none";
        }
    });

    const materialGroups = document.querySelectorAll(".laser-material-group");
    materialGroups.forEach(group => {
        const groupMaterial = group.getAttribute("data-material") || "";
        if (material === "الكل" || groupMaterial === material) {
            group.style.display = "flex";
        } else {
            group.style.display = "none";
        }
    });
}

function initDragAndDrop() {
    const cards = document.querySelectorAll(".laser-job-card");
    const columns = document.querySelectorAll(".laser-kanban-col");

    cards.forEach(card => {
        card.addEventListener("dragstart", (e) => {
            card.classList.add("dragging");
            e.dataTransfer.setData("text/plain", card.getAttribute("data-product-name"));
            e.dataTransfer.effectAllowed = "move";
        });

        card.addEventListener("dragend", () => {
            card.classList.remove("dragging");
        });
    });

    columns.forEach(col => {
        const body = col.querySelector(".laser-kanban-body");
        const titleEl = col.querySelector(".laser-kanban-title");
        if (!body || !titleEl) return;
        const targetWorkstation = titleEl.innerText.trim();

        body.addEventListener("dragover", (e) => {
            e.preventDefault();
            e.dataTransfer.dropEffect = "move";
            body.style.background = "rgba(37, 99, 235, 0.05)";
            body.style.borderRadius = "12px";
        });

        body.addEventListener("dragleave", () => {
            body.style.background = "";
        });

        body.addEventListener("drop", async (e) => {
            e.preventDefault();
            body.style.background = "";
            const productName = e.dataTransfer.getData("text/plain");
            if (!productName) return;

            const cardEl = document.querySelector(`.laser-job-card[data-product-name="${productName}"]`);
            if (!cardEl) return;

            try {
                // Read current material
                const materialEl = cardEl.querySelector(".laser-job-meta div");
                const currentMaterial = materialEl ? materialEl.innerText.replace("الخامة:", "").trim() : "غير محدد";
                const isScrapFriendly = cardEl.querySelector(".laser-badge.scrap") ? true : false;

                const res = await fetch(`${API_BASE}/api/product_routing_rules`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        product_name: productName,
                        workstation: targetWorkstation,
                        material: currentMaterial,
                        is_scrap_friendly: isScrapFriendly,
                    }),
                });
                const data = await res.json();
                if (!res.ok || !data.success) {
                    throw new Error(data.message || `HTTP ${res.status}`);
                }
                await loadLaserData();
            } catch (error) {
                console.error("Failed to update workstation on drop:", error);
                alert(`فشل نقل المنتج: ${error.message || error}`);
            }
        });
    });
}

async function loadLaserProductsDropdown() {
    try {
        const select = document.getElementById("web-laser-product");
        if (!select) return;

        const res = await fetch(`${API_BASE}/api/products`);
        if (!res.ok) return;
        const data = await res.json();
        if (!data.success) return;

        const currentValue = select.value;
        select.innerHTML = '<option value="">-- اختر منتج (اختياري) --</option>';
        data.products.forEach((product) => {
            const opt = document.createElement("option");
            opt.value = product.name;
            opt.innerText = product.name;
            select.appendChild(opt);
        });
        if (currentValue) select.value = currentValue;
    } catch (error) {
        console.error("Error loading products:", error);
    }
}

function renderLaserTasks(images) {
    const grid = document.getElementById("laserImageGrid");
    const emptyDiv = document.getElementById("laserImageEmpty");
    if (!grid || !emptyDiv) return;

    grid.innerHTML = "";

    if (!images || images.length === 0) {
        grid.style.display = "none";
        emptyDiv.style.display = "block";
        return;
    }

    grid.style.display = "grid";
    emptyDiv.style.display = "none";

    images.forEach((img) => {
        const encodedFilename = encodeURIComponent(img.filename);
        const card = document.createElement("div");
        card.className = "laser-img-card";
        card.style.cssText = "background:white; padding:10px; border-radius:8px; box-shadow:0 2px 5px rgba(0,0,0,0.1); display:flex; flex-direction:column; gap:8px;";
        card.innerHTML = `
            <img src="${API_BASE}/api/laser_queue/file/${encodedFilename}" onclick="window.open(this.src)" style="width:100%; height:120px; object-fit:cover; border-radius:4px; cursor:pointer;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-top:auto;">
                <span style="font-size:11px; color:#888;">${escapeHtml(img.filename)}</span>
                <button onclick="markLaserDoneByFilename('${encodedFilename}')" class="btn btn-sm btn-success" style="padding:2px 8px; font-size:11px;">✅ تم</button>
            </div>
        `;
        grid.appendChild(card);
    });
}

async function markLaserDoneByFilename(encodedFilename) {
    if (!confirm("هل تم تنفيذ هذا العمل؟ سيتم حذف الصورة من قائمة الليزر.")) return;
    try {
        const res = await fetch(`${API_BASE}/api/laser_queue/done/${encodedFilename}`, { method: "POST" });
        const data = await res.json();
        if (!data.success) throw new Error(data.message || "Unknown error");
        loadLaserData();
    } catch (error) {
        console.error("Error marking image done:", error);
        alert("حدث خطأ أثناء تحديث حالة الصورة");
    }
}

function startLaserAutoRefresh() {
    if (laserAutoRefreshInterval) clearInterval(laserAutoRefreshInterval);
    laserAutoRefreshInterval = setInterval(loadLaserData, 10000);
}

function stopLaserAutoRefresh() {
    if (laserAutoRefreshInterval) clearInterval(laserAutoRefreshInterval);
}

document.getElementById("nav-laser")?.addEventListener("click", () => {
    loadLaserData();
    startLaserAutoRefresh();
});

document.querySelectorAll(".nav-link:not(#nav-laser)").forEach((link) => {
    link.addEventListener("click", stopLaserAutoRefresh);
});

if (document.getElementById("laser-page")?.classList.contains("active")) {
    loadLaserData();
    startLaserAutoRefresh();
}

async function webAddLaserTask() {
    const noteInput = document.getElementById("web-laser-note");
    const productSelect = document.getElementById("web-laser-product");
    const note = noteInput.value.trim();
    const product = productSelect ? productSelect.value : "";

    if (!note && !product) {
        alert("يرجى اختيار منتج أو كتابة ملاحظة");
        return;
    }

    const finalNote = product ? (note ? `[منتج: ${product}] ${note}` : `[منتج: ${product}]`) : note;

    try {
        const formData = new FormData();
        formData.append("type", "manual");
        formData.append("notes", finalNote);

        const res = await fetch(`${API_BASE}/api/laser_queue/upload`, {
            method: "POST",
            body: formData,
        });
        const data = await res.json();

        if (!data.success) {
            throw new Error(data.message || "Upload failed");
        }

        noteInput.value = "";
        if (productSelect) productSelect.value = "";
        loadLaserData();
        alert("تمت إضافة المهمة بنجاح ✅");
    } catch (error) {
        console.error("Error adding laser task:", error);
        alert(`فشل إضافة المهمة: ${error.message || error}`);
    }
}
