/* =====================================================================
   1. CONSTANTS & STATE
   ===================================================================== */
const MAX_RECENTS = 5;
const TOAST_TIME = 2500;
const MAX_DISCORD_FIELDS = 25;

const TEXT = {
    save: "保存しました",
    low: "不足",
    ok: "適正",
    change: "変更",
    noChange: "変更された項目がありません。",
    delConfirm: "本当に削除しますか？",
    loading: "Loading...",
    noData: "該当するアイテムがありません。",
    noHistory: "履歴がありません。",
    reqName: "商品名を入力してください。",
    errLoad: "ロード失敗",
    errSave: "保存エラー",
    errDel: "削除エラー",
    errUpdate: "更新エラー"
};

const supabaseClient = window.supabase.createClient(window.CONFIG.SUPABASE_URL, window.CONFIG.SUPABASE_KEY);

let inventoryData = [];
let logsData = [];
let favs = JSON.parse(localStorage.getItem('rcs_favs') || '[]');
let recents = JSON.parse(localStorage.getItem('rcs_recents') || '[]');
let toastTimer;

// 로딩 화면 제어
function toggleLoading(show) {
    const overlay = $("loading-overlay");
    if (overlay) {
        if (show) overlay.classList.remove("hidden");
        else overlay.classList.add("hidden");
    }
}

// 최종 동기화 시간 업데이트
function updateSyncTime() {
    const info = $("sync-info");
    if (info) {
        const now = new Date();
        info.innerText = `最終同期 : ${now.toLocaleTimeString('ja-JP', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}`;
    }
}
/* =====================================================================
   2. UTILITIES
   ===================================================================== */
const $ = id => document.getElementById(id);
const num = value => Number(value);

function showToast(msg) {
    const toast = $("toast");
    if (!toast) return;
    clearTimeout(toastTimer);
    toast.innerText = msg;
    toast.classList.add("show");
    toastTimer = setTimeout(() => {
        toast.classList.remove("show");
    }, TOAST_TIME);
}

function normalizeKana(str = "") {
    return str.trim()
              .replace(/[\u3041-\u3096]/g, c => String.fromCharCode(c.charCodeAt(0) + 0x60))
              .toLowerCase();
}

function addRecent(id) {
    recents = recents.filter(x => x !== id);
    recents.unshift(id);
    if (recents.length > MAX_RECENTS) recents.pop();
    localStorage.setItem('rcs_recents', JSON.stringify(recents));
}

function triggerDownload(content, fileName) {
    const encodedUri = encodeURI(content);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", fileName);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

/* =====================================================================
   3. DISCORD INTEGRATION
   ===================================================================== */
function buildDiscordEmbed(title, color, description, fields = []) {
    return { title, color, description, fields, timestamp: new Date().toISOString() };
}

async function sendDiscord(embeds) {
    const toggle = $("discord-toggle");
    if (!toggle || !toggle.checked || !window.CONFIG.DISCORD_RELAY_URL) return;

    try {
        await fetch(window.CONFIG.DISCORD_RELAY_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ embeds })
        });
    } catch (e) {
        console.error("Discord Error", e);
    }
}

/* =====================================================================
   4. UI COMPONENTS (Card & Sections)
   ===================================================================== */
function createBadge(item) {
    const isLow = num(item.current_stock) <= num(item.min_stock);
    return isLow ? `<span class="badge-low">${TEXT.low}</span>` : `<span class="badge-ok">${TEXT.ok}</span>`;
}

function createFavoriteButton(item) {
    const isFav = favs.includes(item.id);
    return `<button class="fav-btn ${isFav ? '' : 'outline'}" data-action="toggleFav" data-id="${item.id}">${isFav ? '★' : '☆'}</button>`;
}

function createCard(item) {
    const catTag = item.category ? `<span class="cat-badge">${item.category}</span>` : '';
    return `
        <div class="card" id="card_${item.id}">
            <div id="view_${item.id}">
                <div class="item-header">
                    <div>
                        <div class="item-title">
                            ${createFavoriteButton(item)}
                            ${catTag} ${item.item_name}
                            <button class="icon-btn" data-action="toggleEdit" data-id="${item.id}">⚙️</button>
                        </div>
                        <div class="item-meta">現在: <strong style="color:white; font-size:1.05rem;">${item.current_stock}</strong> ${item.unit} / 目標: ${item.min_stock}</div>
                    </div>
                    ${createBadge(item)}
                </div>
                
                <div class="stepper-group">
                    <button class="stepper-btn" data-action="adjustStock" data-id="${item.id}" data-amount="-1">−</button>
                    <input type="number" class="stepper-input" id="input_${item.id}" value="${item.current_stock}" step="0.1">
                    <button class="stepper-btn" data-action="adjustStock" data-id="${item.id}" data-amount="1">＋</button>
                </div>
                
                <div style="display: flex; gap: 8px; margin-top: 12px;">
                    <input type="text" id="note_${item.id}" placeholder="メモ (例: 2/3残し)" style="flex: 1; margin-bottom: 0; height: 48px;">
                    <button class="btn-success" style="width: 48px; height: 48px; margin-top: 0; padding: 0; display: flex; align-items: center; justify-content: center; font-size: 1.5rem; border-radius: 8px;" data-action="saveStock" data-id="${item.id}">💾</button>
                </div>
            </div>

            <div id="edit_${item.id}" class="hidden">
                <div style="display:flex; gap:8px; margin-bottom:8px;">
                    <div style="flex:1;">
                        <label style="font-size:0.8rem; color:#94a3b8;">分類</label>
                        <input type="text" id="edit_category_${item.id}" value="${item.category || ''}" list="category-suggestions">
                    </div>
                    <div style="flex:2;">
                        <label style="font-size:0.8rem; color:#94a3b8;">商品名</label>
                        <input type="text" id="edit_name_${item.id}" value="${item.item_name}">
                    </div>
                </div>
                <div style="display:flex; gap:8px; margin-bottom:12px;">
                    <div style="flex:1;">
                        <label style="font-size:0.8rem; color:#94a3b8;">目標値</label>
                        <input type="number" id="edit_min_${item.id}" value="${item.min_stock}" step="0.5">
                    </div>
                    <div style="flex:1;">
                        <label style="font-size:0.8rem; color:#94a3b8;">単位</label>
                        <input type="text" id="edit_unit_${item.id}" value="${item.unit}">
                    </div>
                </div>
                <div style="display:flex; gap:8px;">
                    <button class="btn-success" style="flex:2; margin-top:0; padding:10px; border-radius:8px; font-weight:bold;" data-action="updateItem" data-id="${item.id}">更新</button>
                    <button class="btn-danger" style="flex:1;" data-action="deleteItem" data-id="${item.id}">削除</button>
                    <button class="btn-secondary" style="flex:1;" data-action="toggleEdit" data-id="${item.id}">取消</button>
                </div>
            </div>
        </div>
    `;
}

function renderSection(title, items) {
    if (items.length === 0) return '';
    return `<div class="section-title">${title}</div>${items.map(createCard).join('')}`;
}

/* =====================================================================
   5. CORE LOGIC (Fetch, Render, Actions)
   ===================================================================== */
async function fetchInventory() {
    const list = $("inventory-list");
    if (list) list.innerHTML = `<p style="text-align:center; color:#94a3b8;">${TEXT.loading}</p>`;

    const { data, error } = await supabaseClient.from('inventory').select('*').order('id');
    if (error) {
        showToast(`${TEXT.errLoad}: ${error.message}`);
        return;
    }
    
    inventoryData = data;
    updateCategoryFilter();
    renderInventory();
}

function renderInventory() {
    const list = $("inventory-list");
    if (!list) return;

    const queryRaw = $("search-input") ? $("search-input").value : "";
    const query = normalizeKana(queryRaw);
    const filterEl = $("category-filter");
    const selectedCat = filterEl ? filterEl.value : 'すべて';
    
    const filtered = inventoryData.filter(item => {
        const matchName = normalizeKana(item.item_name).includes(query);
        const matchCat = selectedCat === 'すべて' || item.category === selectedCat;
        return matchName && matchCat;
    });
    
    if (filtered.length === 0) {
        list.innerHTML = `<p style="text-align:center; color:#94a3b8;">${TEXT.noData}</p>`;
        return;
    }

    if (query !== '' || selectedCat !== 'すべて') {
        list.innerHTML = filtered.map(createCard).join('');
        return;
    }

    const favItems = filtered.filter(i => favs.includes(i.id));
    const recentItems = filtered.filter(i => recents.includes(i.id) && !favs.includes(i.id)).sort((a,b) => recents.indexOf(a.id) - recents.indexOf(b.id)); 
    const otherItems = filtered.filter(i => !favs.includes(i.id) && !recents.includes(i.id));

    list.innerHTML = 
        renderSection("⭐ お気に入り", favItems) +
        renderSection("🕒 最近使った項目", recentItems) +
        renderSection("📦 全てのアイテム", otherItems);
}

function updateCategoryFilter() {
    const filter = $("category-filter");
    if (!filter) return;
    const currentVal = filter.value;
    const uniqueCats = [...new Set(inventoryData.map(item => item.category))].filter(Boolean);
    
    let options = '<option value="すべて">全分類</option>';
    uniqueCats.forEach(cat => { options += `<option value="${cat}">${cat}</option>`; });
    filter.innerHTML = options;
    
    if (uniqueCats.includes(currentVal)) filter.value = currentVal;
}

async function fetchHistory() {
    const list = $("history-list");
    if (list) list.innerHTML = `<p style="text-align:center; color:#94a3b8;">${TEXT.loading}</p>`;

    const { data, error } = await supabaseClient.from('inventory_logs').select('*').order('created_at', { ascending: false }).limit(30);
    if (error) {
        showToast(`${TEXT.errLoad}: ${error.message}`);
        return;
    }
    logsData = data;

    if (data.length === 0) {
        list.innerHTML = `<p style="text-align:center; color:#94a3b8;">${TEXT.noHistory}</p>`;
        return;
    }
    
    list.innerHTML = data.map(r => {
        const diff = num(r.diff_qty);
        const diffStr = diff > 0 ? `+${diff}` : `${diff}`;
        const diffClass = diff > 0 ? 'log-diff-plus' : 'log-diff-minus';
        const noteStr = r.note ? `<br><small style="color:#60a5fa;">📝 ${r.note}</small>` : '';
        return `
            <div class="log-item">
                <div>
                    <strong style="color:white;">${r.item_name}</strong>${noteStr}
                    <div style="font-size: 0.75rem; color: #94a3b8; margin-top:2px;">${new Date(r.created_at).toLocaleString('ja-JP')}</div>
                </div>
                <div style="text-align: right;">
                    <small style="color:#94a3b8;">${r.before_qty} → ${r.after_qty}</small>
                    <div class="${diffClass}">${diffStr}</div>
                </div>
            </div>
        `;
    }).join('');
}

/* =====================================================================
   6. CRUD & DOM INTERACTIONS
   ===================================================================== */
function adjustStock(id, amount) {
    if (navigator.vibrate) navigator.vibrate(50);
    const input = $(`input_${id}`);
    if (!input) return;
    let newVal = num(input.value) + num(amount);
    input.value = Number(Math.max(0, newVal).toFixed(2));
}

function toggleEdit(id) {
    $(`view_${id}`).classList.toggle('hidden');
    $(`edit_${id}`).classList.toggle('hidden');
}

function toggleAddPanel() {
    $("add-panel").classList.toggle('hidden');
    $("show-add-btn").classList.toggle('hidden');
}

function toggleFav(id) {
    if (navigator.vibrate) navigator.vibrate(20);
    if (favs.includes(id)) favs = favs.filter(x => x !== id);
    else favs.push(id);
    localStorage.setItem('rcs_favs', JSON.stringify(favs));
    renderInventory();
}

function switchTab(tab) {
    $("tab-update-btn").classList.remove('active');
    $("tab-history-btn").classList.remove('active');
    $("tab-update").classList.add('hidden');
    $("tab-history").classList.add('hidden');

    if (tab === 'update') {
        $("tab-update-btn").classList.add('active');
        $("tab-update").classList.remove('hidden');
        fetchInventory();
    } else {
        $("tab-history-btn").classList.add('active');
        $("tab-history").classList.remove('hidden');
        fetchHistory();
    }
}

async function saveStock(id) {
    const item = inventoryData.find(i => i.id === id);
    if (!item) return;

    const beforeQty = num(item.current_stock);
    const minStock = num(item.min_stock);
    const newQty = num($(`input_${id}`).value);
    const note = $(`note_${id}`).value;
    const diff = Number((newQty - beforeQty).toFixed(2));

    if (diff === 0 && !note) {
        showToast(TEXT.noChange);
        return;
    }

    const { error: updateError } = await supabaseClient.from('inventory').update({ current_stock: newQty }).eq('id', id);
    if (updateError) {
        showToast(`${TEXT.errSave}: ${updateError.message}`);
        return;
    }

    await supabaseClient.from('inventory_logs').insert([{
        item_name: item.item_name, before_qty: beforeQty, after_qty: newQty, diff_qty: diff, note: note
    }]);
    
    const diffStr = diff > 0 ? `+${diff}` : `${diff}`;
    const isLow = newQty <= minStock;
    let statusStr = `🟢 ${TEXT.ok}`;
    
    if (isLow) {
        const shortage = Number((minStock - newQty).toFixed(2));
        statusStr = `🔴 ${TEXT.low} (目標より **${shortage}${item.unit}** ${TEXT.low})`;
    }

    let desc = `${TEXT.change}: ${beforeQty} → **${newQty}** (${diffStr}${item.unit})\n${statusStr}`;
    if (note) desc += `\nメモ: 📝 ${note}`;

    const embed = buildDiscordEmbed(`📦 [在庫更新] ${item.item_name}`, isLow ? 0xef4444 : 0x10b981, desc);
    await sendDiscord([embed]);

    addRecent(id);
    showToast(`✅ ${item.item_name} ${TEXT.save}`);
    $(`note_${id}`).value = ''; 
    fetchInventory();
}

async function saveAllStock() {
    if (navigator.vibrate) navigator.vibrate([50, 50, 50]);

    const updates = [];
    const logs = [];
    const discordFields = [];
    let totalDiffs = 0;

    for (const item of inventoryData) {
        const inputEl = $(`input_${item.id}`);
        const noteEl = $(`note_${item.id}`);
        if (!inputEl) continue;

        const beforeQty = num(item.current_stock);
        const newQty = num(inputEl.value);
        const note = noteEl ? noteEl.value : '';
        const diff = Number((newQty - beforeQty).toFixed(2));

        if (diff !== 0 || note !== '') {
            totalDiffs++;
            updates.push(supabaseClient.from('inventory').update({ current_stock: newQty }).eq('id', item.id));
            logs.push({ item_name: item.item_name, before_qty: beforeQty, after_qty: newQty, diff_qty: diff, note: note });
            addRecent(item.id);

            const diffStr = diff > 0 ? `+${diff}` : `${diff}`;
            const isLow = newQty <= num(item.min_stock);
            let statusStr = `🟢 ${TEXT.ok}`;
            
            if (isLow) {
                const shortage = Number((num(item.min_stock) - newQty).toFixed(2));
                statusStr = `🔴 ${TEXT.low} (目標より ${shortage}${item.unit} ${TEXT.low})`;
            }
            
            let fieldVal = `${TEXT.change}: ${beforeQty} → **${newQty}** (${diffStr}${item.unit})\n${statusStr}`;
            if (note) fieldVal += `\nメモ: 📝 ${note}`;
            
            discordFields.push({ name: `🔹 ${item.item_name}`, value: fieldVal, inline: false });
        }
    }

    if (totalDiffs === 0) {
        showToast(TEXT.noChange);
        return;
    }

    try {
        await Promise.all(updates);
        if (logs.length > 0) await supabaseClient.from('inventory_logs').insert(logs);

        if (discordFields.length > 0) {
            const embed = buildDiscordEmbed(`📦 [在庫一括更新] 計 ${totalDiffs}件`, 0x3b82f6, "", discordFields.slice(0, MAX_DISCORD_FIELDS));
            await sendDiscord([embed]);
        }

        showToast(`✅ ${totalDiffs}件のデータを一括保存しました！`);
        fetchInventory(); 
    } catch (error) {
        showToast(`${TEXT.errSave}: ${error.message}`);
    }
}

async function updateItem(id) {
    const category = $(`edit_category_${id}`).value || '未分類';
    const name = $(`edit_name_${id}`).value;
    const min = $(`edit_min_${id}`).value;
    const unit = $(`edit_unit_${id}`).value;

    const { error } = await supabaseClient.from('inventory').update({
        category: category, item_name: name, min_stock: min, unit: unit
    }).eq('id', id);

    if (error) {
        showToast(`${TEXT.errUpdate}: ${error.message}`);
    } else {
        showToast(`✅ ${TEXT.save}`);
        fetchInventory();
    }
}

async function deleteItem(id) {
    if (!confirm(TEXT.delConfirm)) return;
    const { error } = await supabaseClient.from('inventory').delete().eq('id', id);
    if (error) showToast(`${TEXT.errDel}: ${error.message}`);
    else fetchInventory();
}

async function addNewItem() {
    const category = $('add_category').value || '未分類';
    const name = $('add_name').value;
    const min = $('add_min').value || 0;
    const unit = $('add_unit').value || '個';

    if (!name.trim()) return showToast(TEXT.reqName);

    const { error } = await supabaseClient.from('inventory').insert([{
        category: category, item_name: name, current_stock: 0, min_stock: min, unit: unit
    }]);

    if (error) {
        showToast(`${TEXT.errSave}: ${error.message}`);
    } else {
        $('add_name').value = '';
        $('add_category').value = '';
        toggleAddPanel();
        showToast(`✅ ${name} 追加しました`);
        fetchInventory();
    }
}

function exportCSV(type) {
    let csvContent = "data:text/csv;charset=utf-8,\uFEFF";
    if (type === 'current') {
        csvContent += "分類,商品名,現在在庫,目標値,単位\n";
        inventoryData.forEach(r => { csvContent += `"${r.category}","${r.item_name}",${r.current_stock},${r.min_stock},"${r.unit}"\n`; });
        triggerDownload(csvContent, `current_stock_${new Date().toISOString().slice(0,10)}.csv`);
    } else {
        csvContent += "時間,商品名,変更前,変更後,変動量,メモ\n";
        logsData.forEach(r => { csvContent += `"${r.created_at}","${r.item_name}",${r.before_qty},${r.after_qty},${r.diff_qty},"${r.note || ''}"\n`; });
        triggerDownload(csvContent, `inventory_logs_${new Date().toISOString().slice(0,10)}.csv`);
    }
}

/* =====================================================================
   7. EVENT DELEGATION & INITIALIZATION
   ===================================================================== */
// HTML에서 inline onclick 이벤트들을 스크립트로 중앙 관리
document.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-action]');
    if (!btn) return;
    
    const action = btn.getAttribute('data-action');
    const id = num(btn.getAttribute('data-id'));
    
    switch(action) {
        case 'toggleFav': toggleFav(id); break;
        case 'toggleEdit': toggleEdit(id); break;
        case 'adjustStock': adjustStock(id, btn.getAttribute('data-amount')); break;
        case 'saveStock': saveStock(id); break;
        case 'updateItem': updateItem(id); break;
        case 'deleteItem': deleteItem(id); break;
    }
});

// App Start
fetchInventory();
