// ============================================================================
// Linux Action Adapter - Stub implementation (future work)
// ============================================================================

use super::ActionAdapter;

/// Linux adapter stub (not yet implemented)
pub struct LinuxAdapter {
    initialized: bool,
}

impl LinuxAdapter {
    pub fn new() -> Self {
        LinuxAdapter {
            initialized: false,
        }
    }
}

impl ActionAdapter for LinuxAdapter {
    fn initialize(&mut self) -> Result<(), String> {
        self.initialized = true;
        eprintln!("[Rust] LinuxAdapter initialized (stub - no actions implemented)");
        Ok(())
    }

    fn mouse_move(&self, _x: f64, _y: f64) -> Result<(), String> {
        Err("Linux adapter not yet implemented".to_string())
    }

    fn mouse_move_normalized(&self, _x_norm: f64, _y_norm: f64) -> Result<(), String> {
        Err("Linux adapter not yet implemented".to_string())
    }

    fn mouse_down(&self, _x: f64, _y: f64, _button: u8) -> Result<(), String> {
        Err("Linux adapter not yet implemented".to_string())
    }

    fn mouse_up(&self, _x: f64, _y: f64, _button: u8) -> Result<(), String> {
        Err("Linux adapter not yet implemented".to_string())
    }

    fn mouse_click(&self, _x: f64, _y: f64, _button: u8) -> Result<(), String> {
        Err("Linux adapter not yet implemented".to_string())
    }

    fn mouse_double_click(&self, _x: f64, _y: f64, _button: u8) -> Result<(), String> {
        Err("Linux adapter not yet implemented".to_string())
    }

    fn scroll(&self, _dx: i32, _dy: i32) -> Result<(), String> {
        Err("Linux adapter not yet implemented".to_string())
    }

    fn key_press(&self, _key_code: u16, _modifiers: u64) -> Result<(), String> {
        Err("Linux adapter not yet implemented".to_string())
    }

    fn switch_desktop(&self, _direction: &str) -> Result<(), String> {
        Err("Linux adapter not yet implemented".to_string())
    }

    fn set_volume(&self, _delta: i32) -> Result<(), String> {
        Err("Linux adapter not yet implemented".to_string())
    }

    fn keyboard_shortcut(&self, _shortcut: &str) -> Result<(), String> {
        Err("Linux adapter not yet implemented".to_string())
    }

    fn zoom(&self, _direction: &str, _step: f64) -> Result<(), String> {
        Err("Linux adapter not yet implemented".to_string())
    }

    fn mouse_down_normalized(&self, _x_norm: f64, _y_norm: f64, _button: u8) -> Result<(), String> {
        Err("Linux adapter not yet implemented".to_string())
    }

    fn mouse_up_normalized(&self, _x_norm: f64, _y_norm: f64, _button: u8) -> Result<(), String> {
        Err("Linux adapter not yet implemented".to_string())
    }

    fn mouse_click_normalized(&self, _x_norm: f64, _y_norm: f64, _button: u8) -> Result<(), String> {
        Err("Linux adapter not yet implemented".to_string())
    }

    fn mouse_double_click_normalized(&self, _x_norm: f64, _y_norm: f64, _button: u8) -> Result<(), String> {
        Err("Linux adapter not yet implemented".to_string())
    }

    fn cleanup(&mut self) {
        self.initialized = false;
        eprintln!("[Rust] LinuxAdapter cleaned up");
    }
}
