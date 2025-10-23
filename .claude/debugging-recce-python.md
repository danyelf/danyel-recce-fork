# Debugging Recce Python Backend

This guide documents the workflow for debugging the Recce Python backend during development.

## Setup

### Install Recce in Editable Mode

From the recce repository root:

```bash
pip install -e .
```

This allows you to edit Python files and have changes take effect immediately without reinstalling.

### Starting the Server

**For interactive debugging** (see output in terminal):
```bash
cd /path/to/test/project
recce server
```

**For automated testing** (use the helper script):
```bash
# From anywhere in the repository
bash bin/restart-server.sh

# With debug event logging
bash bin/restart-server.sh true /tmp/server.log
```

The helper script (`bin/restart-server.sh`):
- Kills any existing recce processes
- Activates the venv automatically
- Supports optional debug logging
- Works from any directory

**For manual file capture**:
```bash
pkill -9 -f "recce server" || true
cd /path/to/test/project && source /path/to/venv/bin/activate
recce server > /tmp/server_output.log 2>&1 &
```

## Testing Workflow

### Option 1: API Calls (Fastest for Backend Testing)

Instead of opening a browser, make direct API calls to trigger code paths:

```bash
# Get environment info
curl -s http://localhost:8000/api/info | python3 -m json.tool | head -30

# Extract specific data from responses
curl -s http://localhost:8000/api/info | python3 -c "import sys, json; data=json.load(sys.stdin); print('Base manifest_metadata:', data['lineage']['base'].get('manifest_metadata'))"

# Create a check
curl -X POST http://localhost:8000/api/checks \
  -H "Content-Type: application/json" \
  -d '{"name":"test check","type":"row_count_diff"}'

# List checks
curl -s http://localhost:8000/api/checks | python3 -m json.tool
```

**Key API Endpoints**:
- `/api/info` - Returns environment info
- `/api/checks` - GET lists checks, POST creates check
- `/api/runs/submit` - Submit a run
- `/api/runs` - List runs

### Option 2: Browser (For UI Testing)

Open http://localhost:8000 in browser when you need to test frontend interactions.

## Debugging Techniques

### Add Print Statements

The simplest approach for quick debugging:

```python
# In recce/event/__init__.py or any Python file
print(f"DEBUG: variable_name = {variable_name}")
print(f"DEBUG: type = {type(obj)}, value = {obj}")
```

**Important**: Server output goes to stdout/stderr, visible in the terminal where you ran `recce server`.

### Common Gotchas

#### 1. Type Mismatches with dbt Objects

**Problem**: dbt manifest objects use Pydantic models. Fields that look like strings in JSON are often already Python objects.

**Example Bug We Hit**:
```python
# WRONG - generated_at is already a datetime object
gen_at = datetime.fromisoformat(manifest.metadata.generated_at)  # TypeError!

# CORRECT - use it directly
gen_at = manifest.metadata.generated_at
```

**How to Debug**:
```python
print(f"DEBUG: type = {type(manifest.metadata.generated_at)}")
print(f"DEBUG: value = {manifest.metadata.generated_at}")
```

#### 2. Silent Exception Catching

Many tracking functions use broad `except Exception:` to prevent crashes:

```python
try:
    # tracking code
except Exception:
    # Silently set defaults
    prop["has_base_env"] = False
```

**How to Debug**: Add prints inside the except block temporarily:

```python
except Exception as e:
    print(f"DEBUG: Exception in tracking: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
    prop["has_base_env"] = False
```

#### 3. Manifest vs Lineage Data Access

**Two ways to access manifest metadata**:

1. **Direct from adapter** (used in event tracking):
   ```python
   dbt_adapter.base_manifest.metadata.generated_at  # datetime object
   ```

2. **From lineage API** (used by frontend):
   ```python
   lineage_diff.base['manifest_metadata']['generated_at']  # ISO string
   ```

The adapter stores Python objects; the API serializes them to JSON.

---

## Debugging Instrumentation and Events

This section covers debugging analytics/instrumentation code specifically.

### Check Event Logging

All events are logged with `print()` in the `log_event()` function in `recce/event/__init__.py`:

```python
print("Logging event:", event_type, prop)
```

Look for these lines in server output to verify events are firing.

### Event Data Flow

**Events Triggered on Server Start:**
- `load_state` - Called during server initialization in `server.py`
- `environment_snapshot` - Called during server initialization in `server.py`

**Events Triggered by API Calls:**
- `session_milestone` - Called when milestones are reached
- `create_check` / `check_approved` - Called from check API endpoints
- `create_run` / `run_completed` - Called from run API endpoints

### Testing Event Implementation

### Verify Event Properties

1. **Start server** and watch for event logs in stdout
2. **Trigger the event** via API call or action
3. **Check output** matches expected format:

```
Logging event: environment_snapshot {
    'has_cloud': False,
    'cloud_mode': 'local',
    'has_base_env': True,
    'manifest_base_age_hours': 1462.85,
    ...
}
```

### Verify Session Milestones

Session milestones use in-memory deduplication:

```python
_session_milestones = set()  # Cleared on server restart
```

**To Test**:
1. First call: Event should fire
2. Second call same session: Event should NOT fire (already in set)
3. Restart server: Event should fire again (set cleared)

### Verify Hashing

All IDs should be hashed with SHA256:

```python
from hashlib import sha256
hashed_id = sha256(str(original_id).encode()).hexdigest()
```

**To Verify**: Check event output - IDs should be 64-char hex strings, not original values.

### Event Debugging Checklist

When an event isn't working:

- [ ] Added `print()` statements to verify code execution
- [ ] Checked server stdout for event logs
- [ ] Verified no exceptions in try/except blocks
- [ ] Checked object types (especially dbt Pydantic models)
- [ ] Tested with direct API calls, not just browser
- [ ] Verified event fires in correct code path
- [ ] Checked session state (milestones, deduplication)
- [ ] Ensured IDs are hashed for privacy

---

## File Locations Reference

- **Event tracking core**: `recce/event/__init__.py`
- **Server setup & endpoints**: `recce/server.py`
- **Check API**: `recce/apis/check_api.py`
- **Run execution**: `recce/apis/run_func.py`
- **Adapter interface**: `recce/adapter/dbt_adapter/__init__.py`

---

## Tips for Efficient Debugging

1. **Use the helper script** - `bin/restart-server.sh` handles cleanup and venv activation
2. **Use API calls instead of browser** - Much faster iteration for backend testing
3. **Add temporary print statements liberally** - They're easy to remove later
4. **Test one event at a time** - Isolate the code path
5. **Check both success and failure cases** - Verify error handling
6. **Kill and restart server** between tests if state matters (milestones, etc.)
7. **Keep `.claude/journal.md` updated** with new lessons learned

---

**Last Updated**: 2025-10-23
**Related Files**: `.claude/journal.md`, `.claude/phase1-implementation-summary.md`
