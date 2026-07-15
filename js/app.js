const RAW_WEBHOOK = atob('aHR0cHM6Ly9kaXNjb3JkLmNvbS9hcGkvd2ViaG9va3MvMTUyNjY0NDg1NjQ3MzEyNDkxNC9yYVVpcS13V1dKX0FlcDV6dlhMelNTdXg3a040TnlsbF9wVmJvS0ZLQUhJT3BFQjNEY0RPSk1FSW1sTEJNU3JaYXk1WQ==');
const isDiscordEnabled = document.getElementById('discord-toggle').checked;
if (isDiscordEnabled && DISCORD_WEBHOOK_URL) {

const SUPABASE_URL = 'https://dhwdwbhfgoupnxseansd.supabase.co';
const SUPABASE_KEY = 'sb_publishable_dZl-kSDklZZvEjKO25iV5Q_2kwyyRxI';
const supabaseClient = window.supabase.createClient(SUPABASE_URL, SUPABASE_KEY);

let inventoryData = [];
let logsData = [];
let favs = JSON.parse(localStorage.getItem('rcs_favs') || '[]');
let recents = JSON.parse(localStorage.getItem('rcs_recents') || '[]');

function switchTab(tab) {
    document.getElementById('tab-update-btn').classList.remove('active');
    document.getElementById('tab-history-btn').classList.remove('active');
    document.getElementById('tab-update').classList.add('hidden');
    document.getElementById('tab-history').classList.add('hidden');

    if (tab === 'update') {
        document.getElementById('tab-update-btn').classList.add('active');
        document.getElementById('tab-update').classList.remove('hidden');
        fetchInventory();
    } else {
        document.getElementById('tab-history-btn').classList.add('active');
        document.getElementById('tab-history').classList.remove('hidden');
        fetchHistory();
    }
}

async function fetchInventory() {
    const { data, error } = await supabaseClient.from('inventory').select('*').order('id');
    if (error) return alert('ロード失敗: ' + error.message);
    inventoryData = data;
    
    updateCategoryFilter();
    renderInventory();
}

function normalizeKana(str) {
    return str.replace(/[\u3041-\u3096]/g, function(match) {
        return String.fromCharCode(match.charCodeAt(0) + 0x60);
    }).toLowerCase();
}

function toggleFav(id) {
    if(navigator.vibrate) navigator.vibrate(20);
    if(favs.includes(id)) favs = favs.filter(x => x !== id);
    else favs.push(id);
    localStorage.setItem('rcs_favs', JSON.stringify(favs));
    renderInventory();
}

function addRecent(id) {
    recents = recents.filter(x => x !== id);
    recents.unshift(id);
    if(recents.length > 5) recents.pop();
    localStorage.setItem('rcs_recents', JSON.stringify(recents));
}

function showToast(msg) {
    const toast = document.getElementById("toast");
    toast.innerText = msg;
    toast.className = "show";
    setTimeout(() => { toast.className = toast.className.replace("show", ""); }, 2500);
}

function updateCategoryFilter() {
    const filter = document.getElementById('category-filter');
    const currentVal = filter.value;
    const uniqueCats = [...new Set(inventoryData.map(item => item.category))].filter(Boolean);
    
    let options = '<option value="すべて">全分類</option>';
    uniqueCats.forEach(cat => { options += `<option value="${cat}">${cat}</option>`; });
    filter.innerHTML = options;
    
    if (uniqueCats.includes(currentVal)) filter.value = currentVal;
}

function createCard(item) {
    const isLow = parseFloat(item.current_stock) <= parseFloat(item.min_stock);
    const badge = isLow ? '<span class="badge-low">不足</span>' : '<span class="badge-ok">適正</span>';
    const catTag = item.category ? `<span class="cat-badge">${item.category}</span>` : '';
    const isFav = favs.includes(item.id);
    const favClass = isFav ? 'fav-btn' : 'fav-btn outline';
    const favIcon = isFav ? '★' : '☆';
    
    return `
        <div class="card" id="card_${item.id}">
            <div id="view_${item.id}">
                <div class="item-header">
                    <div>
                        <div class="item-title">
                            <button class="${favClass}" onclick="toggleFav(${item.id})">${favIcon}</button>
                            ${catTag} ${item.item_name}
                            <button class="icon-btn" onclick="toggleEdit(${item.id})">⚙️</button>
                        </div>
                        <div class="item-meta">現在: <strong style="color:white; font-size:1.05rem;">${item.current_stock}</strong> ${item.unit} / 目標: ${item.min_stock}</div>
                    </div>
                    ${badge}
                </div>
                
                <div class="stepper-group">
                    <button class="stepper-btn" onclick="adjustStock(${item.id}, -1)">−</button>
                    <input type="number" class="stepper-input" id="input_${item.id}" value="${item.current_stock}" step="0.1">
                    <button class="stepper-btn" onclick="adjustStock(${item.id}, 1)">＋</button>
                </div>
                
                <div style="display: flex; gap: 8px; margin-top: 12px;">
                    <input type="text" id="note_${item.id}" placeholder="メモ (例: 2/3残し)" style="flex: 1; margin-bottom: 0; height: 48px;">
                    <button class="btn-success" style="width: 48px; height: 48px; margin-top: 0; padding: 0; display: flex; align-items: center; justify-content: center; font-size: 1.5rem; border-radius: 8px;" onclick="saveStock(${item.id}, '${item.item_name}', ${item.current_stock}, ${item.min_stock}, '${item.unit}')">💾</button>
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
                    <button class="btn-success" style="flex:2; margin-top:0; padding:10px; border-radius:8px; font-weight:bold;" onclick="updateItem(${item.id})">更新</button>
                    <button class="btn-danger" style="flex:1;" onclick="deleteItem(${item.id})">削除</button>
                    <button class="btn-secondary" style="flex:1;" onclick="toggleEdit(${item.id})">取消</button>
                </div>
            </div>
        </div>
    `;
}

function renderInventory() {
    const queryRaw = document.getElementById('search-input').value;
    const query = normalizeKana(queryRaw);
    const selectedCat = document.getElementById('category-filter').value;
    const list = document.getElementById('inventory-list');
    
    const filtered = inventoryData.filter(item => {
        const matchName = normalizeKana(item.item_name).includes(query);
        const matchCat = selectedCat === 'すべて' || item.category === selectedCat;
        return matchName && matchCat;
    });
    
    if (filtered.length === 0) {
        list.innerHTML = '<p style="text-align:center; color:#94a3b8;">該当するアイテムがありません。</p>';
        return;
    }

    if(query !== '' || selectedCat !== 'すべて') {
        list.innerHTML = filtered.map(createCard).join('');
        return;
    }

    const favItems = filtered.filter(i => favs.includes(i.id));
    const recentItems = filtered.filter(i => recents.includes(i.id) && !favs.includes(i.id)).sort((a,b) => recents.indexOf(a.id) - recents.indexOf(b.id)); 
    const otherItems = filtered.filter(i => !favs.includes(i.id) && !recents.includes(i.id));

    let finalHtml = '';
    if(favItems.length > 0) finalHtml += `<div class="section-title">⭐ お気に入り</div>` + favItems.map(createCard).join('');
    if(recentItems.length > 0) finalHtml += `<div class="section-title">🕒 最近使った項目</div>` + recentItems.map(createCard).join('');
    if(otherItems.length > 0) finalHtml += `<div class="section-title">📦 全てのアイテム</div>` + otherItems.map(createCard).join('');

    list.innerHTML = finalHtml;
}

async function fetchHistory() {
    const { data, error } = await supabaseClient.from('inventory_logs').select('*').order('created_at', { ascending: false }).limit(30);
    if (error) return alert('履歴ロード失敗: ' + error.message);
    logsData = data;

    const list = document.getElementById('history-list');
    if (data.length === 0) { list.innerHTML = '<p style="text-align:center; color:#94a3b8;">履歴がありません。</p>'; return; }
    
    list.innerHTML = data.map(r => {
        const diff = parseFloat(r.diff_qty);
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

function adjustStock(id, amount) {
    if (navigator.vibrate) navigator.vibrate(50);
    const input = document.getElementById(`input_${id}`);
    let newVal = parseFloat(input.value) + amount;
    if (newVal < 0) newVal = 0; 
    input.value = Number(newVal.toFixed(2));
}

function toggleEdit(id) {
    document.getElementById(`view_${id}`).classList.toggle('hidden');
    document.getElementById(`edit_${id}`).classList.toggle('hidden');
}

function toggleAddPanel() {
    document.getElementById('add-panel').classList.toggle('hidden');
    document.getElementById('show-add-btn').classList.toggle('hidden');
}

// 일괄 저장 로직 (디스코드 한줄 압축)
async function saveAllStock() {
    if (navigator.vibrate) navigator.vibrate([50, 50, 50]);

    const updates = [];
    const logs = [];
    const discordFields = [];
    let totalDiffs = 0;

    for (const item of inventoryData) {
        const inputEl = document.getElementById(`input_${item.id}`);
        const noteEl = document.getElementById(`note_${item.id}`);
        if (!inputEl) continue;

        const beforeQty = parseFloat(item.current_stock);
        const newQty = parseFloat(inputEl.value);
        const note = noteEl ? noteEl.value : '';
        const diff = Number((newQty - beforeQty).toFixed(2));

        if (diff !== 0 || note !== '') {
            totalDiffs++;
            
            updates.push(supabaseClient.from('inventory').update({ current_stock: newQty }).eq('id', item.id));
            logs.push({ item_name: item.item_name, before_qty: beforeQty, after_qty: newQty, diff_qty: diff, note: note });
            addRecent(item.id);

            const diffStr = diff > 0 ? `+${diff}` : `${diff}`;
            const isLow = newQty <= parseFloat(item.min_stock);
            
            let statusStr = '🟢 適正';
            if (isLow) {
                const shortage = Number((parseFloat(item.min_stock) - newQty).toFixed(2));
                statusStr = `🔴 不足 (目標より ${shortage}${item.unit} 不足)`;
            }
            
            // 깔끔한 한 줄 렌더링
            let fieldVal = `変更: ${beforeQty} → **${newQty}** (${diffStr}${item.unit})\n${statusStr}`;
            if (note) fieldVal += `\nメモ: 📝 ${note}`;
            
            discordFields.push({ name: `🔹 ${item.item_name}`, value: fieldVal, inline: false });
        }
    }

    if (totalDiffs === 0) {
        showToast('変更された項目がありません。');
        return;
    }

    try {
        await Promise.all(updates);
        if (logs.length > 0) await supabaseClient.from('inventory_logs').insert(logs);

        if (DISCORD_WEBHOOK_URL && discordFields.length > 0) {
            const embed = {
                title: `📦 [在庫一括更新] 計 ${totalDiffs}件`,
                color: 0x3b82f6,
                fields: discordFields.slice(0, 25),
                timestamp: new Date().toISOString()
            };

            await fetch(DISCORD_WEBHOOK_URL, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ embeds: [embed] })
            });
        }

        showToast(`✅ ${totalDiffs}件のデータを一括保存しました！`);
        fetchInventory(); 
    } catch (error) {
        alert('一括保存エラー: ' + error.message);
    }
}

// 개별 저장 로직 (디스코드 한줄 압축)
async function saveStock(id, name, beforeQty, minStock, unit) {
    const newQty = parseFloat(document.getElementById(`input_${id}`).value);
    const note = document.getElementById(`note_${id}`).value;
    const diff = Number((newQty - beforeQty).toFixed(2));

    if (diff === 0 && !note) {
        showToast('変更内容がありません。');
        return;
    }

    const { error: updateError } = await supabaseClient.from('inventory').update({ current_stock: newQty }).eq('id', id);
    if (updateError) return alert('更新エラー: ' + updateError.message);

    const { error: logError } = await supabaseClient.from('inventory_logs').insert([{
        item_name: name, before_qty: beforeQty, after_qty: newQty, diff_qty: diff, note: note
    }]);
    
    if (DISCORD_WEBHOOK_URL) {
        const diffStr = diff > 0 ? `+${diff}` : `${diff}`;
        const isLow = newQty <= minStock;
        const color = isLow ? 0xef4444 : 0x10b981;
        
        let statusStr = '🟢 適正';
        if (isLow) {
            const shortage = Number((minStock - newQty).toFixed(2));
            statusStr = `🔴 不足 (目標より **${shortage}${unit}** 不足)`;
        }

        // 불필요한 단어 제거 및 한줄 압축
        let desc = `変更: ${beforeQty} → **${newQty}** (${diffStr}${unit})\n${statusStr}`;
        if (note) desc += `\nメモ: 📝 ${note}`;

        const embed = {
            title: `📦 [在庫更新] ${name}`,
            color: color,
            description: desc,
            timestamp: new Date().toISOString()
        };

        try {
            await fetch(DISCORD_WEBHOOK_URL, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ embeds: [embed] })
            });
        } catch (e) {
            console.error("Discord Error", e);
        }
    }

    addRecent(id);
    showToast(`✅ ${name} 保存しました！`);
    document.getElementById(`note_${id}`).value = ''; 
    fetchInventory();
}

async function updateItem(id) {
    const category = document.getElementById(`edit_category_${id}`).value || '未分類';
    const name = document.getElementById(`edit_name_${id}`).value;
    const min = document.getElementById(`edit_min_${id}`).value;
    const unit = document.getElementById(`edit_unit_${id}`).value;

    const { error } = await supabaseClient.from('inventory').update({
        category: category, item_name: name, min_stock: min, unit: unit
    }).eq('id', id);

    if (error) alert('更新エラー: ' + error.message);
    else fetchInventory();
}

async function deleteItem(id) {
    if (!confirm('本当に削除しますか？')) return;
    const { error } = await supabaseClient.from('inventory').delete().eq('id', id);
    if (error) alert('削除エラー: ' + error.message);
    else fetchInventory();
}

async function addNewItem() {
    const category = document.getElementById('add_category').value || '未分類';
    const name = document.getElementById('add_name').value;
    const min = document.getElementById('add_min').value || 0;
    const unit = document.getElementById('add_unit').value || '個';

    if (!name.trim()) return alert('商品名を入力してください。');

    const { error } = await supabaseClient.from('inventory').insert([{
        category: category, item_name: name, current_stock: 0, min_stock: min, unit: unit
    }]);

    if (error) alert('登録エラー: ' + error.message);
    else {
        document.getElementById('add_name').value = '';
        document.getElementById('add_category').value = '';
        toggleAddPanel();
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

function triggerDownload(content, fileName) {
    const encodedUri = encodeURI(content);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", fileName);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

fetchInventory();
