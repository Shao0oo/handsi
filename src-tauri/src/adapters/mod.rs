// ============================================================================
// Action Adapter Trait - Platform-agnostic interface for system control
// ============================================================================

/// Trait for platform-specific action adapters
///
/// Implementations provide OS-specific input control (mouse, keyboard, etc.)
pub trait ActionAdapter: Send {
    /// Initialize adapter (setup resources, verify permissions)
    fn initialize(&mut self) -> Result<(), String>;

    /// Move mouse cursor to absolute pixel position
    fn mouse_move(&self, x: f64, y: f64) -> Result<(), String>;

    /// Move mouse cursor using normalized coordinates [0, 1]
    /// Adapter converts to pixels based on screen dimensions
    fn mouse_move_normalized(&self, x_norm: f64, y_norm: f64) -> Result<(), String>;

    /// Press mouse button (0=left, 1=right, 2=middle)
    fn mouse_down(&self, x: f64, y: f64, button: u8) -> Result<(), String>;

    /// Release mouse button (0=left, 1=right, 2=middle)
    fn mouse_up(&self, x: f64, y: f64, button: u8) -> Result<(), String>;

    /// Click mouse button (press and release)
    fn mouse_click(&self, x: f64, y: f64, button: u8) -> Result<(), String>;

    /// Double-click mouse button with proper click count
    fn mouse_double_click(&self, x: f64, y: f64, button: u8) -> Result<(), String>;

    /// Press mouse button using normalized coordinates [0, 1]
    fn mouse_down_normalized(&self, x_norm: f64, y_norm: f64, button: u8) -> Result<(), String>;

    /// Release mouse button using normalized coordinates [0, 1]
    fn mouse_up_normalized(&self, x_norm: f64, y_norm: f64, button: u8) -> Result<(), String>;

    /// Click mouse button using normalized coordinates [0, 1]
    fn mouse_click_normalized(&self, x_norm: f64, y_norm: f64, button: u8) -> Result<(), String>;

    /// Double-click mouse button using normalized coordinates [0, 1]
    fn mouse_double_click_normalized(&self, x_norm: f64, y_norm: f64, button: u8) -> Result<(), String>;

    /// Get current mouse cursor position in normalized coordinates [0, 1]
    /// Queries the actual OS cursor position (not cached)
    fn get_mouse_position_normalized(&self) -> Result<(f64, f64), String>;

    /// Move mouse cursor by delta using normalized coordinates
    /// Uses internally tracked position (call reset_cursor_tracking at gesture start)
    fn mouse_move_relative_normalized(&self, dx: f64, dy: f64) -> Result<(), String>;

    /// Reset cursor tracking to actual OS position
    /// Call at gesture start to sync with actual cursor location
    fn reset_cursor_tracking(&self) -> Result<(), String>;

    /// Scroll wheel (dx=horizontal, dy=vertical)
    fn scroll(&self, dx: i32, dy: i32) -> Result<(), String>;

    /// Press key with modifiers (uses platform-specific key codes and modifier flags)
    fn key_press(&self, key_code: u16, modifiers: u64) -> Result<(), String>;

    /// Switch virtual desktop/workspace
    /// Direction: "left"/"prev", "right"/"next"
    fn switch_desktop(&self, direction: &str) -> Result<(), String>;

    /// Adjust system volume by delta (-100 to +100)
    fn set_volume(&self, delta: i32) -> Result<(), String>;

    /// Execute keyboard shortcut (e.g., "cmd+c", "cmd+v", "ctrl+z")
    fn keyboard_shortcut(&self, shortcut: &str) -> Result<(), String>;

    /// Zoom in or out (system-wide or browser)
    fn zoom(&self, direction: &str, step: f64) -> Result<(), String>;

    /// Execute semantic action (platform translates to specific shortcuts)
    /// Supported: "copy", "paste", "undo", "redo", "cut", "select_all"
    fn semantic_action(&self, name: &str) -> Result<(), String>;

    /// Cleanup resources (called on adapter drop)
    fn cleanup(&mut self);
}

// Platform-specific modules
#[cfg(target_os = "macos")]
mod macos;

#[cfg(target_os = "linux")]
mod linux;

#[cfg(target_os = "windows")]
mod windows;

// Re-export platform-specific adapter
#[cfg(target_os = "macos")]
pub use macos::MacOSAdapter;

/// Factory function to create platform-specific adapter
///
/// Returns initialized adapter for the current platform, or error if unsupported.
pub fn create_adapter() -> Result<Box<dyn ActionAdapter>, String> {
    #[cfg(target_os = "macos")]
    {
        let mut adapter = Box::new(MacOSAdapter::new());
        adapter.initialize()?;
        eprintln!("[Rust] MacOSAdapter created and initialized");
        Ok(adapter)
    }

    #[cfg(target_os = "linux")]
    {
        let mut adapter = Box::new(linux::LinuxAdapter::new());
        adapter.initialize()?;
        eprintln!("[Rust] LinuxAdapter created and initialized");
        Ok(adapter)
    }

    #[cfg(target_os = "windows")]
    {
        let mut adapter = Box::new(windows::WindowsAdapter::new());
        adapter.initialize()?;
        eprintln!("[Rust] WindowsAdapter created and initialized");
        Ok(adapter)
    }

    #[cfg(not(any(target_os = "macos", target_os = "linux", target_os = "windows")))]
    {
        Err("Unsupported platform - no adapter available".to_string())
    }
}
