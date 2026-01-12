# Guidelines for Claude

This document outlines coding standards and general practices for the Handsi project to maintain code quality and modularity.

## **IMPORTANT**

- Use the existing conda environment: ```conda activate handsi```
- Do not run pip install into base python, always use: ```conda activate handsi```
- Installation should be placed inside of pyproject.toml with specific version
- For motion, always normalize relative to hand scale
- default.yaml should NEVER be changed. I hand tuned many parts of it
- When adding new gestures and actions, make sure to update the registry file inside of src/handsi/core/registry.py

## Core Principles

### 1. Separation of Concerns
- **Never** put utility functions directly in entrypoint files (`main.py`, `__main__.py`)
- Business logic belongs in dedicated modules, not in CLI/UI code
- Keep entrypoints thin - they should orchestrate, not implement

**Bad Example:**
```python
# main.py
def find_config_path(config_arg):  # ❌ Utility in entrypoint
    # ...implementation...

def main():
    config_path = find_config_path(args.config)
```

**Good Example:**
```python
# core/utils.py
def find_config_path(config_arg):  # ✅ Utility in dedicated module
    # ...implementation...

# main.py
from handsi.core.utils import find_config_path

def main():
    config_path = find_config_path(args.config)
```

### 2. Modularity
- Each module should have a single, well-defined responsibility
- Use the following structure:
  - `core/` - Core abstractions (state, queues, config, logging, utils)
  - `vision/` - Computer vision components
  - `gestures/` - Gesture recognition
  - `actions/` - Action execution
  - `ui/` - User interface components
  - `teach/` - Teaching mode (Phase 3)

### 3. Error Handling
- Use structured error codes (e.g., `CAP-001`, `TRK-002`)
- Each layer has its own error prefix:
  - `CAP-xxx`: Capture
  - `TRK-xxx`: Tracking
  - `FEA-xxx`: Features
  - `GES-xxx`: Gestures
  - `ACT-xxx`: Actions
  - `GUI-xxx`: Preview
  - `CFG-xxx`: Configuration
- Always provide actionable error messages

### 4. Configuration
- All configurable values go in YAML config
- Use Pydantic for validation
- Provide sensible defaults
- Never hardcode paths or magic numbers in business logic

### 5. Threading
- Each thread has a single responsibility
- Use thread-safe queues for communication
- Always implement graceful shutdown
- Use bounded queues with frame-skipping for backpressure

## File Organization

### When to Create a New File

**Create a new module when:**
- Functionality is >200 lines
- Code serves a distinct purpose
- Multiple files need the functionality
- It's a utility/helper function

**Keep in existing file when:**
- Tightly coupled to single feature
- <50 lines of simple logic
- Only used once in that file

### Helper Functions

All helper/utility functions belong in:
- `core/utils.py` - General utilities (path resolution, etc.)
- `<module>/helpers.py` - Module-specific helpers (if needed)

Never in:
- `main.py`
- `__init__.py` (unless for package-level imports)
- Thread classes (unless tightly coupled to thread logic)

## Code Style

### Imports
- Group imports: stdlib → third-party → local
- Use absolute imports: `from handsi.core.utils import ...`
- Never use relative imports across packages

### Docstrings
- Use Google-style docstrings
- Always document:
  - Module purpose (at top)
  - Function/class purpose
  - Args and return types
  - Exceptions raised

### Type Hints
- Always use type hints for function signatures
- Use `typing` module types where appropriate
- Prefer `Path` over `str` for file paths

## Testing Strategy (Future)

- Unit tests: `tests/unit/`
- Integration tests: `tests/integration/`
- Test naming: `test_<module>_<function>.py`
- Use pytest fixtures for setup/teardown

## Phase-Specific Guidelines

### Phase 1 (Current)
- Focus: Capture + Tracking + Preview
- No action execution yet
- Keep gesture inference simple (rules-based)

### Phase 2 (Future)
- Add action execution (macOS/Linux adapters)
- System tray UI
- State machine for gesture → action mapping

### Phase 3 (Future)
- Teaching mode
- Voice labeling
- Model training

## Common Pitfalls to Avoid

1. **Don't** put business logic in `main.py`
2. **Don't** use relative paths without resolution
3. **Don't** forget to update error codes when adding new modules
4. **Don't** skip type hints
5. **Don't** create God classes (single responsibility principle)
6. **Don't** block threads unnecessarily (use queues, timeouts)
7. **Don't** forget graceful shutdown logic

## Code Review Checklist

Before submitting code, verify:
- [ ] No utility functions in `main.py`
- [ ] All paths resolved via `core/utils.py`
- [ ] Type hints on all functions
- [ ] Docstrings on all public functions/classes
- [ ] Error codes follow taxonomy
- [ ] No hardcoded values (use config)
- [ ] Thread-safe queue access
- [ ] Graceful shutdown implemented
- [ ] Imports properly organized
- [ ] No circular dependencies

## Questions?

If uncertain about where code belongs:
1. Check this document
2. Look at existing similar functionality
3. Ask: "Is this a utility, core abstraction, or feature?"
4. When in doubt, create a helper module

---

**Remember:** Clean, modular code is easier to maintain, test, and extend. Take the time to do it right.
