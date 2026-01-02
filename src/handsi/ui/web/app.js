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
    // Tabs
    tabButtons: document.querySelectorAll('.tab-btn'),
    tabContents: document.querySelectorAll('.tab-content'),

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
    invertScroll: document.getElementById('invertScroll'),

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
    settingsMessage: document.getElementById('settingsMessage'),

    // Mappings
    mappingsList: document.getElementById('mappingsList'),
    mappingsMessage: document.getElementById('mappingsMessage'),

    // Info
    infoCameraDevice: document.getElementById('infoCameraDevice'),
    infoCameraResolution: document.getElementById('infoCameraResolution'),
    infoCameraFPS: document.getElementById('infoCameraFPS'),
    infoSystemPlatform: document.getElementById('infoSystemPlatform'),
    infoSystemVersion: document.getElementById('infoSystemVersion'),
    infoSystemPython: document.getElementById('infoSystemPython'),
    infoPermissions: document.getElementById('infoPermissions'),

    // First run modal
    firstRunModal: document.getElementById('firstRunModal'),
    closeFirstRunModal: document.getElementById('closeFirstRunModal')
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

function resetToDefaults() {
    if (!bridgeReady) return Promise.resolve({ success: false, error: 'Bridge not ready' });

    return new Promise((resolve) => {
        try {
            bridge.resetToDefaults((resultJson) => {
                console.log('resetToDefaults() response:', resultJson);
                const result = JSON.parse(resultJson);
                resolve({ success: result.success, data: result });
            });
        } catch (error) {
            console.error('resetToDefaults() failed:', error);
            resolve({ success: false, error: error.message });
        }
    });
}

function restart() {
    if (!bridgeReady) return Promise.resolve({ success: false, error: 'Bridge not ready' });

    return new Promise((resolve) => {
        try {
            bridge.restart((resultJson) => {
                console.log('restart() response:', resultJson);
                const result = JSON.parse(resultJson);
                resolve({ success: result.success, data: result });
            });
        } catch (error) {
            console.error('restart() failed:', error);
            resolve({ success: false, error: error.message });
        }
    });
}

function getMappings() {
    if (!bridgeReady) return Promise.resolve({ success: false, error: 'Bridge not ready' });

    return new Promise((resolve) => {
        try {
            bridge.getMappings((resultJson) => {
                const result = JSON.parse(resultJson);
                resolve({ success: result.success, data: result });
            });
        } catch (error) {
            console.error('getMappings() failed:', error);
            resolve({ success: false, error: error.message });
        }
    });
}

function updateMappings(mappings) {
    if (!bridgeReady) return Promise.resolve({ success: false, error: 'Bridge not ready' });

    return new Promise((resolve) => {
        try {
            const mappingsJson = JSON.stringify(mappings);
            bridge.updateMappings(mappingsJson, (resultJson) => {
                console.log('updateMappings() response:', resultJson);
                const result = JSON.parse(resultJson);
                resolve({ success: result.success, data: result });
            });
        } catch (error) {
            console.error('updateMappings() failed:', error);
            resolve({ success: false, error: error.message });
        }
    });
}

function getSystemInfo() {
    if (!bridgeReady) return Promise.resolve({ success: false, error: 'Bridge not ready' });

    return new Promise((resolve) => {
        try {
            bridge.getSystemInfo((resultJson) => {
                const result = JSON.parse(resultJson);
                resolve({ success: result.success, data: result });
            });
        } catch (error) {
            console.error('getSystemInfo() failed:', error);
            resolve({ success: false, error: error.message });
        }
    });
}

function checkFirstRun() {
    if (!bridgeReady) return Promise.resolve({ success: false, error: 'Bridge not ready' });

    return new Promise((resolve) => {
        try {
            bridge.checkFirstRun((resultJson) => {
                const result = JSON.parse(resultJson);
                resolve({ success: result.success, data: result });
            });
        } catch (error) {
            console.error('checkFirstRun() failed:', error);
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

    // Scroll settings
    elements.invertScroll.checked = settings.invert_scroll;

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
        invert_scroll: elements.invertScroll.checked,
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
        showMessage(elements.settingsMessage, 'success', 'Settings saved successfully');

        // Auto-restart if needed
        if (result.data.restart_needed) {
            await handleAutoRestart();
        }
    } else {
        showMessage(elements.settingsMessage, 'error', `Failed to save settings: ${result.data.error || result.error}`);
    }
}

async function handleResetSettings() {
    // Confirm with user
    if (!confirm('Reset all settings to defaults? This will delete your custom configuration.')) {
        return;
    }

    // Call reset API
    const result = await resetToDefaults();
    if (result.success) {
        // Reload settings from server (now defaults)
        const settingsResult = await getSettings();
        if (settingsResult.success) {
            updateSettingsUI(settingsResult.data);

            let message = 'Settings reset to defaults';
            if (result.data.restart_needed) {
                message += ' - Restart detection to apply changes';
            }
            showMessage(elements.settingsMessage, 'success', message, 5000);
        }
    } else {
        showMessage(elements.settingsMessage, 'error', `Failed to reset: ${result.error || result.data?.error}`);
    }
}

// === Tab Switching ===

function switchTab(tabName) {
    // Hide all tabs
    elements.tabContents.forEach(tab => {
        tab.classList.remove('active');
    });

    // Remove active class from all buttons
    elements.tabButtons.forEach(btn => {
        btn.classList.remove('active');
    });

    // Show selected tab
    const selectedTab = document.getElementById(tabName);
    if (selectedTab) {
        selectedTab.classList.add('active');
    }

    // Add active class to clicked button
    const selectedBtn = document.querySelector(`[data-tab="${tabName}"]`);
    if (selectedBtn) {
        selectedBtn.classList.add('active');
    }

    // Load tab-specific data
    if (tabName === 'mappings') {
        loadMappings();
    } else if (tabName === 'info') {
        loadSystemInfo();
    }
}

function setupTabListeners() {
    elements.tabButtons.forEach(btn => {
        btn.addEventListener('click', (e) => {
            const tabName = e.target.getAttribute('data-tab');
            switchTab(tabName);
        });
    });
}

// === Collapsible Sections ===

function setupCollapsibleSections() {
    const collapsibleHeaders = document.querySelectorAll('.collapsible-header');
    collapsibleHeaders.forEach(header => {
        header.addEventListener('click', () => {
            const section = header.parentElement;
            const content = section.querySelector('.collapsible-content');
            const arrow = header.querySelector('.arrow');

            if (content.style.maxHeight) {
                // Collapse
                content.style.maxHeight = null;
                section.classList.remove('active');
                arrow.textContent = '▼';
            } else {
                // Expand
                content.style.maxHeight = content.scrollHeight + 'px';
                section.classList.add('active');
                arrow.textContent = '▲';
            }
        });
    });
}

// === Mappings Tab ===

async function loadMappings() {
    const result = await getMappings();

    if (!result.success) {
        elements.mappingsList.innerHTML = '<div class="error">Failed to load mappings</div>';
        return;
    }

    const mappings = result.data.mappings;

    if (mappings.length === 0) {
        elements.mappingsList.innerHTML = '<div class="no-data">No mappings configured</div>';
        return;
    }

    // Render mappings
    let html = '';
    mappings.forEach(mapping => {
        const gestureDisplay = mapping.gesture.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
        const actionDisplay = mapping.action.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());

        html += `
            <div class="mapping-item">
                <div class="mapping-info">
                    <span class="gesture-name">${gestureDisplay}</span>
                    <span class="mapping-arrow">→</span>
                    <span class="action-name">${actionDisplay}</span>
                </div>
                <label class="toggle-switch">
                    <input type="checkbox" data-gesture="${mapping.gesture}" data-action="${mapping.action}" ${mapping.enabled ? 'checked' : ''}>
                    <span class="toggle-slider"></span>
                </label>
            </div>
        `;
    });

    elements.mappingsList.innerHTML = html;

    // Add event listeners for toggles
    const toggles = elements.mappingsList.querySelectorAll('input[type="checkbox"]');
    toggles.forEach(toggle => {
        toggle.addEventListener('change', handleMappingToggle);
    });
}

async function handleMappingToggle(event) {
    const gesture = event.target.getAttribute('data-gesture');
    const action = event.target.getAttribute('data-action');
    const enabled = event.target.checked;

    // Collect all current mappings
    const toggles = elements.mappingsList.querySelectorAll('input[type="checkbox"]');
    const mappings = {};

    toggles.forEach(toggle => {
        const g = toggle.getAttribute('data-gesture');
        const a = toggle.getAttribute('data-action');
        if (toggle.checked) {
            mappings[g] = a;
        }
    });

    // Update mappings
    const result = await updateMappings(mappings);

    if (result.success) {
        const message = enabled ? `${gesture} enabled` : `${gesture} disabled`;
        showMessage(elements.mappingsMessage, 'success', message);

        // Auto-restart if needed
        if (result.data.restart_needed) {
            await handleAutoRestart();
        }
    } else {
        showMessage(elements.mappingsMessage, 'error', `Failed to update: ${result.error}`);
        // Revert toggle
        event.target.checked = !enabled;
    }
}

// === Info Tab ===

async function loadSystemInfo() {
    const result = await getSystemInfo();

    if (!result.success) {
        elements.infoSystemPlatform.textContent = 'Error loading info';
        return;
    }

    const info = result.data;

    // Camera info
    elements.infoCameraDevice.textContent = info.camera.device_id;
    elements.infoCameraResolution.textContent = `${info.camera.resolution[0]}x${info.camera.resolution[1]}`;
    elements.infoCameraFPS.textContent = `${info.camera.fps_idle}-${info.camera.fps_active} Hz`;

    // System info
    elements.infoSystemPlatform.textContent = info.system.platform;
    elements.infoSystemVersion.textContent = info.system.version;
    elements.infoSystemPython.textContent = info.system.python_version;

    // Permissions
    const permStatus = info.permissions_status;
    let permDisplay = permStatus.charAt(0).toUpperCase() + permStatus.slice(1);
    let permClass = permStatus === 'granted' ? 'status-value running' : 'status-value stopped';
    elements.infoPermissions.textContent = permDisplay;
    elements.infoPermissions.className = `info-value ${permClass}`;
}

// === First Run Modal ===

async function checkAndShowFirstRun() {
    const result = await checkFirstRun();

    if (result.success && result.data.is_first_run) {
        elements.firstRunModal.classList.remove('hidden');
    }
}

function setupFirstRunModal() {
    elements.closeFirstRunModal.addEventListener('click', () => {
        elements.firstRunModal.classList.add('hidden');
    });
}

// === Auto-Restart ===

async function handleAutoRestart() {
    if (confirm('Settings changed. Restart Handsi to apply changes?')) {
        const result = await restart();
        if (result.success) {
            showMessage(elements.controlMessage, 'success', 'Handsi restarted successfully');
            startStatusPolling();
        } else {
            showMessage(elements.controlMessage, 'error', `Failed to restart: ${result.error}`);
        }
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

    // Setup UI event listeners
    setupTabListeners();
    setupCollapsibleSections();
    setupFirstRunModal();

    // Setup control event listeners
    elements.startBtn.addEventListener('click', handleStart);
    elements.stopBtn.addEventListener('click', handleStop);
    elements.saveSettingsBtn.addEventListener('click', handleSaveSettings);
    elements.resetSettingsBtn.addEventListener('click', handleResetSettings);

    setupSliderListeners();

    // Check for first run
    await checkAndShowFirstRun();

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
