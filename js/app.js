/* =====================================================================
   5. CORE LOGIC (Fetch, Render, Actions)
   ===================================================================== */
// isSilent 파라미터를 추가하여 팝업 없는 백그라운드 동기화 지원
async function fetchInventory(isSilent = false) {
    const list = $("inventory-list");
    
    if (list && inventoryData.length === 0 && !isSilent) {
        list.innerHTML = `<p style="text-align:center; color:#94a3b8;">${TEXT.loading}</p>`;
    }

    // isSilent가 false일 때만(최초 로딩 등) 로딩 화면 켜기
    if (!isSilent) toggleLoading(true);

    const { data, error } = await supabaseClient.from('inventory').select('*').order('id');
    
    if (!isSilent) toggleLoading(false);
    updateSyncTime();

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

async function fetchHistory(isSilent = false) {
    const list = $("history-list");
    
    if (list && logsData.length === 0 && !isSilent) {
        list.innerHTML = `<p style="text-align:center; color:#94a3b8;">${TEXT.loading}</p>`;
    }
    
    if (!isSilent) toggleLoading(true);

    const { data, error } = await supabaseClient.from('inventory_logs').select('*').order('created_at', { ascending: false }).limit(30);
    
    if (!isSilent) toggleLoading(false);
    updateSyncTime();

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
        fetchInventory(); // 탭 이동 시에는 로딩 애니메이션 노출
    } else {
        $("tab-history-btn").classList.add('active');
        $("tab-history").classList.remove('hidden');
        fetchHistory(); // 탭 이동 시에는 로딩 애니메이션 노출
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

    // [핵심] 낙관적 업데이트: DB 응답을 기다리지 않고 로컬 데이터를 먼저 고친 후 화면을 즉시 갱신
    item.current_stock = newQty;
    addRecent(id);
    renderInventory();

    // 백그라운드 서버 통신 진행
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

    showToast(`✅ ${item.item_name} ${TEXT.save}`);
    
    // 조용히 백그라운드 데이터 재동기화 (화면 깜빡임 없음)
    fetchInventory(true);
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
            
            // 낙관적 업데이트 즉시 적용
            item.current_stock = newQty;
            addRecent(item.id);

            updates.push(supabaseClient.from('inventory').update({ current_stock: newQty }).eq('id', item.id));
            logs.push({ item_name: item.item_name, before_qty: beforeQty, after_qty: newQty, diff_qty: diff, note: note });

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

    // 화면 즉시 갱신
    renderInventory();

    try {
        await Promise.all(updates);
        if (logs.length > 0) await supabaseClient.from('inventory_logs').insert(logs);

        if (discordFields.length > 0) {
            const embed = buildDiscordEmbed(`📦 [在庫一括更新] 計 ${totalDiffs}件`, 0x3b82f6, "", discordFields.slice(0, MAX_DISCORD_FIELDS));
            await sendDiscord([embed]);
        }

        showToast(`✅ ${totalDiffs}件のデータを一括保存しました！`);
        fetchInventory(true); // 조용히 재동기화
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
        fetchInventory(true); // 아이템 수정은 백그라운드 동기화
    }
}

async function deleteItem(id) {
    if (!confirm(TEXT.delConfirm)) return;
    const { error } = await supabaseClient.from('inventory').delete().eq('id', id);
    if (error) showToast(`${TEXT.errDel}: ${error.message}`);
    else fetchInventory(true);
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
        fetchInventory(true);
    }
}
