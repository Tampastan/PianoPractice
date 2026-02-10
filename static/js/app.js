// 全局变量
let settings = {};
let timerInterval = null;
let startTime = null;
let elapsedSeconds = 0;
let pauseCount = 0;
let isRunning = false;
let isLoggedIn = false;

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', async () => {
    await checkLoginStatus();
    await loadSettings();
    initNavigation();
    initTimer();
    initFilters();
    initImport();
    initLogin();
    loadTodayStats();
    updateUIBasedOnAuth();
});

// 登录功能
async function checkLoginStatus() {
    try {
        const response = await fetch('/api/check-login');
        const data = await response.json();
        isLoggedIn = data.logged_in;
        updateAuthUI();
    } catch (error) {
        console.error('检查登录状态失败:', error);
        isLoggedIn = false;
        updateAuthUI();
    }
}

function updateAuthUI() {
    if (isLoggedIn) {
        document.body.classList.add('logged-in');
        document.getElementById('login-status').textContent = '✅ 已登录';
        document.getElementById('readonly-badge').style.display = 'none';
        document.getElementById('admin-badge').style.display = 'block';
        document.getElementById('login-form-container').style.display = 'none';
        document.getElementById('logged-in-container').style.display = 'block';
    } else {
        document.body.classList.remove('logged-in');
        document.getElementById('login-status').textContent = '🔒 登录';
        document.getElementById('readonly-badge').style.display = 'block';
        document.getElementById('admin-badge').style.display = 'none';
        document.getElementById('login-form-container').style.display = 'block';
        document.getElementById('logged-in-container').style.display = 'none';
    }
}

function updateUIBasedOnAuth() {
    const readonlyNotice = document.getElementById('readonly-notice');
    if (readonlyNotice) {
        readonlyNotice.style.display = isLoggedIn ? 'none' : 'block';
    }
    
    const settingsNotice = document.getElementById('settings-readonly-notice');
    if (settingsNotice) {
        settingsNotice.style.display = isLoggedIn ? 'none' : 'block';
    }
}

function initLogin() {
    const loginForm = document.getElementById('login-form');
    if (loginForm) {
        loginForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            await handleLogin();
        });
    }
}

async function handleLogin() {
    const password = document.getElementById('password-input').value;
    const errorDiv = document.getElementById('login-error');
    
    try {
        const response = await fetch('/api/login', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({password})
        });
        
        const data = await response.json();
        
        if (data.success) {
            isLoggedIn = true;
            updateAuthUI();
            updateUIBasedOnAuth();
            errorDiv.style.display = 'none';
            document.getElementById('password-input').value = '';
            alert('登录成功！现在拥有完整权限。');
        } else {
            errorDiv.textContent = data.message || '密码错误！';
            errorDiv.style.display = 'block';
            document.getElementById('password-input').value = '';
            document.getElementById('password-input').focus();
        }
    } catch (error) {
        errorDiv.textContent = '登录失败: ' + error.message;
        errorDiv.style.display = 'block';
    }
}

async function handleLogout() {
    if (!confirm('确定要退出登录吗？')) {
        return;
    }
    
    try {
        await fetch('/api/logout', {method: 'POST'});
        isLoggedIn = false;
        updateAuthUI();
        updateUIBasedOnAuth();
        alert('已退出登录');
        showPage('practice');
    } catch (error) {
        alert('退出登录失败: ' + error.message);
    }
}

async function requireLogin(action) {
    if (!isLoggedIn) {
        const doLogin = confirm('此操作需要登录。是否前往登录页面？');
        if (doLogin) {
            showPage('login');
        }
        return false;
    }
    return true;
}

// 导航
function initNavigation() {
    document.querySelectorAll('.nav-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const page = btn.dataset.page;
            showPage(page);
        });
    });
}

function showPage(pageName) {
    document.querySelectorAll('.page').forEach(page => {
        page.classList.remove('active');
    });
    
    document.querySelectorAll('.nav-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    
    document.getElementById(`${pageName}-page`).classList.add('active');
    document.querySelector(`[data-page="${pageName}"]`).classList.add('active');
    
    if (pageName === 'history') {
        loadHistory();
        loadTodayHistoryStats();
    } else if (pageName === 'stats') {
        loadStats();
        loadTodayStatsPage();
    } else if (pageName === 'settings') {
        loadSettingsPage();
    }
}

// 设置管理
async function loadSettings() {
    const response = await fetch('/api/settings');
    settings = await response.json();
    
    updateDatalist('collections-list', settings.collections || []);
    updateDatalist('pieces-list', settings.pieces || []);
    updateDatalist('sections-list', settings.sections || []);
    
    const practiceTypes = settings.practice_types || [];
    const typeSelect = document.getElementById('practice-type');
    typeSelect.innerHTML = practiceTypes.map(type => 
        `<option value="${type}">${type}</option>`
    ).join('');
    
    const recordTypeSelect = document.getElementById('record-type');
    recordTypeSelect.innerHTML = practiceTypes.map(type => 
        `<option value="${type}">${type}</option>`
    ).join('');
    
    const collectionFilter = document.getElementById('collection-filter');
    collectionFilter.innerHTML = '<option value="">全部</option>' +
        settings.collections.map(c => `<option value="${c}">${c}</option>`).join('');
}

function updateDatalist(id, options) {
    const datalist = document.getElementById(id);
    datalist.innerHTML = options.map(opt => 
        `<option value="${opt}">`
    ).join('');
}

async function saveSettings(key, value) {
    await fetch(`/api/settings/${key}`, {
        method: 'PUT',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({value})
    });
    await loadSettings();
}
// 计时器
function initTimer() {
    document.getElementById('start-btn').addEventListener('click', startTimer);
    document.getElementById('pause-btn').addEventListener('click', pauseTimer);
    document.getElementById('stop-btn').addEventListener('click', stopTimer);
}

async function startTimer() {
    if (!await requireLogin('开始练习')) return;
    
    if (!validateForm()) return;
    
    isRunning = true;
    startTime = Date.now();
    elapsedSeconds = 0;
    pauseCount = 0;
    
    document.getElementById('start-btn').disabled = true;
    document.getElementById('pause-btn').disabled = false;
    document.getElementById('stop-btn').disabled = false;
    
    document.querySelectorAll('.practice-form input, .practice-form select, .practice-form textarea')
        .forEach(el => el.disabled = true);
    
    updateTimer();
}

function pauseTimer() {
    if (isRunning) {
        isRunning = false;
        pauseCount++;
        document.getElementById('pause-count').textContent = pauseCount;
        document.getElementById('pause-btn').textContent = '继续';
    } else {
        isRunning = true;
        startTime = Date.now() - (elapsedSeconds * 1000);
        document.getElementById('pause-btn').textContent = '暂停';
        updateTimer();
    }
}

async function stopTimer() {
    isRunning = false;
    if (timerInterval) clearInterval(timerInterval);
    
    await savePracticeSession();
    
    elapsedSeconds = 0;
    pauseCount = 0;
    document.getElementById('timer').textContent = '00:00:00';
    document.getElementById('pause-count').textContent = '0';
    document.getElementById('start-btn').disabled = false;
    document.getElementById('pause-btn').disabled = true;
    document.getElementById('pause-btn').textContent = '暂停';
    document.getElementById('stop-btn').disabled = true;
    
    document.querySelectorAll('.practice-form input, .practice-form select, .practice-form textarea')
        .forEach(el => el.disabled = false);
    
    document.getElementById('collection').value = '';
    document.getElementById('piece').value = '';
    document.getElementById('section').value = '';
    document.getElementById('bpm').value = '';
    document.getElementById('notes').value = '';
    
    loadTodayStats();
}

function updateTimer() {
    if (!isRunning) return;
    
    elapsedSeconds = Math.floor((Date.now() - startTime) / 1000);
    const hours = Math.floor(elapsedSeconds / 3600);
    const minutes = Math.floor((elapsedSeconds % 3600) / 60);
    const seconds = elapsedSeconds % 60;
    
    document.getElementById('timer').textContent = 
        `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
    
    timerInterval = setTimeout(updateTimer, 1000);
}

function validateForm() {
    const fields = ['collection', 'piece', 'section', 'bpm'];
    for (const field of fields) {
        if (!document.getElementById(field).value.trim()) {
            alert(`请填写${field === 'collection' ? '练习曲集' : field === 'piece' ? '练习曲目' : field === 'section' ? '小节段落' : 'BPM'}`);
            return false;
        }
    }
    return true;
}

async function savePracticeSession() {
    const now = new Date();
    const startDateTime = new Date(now - elapsedSeconds * 1000);
    
    const data = {
        date: now.toISOString().split('T')[0],
        start_time: startDateTime.toTimeString().split(' ')[0],
        end_time: now.toTimeString().split(' ')[0],
        duration: elapsedSeconds,
        collection: document.getElementById('collection').value,
        piece: document.getElementById('piece').value,
        section: document.getElementById('section').value,
        bpm: document.getElementById('bpm').value,
        practice_type: document.getElementById('practice-type').value,
        pause_count: pauseCount,
        notes: document.getElementById('notes').value
    };
    
    try {
        const response = await fetch('/api/sessions', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(data)
        });
        
        if (response.status === 401) {
            alert('保存失败：需要登录权限');
            showPage('login');
            return;
        }
        
        if (response.ok) {
            alert(`练习记录已保存！\n时长: ${Math.floor(elapsedSeconds/60)} 分 ${elapsedSeconds%60} 秒`);
        }
    } catch (error) {
        alert('保存失败: ' + error.message);
    }
}

// 今日统计
async function loadTodayStats() {
    const response = await fetch('/api/stats/today');
    const stats = await response.json();
    
    const minutes = Math.floor(stats.duration / 60);
    document.getElementById('today-stats').innerHTML = 
        `今日已练习: ${stats.count} 次 | 总时长: ${minutes} 分钟`;
}

async function loadTodayHistoryStats() {
    const response = await fetch('/api/stats/today');
    const stats = await response.json();
    
    const minutes = Math.floor(stats.duration / 60);
    document.getElementById('today-history-stats').innerHTML = `
        <div class="stat-card">
            <h3>今日练习次数</h3>
            <div class="value">${stats.count} 次</div>
        </div>
        <div class="stat-card">
            <h3>今日练习时长</h3>
            <div class="value">${minutes} 分钟</div>
        </div>
        <div class="stat-card">
            <h3>今日平均暂停</h3>
            <div class="value">${stats.avg_pause} 次</div>
        </div>
    `;
}

async function loadTodayStatsPage() {
    const response = await fetch('/api/stats/today');
    const stats = await response.json();
    
    const minutes = Math.floor(stats.duration / 60);
    const today = new Date().toISOString().split('T')[0];
    
    document.getElementById('today-stats-page').innerHTML = `
        <h3 style="text-align: center; margin-bottom: 15px;">📅 今日统计 (${today})</h3>
        <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px;">
            <div class="stat-card">
                <h3>练习次数</h3>
                <div class="value">${stats.count} 次</div>
            </div>
            <div class="stat-card">
                <h3>练习时长</h3>
                <div class="value">${minutes} 分钟</div>
            </div>
            <div class="stat-card">
                <h3>平均暂停</h3>
                <div class="value">${stats.avg_pause} 次</div>
            </div>
        </div>
    `;
}
// 练习历史
function initFilters() {
    document.getElementById('date-range').addEventListener('change', loadHistory);
    document.getElementById('collection-filter').addEventListener('change', loadHistory);
}

async function loadHistory() {
    const days = document.getElementById('date-range').value;
    const collection = document.getElementById('collection-filter').value;
    
    const url = `/api/sessions?days=${days}${collection ? `&collection=${collection}` : ''}`;
    const response = await fetch(url);
    const sessions = await response.json();
    
    const tbody = document.getElementById('history-tbody');
    tbody.innerHTML = sessions.map(s => `
        <tr>
            <td class="admin-only"><input type="checkbox" class="record-checkbox" data-id="${s.id}"></td>
            <td>${s.date}</td>
            <td>${s.start_time}</td>
            <td>${s.end_time}</td>
            <td>${Math.floor(s.duration / 60)}</td>
            <td>${s.collection}</td>
            <td>${s.piece}</td>
            <td>${s.section}</td>
            <td>${s.bpm}</td>
            <td>${s.practice_type}</td>
            <td>${s.pause_count}次</td>
            <td>${(s.notes || '').substring(0, 30)}${s.notes && s.notes.length > 30 ? '...' : ''}</td>
        </tr>
    `).join('');
    
    document.getElementById('select-all').addEventListener('change', (e) => {
        document.querySelectorAll('.record-checkbox').forEach(cb => {
            cb.checked = e.target.checked;
        });
    });
}

function showAddRecordDialog() {
    if (!isLoggedIn) {
        requireLogin('新增记录');
        return;
    }
    
    document.getElementById('dialog-title').textContent = '新增练习记录';
    document.getElementById('record-form').reset();
    document.getElementById('record-id').value = '';
    document.getElementById('record-date').value = new Date().toISOString().split('T')[0];
    document.getElementById('record-dialog').classList.add('show');
}

async function editSelectedRecord() {
    if (!await requireLogin('编辑记录')) return;
    
    const selected = Array.from(document.querySelectorAll('.record-checkbox:checked'));
    if (selected.length === 0) {
        alert('请先选择要编辑的记录！');
        return;
    }
    if (selected.length > 1) {
        alert('一次只能编辑一条记录！');
        return;
    }
    
    const id = selected[0].dataset.id;
    const response = await fetch(`/api/sessions?days=10000`);
    const sessions = await response.json();
    const record = sessions.find(s => s.id == id);
    
    if (!record) return;
    
    document.getElementById('dialog-title').textContent = '编辑练习记录';
    document.getElementById('record-id').value = record.id;
    document.getElementById('record-date').value = record.date;
    document.getElementById('record-start').value = record.start_time;
    document.getElementById('record-end').value = record.end_time;
    document.getElementById('record-duration').value = Math.floor(record.duration / 60);
    document.getElementById('record-collection').value = record.collection;
    document.getElementById('record-piece').value = record.piece;
    document.getElementById('record-section').value = record.section;
    document.getElementById('record-bpm').value = record.bpm;
    document.getElementById('record-type').value = record.practice_type;
    document.getElementById('record-pause').value = record.pause_count;
    document.getElementById('record-notes').value = record.notes || '';
    
    document.getElementById('record-dialog').classList.add('show');
}

async function deleteSelectedRecords() {
    if (!await requireLogin('删除记录')) return;
    
    const selected = Array.from(document.querySelectorAll('.record-checkbox:checked'));
    if (selected.length === 0) {
        alert('请先选择要删除的记录！');
        return;
    }
    
    if (!confirm(`确定要删除选中的 ${selected.length} 条记录吗？`)) {
        return;
    }
    
    for (const checkbox of selected) {
        await fetch(`/api/sessions/${checkbox.dataset.id}`, {method: 'DELETE'});
    }
    
    alert('记录已删除！');
    loadHistory();
    loadTodayHistoryStats();
}

function closeRecordDialog() {
    document.getElementById('record-dialog').classList.remove('show');
}

document.getElementById('record-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    if (!isLoggedIn) {
        alert('需要登录权限');
        closeRecordDialog();
        showPage('login');
        return;
    }
    
    const data = {
        date: document.getElementById('record-date').value,
        start_time: document.getElementById('record-start').value,
        end_time: document.getElementById('record-end').value,
        duration: parseInt(document.getElementById('record-duration').value) * 60,
        collection: document.getElementById('record-collection').value,
        piece: document.getElementById('record-piece').value,
        section: document.getElementById('record-section').value,
        bpm: document.getElementById('record-bpm').value,
        practice_type: document.getElementById('record-type').value,
        pause_count: parseInt(document.getElementById('record-pause').value),
        notes: document.getElementById('record-notes').value
    };
    
    const id = document.getElementById('record-id').value;
    
    try {
        if (id) {
            await fetch(`/api/sessions/${id}`, {
                method: 'PUT',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(data)
            });
            alert('记录已更新！');
        } else {
            await fetch('/api/sessions', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(data)
            });
            alert('记录已添加！');
        }
        
        closeRecordDialog();
        loadHistory();
        loadTodayHistoryStats();
    } catch (error) {
        alert('保存失败: ' + error.message);
    }
});

// 数据统计
async function loadStats() {
    const days = document.getElementById('stats-period').value;
    
    const response = await fetch(`/api/stats/period?days=${days}`);
    const stats = await response.json();
    
    const hours = (stats.total_duration / 3600).toFixed(1);
    
    document.getElementById('period-stats').innerHTML = `
        <div class="stat-card">
            <h3>总练习时长</h3>
            <div class="value">${hours} 小时</div>
        </div>
        <div class="stat-card">
            <h3>总练习次数</h3>
            <div class="value">${stats.total_count}</div>
        </div>
        <div class="stat-card">
            <h3>平均暂停次数</h3>
            <div class="value">${stats.avg_pause}</div>
        </div>
        <div class="stat-card">
            <h3>连续打卡</h3>
            <div class="value">${stats.consecutive_days} 天</div>
        </div>
    `;
    
    const durationChart = await fetch(`/api/charts/duration_trend?days=${days}`);
    const durationData = await durationChart.json();
    document.getElementById('duration-chart').src = durationData.image;
    
    const typeChart = await fetch(`/api/charts/type_distribution?days=${days}`);
    const typeData = await typeChart.json();
    document.getElementById('type-chart').src = typeData.image;
}

document.getElementById('stats-period').addEventListener('change', loadStats);

// 设置页面
function loadSettingsPage() {
    renderOptionsWithDrag('collections', settings.collections || []);
    renderOptionsWithDrag('pieces', settings.pieces || []);
    renderOptionsWithDrag('sections', settings.sections || []);
    renderOptionsWithDrag('practice_types', settings.practice_types || []);
}

function renderOptionsWithDrag(key, options) {
    const editorId = key.replace(/_/g, '-') + '-editor';
    const editor = document.getElementById(editorId);
    
    if (!editor) {
        console.error(`找不到元素: ${editorId}`);
        return;
    }
    
    editor.innerHTML = options.map((opt, idx) => `
        <div class="option-item" draggable="true" data-index="${idx}">
            <span class="drag-handle">⋮⋮</span>
            <input type="text" value="${opt}" onchange="updateOption('${key}', ${idx}, this.value)" onclick="event.stopPropagation()">
            <div class="option-controls">
                <button class="btn btn-danger btn-icon" onclick="deleteOption('${key}', ${idx}); event.stopPropagation()">🗑</button>
            </div>
        </div>
    `).join('');
    
    initDragAndDrop(editor, key);
}

function initDragAndDrop(container, key) {
    const items = container.querySelectorAll('.option-item');
    let draggedItem = null;
    
    items.forEach(item => {
        item.addEventListener('dragstart', (e) => {
            draggedItem = item;
            item.classList.add('dragging');
            e.dataTransfer.effectAllowed = 'move';
        });
        
        item.addEventListener('dragend', (e) => {
            item.classList.remove('dragging');
            container.querySelectorAll('.option-item').forEach(i => {
                i.classList.remove('drag-over');
            });
        });
        
        item.addEventListener('dragover', (e) => {
            e.preventDefault();
            if (draggedItem !== item) {
                item.classList.add('drag-over');
            }
        });
        
        item.addEventListener('dragleave', (e) => {
            item.classList.remove('drag-over');
        });
        
        item.addEventListener('drop', async (e) => {
            e.preventDefault();
            item.classList.remove('drag-over');
            
            if (draggedItem !== item) {
                const fromIndex = parseInt(draggedItem.dataset.index);
                const toIndex = parseInt(item.dataset.index);
                
                const options = settings[key] || [];
                const [removed] = options.splice(fromIndex, 1);
                options.splice(toIndex, 0, removed);
                
                await saveSettings(key, options);
                loadSettingsPage();
            }
        });
    });
}

function addOption(key) {
    if (!isLoggedIn) {
        requireLogin('添加选项');
        return;
    }
    
    const value = prompt('请输入新选项:');
    if (value && value.trim()) {
        const options = settings[key] || [];
        if (options.includes(value.trim())) {
            alert('该选项已存在！');
            return;
        }
        options.push(value.trim());
        saveSettings(key, options);
        loadSettingsPage();
    }
}

async function updateOption(key, index, value) {
    if (!isLoggedIn) return;
    
    value = value.trim();
    if (!value) {
        alert('选项内容不能为空！');
        loadSettingsPage();
        return;
    }
    
    const options = settings[key] || [];
    if (options.includes(value) && options[index] !== value) {
        alert('该选项已存在！');
        loadSettingsPage();
        return;
    }
    
    options[index] = value;
    await saveSettings(key, options);
}

function deleteOption(key, index) {
    if (!isLoggedIn) {
        requireLogin('删除选项');
        return;
    }
    
    const options = settings[key] || [];
    if (options.length <= 1) {
        alert('至少保留一个选项！');
        return;
    }
    
    if (confirm(`确定要删除 '${options[index]}' 吗？`)) {
        options.splice(index, 1);
        saveSettings(key, options);
        loadSettingsPage();
    }
}

// 数据导入导出
function exportData() {
    window.location.href = '/api/export';
}

function initImport() {
    document.getElementById('import-file').addEventListener('change', async (e) => {
        if (!isLoggedIn) {
            alert('导入数据需要登录权限');
            e.target.value = '';
            showPage('login');
            return;
        }
        
        const file = e.target.files[0];
        if (!file) return;
        
        if (!file.name.endsWith('.db')) {
            alert('只支持.db文件！');
            e.target.value = '';
            return;
        }
        
        if (!confirm('导入数据将覆盖当前所有数据！\n确定要继续吗？')) {
            e.target.value = '';
            return;
        }
        
        const formData = new FormData();
        formData.append('file', file);
        
        try {
            const response = await fetch('/api/import', {
                method: 'POST',
                body: formData
            });
            
            const result = await response.json();
            
            if (result.success) {
                alert(result.message + '\n\n页面将刷新以加载新数据。');
                window.location.reload();
            } else {
                alert('导入失败: ' + result.error);
            }
        } catch (error) {
            alert('导入失败: ' + error.message);
        }
        
        e.target.value = '';
    });
}
