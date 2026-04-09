/* === Break Wave Mini App === */

const API = window.location.origin;
const tg = window.Telegram?.WebApp;

let currentScreen = 'home';
let screenHistory = [];
let currentEventTab = 'school';
let isAdmin = false;
let initData = '';
let newEventType = 'school';

// --- Init ---
document.addEventListener('DOMContentLoaded', async () => {
    if (tg) {
        tg.ready();
        tg.expand();
        tg.enableClosingConfirmation?.();
        tg.headerColor = '#0F2035';
        tg.backgroundColor = '#0A1628';
        tg.setBackgroundColor?.('#0A1628');
        tg.setHeaderColor?.('#0F2035');
        initData = tg.initData || '';
    }

    // Check admin status
    await checkAdmin();

    // Check hash for deep link
    const hash = window.location.hash.replace('#', '');
    if (hash && hash !== '') {
        navigate(hash);
    } else {
        loadHome();
    }
});

async function checkAdmin() {
    if (!initData) return;
    try {
        const res = await fetch(`${API}/api/admin/check`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({initData}),
        });
        const data = await res.json();
        isAdmin = data.is_admin;
        if (isAdmin) {
            document.getElementById('admin-fab').classList.add('visible');
        }
    } catch (e) {
        console.error('Admin check failed:', e);
    }
}

// --- Navigation ---
function navigate(screen, params) {
    if (currentScreen !== screen) {
        screenHistory.push(currentScreen);
    }
    showScreen(screen, params);
}

function goBack() {
    if (screenHistory.length > 0) {
        const prev = screenHistory.pop();
        showScreen(prev);
    } else {
        showScreen('home');
    }
}

function showScreen(screen, params) {
    currentScreen = screen;

    document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));

    const el = document.getElementById(`screen-${screen}`);
    if (el) {
        el.classList.add('active');
    }

    // Scroll to top
    document.getElementById('content').scrollTop = 0;

    // Back button
    const backBtn = document.getElementById('btn-back');
    if (screen === 'home') {
        backBtn.classList.add('hidden');
    } else {
        backBtn.classList.remove('hidden');
    }

    // Load data
    switch (screen) {
        case 'home': loadHome(); break;
        case 'ranking': loadRanking(); break;
        case 'nominations': loadNominations(); break;
        case 'nomination-detail': loadNominationDetail(params); break;
        case 'events': loadEvents(); break;
        case 'event-detail': loadEventDetail(params); break;
        case 'event-results': loadEventResults(params); break;
        case 'search': loadSearch(); break;
        case 'participant': loadParticipant(params); break;
        case 'dashboard': loadDashboard(); break;
        case 'seasons': loadSeasons(); break;
        // Admin screens
        case 'admin-events': loadAdminEvents(); break;
        case 'admin-participants': loadAdminParticipants(); break;
        case 'admin-participant-form': loadParticipantForm(); break;
        case 'admin-stats': loadAdminStats(); break;
        case 'admin-seasons': loadAdminSeasons(); break;
        case 'admin-nominations': loadAdminNominations(); break;
        case 'admin-results': loadAdminResults(); break;
        case 'admin-results-form': loadAdminResultsForm(params); break;
    }

    // Show/hide admin FAB
    const fab = document.getElementById('admin-fab');
    if (fab && isAdmin) {
        fab.style.display = screen.startsWith('admin') ? 'none' : '';
    }
}

// --- API Helper ---
async function api(path) {
    try {
        const res = await fetch(`${API}${path}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return await res.json();
    } catch (e) {
        console.error('API Error:', e);
        return null;
    }
}

function loading() {
    return '<div class="loading"><div class="spinner"></div>Загрузка...</div>';
}

function emptyState(icon, text) {
    return `<div class="empty-state"><div class="empty-state-icon">${icon}</div><div class="empty-state-text">${text}</div></div>`;
}

function rankClass(rank) {
    if (rank === 1) return 'gold';
    if (rank === 2) return 'silver';
    if (rank === 3) return 'bronze';
    return '';
}

function rankBadgeClass(rank) {
    if (rank <= 3) return `r${rank}`;
    return '';
}

function medalEmoji(rank) {
    if (rank === 1) return '🥇';
    if (rank === 2) return '🥈';
    if (rank === 3) return '🥉';
    return `#${rank}`;
}

// --- Home ---
async function loadHome() {
    const season = await api('/api/seasons/current');
    if (season && season.name) {
        document.getElementById('season-name').textContent = season.name.toUpperCase();
    }
}

// --- Ranking ---
async function loadRanking() {
    const container = document.getElementById('ranking-list');
    container.innerHTML = loading();

    const data = await api('/api/ranking');
    if (!data || data.length === 0) {
        container.innerHTML = emptyState('🏆', 'Нет данных о рейтинге');
        return;
    }

    container.innerHTML = data.map(p => `
        <div class="rank-item ${rankClass(p.rank)}" onclick="navigate('participant', ${p.id})">
            <div class="rank-badge ${rankBadgeClass(p.rank)}">${p.rank <= 3 ? medalEmoji(p.rank) : p.rank}</div>
            <div class="rank-info">
                <div class="rank-name">${esc(p.name)}</div>
                <div class="rank-nomination">${esc(p.nomination)}</div>
            </div>
            <div style="text-align:right">
                <div class="rank-points">${p.total_points}</div>
                <div class="rank-points-label">баллов</div>
            </div>
        </div>
    `).join('');
}

// --- Nominations ---
async function loadNominations() {
    const container = document.getElementById('nominations-grid');
    container.innerHTML = loading();

    const data = await api('/api/nominations');
    if (!data || data.length === 0) {
        container.innerHTML = emptyState('🏅', 'Нет номинаций');
        return;
    }

    const icons = {
        'до 6 лет': '👶',
        '1 год обучения': '📗',
        'до 3 лет опыта': '📘',
        '7-9 лет': '📙',
        '10-13 лет': '📕',
        'Kids Pro': '🌟',
        'Bgirl': '🌸',
    };

    container.innerHTML = data.map(n => `
        <div class="nom-card" onclick="navigate('nomination-detail', '${esc(n.name)}')">
            <div style="font-size:28px;margin-bottom:6px">${icons[n.name] || '🏅'}</div>
            <div class="nom-card-name">${esc(n.name)}</div>
            <div class="nom-card-count">${n.count} участн.</div>
        </div>
    `).join('');
}

// --- Nomination Detail ---
async function loadNominationDetail(nomination) {
    const title = document.getElementById('nom-detail-title');
    const container = document.getElementById('nom-detail-list');
    title.textContent = `🏅 ${nomination}`;
    container.innerHTML = loading();

    const data = await api(`/api/ranking/nomination/${encodeURIComponent(nomination)}`);
    if (!data || data.length === 0) {
        container.innerHTML = emptyState('🏅', 'Нет участников');
        return;
    }

    container.innerHTML = data.map(p => `
        <div class="rank-item ${rankClass(p.rank)}" onclick="navigate('participant', ${p.id})">
            <div class="rank-badge ${rankBadgeClass(p.rank)}">${p.rank <= 3 ? medalEmoji(p.rank) : p.rank}</div>
            <div class="rank-info">
                <div class="rank-name">${esc(p.name)}</div>
                <div class="rank-nomination">${esc(p.nomination)}</div>
            </div>
            <div style="text-align:right">
                <div class="rank-points">${p.total_points}</div>
                <div class="rank-points-label">баллов</div>
            </div>
        </div>
    `).join('');
}

// --- Events ---
async function loadEvents() {
    loadEventsByType(currentEventTab);
}

function switchEventTab(type, btn) {
    currentEventTab = type;
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    btn.classList.add('active');
    loadEventsByType(type);
}

async function loadEventsByType(type) {
    const container = document.getElementById('events-list');
    container.innerHTML = loading();

    const data = await api(`/api/events?event_type=${type}`);
    if (!data || data.length === 0) {
        container.innerHTML = emptyState('📅', type === 'school' ? 'Нет мероприятий школы' : 'Нет других соревнований');
        return;
    }

    container.innerHTML = data.map(e => {
        let statusLabel = '';
        let statusClass = '';
        if (e.status === 'completed') { statusLabel = '✅ Проведено'; statusClass = 'status-completed'; }
        else if (e.status === 'upcoming') { statusLabel = '⏳ Скоро'; statusClass = 'status-upcoming'; }
        else { statusLabel = '🔒 Впереди'; statusClass = 'status-locked'; }

        const onclick = e.event_type === 'school' && e.status === 'completed'
            ? `navigate('event-results', {id: ${e.id}, name: '${esc(e.emoji)} ${esc(e.name)}'})`
            : `navigate('event-detail', ${e.id})`;

        return `
            <div class="event-card" onclick="${onclick}">
                <div class="event-card-header">
                    <div class="event-card-name">${e.emoji} ${esc(e.name)}</div>
                    <div class="event-card-status ${statusClass}">${statusLabel}</div>
                </div>
                <div class="event-card-details">
                    ${e.date ? `<div class="event-card-detail">📅 ${esc(e.date)}</div>` : ''}
                    ${e.location ? `<div class="event-card-detail">📍 ${esc(e.location)}</div>` : ''}
                    ${e.multiplier > 1 ? `<div class="event-card-detail">⚡ Баллы x${e.multiplier}</div>` : ''}
                </div>
            </div>
        `;
    }).join('');
}

// --- Event Detail ---
async function loadEventDetail(eventId) {
    const container = document.getElementById('event-detail-content');
    container.innerHTML = loading();

    const e = await api(`/api/events/${eventId}`);
    if (!e) {
        container.innerHTML = emptyState('❌', 'Мероприятие не найдено');
        return;
    }

    const typeLabel = e.event_type === 'school' ? '🏠 BREAK WAVE' : '🌍 ВНЕШНЕЕ';

    let html = `
        <div class="event-detail">
            <div class="event-detail-header">
                <div class="event-detail-emoji">${e.emoji}</div>
                <div class="event-detail-name">${esc(e.name)}</div>
                <div class="event-detail-type">${typeLabel}</div>
            </div>
            <div class="event-detail-body">
    `;

    if (e.date) html += detailRow('📅', 'Дата', e.date);
    if (e.time) html += detailRow('🕐', 'Время', e.time);
    if (e.location) html += detailRow('📍', 'Место', e.location);
    if (e.description) html += detailRow('📋', 'Описание', e.description);
    if (e.fee) html += detailRow('💰', 'Взнос', e.fee);
    if (e.contact) html += detailRow('📱', 'Контакт', e.contact);
    if (e.multiplier > 1) html += detailRow('⚡', 'Множитель баллов', `x${e.multiplier}`);

    if (e.status === 'completed' && e.event_type === 'school') {
        html += `<button class="btn-primary" onclick="navigate('event-results', {id: ${e.id}, name: '${esc(e.emoji)} ${esc(e.name)}'})">🏆 Смотреть результаты</button>`;
    }

    html += '</div></div>';
    container.innerHTML = html;
}

function detailRow(icon, label, value) {
    return `
        <div class="detail-row">
            <div class="detail-row-icon">${icon}</div>
            <div class="detail-row-content">
                <div class="detail-row-label">${label}</div>
                <div class="detail-row-value">${esc(String(value))}</div>
            </div>
        </div>
    `;
}

// --- Event Results ---
async function loadEventResults(params) {
    const title = document.getElementById('event-results-title');
    const container = document.getElementById('event-results-list');
    title.textContent = params.name || 'Результаты';
    container.innerHTML = loading();

    const data = await api(`/api/events/${params.id}/results`);
    if (!data || data.length === 0) {
        container.innerHTML = emptyState('📊', 'Нет результатов');
        return;
    }

    container.innerHTML = data.map(r => `
        <div class="rank-item ${rankClass(r.rank)}" onclick="navigate('participant', ${r.participant_id})">
            <div class="rank-badge ${rankBadgeClass(r.rank)}">${r.rank <= 3 ? medalEmoji(r.rank) : r.rank}</div>
            <div class="rank-info">
                <div class="rank-name">${esc(r.name)}</div>
                <div class="rank-nomination">${esc(r.nomination)}</div>
            </div>
            <div style="text-align:right">
                <div class="rank-points">${r.points}</div>
                <div class="rank-points-label">баллов</div>
            </div>
        </div>
    `).join('');
}

// --- Search ---
let searchTimeout;
async function loadSearch() {
    const container = document.getElementById('all-participants');
    const searchRes = document.getElementById('search-results');
    document.getElementById('search-input').value = '';
    searchRes.innerHTML = '';
    container.innerHTML = loading();

    const data = await api('/api/participants');
    if (!data || data.length === 0) {
        container.innerHTML = emptyState('🔍', 'Нет участников');
        return;
    }

    container.innerHTML = data.map(p => `
        <div class="rank-item" onclick="navigate('participant', ${p.id})">
            <div class="rank-badge" style="font-size:12px">${esc(p.name.charAt(0))}</div>
            <div class="rank-info">
                <div class="rank-name">${esc(p.name)}</div>
                <div class="rank-nomination">${esc(p.nomination)}</div>
            </div>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" style="flex-shrink:0"><path d="M9 18L15 12L9 6" stroke="#5A7A96" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
        </div>
    `).join('');
}

function onSearch(query) {
    clearTimeout(searchTimeout);
    const allContainer = document.getElementById('all-participants');
    const searchRes = document.getElementById('search-results');

    if (!query.trim()) {
        searchRes.innerHTML = '';
        allContainer.style.display = 'flex';
        return;
    }

    allContainer.style.display = 'none';
    searchTimeout = setTimeout(async () => {
        searchRes.innerHTML = loading();
        const data = await api(`/api/participants/search?q=${encodeURIComponent(query)}`);
        if (!data || data.length === 0) {
            searchRes.innerHTML = emptyState('🔍', 'Ничего не найдено');
            return;
        }
        searchRes.innerHTML = data.map(p => `
            <div class="rank-item" onclick="navigate('participant', ${p.id})">
                <div class="rank-badge" style="font-size:12px">${esc(p.name.charAt(0))}</div>
                <div class="rank-info">
                    <div class="rank-name">${esc(p.name)}</div>
                    <div class="rank-nomination">${esc(p.nomination)}</div>
                </div>
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" style="flex-shrink:0"><path d="M9 18L15 12L9 6" stroke="#5A7A96" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
            </div>
        `).join('');
    }, 300);
}

// --- Participant ---
async function loadParticipant(id) {
    const container = document.getElementById('participant-card');
    container.innerHTML = loading();

    const p = await api(`/api/participants/${id}`);
    if (!p) {
        container.innerHTML = emptyState('❌', 'Участник не найден');
        return;
    }

    const medal = p.overall_rank <= 3 ? medalEmoji(p.overall_rank) : `#${p.overall_rank}`;
    const nomMedal = p.nomination_rank <= 3 ? medalEmoji(p.nomination_rank) : `#${p.nomination_rank}`;

    let eventsHtml = p.events.map(e => {
        const pts = e.points > 0 ? e.points : '—';
        const ptsClass = e.points > 0 ? 'has-points' : 'no-points';
        return `
            <div class="p-event-row">
                <div class="p-event-emoji">${e.emoji}</div>
                <div class="p-event-info">
                    <div class="p-event-name">${esc(e.event_name)}</div>
                    ${e.multiplier > 1 ? `<div class="p-event-multi">x${e.multiplier} баллов</div>` : ''}
                </div>
                <div class="p-event-points ${ptsClass}">${pts}</div>
            </div>
        `;
    }).join('');

    container.innerHTML = `
        <div class="p-card">
            <div class="p-card-header">
                <div class="p-card-name">${esc(p.name)}</div>
                <div class="p-card-nomination">${esc(p.nomination)}</div>
                <div class="p-card-stats">
                    <div class="p-stat">
                        <div class="p-stat-value accent">${p.total_points}</div>
                        <div class="p-stat-label">Баллов</div>
                    </div>
                    <div class="p-stat">
                        <div class="p-stat-value gold">${medal}</div>
                        <div class="p-stat-label">Общий</div>
                    </div>
                    <div class="p-stat">
                        <div class="p-stat-value gold">${nomMedal}</div>
                        <div class="p-stat-label">В номинации</div>
                    </div>
                </div>
            </div>
            <div class="p-card-events">
                ${eventsHtml}
                <div class="p-total-row">
                    <div class="p-total-label">Итого за сезон</div>
                    <div class="p-total-value">${p.total_points} б.</div>
                </div>
            </div>
        </div>
    `;
}

// --- Dashboard ---
async function loadDashboard() {
    const container = document.getElementById('dashboard-content');
    container.innerHTML = loading();

    const data = await api('/api/dashboard');
    if (!data || data.length === 0) {
        container.innerHTML = emptyState('📊', 'Нет данных');
        return;
    }

    const icons = {
        'до 6 лет': '👶',
        '1 год обучения': '📗',
        'до 3 лет опыта': '📘',
        '7-9 лет': '📙',
        '10-13 лет': '📕',
        'Kids Pro': '🌟',
        'Bgirl': '🌸',
    };

    container.innerHTML = data.map(section => {
        const icon = icons[section.nomination] || '🏅';
        if (section.top3.length === 0) {
            return `
                <div class="dash-section">
                    <div class="dash-section-title">${icon} ${esc(section.nomination)}</div>
                    <div style="color:var(--text-muted);font-size:13px;padding:8px 0">Нет данных</div>
                </div>
            `;
        }
        return `
            <div class="dash-section">
                <div class="dash-section-title">${icon} ${esc(section.nomination)}</div>
                ${section.top3.map(p => `
                    <div class="dash-item" onclick="navigate('participant', ${p.id})" style="cursor:pointer">
                        <div class="dash-medal">${medalEmoji(p.rank)}</div>
                        <div class="dash-name">${esc(p.name)}</div>
                        <div class="dash-points">${p.total_points} б.</div>
                    </div>
                `).join('')}
            </div>
        `;
    }).join('');
}

// --- Seasons ---
async function loadSeasons() {
    const container = document.getElementById('seasons-list');
    container.innerHTML = loading();

    const data = await api('/api/seasons');
    if (!data || data.length === 0) {
        container.innerHTML = emptyState('📂', 'Нет сезонов');
        return;
    }

    container.innerHTML = data.map(s => `
        <div class="season-item ${s.is_current ? 'current' : ''}">
            <div style="font-weight:700">${esc(s.name)}</div>
            ${s.is_current ? '<div class="season-badge">Текущий</div>' : ''}
        </div>
    `).join('');
}

// ===========================
// === ADMIN FUNCTIONS ===
// ===========================

// --- Admin: Upload Excel ---
function onFileSelected(input) {
    const display = document.getElementById('file-name-display');
    const btn = document.getElementById('btn-upload-excel');
    if (input.files.length > 0) {
        display.textContent = input.files[0].name;
        display.classList.add('selected');
        btn.disabled = false;
    } else {
        display.textContent = 'Выбрать файл';
        display.classList.remove('selected');
        btn.disabled = true;
    }
}

async function uploadExcel() {
    const input = document.getElementById('excel-file-input');
    const result = document.getElementById('upload-result');
    const btn = document.getElementById('btn-upload-excel');

    if (!input.files.length) return;

    btn.disabled = true;
    btn.textContent = '⏳ Загрузка...';
    result.innerHTML = '';

    const formData = new FormData();
    formData.append('file', input.files[0]);
    formData.append('initData', initData);

    try {
        const res = await fetch(`${API}/api/admin/upload-excel`, {
            method: 'POST',
            body: formData,
        });
        const data = await res.json();

        if (data.success) {
            const events = data.updated_events?.join(', ') || 'нет';
            result.innerHTML = `<div class="result-success">✅ Обновлено!<br>👥 Участников: ${data.participants}<br>📅 Мероприятия: ${events}</div>`;
        } else {
            result.innerHTML = `<div class="result-error">❌ ${data.error || 'Ошибка'}</div>`;
        }
    } catch (e) {
        result.innerHTML = `<div class="result-error">❌ Ошибка сети</div>`;
    }

    btn.textContent = '📤 Загрузить и обновить';
    btn.disabled = false;
}

// --- Admin: Events ---
async function loadAdminEvents() {
    const container = document.getElementById('admin-events-list');
    container.innerHTML = loading();

    const data = await api('/api/events');
    if (!data || data.length === 0) {
        container.innerHTML = emptyState('📅', 'Нет мероприятий');
        return;
    }

    container.innerHTML = data.map(e => {
        const typeIcon = e.event_type === 'school' ? '🏠' : '🌍';
        return `
            <div class="admin-event-item">
                <div class="admin-event-info">
                    <div class="admin-event-name">${e.emoji} ${esc(e.name)}</div>
                    <div class="admin-event-meta">${typeIcon} ${e.event_type === 'school' ? 'Break Wave' : 'Другое'} · ${e.date || 'без даты'} · ${e.status}</div>
                </div>
                <button class="btn-icon-danger" onclick="deleteEvent(${e.id}, '${esc(e.name)}')">🗑</button>
            </div>
        `;
    }).join('');
}

async function deleteEvent(id, name) {
    if (!confirm(`Удалить мероприятие "${name}"?`)) return;

    try {
        const res = await fetch(`${API}/api/admin/events/${id}`, {
            method: 'DELETE',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({initData}),
        });
        const data = await res.json();
        if (data.success) {
            loadAdminEvents();
        }
    } catch (e) {
        alert('Ошибка удаления');
    }
}

// --- Admin: Event Form ---
function setEventType(type, btn) {
    newEventType = type;
    btn.parentElement.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    btn.classList.add('active');
}

async function saveEvent() {
    const name = document.getElementById('ef-name').value.trim();
    if (!name) { alert('Введи название'); return; }

    const result = document.getElementById('event-form-result');
    result.innerHTML = '';

    const body = {
        initData,
        name,
        emoji: document.getElementById('ef-emoji').value.trim() || '🏆',
        event_type: newEventType,
        date: document.getElementById('ef-date').value.trim() || null,
        time: document.getElementById('ef-time').value.trim() || null,
        location: document.getElementById('ef-location').value.trim() || null,
        description: document.getElementById('ef-description').value.trim() || null,
        fee: document.getElementById('ef-fee').value.trim() || null,
        contact: document.getElementById('ef-contact').value.trim() || null,
    };

    try {
        const res = await fetch(`${API}/api/admin/events`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(body),
        });
        const data = await res.json();
        if (data.success) {
            result.innerHTML = '<div class="result-success">✅ Мероприятие добавлено!</div>';
            // Clear form
            ['ef-name', 'ef-date', 'ef-time', 'ef-location', 'ef-description', 'ef-fee', 'ef-contact'].forEach(id => {
                document.getElementById(id).value = '';
            });
            document.getElementById('ef-emoji').value = '🏆';
        } else {
            result.innerHTML = `<div class="result-error">❌ ${data.error || 'Ошибка'}</div>`;
        }
    } catch (e) {
        result.innerHTML = '<div class="result-error">❌ Ошибка сети</div>';
    }
}

// --- Admin: Participants ---
async function loadAdminParticipants() {
    const container = document.getElementById('admin-participants-list');
    container.innerHTML = loading();

    const data = await api('/api/participants');
    if (!data || data.length === 0) {
        container.innerHTML = emptyState('👥', 'Нет участников');
        return;
    }

    container.innerHTML = data.map(p => `
        <div class="admin-event-item">
            <div class="admin-event-info">
                <div class="admin-event-name">${esc(p.name)}</div>
                <div class="admin-event-meta">${esc(p.nomination)}</div>
            </div>
            <button class="btn-icon-danger" onclick="deleteParticipant(${p.id}, '${esc(p.name)}')">🗑</button>
        </div>
    `).join('');
}

async function deleteParticipant(id, name) {
    if (!confirm(`Удалить участника "${name}"?`)) return;

    try {
        const res = await fetch(`${API}/api/admin/participants/${id}`, {
            method: 'DELETE',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({initData}),
        });
        const data = await res.json();
        if (data.success) {
            loadAdminParticipants();
        }
    } catch (e) {
        alert('Ошибка удаления');
    }
}

async function saveParticipant() {
    const name = document.getElementById('pf-name').value.trim();
    const nomination = document.getElementById('pf-nomination').value;
    const result = document.getElementById('participant-form-result');

    if (!name || !nomination) { alert('Заполни имя и номинацию'); return; }
    result.innerHTML = '';

    try {
        const res = await fetch(`${API}/api/admin/participants`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({initData, name, nomination}),
        });
        const data = await res.json();
        if (data.success) {
            result.innerHTML = '<div class="result-success">✅ Участник добавлен!</div>';
            document.getElementById('pf-name').value = '';
            document.getElementById('pf-nomination').value = '';
        } else {
            result.innerHTML = `<div class="result-error">❌ ${data.error || 'Ошибка'}</div>`;
        }
    } catch (e) {
        result.innerHTML = '<div class="result-error">❌ Ошибка сети</div>';
    }
}

// --- Admin: Notify ---
function setNotifyText(text) {
    document.getElementById('notify-text').value = text;
}

async function sendNotify() {
    const text = document.getElementById('notify-text').value.trim();
    const result = document.getElementById('notify-result');
    if (!text) { alert('Введи текст'); return; }

    result.innerHTML = '';

    try {
        const res = await fetch(`${API}/api/admin/notify`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({initData, text}),
        });
        const data = await res.json();
        if (data.success) {
            result.innerHTML = `<div class="result-success">✅ Отправлено ${data.sent} подписчикам!</div>`;
            document.getElementById('notify-text').value = '';
        } else {
            result.innerHTML = `<div class="result-error">❌ ${data.error || 'Ошибка'}</div>`;
        }
    } catch (e) {
        result.innerHTML = '<div class="result-error">❌ Ошибка сети</div>';
    }
}

// --- Admin: Stats ---
async function loadAdminStats() {
    const container = document.getElementById('admin-stats-content');
    container.innerHTML = loading();

    try {
        const res = await fetch(`${API}/api/admin/stats`);
        const data = await res.json();

        container.innerHTML = `
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-card-value">${data.subscribers_active}</div>
                    <div class="stat-card-label">Подписчиков</div>
                </div>
                <div class="stat-card">
                    <div class="stat-card-value">${data.participants}</div>
                    <div class="stat-card-label">Участников</div>
                </div>
                <div class="stat-card">
                    <div class="stat-card-value">${data.events}</div>
                    <div class="stat-card-label">Мероприятий</div>
                </div>
                <div class="stat-card">
                    <div class="stat-card-value">${data.subscribers_total}</div>
                    <div class="stat-card-label">Всего подписок</div>
                </div>
            </div>
        `;
    } catch (e) {
        container.innerHTML = emptyState('❌', 'Ошибка загрузки');
    }
}

// --- Admin: Seasons ---
async function loadAdminSeasons() {
    const container = document.getElementById('admin-seasons-content');
    container.innerHTML = loading();

    const data = await api('/api/seasons');
    if (!data || data.length === 0) {
        container.innerHTML = emptyState('📂', 'Нет сезонов');
        return;
    }

    container.innerHTML = `<div class="list-container">${data.map(s => `
        <div class="season-item ${s.is_current ? 'current' : ''}">
            <div style="font-weight:700">${esc(s.name)}</div>
            ${s.is_current ? '<div class="season-badge">Текущий</div>' : ''}
        </div>
    `).join('')}</div>`;
}

async function createNewSeason() {
    const name = document.getElementById('new-season-name').value.trim();
    if (!name) { alert('Введи название сезона'); return; }
    if (!confirm(`Начать новый сезон "${name}"? Текущий будет архивирован.`)) return;

    try {
        const res = await fetch(`${API}/api/admin/season-new`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({initData, name}),
        });
        const data = await res.json();
        if (data.success) {
            alert('✅ Новый сезон создан!');
            document.getElementById('new-season-name').value = '';
            loadAdminSeasons();
        }
    } catch (e) {
        alert('Ошибка');
    }
}

// --- Admin: Nominations ---
async function loadAdminNominations() {
    const container = document.getElementById('admin-nominations-list');
    container.innerHTML = loading();

    const data = await api('/api/nominations/all');
    if (!data || data.length === 0) {
        container.innerHTML = emptyState('🏅', 'Нет номинаций');
        return;
    }

    container.innerHTML = data.map(n => `
        <div class="admin-event-item">
            <div class="admin-event-info">
                <div class="admin-event-name">🏅 ${esc(n.name)}</div>
            </div>
            <button class="btn-icon-danger" onclick="deleteNomination(${n.id}, '${esc(n.name)}')">🗑</button>
        </div>
    `).join('');
}

async function addNomination() {
    const input = document.getElementById('new-nom-name');
    const result = document.getElementById('nom-form-result');
    const name = input.value.trim();
    if (!name) { alert('Введи название'); return; }

    result.innerHTML = '';
    try {
        const res = await fetch(`${API}/api/admin/nominations`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({initData, name}),
        });
        const data = await res.json();
        if (data.success) {
            input.value = '';
            result.innerHTML = '<div class="result-success">✅ Номинация добавлена!</div>';
            loadAdminNominations();
        } else {
            result.innerHTML = `<div class="result-error">❌ ${data.error || 'Ошибка'}</div>`;
        }
    } catch (e) {
        result.innerHTML = '<div class="result-error">❌ Ошибка сети</div>';
    }
}

async function deleteNomination(id, name) {
    if (!confirm(`Удалить номинацию "${name}"?`)) return;
    try {
        const res = await fetch(`${API}/api/admin/nominations/${id}`, {
            method: 'DELETE',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({initData}),
        });
        const data = await res.json();
        if (data.success) {
            loadAdminNominations();
        }
    } catch (e) {
        alert('Ошибка удаления');
    }
}

// --- Admin: Results Input ---
let currentResultsEventId = null;

async function loadAdminResults() {
    const container = document.getElementById('admin-results-events');
    container.innerHTML = loading();

    const data = await api('/api/events?event_type=school');
    if (!data || data.length === 0) {
        container.innerHTML = emptyState('📅', 'Нет мероприятий');
        return;
    }

    container.innerHTML = data.map(e => {
        const statusIcon = e.status === 'completed' ? '✅' : '⏳';
        return `
            <div class="event-card" onclick="navigate('admin-results-form', ${e.id})" style="cursor:pointer">
                <div class="event-card-header">
                    <div class="event-card-name">${e.emoji} ${esc(e.name)}</div>
                    <div class="event-card-status">${statusIcon} ${e.status === 'completed' ? 'Есть результаты' : 'Нет результатов'}</div>
                </div>
                ${e.multiplier > 1 ? `<div class="event-card-details"><div class="event-card-detail">⚡ Баллы x${e.multiplier}</div></div>` : ''}
            </div>
        `;
    }).join('');
}

async function loadAdminResultsForm(eventId) {
    currentResultsEventId = eventId;
    const title = document.getElementById('results-form-title');
    const container = document.getElementById('results-form-content');
    container.innerHTML = loading();

    const data = await api(`/api/admin/events/${eventId}/participants`);
    if (!data || !data.participants) {
        container.innerHTML = emptyState('❌', 'Ошибка загрузки');
        return;
    }

    title.textContent = `📝 ${data.event_name}`;

    // Group by nomination
    const groups = {};
    data.participants.forEach(p => {
        if (!groups[p.nomination]) groups[p.nomination] = [];
        groups[p.nomination].push(p);
    });

    let html = '';
    for (const [nom, participants] of Object.entries(groups)) {
        html += `<div class="results-group">`;
        html += `<div class="results-group-title">🏅 ${esc(nom)}</div>`;
        participants.forEach(p => {
            const placeVal = p.main_place !== null ? p.main_place : '';
            html += `
                <div class="results-row">
                    <div class="results-name">${esc(p.name)}</div>
                    <div class="results-input-wrap">
                        <input type="number" class="results-place-input"
                               data-pid="${p.participant_id}"
                               value="${placeVal}"
                               placeholder="Место"
                               min="1"
                               inputmode="numeric">
                    </div>
                </div>
            `;
        });
        html += `</div>`;
    }

    container.innerHTML = html;
    document.getElementById('results-form-result').innerHTML = '';
}

async function saveResults() {
    const btn = document.getElementById('btn-save-results');
    const resultEl = document.getElementById('results-form-result');
    btn.disabled = true;
    btn.textContent = '⏳ Сохранение...';
    resultEl.innerHTML = '';

    const inputs = document.querySelectorAll('.results-place-input');
    const results = [];
    inputs.forEach(input => {
        const pid = parseInt(input.dataset.pid);
        const val = input.value.trim();
        results.push({
            participant_id: pid,
            main_place: val !== '' ? parseFloat(val) : null,
        });
    });

    try {
        const res = await fetch(`${API}/api/admin/events/${currentResultsEventId}/results`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({initData, results}),
        });
        const data = await res.json();
        if (data.success) {
            resultEl.innerHTML = '<div class="result-success">✅ Результаты сохранены!</div>';
        } else {
            resultEl.innerHTML = `<div class="result-error">❌ ${data.error || 'Ошибка'}</div>`;
        }
    } catch (e) {
        resultEl.innerHTML = '<div class="result-error">❌ Ошибка сети</div>';
    }

    btn.disabled = false;
    btn.textContent = '💾 Сохранить результаты';
}

// --- Admin: Dynamic nomination dropdown for participant form ---
async function loadParticipantForm() {
    const select = document.getElementById('pf-nomination');
    select.innerHTML = '<option value="">Выбери номинацию</option>';

    const data = await api('/api/nominations/all');
    if (data && data.length > 0) {
        data.forEach(n => {
            const opt = document.createElement('option');
            opt.value = n.name;
            opt.textContent = n.name;
            select.appendChild(opt);
        });
    }
}

// --- Util ---
function esc(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = String(str);
    return div.innerHTML;
}
