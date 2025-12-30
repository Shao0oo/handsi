/**
 * Handsi Control Panel - Frontend Logic
 *
 * Handles UI interactions and API communication via QWebChannel.
 */

// === Configuration ===
const STATUS_POLL_INTERVAL = 500;  // ms

// === State ===
let statusPollTimer = null;
let currentSettings = {};
let bridge = null;  // Qt bridge object
let bridgeReady = false;

// === DOM Elements ===
const elements = {
    // Status
    connectionStatus: document.getElementById('connectionStatus'),
    runningStatus: document.getElementById('runningStatus'),
    fpsValue: document.getElementById('fpsValue'),
    activityValue: document.getElementById('activityValue'),
    latchStatus: document.getElementById('latchStatus'),
    framesCaptured: document.getElementById('framesCaptured'),
    framesProcessed: document.getElementById('framesProcessed'),

    // Controls
    startBtn: document.getElementById('startBtn'),
    stopBtn: document.getElementById('stopBtn'),
    controlMessage: document.getElementById('controlMessage'),

    // Settings - Mouse
    sensitivity: document.getElementById('sensitivity'),
    sensitivityValue: document.getElementById('sensitivityValue'),
    smoothing: document.getElementById('smoothing'),
    smoothingValue: document.getElementById('smoothingValue'),
    deadZone: document.getElementById('deadZone'),
    deadZoneValue: document.getElementById('deadZoneValue'),
    mirrorX: document.getElementById('mirrorX'),

    // Settings - Gestures
    pinchThreshold: document.getElementById('pinchThreshold'),
    pinchThresholdValue: document.getElementById('pinchThresholdValue'),
    fistThreshold: document.getElementById('fistThreshold'),
    fistThresholdValue: document.getElementById('fistThresholdValue'),
    swipeVelocity: document.getElementById('swipeVelocity'),
    swipeVelocityValue: document.getElementById('swipeVelocityValue'),
    openHandSpread: document.getElementById('openHandSpread'),
    openHandSpreadValue: document.getElementById('openHandSpreadValue'),
    thumbsVertical: document.getElementById('thumbsVertical'),
    thumbsVerticalValue: document.getElementById('thumbsVerticalValue'),

    // Settings - Timing
    debounceMs: document.getElementById('debounceMs'),
    debounceMsValue: document.getElementById('debounceMsValue'),
    latchCooldownMs: document.getElementById('latchCooldownMs'),
    latchCooldownMsValue: document.getElementById('latchCooldownMsValue'),
    smoothingWindow: document.getElementById('smoothingWindow'),
    smoothingWindowValue: document.getElementById('smoothingWindowValue'),

    // Settings controls
    saveSettingsBtn: document.getElementById('saveSettingsBtn'),
    resetSettingsBtn: document.getElementById('resetSettingsBtn'),
    settingsMessage: document.getElementById('settingsMessage')
};

// === QWebChannel Initialization ===

function initQWebChannel() {
    return new Promise((resolve, reject) => {
        if (typeof QWebChannel === 'undefined') {
            console.error('QWebChannel not available - are we running in Qt?');
            reject(new Error('QWebChannel not available'));
            return;
        }

        new QWebChannel(qt.webChannelTransport, (channel) => {
            bridge = channel.objects.bridge;
            bridgeReady = true;
            console.log('QWebChannel bridge connected');

            // Connect to status change signal
            bridge.statusChanged.connect((statusJson) => {
                const status = JSON.parse(statusJson);
                updateStatusUI(status);
            });

            resolve();
        });
    });
}

// === API Functions (Qt Bridge) ===
// QWebChannel requires callback-based API, not async/await

function startHandsi() {
    if (!bridgeReady) return Promise.resolve({ success: false, error: 'Bridge not ready' });

    return new Promise((resolve) => {
        try {
            bridge.start((resultJson) => {
                console.log('start() response:', resultJson);
                const result = JSON.parse(resultJson);
                resolve({ success: result.success, data: result });
            });
        } catch (error) {
            console.error('start() failed:', error);
            resolve({ success: false, error: error.message });
        }
    });
}

function stopHandsi() {
    if (!bridgeReady) return Promise.resolve({ success: false, error: 'Bridge not ready' });

    return new Promise((resolve) => {
        try {
            bridge.stop((resultJson) => {
                console.log('stop() response:', resultJson);
                const result = JSON.parse(resultJson);
                resolve({ success: result.success, data: result });
            });
        } catch (error) {
            console.error('stop() failed:', error);
            resolve({ success: false, error: error.message });
        }
    });
}

function getStatus() {
    if (!bridgeReady) return Promise.resolve({ success: false, error: 'Bridge not ready' });

    return new Promise((resolve) => {
        try {
            bridge.getStatus((statusJson) => {
                const status = JSON.parse(statusJson);
                resolve({ success: true, data: status });
            });
        } catch (error) {
            console.error('getStatus() failed:', error);
            resolve({ success: false, error: error.message });
        }
    });
}

function getSettings() {
    if (!bridgeReady) return Promise.resolve({ success: false, error: 'Bridge not ready' });

    return new Promise((resolve) => {
        try {
            bridge.getSettings((settingsJson) => {
                const settings = JSON.parse(settingsJson);
                resolve({ success: true, data: settings });
            });
        } catch (error) {
            console.error('getSettings() failed:', error);
            resolve({ success: false, error: error.message });
        }
    });
}

function updateSettings(settings) {
    if (!bridgeReady) return Promise.resolve({ success: false, error: 'Bridge not ready' });

    return new Promise((resolve) => {
        try {
            const settingsJson = JSON.stringify(settings);
            bridge.updateSettings(settingsJson, (resultJson) => {
                console.log('updateSettings() response:', resultJson);
                const result = JSON.parse(resultJson);
                resolve({ success: result.success, data: result });
            });
        } catch (error) {
            console.error('updateSettings() failed:', error);
            resolve({ success: false, error: error.message });
        }
    });
}

// === UI Update Functions ===

function updateStatusUI(status) {
    // Running status
    const running = status.running;
    elements.runningStatus.textContent = running ? 'Running' : 'Stopped';
    elements.runningStatus.className = running ? 'status-value running' : 'status-value stopped';

    // FPS
    elements.fpsValue.textContent = status.fps || 0;

    // Activity
    elements.activityValue.textContent = status.activity || 'IDLE';

    // Latch status
    elements.latchStatus.textContent = status.latch_enabled ? 'Enabled' : 'Disabled';
    elements.latchStatus.className = status.latch_enabled ? 'status-value running' : 'status-value';

    // Frame counts
    elements.framesCaptured.textContent = status.frames_captured || 0;
    elements.framesProcessed.textContent = status.frames_processed || 0;

    // Button states
    elements.startBtn.disabled = running;
    elements.stopBtn.disabled = !running;
}

function updateSettingsUI(settings) {
    currentSettings = settings;

    // Mouse settings
    elements.sensitivity.value = settings.sensitivity;
    elements.sensitivityValue.textContent = settings.sensitivity;

    elements.smoothing.value = settings.smoothing;
    elements.smoothingValue.textContent = settings.smoothing;

    elements.deadZone.value = settings.dead_zone;
    elements.deadZoneValue.textContent = settings.dead_zone;

    elements.mirrorX.checked = settings.mirror_x;

    // Gesture settings
    elements.pinchThreshold.value = settings.pinch_threshold;
    elements.pinchThresholdValue.textContent = settings.pinch_threshold;

    elements.fistThreshold.value = settings.fist_threshold;
    elements.fistThresholdValue.textContent = settings.fist_threshold;

    elements.swipeVelocity.value = settings.swipe_velocity;
    elements.swipeVelocityValue.textContent = settings.swipe_velocity;

    elements.openHandSpread.value = settings.open_hand_spread;
    elements.openHandSpreadValue.textContent = settings.open_hand_spread;

    elements.thumbsVertical.value = settings.thumbs_vertical;
    elements.thumbsVerticalValue.textContent = settings.thumbs_vertical;

    // Timing settings
    elements.debounceMs.value = settings.debounce_ms;
    elements.debounceMsValue.textContent = settings.debounce_ms;

    elements.latchCooldownMs.value = settings.latch_cooldown_ms;
    elements.latchCooldownMsValue.textContent = settings.latch_cooldown_ms;

    elements.smoothingWindow.value = settings.smoothing_window;
    elements.smoothingWindowValue.textContent = settings.smoothing_window;
}

function showMessage(element, type, message, duration = 3000) {
    element.textContent = message;
    element.className = `message ${type}`;

    setTimeout(() => {
        element.className = 'message';
        element.textContent = '';
    }, duration);
}

function setConnectionStatus(connected) {
    if (connected) {
        elements.connectionStatus.classList.remove('disconnected');
        elements.connectionStatus.querySelector('.label').textContent = 'Connected';
    } else {
        elements.connectionStatus.classList.add('disconnected');
        elements.connectionStatus.querySelector('.label').textContent = 'Disconnected';
    }
}

// === Event Handlers ===

async function handleStart() {
    elements.startBtn.disabled = true;
    const result = await startHandsi();

    if (result.success) {
        showMessage(elements.controlMessage, 'success', 'Handsi started successfully');
        startStatusPolling();
    } else {
        showMessage(elements.controlMessage, 'error', `Failed to start: ${result.data.error || result.error}`);
        elements.startBtn.disabled = false;
    }
}

async function handleStop() {
    elements.stopBtn.disabled = true;
    const result = await stopHandsi();

    if (result.success) {
        showMessage(elements.controlMessage, 'success', 'Handsi stopped successfully');
        stopStatusPolling();

        // Update UI to reflect stopped state
        updateStatusUI({
            running: false,
            fps: 0,
            activity: 'IDLE',
            frames_captured: 0,
            frames_processed: 0,
            latch_enabled: false
        });
    } else {
        showMessage(elements.controlMessage, 'error', `Failed to stop: ${result.data.error || result.error}`);
        elements.stopBtn.disabled = false;
    }
}

async function handleSaveSettings() {
    // Collect current settings from UI
    const settings = {
        sensitivity: parseFloat(elements.sensitivity.value),
        smoothing: parseFloat(elements.smoothing.value),
        dead_zone: parseFloat(elements.deadZone.value),
        mirror_x: elements.mirrorX.checked,
        pinch_threshold: parseFloat(elements.pinchThreshold.value),
        fist_threshold: parseFloat(elements.fistThreshold.value),
        swipe_velocity: parseFloat(elements.swipeVelocity.value),
        open_hand_spread: parseFloat(elements.openHandSpread.value),
        thumbs_vertical: parseFloat(elements.thumbsVertical.value),
        debounce_ms: parseInt(elements.debounceMs.value),
        latch_cooldown_ms: parseInt(elements.latchCooldownMs.value),
        smoothing_window: parseInt(elements.smoothingWindow.value)
    };

    const result = await updateSettings(settings);

    if (result.success) {
        let message = 'Settings saved successfully';
        if (result.data.restart_needed) {
            message += ' - Restart detection to apply changes';
        }
        showMessage(elements.settingsMessage, result.data.restart_needed ? 'info' : 'success', message, 5000);
    } else {
        showMessage(elements.settingsMessage, 'error', `Failed to save settings: ${result.data.error || result.error}`);
    }
}

async function handleResetSettings() {
    // Reload settings from server (which has defaults)
    const result = await getSettings();
    if (result.success) {
        updateSettingsUI(result.data);
        showMessage(elements.settingsMessage, 'info', 'Settings reset to current config values');
    }
}

// === Slider Updates ===

function setupSliderListeners() {
    // Mouse settings
    elements.sensitivity.addEventListener('input', (e) => {
        elements.sensitivityValue.textContent = e.target.value;
    });

    elements.smoothing.addEventListener('input', (e) => {
        elements.smoothingValue.textContent = e.target.value;
    });

    elements.deadZone.addEventListener('input', (e) => {
        elements.deadZoneValue.textContent = e.target.value;
    });

    // Gesture settings
    elements.pinchThreshold.addEventListener('input', (e) => {
        elements.pinchThresholdValue.textContent = e.target.value;
    });

    elements.fistThreshold.addEventListener('input', (e) => {
        elements.fistThresholdValue.textContent = e.target.value;
    });

    elements.swipeVelocity.addEventListener('input', (e) => {
        elements.swipeVelocityValue.textContent = e.target.value;
    });

    elements.openHandSpread.addEventListener('input', (e) => {
        elements.openHandSpreadValue.textContent = e.target.value;
    });

    elements.thumbsVertical.addEventListener('input', (e) => {
        elements.thumbsVerticalValue.textContent = e.target.value;
    });

    // Timing settings
    elements.debounceMs.addEventListener('input', (e) => {
        elements.debounceMsValue.textContent = e.target.value;
    });

    elements.latchCooldownMs.addEventListener('input', (e) => {
        elements.latchCooldownMsValue.textContent = e.target.value;
    });

    elements.smoothingWindow.addEventListener('input', (e) => {
        elements.smoothingWindowValue.textContent = e.target.value;
    });
}

// === Status Polling ===

function startStatusPolling() {
    if (statusPollTimer) return;

    statusPollTimer = setInterval(async () => {
        const result = await getStatus();
        if (result.success) {
            updateStatusUI(result.data);
            setConnectionStatus(true);
        } else {
            setConnectionStatus(false);
        }
    }, STATUS_POLL_INTERVAL);
}

function stopStatusPolling() {
    if (statusPollTimer) {
        clearInterval(statusPollTimer);
        statusPollTimer = null;
    }
}

// === Initialization ===

async function init() {
    console.log('Initializing Handsi Control Panel...');

    // Initialize QWebChannel first
    try {
        await initQWebChannel();
        console.log('QWebChannel initialized');
    } catch (error) {
        console.error('Failed to initialize QWebChannel:', error);
        setConnectionStatus(false);
        showMessage(elements.controlMessage, 'error', 'Failed to initialize bridge');
        return;
    }

    // Setup event listeners
    elements.startBtn.addEventListener('click', handleStart);
    elements.stopBtn.addEventListener('click', handleStop);
    elements.saveSettingsBtn.addEventListener('click', handleSaveSettings);
    elements.resetSettingsBtn.addEventListener('click', handleResetSettings);

    setupSliderListeners();

    // Load initial data
    const statusResult = await getStatus();
    if (statusResult.success) {
        updateStatusUI(statusResult.data);
        setConnectionStatus(true);

        // Start polling if already running
        if (statusResult.data.running) {
            startStatusPolling();
        }
    } else {
        setConnectionStatus(false);
        showMessage(elements.controlMessage, 'error', 'Failed to connect to bridge');
    }

    const settingsResult = await getSettings();
    if (settingsResult.success) {
        updateSettingsUI(settingsResult.data);
    }

    console.log('Initialization complete');
}

// === Start Application ===

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}
