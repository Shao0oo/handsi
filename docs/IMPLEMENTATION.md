# implementation.md — Phase 1 (CLI MVP)

## Purpose
Phase 1 delivers a **command-line** AirDesk that:
- Captures webcam frames
- Tracks hands (optionally head/pose later)
- Decodes a small, reliable gesture set
- Applies **safety latch + debouncing**
- Executes a minimal set of desktop actions
- Runs locally with a debug preview window and logs

**No tray app. No autostart. No teaching mode.** Just a solid engine.

---

## Phase 1 Scope

### Must-have
- Real-time webcam capture (OpenCV)
- Hand landmark tracking (MediaPipe Hands)
- Gesture decoding (rule-based)
- Temporal smoothing + state machine (latch, cooldown)
- Action execution (macOS first; leave adapter interface for Linux)
- CLI entrypoint with:
  - `--preview` (overlay window)
  - `--debug` (prints gesture states / confidence)
  - `--config path`

### Nice-to-have (still Phase 1 if easy)
- Basic head pose/face detection overlay (no actions yet)
- JSON/TOML config instead of YAML (if you want better validation)

### Non-goals
- System tray UI
- Run-on-startup
- Gesture teaching / personalization
- Complex window management beyond a couple OS actions

---

## Deliverables (Acceptance Criteria)
You can run:

```bash
python -m airdesk.main --preview --debug --config config/default.yaml
```
