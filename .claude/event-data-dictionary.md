# Recce Event Telemetry Data Dictionary

## Overview

This document defines the 7 core events that Recce emits for analytics and performance tracking. Events are sent to Amplitude and Sentry via the event collector.

---

## Event 1: `[User] load_state`

**When it fires:**

- Server startup
- When `recce run` command is executed

**Purpose:**
Track initial state of project and check inventory when Recce loads

**Example output:**

```json
{
  "command": "server",
  "checks": 4,
  "preset_checks": 4,
  "single_env": false
}
```

**Fields:**
| Field | Type | Description |
|-------|------|-------------|
| `command` | string | How recce was invoked: 'server' or 'run' |
| `checks` | integer | Total number of checks configured in project |
| `preset_checks` | integer | Number of preset checks (provided by Recce) |
| `single_env` | boolean | Whether running in single environment mode (only for 'server' command) |

**Status:** ✅ Implemented

---

## Event 2: `[User] environment_snapshot`

**When it fires:**

- Server startup (after load_state)
- Once per session

**Purpose:**
Capture the execution environment, infrastructure, and data freshness at startup time

**Example output:**

```json
{
  "has_cloud": false,
  "cloud_mode": "local",
  "has_pr": false,
  "pr_info": {
    "number": "sha256hash...",
    "state": "open",
    "age_hours": 24.5
  },
  "adapter_type": "dbt",
  "warehouse_type": "duckdb",
  "has_database": true,
  "has_base_env": true,
  "catalog_age_hours_base": 334.44,
  "has_current_env": true,
  "catalog_age_hours_current": 334.42
}
```

**Fields:**
| Field | Type | Description |
|-------|------|-------------|
| `has_cloud` | boolean | Is Recce Cloud integration enabled |
| `cloud_mode` | string | 'cloud' or 'local' - deployment mode |
| `has_pr` | boolean | Is this execution tied to a GitHub PR |
| `pr_info` | object\|null | PR metadata (only present if has_pr=true) |
| `pr_info.number` | string\|null | SHA256 hash of PR number (for privacy) |
| `pr_info.state` | string\|null | PR state: 'open', 'closed', 'merged' |
| `pr_info.age_hours` | float\|null | Hours since PR was created |
| `adapter_type` | string | Data tool adapter: 'dbt', 'sqlmesh', etc. |
| `warehouse_type` | string | Database: 'duckdb', 'postgres', 'snowflake', 'bigquery', etc. |
| `has_database` | boolean | Whether database connection is configured |
| `has_base_env` | boolean | Whether base/reference environment is available |
| `catalog_age_hours_base` | float\|null | Hours old - base environment catalog/manifest |
| `has_current_env` | boolean | Whether current/target environment is available |
| `catalog_age_hours_current` | float\|null | Hours old - current environment catalog/manifest |

**Status:** ✅ Implemented with collapsed PR fields and catalog age

## Event 3: `[Performance] model lineage`

**When it fires:**

- During server startup (first lineage computation)
- When user views lineage tab in UI
- Potentially on every lineage computation

**Purpose:**
Track lineage computation performance metrics and changes detected

**Example output:**

```json
{
  "lineage_elapsed_ms": 3.47,
  "column_lineage_elapsed_ms": null,
  "total_nodes": 11,
  "model_nodes": 8,
  "source_nodes": 3,
  "init_nodes": null,
  "cll_nodes": 0,
  "change_analysis_nodes": 0,
  "anchor_nodes": null,
  "params": null,
  "change_status": {
    "models": {
      "new": 1,
      "modified": 3,
      "unchanged": 4
    },
    "sources": {
      "new": 0,
      "modified": 0,
      "unchanged": 3
    }
  }
}
```

**Fields:**
| Field | Type | Description |
|-------|------|-------------|
| `lineage_elapsed_ms` | float | Time in milliseconds to compute model lineage |
| `column_lineage_elapsed_ms` | float\|null | Time in milliseconds for column-level lineage (not implemented yet) |
| `total_nodes` | integer | Total nodes in lineage (models + sources) |
| `model_nodes` | integer | Count of dbt model nodes |
| `source_nodes` | integer | Count of dbt source nodes |
| `init_nodes` | integer\|null | **RESERVED** - initialization nodes (future feature) |
| `cll_nodes` | integer | **RESERVED** - column-level lineage node count (future feature) |
| `change_analysis_nodes` | integer | **RESERVED** - nodes affected by change analysis (future feature) |
| `anchor_nodes` | integer\|null | **RESERVED** - anchor nodes for lineage analysis (future feature) |
| `params` | object\|null | Query parameters and flags (if applicable) |
| `change_status` | object | **NEW (Oct 22, 2025)** - Semantic change tracking by resource type |
| `change_status.models` | object | Models breakdown: `{new: int, modified: int, unchanged: int}` |
| `change_status.sources` | object | Sources breakdown: `{new: int, modified: int, unchanged: int}` |

**Implementation Notes:**

- `change_status` is included for self-containment even though it's a duplicate of the [User] model_lineage event
- These are pure performance metrics

**Status:** ✅ Implemented with performance-only focus

---

## Event 3.5: `[User] model_lineage`

**When it fires:**

- During server startup (first lineage computation)
- When user views lineage tab in UI
- Periodically when lineage is recomputed

**Purpose:**
Track semantic changes detected during model lineage analysis (separate from performance metrics)

**Example output:**

```json
{
  "total_nodes": 11,
  "model_nodes": 8,
  "source_nodes": 3,
  "change_status": {
    "models": {
      "new": 1,
      "modified": 3,
      "unchanged": 4
    },
    "sources": {
      "new": 0,
      "modified": 0,
      "unchanged": 3
    }
  }
}
```

**Fields:**
| Field | Type | Description |
|-------|------|-------------|
| `total_nodes` | integer | Total nodes in lineage (models + sources) |
| `model_nodes` | integer | Count of dbt model nodes |
| `source_nodes` | integer | Count of dbt source nodes |
| `change_status` | object | Semantic change tracking by resource type |
| `change_status.models` | object | Models breakdown: `{new: int, modified: int, unchanged: int}` |
| `change_status.sources` | object | Sources breakdown: `{new: int, modified: int, unchanged: int}` |

**Implementation Notes:**

- `change_status` only counts actual code changes (checksum-based comparison)
- Metadata-only changes (like schema field updates) are excluded
- Only resources with actual SQL code differences are marked as "modified"
- Node counts included for self-containment so this event is independently useful

**Status:** ✅ Implemented as separate user event

---

## Event 4: `[User] viewed_lineage`

**When it fires:**

- Once per session when user opens the lineage graph
- Subsequent views in same session do not fire (in-memory deduplication)

**Purpose:**
Track when users engage with model lineage visualization

**Example output:**

```json
{
  "session_context": {
    "num_checks": 4,
    "num_runs": 0,
    "num_changes": 3
  }
}
```

**Fields:**
| Field | Type | Description |
|-------|------|-------------|
| `session_context` | object | Snapshot of session state when milestone reached |
| `session_context.num_checks` | integer | Number of checks loaded in session |
| `session_context.num_runs` | integer | Number of check runs completed in session |
| `session_context.num_changes` | integer | Number of changed nodes detected |

**Status:** ✅ Implemented

---

## Event 5: `[User] viewed_checks`

**When it fires:**

- Once per session when user opens the checks panel
- Subsequent views in same session do not fire (in-memory deduplication)

**Purpose:**
Track when users engage with check management interface

**Status:** ✅ Implemented

---

## Event 6: `[User] viewed_query`

**When it fires:**

- Once per session when user opens the query builder
- Subsequent views in same session do not fire (in-memory deduplication)

**Purpose:**
Track when users engage with custom query interface

**Status:** ✅ Implemented

---

## Event 7: `[User] ran_check`

**When it fires:**

- When user executes a check (after clicking run)
- Fires every time a check is executed

**Purpose:**
Track check execution engagement

**Status:** ✅ Implemented

---

## Event 8: `[User] approved_check`

**When it fires:**

- When user marks a check as approved/passing
- Only fires on approval transition (not on unapproval)

**Purpose:**
Track check approval workflow engagement

**Status:** ✅ Implemented

---

## Event 9: `[User] created_check`

**When it fires:**

- When user creates a new check
- Fires once per check creation

**Purpose:**
Track check creation engagement

**Status:** ✅ Implemented

---

## Event 10: `[User] run_completed`

**When it fires:**

- When a check run finishes executing (success, error, or cancelled)

**Purpose:**
Track check execution outcomes, performance, and error patterns

**Example output:**

```json
{
  "run_id": "abc123def456...",
  "run_type": "schema_diff",
  "status": "success",
  "duration_seconds": 1.234,
  "error_type": null,
  "error_message": null,
  "result_size": 0,
  "has_differences": false
}
```

**Fields:**
| Field | Type | Description |
|-------|------|-------------|
| `run_id` | string | SHA256 hash of run ID (for privacy) |
| `run_type` | string | Type of check: 'query_diff', 'schema_diff', 'row_count_diff', 'value_diff', 'profile_diff', etc. |
| `status` | string | Outcome: 'success', 'error', or 'cancelled' |
| `duration_seconds` | float | Elapsed time to execute the check |
| `error_type` | string\|null | Category: 'connection', 'timeout', 'query_error', 'validation_error', 'other' |
| `error_message` | string\|null | Truncated error message (first 200 chars, no sensitive data) |
| `result_size` | integer\|null | Number of rows returned in result (if applicable) |
| `has_differences` | boolean\|null | Whether diff operation found differences |

**Status:** ✅ Implemented (flagged for testing with various run types)

---

## Event 11: `api_event`

**When it fires:**

- When API endpoints are called (create_check, submit_run, etc.)

**Purpose:**
Track which API endpoints are used and how they're accessed

**Current coverage:**
- `create_check` - Check creation with source tracking (manual, preset, history, run-based)
- `check_approved` - Check approval transitions with context

**Status:** ✅ Partially Implemented (flagged for ongoing monitoring)

---

## Event 12: `[Performance] column level lineage`

**When it fires:**

- When column-level lineage is computed (if/when feature is implemented)

**Purpose:**
Track performance and results of column-level lineage analysis

**Expected fields:**
Similar structure to model lineage event:

- `lineage_elapsed_ms`
- `cll_nodes` (actual count, not reserved)
- `per_node_metrics`
- `change_status` (potentially by column granularity)

**Status:** 🚧 Not Yet Implemented (reserved for future feature)

---

## Additional Context

### Event Anatomy

All events include standard context fields added by `log_event()`:

- `repository` - SHA256 hash of repository URL (privacy)
- `branch` - SHA256 hash of current branch name (privacy)
- `runner_type` - 'github codespaces', 'ci', etc. (if detectable)
- `codespaces_name` - GitHub Codespaces name (if applicable)

### Event Transport

- **Amplitude**: Anonymous analytics (event_type, properties, timestamp)
- **Sentry**: Error tracking and performance monitoring
- Events scheduled for batch sending via `_collector.schedule_flush()`

### Debug Mode

Set `RECCE_DEBUG_EVENTS=true` environment variable to print all events to console with format:

```
[RECCE_DEBUG] Logging event: {event_type} {properties_dict}
```

---

## Feedback Section

**Overall observations and suggestions:**

_[User adds comments here]_

**Missing events:**
_[User identifies gaps]_

**Fields to reconsider:**
_[User flags problematic fields]_

**Privacy concerns:**
_[User notes any privacy issues]_
