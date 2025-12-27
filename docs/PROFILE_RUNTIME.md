# Safe profiling workflow (no orphaned processes)

This is the clean way to profile `src/handsi/main.py --preview` so:
- `profile.stats` is written reliably
- you don’t end up with a background process you have to hunt/kill

---

## 1) Run in the foreground (recommended)

**Do NOT use `&`.** Let the program run for a fixed amount of time, then stop it with Ctrl+C.

```bash
cd ~/Desktop/Contactless_Workspace
python -m cProfile -o profile.stats src/handsi/main.py
```

Let it run for ~10–30 seconds, then press:

Ctrl+C (once)

This should stop cleanly and write profile.stats.

View results:

```bash
python -m pstats profile.stats

# Inside pstats:
sort cumtime
stats 50
stats handsi
```