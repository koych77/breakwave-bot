/* === Break Wave Mini App === */

const API = window.location.origin;
const tg = window.Telegram?.WebApp;

let currentScreen = 'home';
let screenHistory = [];
let currentEventTab = 'school';

// --- Init ---
document.addEventListener('DOMContentLoaded', () => {
    if (tg) {
        tg.ready();
        tg.expand();
        tg.enableClosingConfirmation?.();
        tg.headerColor = '#0F2035';
        tg.backgroundColor = '#0A1628';
        tg.setBackgroundColor?.('#0A1628');
        tg.setHeaderColor?.('#0F2035');
    }

    // Check hash for deep link
    const hash = window.location.hash.replace('#', '');
    if (hash && hash !== '') {
        navigate(hash);
    } else {
        loadHome();
    }
});

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

// --- Util ---
function esc(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = String(str);
    return div.innerHTML;
}
