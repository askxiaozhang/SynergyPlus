let isRunning = false;
let logCursor = 0;

document.addEventListener('DOMContentLoaded', () => {
    // Initial fetch
    fetchStatus();
    fetchLogs();

    // Poll for updates
    setInterval(fetchStatus, 2000);
    setInterval(fetchLogs, 2000);
});

async function fetchStatus() {
    try {
        const response = await fetch('/api/status');
        const data = await response.json();

        updateStatusUI(data);
    } catch (error) {
        console.error('Error fetching status:', error);
    }
}

function updateStatusUI(data) {
    const statusBadge = document.getElementById('server-status-badge');
    const statusText = document.getElementById('server-status');
    const clientText = document.getElementById('client-info');
    const startBtn = document.getElementById('start-btn');
    const stopBtn = document.getElementById('stop-btn');
    const portText = document.getElementById('server-port');

    isRunning = data.running;

    if (isRunning) {
        statusBadge.textContent = 'Running';
        statusBadge.classList.add('running');
        statusText.textContent = 'Running';
        startBtn.disabled = true;
        stopBtn.disabled = false;
    } else {
        statusBadge.textContent = 'Not Running';
        statusBadge.classList.remove('running');
        statusText.textContent = 'Not Running';
        startBtn.disabled = false;
        stopBtn.disabled = true;
    }

    // Update client info
    if (data.client_connected) {
        clientText.textContent = `${data.client_address}`;
    } else {
        clientText.textContent = 'None';
    }

    portText.textContent = data.port;

    // Update config inputs if not focused (to avoid interrupting typing)
    if (document.activeElement.id !== 'config-port') {
        // Only update if value changed externally, but honestly for config it's better to fetch once or on explicit reload
        // For simplicity we won't auto-update inputs to avoid overwriting user input
    }
}

async function fetchLogs() {
    try {
        const response = await fetch(`/api/logs?cursor=${logCursor}`);
        const data = await response.json();

        if (data.logs && data.logs.length > 0) {
            const logContainer = document.getElementById('log-container');
            const wasScrolledToBottom = logContainer.scrollHeight - logContainer.scrollTop === logContainer.clientHeight;

            data.logs.forEach(log => {
                const entry = document.createElement('div');
                entry.className = 'log-entry';
                entry.textContent = log;
                logContainer.appendChild(entry);
            });

            logCursor = data.cursor;

            if (wasScrolledToBottom) {
                logContainer.scrollTop = logContainer.scrollHeight;
            }
        }
    } catch (error) {
        console.error('Error fetching logs:', error);
    }
}

async function startServer() {
    try {
        const response = await fetch('/api/start', { method: 'POST' });
        const data = await response.json();
        if (data.status === 'success') {
            fetchStatus(); // Instant update
        } else {
            alert('Failed to start server: ' + data.message);
        }
    } catch (error) {
        alert('Error starting server: ' + error);
    }
}

async function stopServer() {
    try {
        const response = await fetch('/api/stop', { method: 'POST' });
        const data = await response.json();
        if (data.status === 'success') {
            fetchStatus();
        } else {
            alert('Failed to stop server: ' + data.message);
        }
    } catch (error) {
        alert('Error stopping server: ' + error);
    }
}

async function saveConfig() {
    const port = document.getElementById('config-port').value;
    const whitelist = document.getElementById('config-whitelist').value;

    const configData = {
        'network.port': parseInt(port),
        'security.whitelist': whitelist.split(',').map(s => s.trim()).filter(s => s.length > 0)
    };

    try {
        const response = await fetch('/api/config', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(configData)
        });

        const data = await response.json();
        if (data.status === 'success') {
            alert('Configuration saved. If server is running, please restart it to apply changes.');
            fetchStatus();
        } else {
            alert('Failed to save configuration: ' + data.message);
        }
    } catch (error) {
        alert('Error saving configuration: ' + error);
    }
}
