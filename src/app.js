/**
 * Handsi Control Panel - Frontend Logic
 *
 * Handles UI interactions and API communication via Tauri IPC.
 */

console.log('📱 app.js loading...');

// Tauri invoke function - will be set once API loads
let invoke = null;

// Wait for Tauri API to load
function waitForTauriAPI() {
    return new Promise((resolve, reject) => {
        let attempts = 0;
        const maxAttempts = 100; // 5 seconds max

        const checkAPI = () => {
            attempts++;

            if (window.__TAURI_INVOKE__) {
                invoke = window.__TAURI_INVOKE__;
                console.log('✓ Tauri invoke function ready');
                resolve();
            } else if (attempts >= maxAttempts) {
                console.error('✗ Tauri API failed to load after 5 seconds');
                reject(new Error('Tauri API timeout'));
            } else {
                if (attempts % 10 === 0) {
                    console.log(`⏳ Waiting for Tauri API... (attempt ${attempts}/${maxAttempts})`);
                }
                setTimeout(checkAPI, 50);
            }
        };

        checkAPI();
    });
}

// === Configuration ===
const STATUS_POLL_INTERVAL = 1000;  // ms (reduced from 500ms to minimize IPC load)

// === State ===
let statusPollTimer = null;
let currentSettings = {};
let bridgeReady = true;  // Tauri is always ready

// === DOM Elements ===
// Will be populated when DOM is ready
let elements = null;

function getElements() {
    return {
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

        // Settings - General
        cameraDevice: document.getElementById('cameraDevice'),

        // Settings - Mouse
        sensitivity: document.getElementById('sensitivity'),
        sensitivityValue: document.getElementById('sensitivityValue'),
        smoothing: document.getElementById('smoothing'),
        smoothingValue: document.getElementById('smoothingValue'),
        deadZone: document.getElementById('deadZone'),
        deadZoneValue: document.getElementById('deadZoneValue'),
        mirrorX: document.getElementById('mirrorX'),

        // Settings - Scroll
        scrollSensitivity: document.getElementById('scrollSensitivity'),
        scrollSensitivityValue: document.getElementById('scrollSensitivityValue'),
        scrollDeadZone: document.getElementById('scrollDeadZone'),
        scrollDeadZoneValue: document.getElementById('scrollDeadZoneValue'),
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
}

// === Tauri Initialization ===

function initTauri() {
    return new Promise((resolve) => {
        console.log('Tauri initialized');
        resolve();
    });
}

// === API Functions (Tauri IPC) ===

async function startHandsi() {
    try {
        console.log('[JS] Calling invoke("start")...');
        const result = await invoke('start');
        console.log('[JS] start() response:', result);
        return result;
    } catch (error) {
        console.error('[JS] start() failed:', error);
        return { success: false, error: String(error) };
    }
}

async function stopHandsi() {
    try {
        console.log('[JS] Calling invoke("stop")...');
        const result = await invoke('stop');
        console.log('[JS] stop() response:', result);
        return result;
    } catch (error) {
        console.error('[JS] stop() failed:', error);
        return { success: false, error: String(error) };
    }
}

async function getStatus() {
    try {
        console.log('[JS] Calling invoke("get_status")...');
        const result = await invoke('get_status');
        console.log('[JS] get_status() response:', result);
        return result;
    } catch (error) {
        console.error('[JS] getStatus() failed:', error);
        return { success: false, error: String(error) };
    }
}

async function getSettings() {
    try {
        const result = await invoke('get_settings');
        return result;
    } catch (error) {
        console.error('getSettings() failed:', error);
        return { success: false, error: error };
    }
}

async function updateSettings(settings) {
    try {
        const result = await invoke('update_settings', { settings });
        console.log('updateSettings() response:', result);
        return result;
    } catch (error) {
        console.error('updateSettings() failed:', error);
        return { success: false, error: error };
    }
}

async function getMappings() {
    try {
        const result = await invoke('get_mappings');
        return result;
    } catch (error) {
        console.error('getMappings() failed:', error);
        return { success: false, error: error };
    }
}

async function updateMapping(gesture, enabled) {
    try {
        const result = await invoke('update_mapping', { gesture, enabled });
        console.log('updateMapping() response:', result);
        return result;
    } catch (error) {
        console.error('updateMapping() failed:', error);
        return { success: false, error: error };
    }
}

async function updateMappings(mappings) {
    try {
        const result = await invoke('update_mappings', { mappings });
        console.log('updateMappings() response:', result);
        return result;
    } catch (error) {
        console.error('updateMappings() failed:', error);
        return { success: false, error: error };
    }
}

async function getAvailableGesturesAndActions() {
    try {
        const result = await invoke('get_available_gestures_and_actions');
        return result;
    } catch (error) {
        console.error('getAvailableGesturesAndActions() failed:', error);
        return { success: false, error: error };
    }
}

async function getSystemInfo() {
    try {
        const result = await invoke('get_info');
        return result;
    } catch (error) {
        console.error('getSystemInfo() failed:', error);
        return { success: false, error: error };
    }
}

// Removed: getAvailableGesturesAndActions, resetToDefaults, restart, checkFirstRun
// These functions were Qt-specific and may need to be re-implemented if needed

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

function updateSettingsUI(result) {
    // Extract settings from nested response
    const settings = result.data || result;
    currentSettings = settings;

    // General settings
    elements.cameraDevice.value = settings.device_id;

    // Mouse settings
    elements.sensitivity.value = settings.sensitivity;
    elements.sensitivityValue.textContent = settings.sensitivity;

    elements.smoothing.value = settings.smoothing;
    elements.smoothingValue.textContent = settings.smoothing;

    elements.deadZone.value = settings.dead_zone;
    elements.deadZoneValue.textContent = settings.dead_zone;

    elements.mirrorX.checked = settings.mirror_x;

    // Scroll settings
    elements.scrollSensitivity.value = settings.scroll_sensitivity;
    elements.scrollSensitivityValue.textContent = settings.scroll_sensitivity;

    elements.scrollDeadZone.value = settings.scroll_dead_zone;
    elements.scrollDeadZoneValue.textContent = settings.scroll_dead_zone;

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
    console.log('[JS] handleStart() called - Start button clicked!');
    elements.startBtn.disabled = true;
    const result = await startHandsi();
    console.log('[JS] handleStart() - result:', result);

    if (result.success) {
        showMessage(elements.controlMessage, 'success', 'Handsi started successfully');
        startStatusPolling();
    } else {
        showMessage(elements.controlMessage, 'error', `Failed to start: ${result.data?.error || result.error}`);
        elements.startBtn.disabled = false;
    }
}

async function handleStop() {
    console.log('[JS] handleStop() called - Stop button clicked!');
    elements.stopBtn.disabled = true;
    const result = await stopHandsi();
    console.log('[JS] handleStop() - result:', result);

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
        device_id: parseInt(elements.cameraDevice.value),
        sensitivity: parseFloat(elements.sensitivity.value),
        smoothing: parseFloat(elements.smoothing.value),
        dead_zone: parseFloat(elements.deadZone.value),
        mirror_x: elements.mirrorX.checked,
        scroll_sensitivity: parseFloat(elements.scrollSensitivity.value),
        scroll_dead_zone: parseFloat(elements.scrollDeadZone.value),
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
    // TODO: Implement reset to defaults via Python IPC
    // For now, just show a message
    showMessage(elements.settingsMessage, 'info', 'Reset to defaults not yet implemented in Tauri version');
}

// === Tab Switching ===

async function switchTab(tabName) {
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

    // Load tab-specific data (await to prevent race conditions)
    if (tabName === 'mappings') {
        await loadMappings();
    } else if (tabName === 'info') {
        await loadSystemInfo();
    }
}

function setupTabListeners() {
    elements.tabButtons.forEach(btn => {
        btn.addEventListener('click', async (e) => {
            const tabName = e.target.getAttribute('data-tab');
            await switchTab(tabName);
        });
    });
}

// === Collapsible Sections ===

function setupCollapsibleSections() {
    const collapsibleHeaders = document.querySelectorAll('.collapsible-header');

    // Helper function to update all parent collapsible heights
    function updateParentHeights(element, immediate = false) {
        let parent = element.parentElement;
        const parentsToUpdate = [];

        // First, collect all parent collapsibles
        while (parent) {
            if (parent.classList.contains('collapsible-content') && parent.style.maxHeight) {
                parentsToUpdate.push(parent);
            }
            parent = parent.parentElement;
        }

        // Update in reverse order (outermost to innermost) to prevent jitter
        parentsToUpdate.reverse().forEach(parentContent => {
            if (immediate) {
                // For expand: set to scrollHeight immediately so it animates
                parentContent.style.maxHeight = parentContent.scrollHeight + 'px';
            } else {
                // For collapse: use the two-phase approach
                parentContent.style.maxHeight = '9999px';

                requestAnimationFrame(() => {
                    requestAnimationFrame(() => {
                        parentContent.style.maxHeight = parentContent.scrollHeight + 'px';
                    });
                });
            }
        });
    }

    // Helper function to continuously update parent heights during animation
    function animateParentHeights(element, duration = 300) {
        const startTime = performance.now();

        function update() {
            const elapsed = performance.now() - startTime;

            if (elapsed < duration) {
                updateParentHeights(element, true);
                requestAnimationFrame(update);
            } else {
                // Final update after animation completes
                updateParentHeights(element, true);
            }
        }

        requestAnimationFrame(update);
    }

    collapsibleHeaders.forEach(header => {
        header.addEventListener('click', (e) => {
            e.stopPropagation();  // Prevent bubbling to parent collapsibles

            const section = header.parentElement;
            const content = section.querySelector('.collapsible-content');
            const arrow = header.querySelector('.arrow');
            const container = document.querySelector('.container');  // Get container reference

            if (content.style.maxHeight) {
                // Collapse
                content.style.maxHeight = null;
                section.classList.remove('active');
                arrow.textContent = '▼';

                // Update parent heights after collapse animation completes
                setTimeout(() => {
                    updateParentHeights(section);
                }, 350);  // Wait for transition to complete
            } else {
                // Expand
                section.classList.add('active');
                arrow.textContent = '▲';

                // Step 1: Set to 0 to establish starting point
                content.style.maxHeight = '0px';

                // Step 2: In next frame, measure the actual height needed
                requestAnimationFrame(() => {
                    const fullHeight = content.scrollHeight;

                    // Step 3: Trigger the transition by setting to actual height
                    content.style.maxHeight = fullHeight + 'px';

                    // Step 4: Continuously update parent heights DURING the animation
                    // This makes them expand smoothly along with the content
                    animateParentHeights(section, 300);

                    // After expansion completes, ensure the expanded section is visible
                    setTimeout(() => {
                        const sectionRect = section.getBoundingClientRect();
                        const containerRect = container.getBoundingClientRect();

                        // // If section bottom is below container bottom, scroll to make it visible
                        // if (sectionRect.bottom > containerRect.bottom) {
                        //     section.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                        // }
                    }, 350);  // Wait for transition to complete
                });
            }
        });
    });
}

// === Mappings Tab ===

async function loadMappings() {
    // Load available gestures and actions
    const availableResult = await getAvailableGesturesAndActions();
    console.log('[Mappings] availableResult:', availableResult);
    if (!availableResult.success) {
        elements.mappingsList.innerHTML = '<div class="error">Failed to load available gestures and actions</div>';
        return;
    }

    const availableGestures = availableResult.data?.gestures || availableResult.gestures || [];
    const availableActions = availableResult.data?.actions || availableResult.actions || [];
    console.log('[Mappings] availableGestures:', availableGestures);
    console.log('[Mappings] availableActions:', availableActions);

    // Load current mappings
    const mappingsResult = await getMappings();
    console.log('[Mappings] mappingsResult:', mappingsResult);
    if (!mappingsResult.success) {
        elements.mappingsList.innerHTML = '<div class="error">Failed to load mappings</div>';
        return;
    }

    const mappings = mappingsResult.mappings || mappingsResult.data?.mappings || [];
    console.log('[Mappings] mappings:', mappings);

    if (mappings.length === 0) {
        elements.mappingsList.innerHTML = '<div class="no-data">No gestures available</div>';
        return;
    }

    // Sort: mapped first, then unmapped
    mappings.sort((a, b) => {
        if (a.enabled && !b.enabled) return -1;
        if (!a.enabled && b.enabled) return 1;
        return 0;
    });

    // Render each gesture with a dropdown to select action
    let html = '';
    mappings.forEach(mapping => {
        const gestureDisplay = mapping.gesture.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());

        // Build action dropdown
        let actionOptions = '<option value="">-- None --</option>';
        availableActions.forEach(action => {
            const selected = mapping.action === action ? 'selected' : '';
            const actionDisplay = action.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
            actionOptions += `<option value="${action}" ${selected}>${actionDisplay}</option>`;
        });

        html += `
            <div class="mapping-item ${!mapping.enabled ? 'unmapped' : ''}">
                <div class="gesture-label">${gestureDisplay}</div>
                <div class="mapping-arrow">→</div>
                <select class="action-dropdown" data-gesture="${mapping.gesture}">
                    ${actionOptions}
                </select>
            </div>
        `;
    });

    elements.mappingsList.innerHTML = html;

    // Attach event listeners to all dropdowns
    document.querySelectorAll('.action-dropdown').forEach(dropdown => {
        dropdown.addEventListener('change', handleMappingChange);
    });
}

async function handleMappingChange(event) {
    const gesture = event.target.getAttribute('data-gesture');
    const newAction = event.target.value;  // Empty string if "-- None --"

    // Collect all current mappings from dropdowns
    const mappings = {};
    document.querySelectorAll('.action-dropdown').forEach(dropdown => {
        const g = dropdown.getAttribute('data-gesture');
        const a = dropdown.value;
        if (a) {  // Only include non-empty selections
            mappings[g] = a;
        }
    });

    // Update mappings
    const result = await updateMappings(mappings);
    console.log('[Mappings] updateMappings result:', result);

    if (result.success) {
        const gestureDisplay = gesture.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
        const message = newAction
            ? `${gestureDisplay} → ${newAction.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}`
            : `${gestureDisplay} unmapped`;
        showMessage(elements.mappingsMessage, 'success', message);

        // Reload to update styling (mapped vs unmapped)
        await loadMappings();

        // Auto-restart if needed
        const data = result.data || result;
        console.log('[Mappings] Checking restart_needed:', data.restart_needed);
        if (data.restart_needed) {
            await handleAutoRestart();
        }
    } else {
        const errorMsg = result.data?.error || result.error || 'Unknown error';
        console.error('[Mappings] Update failed:', errorMsg);
        showMessage(elements.mappingsMessage, 'error', `Failed: ${errorMsg}`);
        // Revert dropdown
        await loadMappings();
    }
}

// === Info Tab ===

async function loadSystemInfo() {
    const result = await getSystemInfo();

    if (!result.success) {
        elements.infoSystemPlatform.textContent = 'Error loading info';
        return;
    }

    // Handle both wrapped and unwrapped responses
    const info = result.data || result;

    // Camera info
    elements.infoCameraDevice.textContent = info.camera.device_id;
    elements.infoCameraResolution.textContent = `${info.camera.resolution[0]}x${info.camera.resolution[1]}`;
    elements.infoCameraFPS.textContent = `${info.camera.fps_idle}-${info.camera.fps_active} Hz`;

    // System info
    elements.infoSystemPlatform.textContent = info.system.platform;
    elements.infoSystemVersion.textContent = info.system.version;
    elements.infoSystemVersion.title = info.system.version; // Show full version on hover
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
    // TODO: Implement first-run check via Tauri if needed
    // For now, just hide the modal
    elements.firstRunModal.classList.add('hidden');
}

function setupFirstRunModal() {
    elements.closeFirstRunModal.addEventListener('click', () => {
        elements.firstRunModal.classList.add('hidden');
    });
}

// === Auto-Restart ===

async function handleAutoRestart() {
    // Auto-restart for camera device change
    // Most settings apply immediately via shared config references, but camera requires restart
    showMessage(elements.settingsMessage, 'info', 'Restarting to apply camera change...');

    // Stop current detection
    const stopResult = await stopHandsi();
    if (!stopResult.success) {
        showMessage(elements.settingsMessage, 'error', 'Failed to stop: ' + (stopResult.error || 'Unknown error'));
        return;
    }

    // Wait a moment for cleanup
    await new Promise(resolve => setTimeout(resolve, 500));

    // Start with new camera
    const startResult = await startHandsi();
    if (startResult.success) {
        showMessage(elements.settingsMessage, 'success', 'Restarted with new camera');
        startStatusPolling();
    } else {
        showMessage(elements.settingsMessage, 'error', 'Failed to restart: ' + (startResult.error || 'Unknown error'));
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

    // Scroll settings
    elements.scrollSensitivity.addEventListener('input', (e) => {
        elements.scrollSensitivityValue.textContent = e.target.value;
    });

    elements.scrollDeadZone.addEventListener('input', (e) => {
        elements.scrollDeadZoneValue.textContent = e.target.value;
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
    console.log('🚀 [JS] Initializing Handsi Control Panel...');
    console.log('🔍 [JS] invoke function type:', typeof invoke);
    console.log('🔍 [JS] window.__TAURI_INVOKE__ type:', typeof window.__TAURI_INVOKE__);

    // Get DOM elements now that DOM is ready
    elements = getElements();
    console.log('✓ [JS] DOM elements loaded');

    // Wait for Tauri API to load
    try {
        await waitForTauriAPI();
        console.log('✓ [JS] Tauri API ready, invoke type:', typeof invoke);
    } catch (error) {
        console.error('❌ [JS] Failed to load Tauri API:', error);
        setConnectionStatus(false);
        showMessage(elements.controlMessage, 'error', 'Failed to initialize: ' + error.message);
        // Add visible error on page
        alert('CRITICAL ERROR: Tauri API failed to load!\n\n' + error.message + '\n\nCheck browser console (Cmd+Option+I) for details.');
        return;
    }

    // Setup UI event listeners
    console.log('[JS] Setting up UI event listeners...');
    setupTabListeners();
    setupCollapsibleSections();
    setupFirstRunModal();

    // Setup control event listeners
    console.log('[JS] Attaching button event listeners...');
    console.log('[JS] Start button:', elements.startBtn);
    console.log('[JS] Stop button:', elements.stopBtn);
    elements.startBtn.addEventListener('click', handleStart);
    elements.stopBtn.addEventListener('click', handleStop);
    elements.saveSettingsBtn.addEventListener('click', handleSaveSettings);
    elements.resetSettingsBtn.addEventListener('click', handleResetSettings);
    console.log('[JS] Button event listeners attached successfully');

    setupSliderListeners();

    // Check for first run
    await checkAndShowFirstRun();

    // Load initial data
    console.log('[JS] Loading initial status...');
    const statusResult = await getStatus();
    console.log('[JS] Initial status result:', statusResult);
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

    console.log('[JS] Loading initial settings...');
    const settingsResult = await getSettings();
    console.log('[JS] Initial settings result:', settingsResult);
    if (settingsResult.success) {
        updateSettingsUI(settingsResult.data);
    }

    console.log('[JS] ✅ Initialization complete');
}

// === Start Application ===

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}
