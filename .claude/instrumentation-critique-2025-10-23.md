# Code Review: Analytics Instrumentation PR
**Date**: October 23, 2025
**Reviewer**: Claude (unsparing critique requested)
**Branch**: amplitude-instrumentation-clean

## Summary
486 lines of analytics instrumentation code across 9 files. Generally captures the right data points with good privacy practices, but has significant code quality issues that need addressing before merge.

---

## 🔴 Major Issues (Must Fix)

### 1. Bare `except Exception` blocks everywhere
**Location**: `recce/event/__init__.py` throughout

**Problem**:
```python
except Exception:
    # Context not ready yet
    return
```

Silently swallows ALL exceptions including:
- `KeyboardInterrupt` (user trying to kill the process)
- `SystemExit` (process trying to exit)
- `MemoryError`
- Actual bugs in your code

**Impact**: Makes debugging impossible, can hide critical failures, prevents graceful shutdown

**Fix**:
- Be specific about expected exceptions (`AttributeError`, `ValueError`, etc.)
- At minimum, log the exception before swallowing it
- Never catch `KeyboardInterrupt` or `SystemExit`
- Consider: `except Exception as e: logger.warning(f"Failed to track event: {e}")`

---

### 2. Massive code duplication in `log_environment_snapshot()`
**Location**: `recce/event/__init__.py` lines 376-494

**Problem**:
- Imports `DbtAdapter` **twice** (lines 363, 376)
- Checks `adapter_type == "dbt"` **three times** (lines 359, 373, 376)
- Repeats nearly identical try-except blocks for base and current environments
- ~50 lines that could be 20 with proper abstraction

**Example of duplication**:
```python
# Base environment (lines 380-391)
if dbt_adapter.base_manifest:
    prop["has_base_env"] = True
    if (dbt_adapter.base_catalog and ...):
        gen_at = dbt_adapter.base_catalog.metadata.generated_at
        now = datetime.now(timezone.utc)
        prop["catalog_age_hours_base"] = ...

# Current environment (lines 393-404) - IDENTICAL PATTERN
if dbt_adapter.curr_manifest:
    prop["has_current_env"] = True
    if (dbt_adapter.curr_catalog and ...):
        gen_at = dbt_adapter.curr_catalog.metadata.generated_at
        now = datetime.now(timezone.utc)
        prop["catalog_age_hours_current"] = ...
```

**Fix**: Extract a helper function:
```python
def _get_catalog_age(catalog) -> Optional[float]:
    if not catalog or not catalog.metadata or not catalog.metadata.generated_at:
        return None
    gen_at = catalog.metadata.generated_at
    now = datetime.now(timezone.utc)
    return (now - gen_at).total_seconds() / 3600

# Then use it:
prop["catalog_age_hours_base"] = _get_catalog_age(dbt_adapter.base_catalog)
prop["catalog_age_hours_current"] = _get_catalog_age(dbt_adapter.curr_catalog)
```

---

### 3. Silent data loss in error handling
**Location**: Multiple locations in `recce/event/__init__.py`

**Problem**:
```python
except Exception:
    prop["warehouse_type"] = None
    prop["has_database"] = False
```

If getting warehouse type fails, you set it to None and **never tell anyone why**. In production, you'll have no idea what went wrong.

**Impact**: Lost debugging information, silent failures

**Fix**: Log the exception
```python
except Exception as e:
    logger.debug(f"Failed to get warehouse type: {e}")
    prop["warehouse_type"] = None
```

---

### 4. Inconsistent hashing approach
**Location**: Various files

**Problem**:
```python
# Sometimes:
sha256(str(check_id).encode()).hexdigest()

# Other times:
sha256(check_id.encode()).hexdigest()  # if already a string
```

The `str()` call is:
- Unnecessary if it's already a string (wasteful)
- Required if it's a UUID but inconsistently applied

**Fix**: Create a helper function:
```python
def hash_id(value: Union[str, UUID]) -> str:
    """Hash an ID for privacy. Handles both strings and UUIDs."""
    return sha256(str(value).encode()).hexdigest()
```

---

### 5. Magic strings everywhere
**Location**: `recce/apis/check_api.py` lines 80-93

**Problem**:
```python
source = "run"
source = "preset"
source = "history"
source = "manual"
```

No enum, no constants, just strings scattered through the code. Typo waiting to happen.

**Fix**: Use an enum or constants
```python
from enum import Enum

class CheckSource(str, Enum):
    RUN = "run"
    PRESET = "preset"
    HISTORY = "history"
    MANUAL = "manual"

# Then use:
source = CheckSource.RUN
```

---

### 6. Frontend ref hack is fragile
**Location**: `js/app/page.tsx` lines 322, 346-354

**Problem**:
```javascript
isUserTabClickRef.current = true;
// ... later in useEffect
if (!isUserTabClickRef.current) {
    setValueLocation(newTab);
} else {
    isUserTabClickRef.current = false;
}
```

This is a race condition waiting to happen. If useEffect runs before you reset the flag, or if React batches updates differently, this breaks. It works now but it's brittle.

**Impact**: Fragile behavior that could break with React updates or timing changes

**Fix**: Consider using a more robust pattern like tracking the source of state changes, or restructure to avoid the conflict entirely. At minimum, add a detailed comment explaining the race condition and why this pattern is necessary.

---

## 🟡 Medium Issues (Should Fix)

### 7. Inconsistent parameter naming
**Problem**: Mixed `snake_case` and `camelCase`
- Python: `check_id`, `run_id` ✓
- TypeScript: Sometimes `checkId`, sometimes `check_id`

**Fix**: Be consistent - Python uses snake_case, TypeScript uses camelCase

---

### 8. Function signatures are sprawling
**Location**: `recce/event/__init__.py` line 476

**Problem**:
```python
def log_run_completed(
    run_id: str,
    run_type: str,
    status: str,
    duration_seconds: float,
    error: str = None,
    result=None,
    check_id: str = None,
    check_position: int = None
):
```

8 parameters! This is hard to call correctly and maintain.

**Fix**: Use a dataclass or TypedDict:
```python
@dataclass
class RunCompletedEvent:
    run_id: str
    run_type: str
    status: str
    duration_seconds: float
    error: Optional[str] = None
    check_id: Optional[str] = None
    check_position: Optional[int] = None

def log_run_completed(event: RunCompletedEvent):
    ...
```

---

### 9. No tests
**Problem**: Shipping 486 lines of instrumentation code with **zero tests**

**Questions unanswered**:
- Do events fire when they should?
- Do they NOT fire when they shouldn't?
- Is data correctly hashed?
- What happens if Amplitude is down?
- Are all code paths exercised?

**Fix**: Add at least basic tests:
- Unit tests for event formatting functions
- Integration tests that verify events fire
- Tests for privacy (hashing works correctly)
- Tests for error cases

---

### 10. Debug logging uses print()
**Location**: `recce/event/__init__.py` line 177

**Problem**:
```python
if os.getenv("RECCE_DEBUG_EVENTS"):
    print(f"[RECCE_DEBUG] Logging event: {event_type} {prop}")
```

Should use Python's logging module, not print(). This doesn't respect log levels, can't be redirected, and can't be filtered.

**Fix**:
```python
import logging
logger = logging.getLogger(__name__)

if os.getenv("RECCE_DEBUG_EVENTS"):
    logger.debug(f"Logging event: {event_type} {prop}")
```

---

### 11. Dead code
**Location**: `recce/event/__init__.py` lines 431-438

**Problem**:
```python
def log_viewed_checks():
    """Log when user views the checks panel"""
    log_event({}, "[User] viewed_checks")

def log_viewed_query():
    """Log when user views the query builder"""
    log_event({}, "[User] viewed_query")
```

These functions are defined but **never called anywhere**. Dead code that will confuse future developers.

**Fix**: Remove them or implement the tracking

---

## 🟢 Good Things

1. **Privacy-conscious hashing** - SHA256 for IDs is appropriate
2. **Comprehensive tracking** - Captures the right data points (environment, milestones, lifecycle)
3. **Event naming convention** - `[User]` and `[Performance]` prefixes make event categories clear
4. **Documentation in commit messages** - Very thorough explanations
5. **Debug mode** - `RECCE_DEBUG_EVENTS` environment variable is helpful
6. **Session deduplication** - Milestone tracking prevents duplicate events

---

## 📋 Pre-Merge Checklist

**Must fix before merge**:
- [ ] Replace bare `except Exception` with specific exceptions or logging
- [ ] Refactor `log_environment_snapshot()` to eliminate duplication
- [ ] Add constants/enums for magic strings (source types, etc.)
- [ ] Use logging module instead of print()
- [ ] Remove dead code (log_viewed_checks, log_viewed_query)
- [ ] Add at least basic tests for event functions
- [ ] Document the frontend ref pattern with detailed comment

**Should fix before merge**:
- [ ] Consistent naming conventions across languages
- [ ] Refactor long parameter lists into data structures
- [ ] Create hash_id() helper function
- [ ] Add error logging to exception handlers

**Nice to have**:
- [ ] Type hints for all function parameters
- [ ] Docstrings for all public functions
- [ ] Integration tests for full event flow

---

## The Honest Question

**Would you approve this PR if someone else submitted it to your project?**

Answer: No, not without addressing the major issues. The bare exception handlers and code duplication are embarrassing for production code. The lack of tests means we have no confidence it works correctly.

However, the **architecture is sound** and the **privacy approach is good**. With cleanup, this would be solid code.

---

## Estimated Effort to Fix

- Major issues: 2-3 hours
- Medium issues: 1-2 hours
- Tests: 3-4 hours
- Total: ~1 day of focused work

Worth it to ship quality code to the open source community.
