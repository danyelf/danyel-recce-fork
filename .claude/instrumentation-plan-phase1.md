# Recce Analytics Instrumentation - Phase 1 Implementation

## Overview

This is a minimal first phase focusing on 7 core events that answer the highest-priority questions from the instrumentation goals. We're following YAGNI principles - implementing just enough to get actionable insights, then iterating.

## Events to Implement (Phase 1)

### 1. `environment_snapshot`
**When**: Server startup only (not periodic)
**Where**: `recce/server.py` - after `load_context()` completes
**Why**: Understand user configuration and identify where users get stuck

**Properties**:
```python
{
    'has_cloud': bool,              # CloudStateLoader vs FileStateLoader
    'has_pr': bool,                 # PR metadata exists in state
    'has_database': bool,           # Adapter initialized with credentials
    'cloud_mode': str,              # 'cloud', 'local', 'single_env'
    'pr_number': str | None,        # Hashed PR number
    'pr_age_hours': float | None,   # Hours since PR created
    'pr_state': str | None,         # 'open', 'closed', 'merged'
    'manifest_base_age_hours': float | None,   # From manifest.metadata.generated_at
    'manifest_current_age_hours': float | None,
    'catalog_base_age_hours': float | None,    # From catalog.metadata.generated_at
    'catalog_current_age_hours': float | None,
    'warehouse_type': str | None,   # 'snowflake', 'bigquery', etc.
    'adapter_type': str,            # 'dbt', 'sqlmesh'
    'has_base_env': bool,           # Whether base manifest exists
    'has_current_env': bool,        # Whether current manifest exists
}
```

**Implementation**:
- Extract properties from `RecceContext`
- Use `manifest.metadata.generated_at` for artifact timestamps
- Hash PR number using SHA256 like repo/branch
- Don't actually test database connection (just check if configured)

---

### 2. `session_milestone` (NEW)
**When**: User crosses a significant milestone for first time in session
**Where**: Backend - various locations as milestones are reached
**Why**: Identify drop-off points in user journey

**Properties**:
```python
{
    'milestone': str,               # 'viewed_lineage', 'created_check', 'ran_check', 'approved_check', 'viewed_results'
    'time_since_session_start_seconds': float,
    'session_context': {
        'num_checks': int,          # Total checks at milestone
        'num_runs': int,            # Total runs at milestone
        'num_changes': int,         # Number of changed nodes
    }
}
```

**Milestones to track**:
- `viewed_lineage` - when `/api/info` is called (lineage loaded)
- `created_check` - first check created
- `ran_check` - first run submitted
- `approved_check` - first check approved
- `viewed_results` - first run result retrieved

**Implementation**:
- Track milestones in session state (in-memory set)
- Fire event only once per milestone per session
- Session = server uptime (reset on restart)

---

### 3. `feature_used` (ENRICH EXISTING)
**When**: Run is submitted
**Where**: Backend - `recce/apis/run_api.py` in `submit_run_handler()`
**Why**: Understand which features users try

**Properties**:
```python
{
    'run_id': str,                  # Hashed run ID
    'run_type': str,                # 'query', 'profile_diff', 'value_diff', etc.
    'from_context': str,            # 'check', 'history', 'direct', 'preset'
    'has_check': bool,              # Is this associated with a check?
    'node_id': str | None,          # Hashed node ID if single-node operation
    'num_nodes': int | None,        # For multi-node operations
}
```

**Implementation**:
- This is already tracked via `log_api_event` in run submission
- Enrich with additional context properties
- Use existing event infrastructure

---

### 4. `run_completed` (NEW - CRITICAL)
**When**: Run finishes (success, error, or cancellation)
**Where**: Backend - `recce/tasks/core.py` in Task execution or run_api response
**Why**: Understand success rates and performance

**Properties**:
```python
{
    'run_id': str,                  # Hashed, matches feature_used
    'run_type': str,
    'status': str,                  # 'success', 'error', 'cancelled'
    'duration_seconds': float,
    'error_type': str | None,       # 'connection', 'timeout', 'query_error', 'validation_error'
    'error_message': str | None,    # First 200 chars of error (no sensitive data)
    'result_size': int | None,      # Number of rows returned (for diffs)
    'has_differences': bool | None, # For diff operations
}
```

**Implementation**:
- Track in run submission/completion flow
- Capture error info safely (no SQL, no data values)
- Fire even on errors/cancellation

---

### 5. `check_created` (ENRICH EXISTING)
**When**: Check is added to checklist
**Where**: Backend - `recce/apis/check_api.py` in `create_check()`
**Why**: Understand checklist building patterns

**Properties**:
```python
{
    'check_id': str,                # Hashed
    'check_type': str,              # RunType value
    'source': str,                  # 'manual', 'preset', 'history', 'run'
    'has_run': bool,                # Created with existing run?
    'num_existing_checks': int,     # How many checks already exist?
    'is_first_check': bool,         # Is this the user's first check this session?
}
```

**Implementation**:
- Already partially tracked via `log_api_event`
- Add context about source and existing checks
- Determine source from request params

---

### 6. `check_approved` (NEW)
**When**: Check is approved or unapproved
**Where**: Backend - check approval endpoint
**Why**: Measure checklist completion behavior

**Properties**:
```python
{
    'check_id': str,                # Hashed
    'check_type': str,
    'approved': bool,               # True = approved, False = unapproved
    'has_passing_run': bool | None, # Does latest run show success/no differences?
    'num_approved': int,            # Total approved checks after this action
    'num_total_checks': int,        # Total checks
}
```

**Implementation**:
- Track in check update endpoint when `is_checked` changes
- Determine "passing" based on run result (no errors, no unexpected differences)

---

### 7. `tab_changed` (NEW - FRONTEND)
**When**: User switches tabs in UI
**Where**: Frontend - `js/app/page.tsx` or routing logic
**Why**: Understand navigation patterns and workflow

**Properties**:
```python
{
    'from_tab': str,                # 'lineage', 'checks', 'query', 'runs', null (initial)
    'to_tab': str,
    'time_on_previous_tab_seconds': float | None,
}
```

**Implementation**:
- Use frontend Amplitude SDK directly (already available)
- Track in React state/effect when active tab changes
- Calculate time using timestamps

---

## Implementation Approach

### Backend Events (1-6)

**Step 1**: Add helper functions to `recce/event/__init__.py`
```python
def log_environment_snapshot(context: RecceContext):
    """Log environment configuration at server startup"""

def log_session_milestone(milestone: str, context: RecceContext):
    """Log when user reaches a journey milestone"""

def log_run_completed(run_id: str, run: Run, duration: float):
    """Log run completion with status and metrics"""
```

**Step 2**: Modify backend files
- `recce/server.py`: Add environment snapshot after context load
- `recce/server.py`: Initialize session milestone tracker
- `recce/apis/run_api.py`: Enrich feature_used, add run_completed
- `recce/apis/check_api.py`: Enrich check_created, add check_approved

**Step 3**: Test events fire correctly
- Start server → verify environment_snapshot
- Create check → verify check_created + milestone
- Run check → verify feature_used + run_completed + milestone
- Approve check → verify check_approved + milestone

### Frontend Events (7)

**Step 1**: Add tracking function to `js/src/lib/api/track.ts`
```typescript
interface TabChangedProps {
  from_tab: string | null;
  to_tab: string;
  time_on_previous_tab_seconds: number | null;
}

export function trackTabChanged(props: TabChangedProps) {
  track("tab_changed", props);
}
```

**Step 2**: Add to tab component
- Track tab changes in React state
- Calculate time on tab
- Call tracking function on change

**Step 3**: Test in browser
- Switch tabs → verify events in Amplitude debugger

---

## Event Property Standards

### Hashing
Use SHA256 for all IDs (consistent with existing repo/branch hashing):
```python
from hashlib import sha256
hashed_id = sha256(str(original_id).encode()).hexdigest()
```

### Time Calculations
```python
from datetime import datetime, timezone

def hours_since(timestamp_str: str) -> float:
    """Calculate hours since a timestamp"""
    dt = datetime.fromisoformat(timestamp_str)
    now = datetime.now(timezone.utc)
    return (now - dt).total_seconds() / 3600
```

### Error Messages
Truncate to 200 chars, remove any data values:
```python
error_msg = str(error)[:200]
# TODO: Sanitize further if needed
```

---

## Testing Strategy

### 1. Local Testing
- Run recce server locally
- Perform actions: create check, run check, approve check, switch tabs
- Verify events in console (currently prints "Logging event:")
- Check event properties are correct

### 2. Amplitude Validation
- Once `RECCE_EVENT_API_KEY` is set
- Use Amplitude debugger to see events in real-time
- Validate property types and values

### 3. Privacy Check
- Verify all IDs are hashed
- Verify no SQL or data values in properties
- Verify PR numbers/node names are hashed

---

## Success Metrics (Phase 1)

After implementation, we should be able to answer:

1. **"Are users getting stuck?"**
   - Look at environment_snapshot: % with cloud, PR, database
   - Look at session_milestone: drop-off between viewed_lineage → created_check → ran_check

2. **"Which features work/fail?"**
   - Compare feature_used vs run_completed
   - Calculate success rate per run_type
   - Identify common error_types

3. **"Are checklists being used?"**
   - check_created count and sources
   - check_approved rate
   - Time from created → approved

4. **"How do users navigate?"**
   - tab_changed sequences (lineage → checks → runs?)
   - Time spent per tab

---

## What We're NOT Doing (Yet)

Explicitly deferring to Phase 2+:
- Dataset size/complexity tracking (lineage_computed)
- Detailed lineage interactions (model_selected, zoom, pan)
- Collaboration/sharing events
- Query builder details
- Comprehensive error tracking
- Result viewing details
- Preset loading tracking

We can add these once we validate Phase 1 gives us actionable insights.

---

## Implementation Order

1. ✅ Backend helper functions (`recce/event/__init__.py`)
2. ✅ environment_snapshot (server startup)
3. ✅ session_milestone infrastructure
4. ✅ Enrich feature_used (run submission)
5. ✅ Add run_completed (run completion)
6. ✅ Enrich check_created
7. ✅ Add check_approved
8. ✅ Frontend tab_changed

Estimated effort: 1-2 days implementation + 0.5 day testing
