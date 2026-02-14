// ==================== State ====================
let controlEnabled = false;
let logCursor = 0;
let layout = null;
let servers = [];

// Canvas scale
const CANVAS_PADDING = 40;
let canvasScale = 1;
let canvasOffsetX = 0;
let canvasOffsetY = 0;

// Dragging
let dragging = null; // { id, startX, startY, origX, origY }

document.addEventListener('DOMContentLoaded', () => {
    fetchStatus();
    fetchLogs();
    fetchLayout();

    setInterval(fetchStatus, 2000);
    setInterval(fetchLogs, 2000);
});

// ==================== API Calls ====================

async function fetchStatus() {
    try {
        const res = await fetch('/api/status');
        const data = await res.json();
        servers = data.servers || [];
        controlEnabled = data.control_enabled;
        updateStatusUI(data);
        updateServerList(data);
    } catch (e) {
        console.error('Error fetching status:', e);
    }
}

async function fetchLogs() {
    try {
        const res = await fetch(`/api/logs?cursor=${logCursor}`);
        const data = await res.json();
        if (data.logs && data.logs.length > 0) {
            const container = document.getElementById('log-container');
            const atBottom = container.scrollHeight - container.scrollTop <= container.clientHeight + 20;
            data.logs.forEach(log => {
                const div = document.createElement('div');
                div.className = 'log-entry';
                div.textContent = log;
                container.appendChild(div);
            });
            logCursor = data.cursor;
            if (atBottom) container.scrollTop = container.scrollHeight;
        }
    } catch (e) {
        console.error('Error fetching logs:', e);
    }
}

async function fetchLayout() {
    try {
        const res = await fetch('/api/layout');
        layout = await res.json();
        renderLayout();
    } catch (e) {
        console.error('Error fetching layout:', e);
    }
}

async function connectServer() {
    const host = document.getElementById('server-host').value.trim();
    const port = document.getElementById('server-port').value.trim();
    if (!host) return alert('Please enter a host');

    try {
        const res = await fetch('/api/connect', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ host, port: parseInt(port) })
        });
        const data = await res.json();
        if (data.status === 'success') {
            fetchStatus();
            setTimeout(fetchLayout, 500);
        } else {
            alert(data.message);
        }
    } catch (e) {
        alert('Connection error: ' + e);
    }
}

async function disconnectServer(id) {
    try {
        const res = await fetch('/api/disconnect', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id })
        });
        const data = await res.json();
        if (data.status === 'success') {
            fetchStatus();
            fetchLayout();
        }
    } catch (e) {
        alert('Error: ' + e);
    }
}

async function toggleControl() {
    const url = controlEnabled ? '/api/control/disable' : '/api/control/enable';
    try {
        const res = await fetch(url, { method: 'POST' });
        const data = await res.json();
        if (data.status === 'success') {
            fetchStatus();
        } else {
            alert(data.message);
        }
    } catch (e) {
        alert('Error: ' + e);
    }
}

async function saveLayout() {
    if (!layout) return;
    try {
        const res = await fetch('/api/layout', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(layout)
        });
        const data = await res.json();
        if (data.status !== 'success') alert(data.message);
    } catch (e) {
        alert('Error saving layout: ' + e);
    }
}

function resetLayout() {
    if (!layout) return;
    // Reset master to origin, servers to the right stacked
    layout.master.x = 0;
    layout.master.y = 0;
    let offsetX = layout.master.w;
    for (const sid in layout.servers) {
        layout.servers[sid].x = offsetX;
        layout.servers[sid].y = 0;
        offsetX += layout.servers[sid].w;
    }
    renderLayout();
    saveLayout();
}

// ==================== UI Updates ====================

function updateStatusUI(data) {
    const badge = document.getElementById('control-badge');
    const btn = document.getElementById('control-btn');
    const statusText = document.getElementById('control-status');

    if (data.control_enabled) {
        badge.textContent = 'Enabled';
        badge.classList.add('running');
        btn.textContent = 'Disable Control';
        if (data.active_screen === 'master') {
            statusText.textContent = 'Controlling: This PC';
        } else {
            statusText.textContent = 'Controlling: ' + data.active_screen;
        }
    } else {
        badge.textContent = 'Disabled';
        badge.classList.remove('running');
        btn.textContent = 'Enable Control';
        statusText.textContent = data.servers.length > 0
            ? 'Ready — click Enable to start'
            : 'Disabled — connect a server first';
    }

    btn.disabled = data.servers.length === 0;
}

function updateServerList(data) {
    const list = document.getElementById('server-list');
    if (data.servers.length === 0) {
        list.innerHTML = '<div class="empty-state">No servers connected</div>';
        return;
    }

    list.innerHTML = data.servers.map(s => `
        <div class="server-item">
            <div class="server-info">
                <div class="server-dot ${s.is_active ? 'active' : ''}"></div>
                <div>
                    <div class="server-name">${s.host}:${s.port}</div>
                    <div class="server-res">${s.screen_w} × ${s.screen_h}</div>
                </div>
            </div>
            <button class="btn btn-danger btn-sm" onclick="disconnectServer('${s.id}')">Disconnect</button>
        </div>
    `).join('');
}

// ==================== Layout Canvas ====================

function renderLayout() {
    if (!layout) return;

    const canvas = document.getElementById('layout-canvas');
    canvas.innerHTML = '';

    // Compute bounding box of all screens
    let allScreens = [{ id: 'master', ...layout.master }];
    for (const sid in layout.servers) {
        allScreens.push({ id: sid, ...layout.servers[sid] });
    }

    if (allScreens.length === 0) return;

    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    allScreens.forEach(s => {
        minX = Math.min(minX, s.x);
        minY = Math.min(minY, s.y);
        maxX = Math.max(maxX, s.x + s.w);
        maxY = Math.max(maxY, s.y + s.h);
    });

    const totalW = maxX - minX;
    const totalH = maxY - minY;
    const canvasW = canvas.clientWidth - CANVAS_PADDING * 2;
    const canvasH = canvas.clientHeight - CANVAS_PADDING * 2;

    canvasScale = Math.min(canvasW / totalW, canvasH / totalH, 0.15);
    canvasOffsetX = CANVAS_PADDING + (canvasW - totalW * canvasScale) / 2 - minX * canvasScale;
    canvasOffsetY = CANVAS_PADDING + (canvasH - totalH * canvasScale) / 2 - minY * canvasScale;

    // Render each screen
    allScreens.forEach(s => {
        const div = document.createElement('div');
        div.className = `screen-block ${s.id === 'master' ? 'master-screen' : 'server-screen'}`;

        // Check if this server is active
        const serverData = servers.find(sv => sv.id === s.id);
        if (serverData && serverData.is_active) {
            div.classList.add('active');
        }

        const px = canvasOffsetX + s.x * canvasScale;
        const py = canvasOffsetY + s.y * canvasScale;
        const pw = s.w * canvasScale;
        const ph = s.h * canvasScale;

        div.style.left = px + 'px';
        div.style.top = py + 'px';
        div.style.width = pw + 'px';
        div.style.height = ph + 'px';

        const label = s.id === 'master' ? 'This PC' : s.id;
        div.innerHTML = `
            <span class="screen-label">${label}</span>
            <span class="screen-res">${s.w}×${s.h}</span>
        `;

        // Dragging for server screens only
        if (s.id !== 'master') {
            div.addEventListener('pointerdown', (e) => startDrag(e, s.id));
        }

        canvas.appendChild(div);
    });
}

function startDrag(e, serverId) {
    e.preventDefault();
    dragging = {
        id: serverId,
        startX: e.clientX,
        startY: e.clientY,
        origX: layout.servers[serverId].x,
        origY: layout.servers[serverId].y
    };

    const onMove = (e) => {
        if (!dragging) return;
        const dx = (e.clientX - dragging.startX) / canvasScale;
        const dy = (e.clientY - dragging.startY) / canvasScale;
        layout.servers[dragging.id].x = Math.round(dragging.origX + dx);
        layout.servers[dragging.id].y = Math.round(dragging.origY + dy);
        renderLayout();
    };

    const onUp = () => {
        if (dragging) {
            // Snap to nearest edge of master
            snapToMaster(dragging.id);
            renderLayout();
        }
        dragging = null;
        document.removeEventListener('pointermove', onMove);
        document.removeEventListener('pointerup', onUp);
    };

    document.addEventListener('pointermove', onMove);
    document.addEventListener('pointerup', onUp);
}

function snapToMaster(serverId) {
    if (!layout || !layout.servers[serverId]) return;

    const s = layout.servers[serverId];
    const m = layout.master;
    const SNAP = 100; // snap threshold in logical pixels

    // Calculate distances to each master edge
    const distRight = Math.abs(s.x - (m.x + m.w));
    const distLeft = Math.abs((s.x + s.w) - m.x);
    const distBottom = Math.abs(s.y - (m.y + m.h));
    const distTop = Math.abs((s.y + s.h) - m.y);

    const minDist = Math.min(distRight, distLeft, distBottom, distTop);

    if (minDist > SNAP * 5) return; // too far, don't snap

    if (minDist === distRight) {
        s.x = m.x + m.w;
        // Align vertical center
        if (Math.abs(s.y - m.y) < SNAP) s.y = m.y;
    } else if (minDist === distLeft) {
        s.x = m.x - s.w;
        if (Math.abs(s.y - m.y) < SNAP) s.y = m.y;
    } else if (minDist === distBottom) {
        s.y = m.y + m.h;
        if (Math.abs(s.x - m.x) < SNAP) s.x = m.x;
    } else if (minDist === distTop) {
        s.y = m.y - s.h;
        if (Math.abs(s.x - m.x) < SNAP) s.x = m.x;
    }
}

// Re-render layout on window resize
window.addEventListener('resize', () => {
    if (layout) renderLayout();
});
