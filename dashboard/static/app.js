// KubeGuard Dashboard - Advanced WebSocket Client with Chart.js
const WS_URL = `ws://${window.location.host}/ws`;

// DOM Elements
const podsContainer = document.getElementById('pods-container');
const eventsContainer = document.getElementById('events-container');
const statusIndicator = document.getElementById('connection-status');
const lastUpdate = document.getElementById('last-update');
const podCount = document.getElementById('pod-count');
const prometheusStatus = document.getElementById('prometheus-status');
const riskContainer = document.getElementById('risk-container');

// Stats elements
const avgUptimeEl = document.getElementById('avg-uptime');
const requestRateEl = document.getElementById('request-rate');
const totalCrashesEl = document.getElementById('total-crashes');
const totalRestartsEl = document.getElementById('total-restarts');
const statRestartsEl = document.getElementById('stat-restarts');
const crashCountEl = document.getElementById('crash-count');
const recoveryCountEl = document.getElementById('recovery-count');

// State
let ws;
let reconnectAttempts = 0;
let prometheusAvailable = false;
let currentPods = [];

const CRASH_STATUSES = ['CrashLoopBackOff', 'Error', 'OOMKilled', 'ImagePullBackOff'];

// ============== Chart.js Configuration ==============
const chartConfig = {
    requestRate: null,
    restartTrends: null
};

const chartColors = {
    primary: '#2563eb',
    primaryLight: 'rgba(37, 99, 235, 0.1)',
    danger: '#ef4444',
    dangerLight: 'rgba(239, 68, 68, 0.2)',
    success: '#10b981',
    warning: '#f59e0b'
};

const commonChartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    animation: { duration: 300 },
    plugins: {
        legend: { display: false }
    },
    scales: {
        x: {
            grid: { color: 'rgba(0,0,0,0.05)' },
            ticks: { color: '#64748b', font: { size: 10 }, maxTicksLimit: 8 }
        },
        y: {
            grid: { color: 'rgba(0,0,0,0.05)' },
            ticks: { color: '#64748b', font: { size: 10 } },
            beginAtZero: true
        }
    }
};

function initCharts() {
    // Request Rate Line Chart
    const requestCtx = document.getElementById('request-chart');
    if (requestCtx) {
        chartConfig.requestRate = new Chart(requestCtx.getContext('2d'), {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'Requests/min',
                    data: [],
                    borderColor: chartColors.primary,
                    backgroundColor: chartColors.primaryLight,
                    fill: true,
                    tension: 0.4,
                    pointRadius: 2,
                    borderWidth: 2
                }]
            },
            options: commonChartOptions
        });
    }

    // Restart Trends Bar Chart
    const restartCtx = document.getElementById('restart-chart');
    if (restartCtx) {
        chartConfig.restartTrends = new Chart(restartCtx.getContext('2d'), {
            type: 'bar',
            data: {
                labels: [],
                datasets: [{
                    label: 'Restarts',
                    data: [],
                    backgroundColor: chartColors.danger,
                    borderRadius: 6,
                    borderSkipped: false
                }]
            },
            options: {
                ...commonChartOptions,
                plugins: {
                    ...commonChartOptions.plugins,
                    tooltip: {
                        callbacks: {
                            label: (ctx) => `${ctx.parsed.y} restarts`
                        }
                    }
                }
            }
        });
    }
}

// ============== Prometheus Metrics ==============
async function fetchMetrics() {
    try {
        const [healthSummary, riskScores, requestRate] = await Promise.all([
            fetch('/api/metrics/health-summary').then(r => r.json()),
            fetch('/api/metrics/risk-scores').then(r => r.json()),
            fetch('/api/metrics/request-rate').then(r => r.json())
        ]);

        prometheusAvailable = healthSummary.prometheus_available;
        updatePrometheusStatus(prometheusAvailable);

        // Update health summary
        if (healthSummary.success) {
            avgUptimeEl.textContent = Math.round(healthSummary.avg_uptime);
            const reqPerMin = (healthSummary.request_rate_per_sec || 0) * 60;
            requestRateEl.textContent = `${reqPerMin.toFixed(1)}/min`;
            totalCrashesEl.textContent = Math.round(healthSummary.total_crashes);
            totalRestartsEl.textContent = Math.round(healthSummary.total_restarts || 0);
        }

        // Update risk scores
        if (riskScores.success && riskScores.scores) {
            renderRiskScores(riskScores.scores);
        }

        // Update request rate chart
        if (requestRate.success && requestRate.data && requestRate.data.length > 0) {
            updateRequestRateChart(requestRate.data);
        }

        // Update charts with pod restart data
        if (currentPods.length > 0) {
            updateRestartChart(currentPods);
        }

        // Show/hide chart fallbacks
        toggleChartFallbacks(!prometheusAvailable);

    } catch (e) {
        console.error('Metrics fetch failed:', e);
        updatePrometheusStatus(false);
        toggleChartFallbacks(true);
    }
}

function updateRequestRateChart(data) {
    if (!chartConfig.requestRate || !data || data.length === 0) return;

    // Get the first series (aggregate or first pod)
    const series = data[0];
    if (!series.values || series.values.length === 0) return;

    // Extract timestamps and values
    const values = series.values;
    const labels = values.map(v => {
        const date = new Date(v[0] * 1000);
        return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    });
    const dataPoints = values.map(v => parseFloat(v[1]).toFixed(2));

    chartConfig.requestRate.data.labels = labels;
    chartConfig.requestRate.data.datasets[0].data = dataPoints;
    chartConfig.requestRate.update('none');
}

function updateRestartChart(pods) {
    if (!chartConfig.restartTrends) return;

    const labels = pods.map(p => p.name.split('-').slice(-1)[0]);
    const data = pods.map(p => p.restarts);

    chartConfig.restartTrends.data.labels = labels;
    chartConfig.restartTrends.data.datasets[0].data = data;
    chartConfig.restartTrends.update('none');
}

function renderRiskScores(scores) {
    if (!scores || scores.length === 0) {
        riskContainer.innerHTML = '<div class="no-data">No pods found</div>';
        return;
    }

    riskContainer.innerHTML = scores.map(s => `
        <div class="risk-item ${getRiskClass(s.score)}">
            <span class="risk-pod">${truncate(s.pod.split('-').slice(-1)[0], 8)}</span>
            <div class="risk-bar">
                <div class="risk-fill" style="width: ${s.score}%"></div>
            </div>
            <span class="risk-score">${s.score}%</span>
        </div>
    `).join('');
}

function getRiskClass(score) {
    if (score >= 60) return 'risk-high';
    if (score >= 30) return 'risk-medium';
    return 'risk-low';
}

function updatePrometheusStatus(available) {
    if (available) {
        prometheusStatus.classList.remove('unavailable');
        prometheusStatus.classList.add('available');
    } else {
        prometheusStatus.classList.remove('available');
        prometheusStatus.classList.add('unavailable');
    }
}

function toggleChartFallbacks(show) {
    document.querySelectorAll('.chart-fallback').forEach(el => {
        el.classList.toggle('visible', show);
    });
    document.querySelectorAll('.chart-card canvas').forEach(el => {
        el.style.display = show ? 'none' : 'block';
    });
}

function formatNumber(num) {
    if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
    if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
    return Math.round(num).toString();
}

// ============== WebSocket Connection ==============
function connect() {
    ws = new WebSocket(WS_URL);

    ws.onopen = () => {
        statusIndicator.textContent = '● Connected';
        statusIndicator.className = 'connected';
        reconnectAttempts = 0;
    };

    ws.onclose = () => {
        statusIndicator.textContent = '● Disconnected';
        statusIndicator.className = 'disconnected';
        const delay = Math.min(1000 * Math.pow(2, reconnectAttempts), 10000);
        reconnectAttempts++;
        setTimeout(connect, delay);
    };

    ws.onerror = () => {
        ws.close();
    };

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        currentPods = data.pods;
        renderPods(data.pods);
        renderEvents(data.events);
        updateStats(data.pods, data.events);
        lastUpdate.textContent = new Date(data.timestamp).toLocaleTimeString();
    };
}

// ============== Pod Rendering ==============
function renderPods(pods) {
    const running = pods.filter(p => p.status === 'Running').length;
    podCount.textContent = `${running}/${pods.length} Running`;
    podCount.className = running === pods.length ? 'healthy' : 'unhealthy';

    podsContainer.innerHTML = pods.map(pod => `
        <div class="pod-card ${getStatusClass(pod.status)}" onclick='openPodModal(${JSON.stringify(pod).replace(/'/g, "\\'")})'>
            <div class="pod-header">
                <span class="status-dot"></span>
                <span class="pod-name">${pod.name}</span>
            </div>
            <div class="pod-body">
                <div class="pod-status">${pod.status}</div>
                <div class="pod-restarts">
                    <span class="label">Restarts:</span>
                    <span class="value">${pod.restarts}</span>
                </div>
                ${pod.message ? `<div class="pod-message">${truncate(pod.message, 80)}</div>` : ''}
            </div>
            <div class="pod-footer">
                ${pod.ready ? '<span class="ready-badge">Ready</span>' : '<span class="not-ready-badge">Not Ready</span>'}
            </div>
        </div>
    `).join('');
}

function getStatusClass(status) {
    if (status === 'Running') return 'status-running';
    if (CRASH_STATUSES.includes(status)) return 'status-crashed';
    return 'status-pending';
}

function truncate(str, len) {
    if (!str) return '';
    return str.length > len ? str.substring(0, len) + '...' : str;
}

// ============== Events Timeline ==============
function renderEvents(events) {
    if (!events || events.length === 0) {
        eventsContainer.innerHTML = '<div class="no-events">No events yet. Trigger a crash to see self-healing!</div>';
        return;
    }

    eventsContainer.innerHTML = events.slice(0, 12).map(evt => `
        <div class="event-item event-${evt.type}">
            <span class="event-icon">${getEventIcon(evt.type)}</span>
            <div class="event-content">
                <span class="event-pod">${evt.pod}</span>
                <span class="event-status">${evt.status}</span>
            </div>
            <span class="event-time">${formatTime(evt.time)}</span>
        </div>
    `).join('');
}

function getEventIcon(type) {
    switch(type) {
        case 'crash': return '💥';
        case 'recovery': return '✅';
        case 'manual': return '🔧';
        default: return '📌';
    }
}

function formatTime(isoString) {
    return new Date(isoString).toLocaleTimeString();
}

// ============== Stats ==============
function updateStats(pods, events) {
    const restarts = pods.reduce((sum, p) => sum + p.restarts, 0);
    totalRestartsEl.textContent = restarts;
    statRestartsEl.textContent = restarts;

    const crashes = events.filter(e => e.type === 'crash' || e.type === 'manual').length;
    const recoveries = events.filter(e => e.type === 'recovery').length;

    crashCountEl.textContent = crashes;
    recoveryCountEl.textContent = recoveries;

    // Update restart chart with current pod data
    updateRestartChart(pods);
}

// ============== Pod Modal ==============
function openPodModal(pod) {
    const modal = document.getElementById('pod-modal');
    document.getElementById('modal-pod-name').textContent = pod.name;

    const statusEl = document.getElementById('modal-status');
    statusEl.textContent = pod.status;
    statusEl.className = `detail-value ${getStatusClass(pod.status)}`;

    document.getElementById('modal-restarts').textContent = pod.restarts;
    document.getElementById('modal-ready').textContent = pod.ready ? 'Yes' : 'No';

    modal.classList.remove('hidden');
}

function closePodModal() {
    document.getElementById('pod-modal').classList.add('hidden');
}

// Close modal on backdrop click
document.getElementById('pod-modal')?.addEventListener('click', (e) => {
    if (e.target.id === 'pod-modal') closePodModal();
});

// Close modal on Escape key
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closePodModal();
});

// ============== Crash Button ==============
document.getElementById('trigger-crash').addEventListener('click', async () => {
    const btn = document.getElementById('trigger-crash');
    btn.disabled = true;
    btn.innerHTML = '⏳ Crashing...';

    try {
        await fetch('/api/crash', { method: 'POST' });
    } catch (e) {
        // Expected - pod crashes
    }

    setTimeout(() => {
        btn.disabled = false;
        btn.innerHTML = '💥 Trigger Crash';
    }, 2000);
});

// ============== Initialization ==============
document.addEventListener('DOMContentLoaded', () => {
    initCharts();
    connect();
    fetchMetrics();

    // Fetch metrics every 10 seconds
    setInterval(fetchMetrics, 10000);
});
