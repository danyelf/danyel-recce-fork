# Recce Analytics Instrumentation Plan

## Executive Summary

This plan outlines a comprehensive analytics instrumentation strategy for Recce, designed to answer key product questions about user configuration, dataset characteristics, feature usage, collaboration patterns, and checklist behavior. The instrumentation will leverage existing infrastructure (Amplitude via `recce/event/`) and add strategic tracking points throughout both backend (Python/FastAPI) and frontend (TypeScript/React).

## Current Infrastructure

### Backend Event System
- **Location**: `recce/event/__init__.py`, `recce/event/track.py`, `recce/event/collector.py`
- **API**: `log_event(prop: dict, event_type: str, **kwargs)`
- **Transport**: Amplitude API via Collector class
- **User ID**: Generated UUID stored in `~/.recce/profile.yml`
- **Properties**: Automatically enriches with version, Python version, CI status, GitHub Codespace info
- **Existing Events**: `command`, `api_event`, `load_state`, `codespace_instance`, performance events

### Frontend Event System
- **Location**: `js/src/lib/api/track.ts`
- **API**: Amplitude SDK's `track()` function wrapped in typed helper functions
- **User ID**: From cookie `recce_user_id` (set by backend)
- **Existing Events**: Multi-node actions, history actions, preview change, column-level lineage, share state, copy to clipboard

### API Event Pattern
Backend endpoints use `log_api_event(endpoint_name, props)` which wraps `log_event()` and auto-flushes.

## Instrumentation Strategy by Category

---

## 1. Configuration Tracking

**Goal**: Understand how users are configured to identify where they might be getting stuck or not seeing full value.

### Questions to Answer:
- Is there a cloud connection? Is there a PR? Is there data?
- Recency of PR and dbt artifacts
- How many users are in each configuration mode?

### Events to Track

#### Event: `environment_snapshot`
**When**: Server startup, every 15 minutes while running
**Where**: `recce/server.py` - add after `load_context()` and on timer
**Properties**:
```python
{
    'has_cloud': bool,              # CloudStateLoader vs FileStateLoader
    'has_pr': bool,                 # PR metadata exists in state
    'has_database': bool,           # Adapter can connect to warehouse
    'cloud_mode': str,              # 'cloud', 'local', 'single_env'
    'pr_number': int | None,        # Hashed PR number
    'pr_age_hours': float | None,   # Hours since PR created
    'pr_state': str | None,         # 'open', 'closed', 'merged'
    'manifest_age_hours': float,    # Hours since manifest.json modified
    'catalog_age_hours': float | None,  # Hours since catalog.json modified
    'warehouse_type': str | None,   # 'snowflake', 'bigquery', etc.
    'adapter_type': str,            # 'dbt', 'sqlmesh'
    'has_base_env': bool,           # Whether base environment exists
    'has_current_env': bool,        # Whether current environment exists
}
```

**Implementation Notes**:
- Read state from `RecceContext`
- Get manifest timestamps from `manifest.metadata.generated_at` (base and current)
- Get catalog timestamps from `catalog.metadata.generated_at` (base and current) if available
- Calculate age from current time vs `generated_at` timestamp
- Hash PR numbers for privacy
- Detect cloud mode from state loader type
- Test database connection at startup (try connecting via adapter)

---

## 2. Dataset Specifications

**Goal**: Understand dataset size and change magnitude to inform UI/UX design decisions.

### Questions to Answer:
- How many nodes by type (changed, unchanged, added, removed)?
- How many column changes by type?
- Which changes are code-changed vs propagated-forward?
- How big are typical datasets?

### Events to Track

#### Event: `lineage_computed`
**When**: After DbtAdapter computes lineage diff
**Where**: `recce/adapter/dbt_adapter/__init__.py` - in `get_lineage_diff()` or after it's called
**Properties**:
```python
{
    'total_nodes': int,
    'changed_nodes': int,           # Modified models (code changed)
    'unchanged_nodes': int,         # Unmodified models
    'added_nodes': int,             # New models
    'removed_nodes': int,           # Deleted models
    'nodes_by_type': {              # Breakdown by resource_type
        'model': int,
        'source': int,
        'seed': int,
        'snapshot': int,
    },
    'total_columns': int,
    'added_columns': int,
    'removed_columns': int,
    'modified_columns': int,
    'renamed_columns': int,
    'columns_in_changed_models': int,      # Columns in code-changed models
    'columns_in_propagated_models': int,   # Columns in unchanged but downstream-affected
    'max_depth': int,               # Maximum lineage depth
    'total_edges': int,             # Number of dependencies
}
```

**Implementation Notes**:
- Calculate after `_get_lineage_diff()` completes
- Distinguish code-changed (in modified nodes) from propagated (unchanged nodes downstream of changes)
- Track column-level changes from schema diff if available
- Fire event once per lineage load, not on every query

---

## 3. User Interactions

**Goal**: Understand feature usage, navigation patterns, and identify bumps in user workflows.

### Questions to Answer:
- Which features are most/least popular?
- How do users navigate between views?
- What cues do users follow when exploring lineage?
- Which diff types are most commonly used?

### Events to Track

#### Event: `tab_changed`
**When**: User switches tabs
**Where**: Frontend - `js/app/page.tsx`
**Properties**:
```python
{
    'from_tab': str,    # 'lineage', 'checks', 'query', 'runs'
    'to_tab': str,
    'time_on_tab_seconds': float,
}
```

#### Event: `feature_used`
**When**: User initiates any check/run type
**Where**: Backend - `recce/apis/run_api.py` in `submit_run_handler()`
**Properties**:
```python
{
    'feature_type': str,        # 'query', 'query_diff', 'profile_diff', etc.
    'from_context': str,        # 'lineage', 'check', 'history', 'direct'
    'has_params': bool,
    'is_preset': bool,
    'node_id': str | None,      # Hashed node ID
    'num_nodes': int,           # For multi-node operations
}
```

#### Event: `model_selected`
**When**: User selects node(s) in lineage
**Where**: Frontend - when nodes are selected in lineage view
**Properties**:
```python
{
    'num_selected': int,
    'node_types': list[str],        # Types of selected nodes
    'selection_method': str,        # 'click', 'multi_select', 'search', 'filter'
}
```

#### Event: `lineage_interaction`
**When**: User interacts with lineage graph
**Where**: Frontend - lineage component event handlers
**Properties**:
```python
{
    'action': str,              # 'zoom', 'pan', 'expand', 'collapse', 'search', 'filter'
    'node_id': str | None,      # Hashed
    'node_status': str | None,  # 'changed', 'added', 'removed', 'unchanged'
    'filter_applied': str | None,  # Active filters
}
```

#### Event: `query_builder_used`
**When**: User constructs query in query builder
**Where**: Frontend - query builder component
**Properties**:
```python
{
    'query_type': str,          # 'ad_hoc', 'template', 'modified_preset'
    'has_base_query': bool,
    'has_current_query': bool,
    'execution_method': str,    # 'run_button', 'keyboard_shortcut'
}
```

#### Event: `result_viewed`
**When**: User views diff results
**Where**: Frontend - result display components
**Properties**:
```python
{
    'result_type': str,         # 'profile_diff', 'value_diff', etc.
    'has_differences': bool,
    'num_rows': int | None,
    'view_duration_seconds': float,
    'exported': bool,           # Did they export/copy results?
}
```

---

## 4. Collaboration Features

**Goal**: Understand sharing patterns, multi-user access, and identify friction in collaboration workflows.

### Questions to Answer:
- How often do different people view the same dataset?
- Do users arrive via PR or via share button?
- Where do users drop off in the share funnel?
- How effective are collaboration features?

### Events to Track

#### Event: `share_initiated`
**When**: User clicks share button
**Where**: Frontend - share button component
**Properties**:
```python
{
    'from_view': str,           # 'lineage', 'check', 'run'
    'has_cloud_account': bool,
    'share_type': str,          # 'enabled', 'created', 'copied'
}
```

#### Event: `share_url_created`
**When**: Share URL is generated
**Where**: Backend - `recce/state/state.py` in `RecceShareStateManager`
**Properties**:
```python
{
    'share_id': str,            # Hashed share ID
    'state_size_bytes': int,
    'num_checks': int,
    'num_runs': int,
    'has_pr': bool,
}
```

#### Event: `shared_state_accessed`
**When**: Someone accesses via share URL
**Where**: Backend - when shared state is loaded
**Properties**:
```python
{
    'share_id': str,            # Hashed
    'is_owner': bool,           # Same user who created it?
    'access_method': str,       # 'direct_link', 'pr_comment', 'slack', 'unknown'
    'time_since_creation_hours': float,
}
```

#### Event: `cloud_auth_flow`
**When**: User goes through cloud authentication
**Where**: Backend - cloud auth endpoints
**Properties**:
```python
{
    'action': str,              # 'login_started', 'login_completed', 'signup_started', 'signup_completed', 'login_failed'
    'trigger': str,             # 'share_button', 'manual', 'redirect'
}
```

#### Event: `multi_user_session`
**When**: Multiple users detected on same state
**Where**: Backend - periodic check in cloud state loader
**Properties**:
```python
{
    'num_users': int,           # Hashed user IDs
    'session_duration_hours': float,
    'has_pr': bool,
}
```

---

## 5. Checklist Operations

**Goal**: Understand checklist usage patterns and identify good/bad aspects.

### Questions to Answer:
- How often do people add checks to checklist?
- How often do they save checks from presets?
- How often do they approve/unapprove checks?
- Do people create new checks or modify existing ones?

### Events to Track

#### Event: `check_created`
**When**: Check is added to checklist
**Where**: Backend - `recce/apis/check_api.py` in `create_check()`
**Properties**:
```python
{
    'check_type': str,
    'source': str,              # 'manual', 'preset', 'history', 'suggested'
    'has_run': bool,            # Created with existing run?
    'from_feature': str | None, # Which UI feature triggered creation
}
```
*(Already partially implemented via `log_api_event` but needs enrichment)*

#### Event: `check_modified`
**When**: Check is updated
**Where**: Backend - `recce/apis/check_api.py` in `update_check()`
**Properties**:
```python
{
    'check_type': str,
    'fields_changed': list[str],  # ['name', 'description', 'params', 'view_options']
    'is_preset': bool,
}
```

#### Event: `check_approved`
**When**: Check is marked as approved/unapproved
**Where**: Backend - check approval endpoint
**Properties**:
```python
{
    'check_type': str,
    'approved': bool,           # True = approved, False = unapproved
    'approval_method': str,     # 'checkbox', 'keyboard', 'batch'
    'has_passing_result': bool | None,
}
```

#### Event: `check_deleted`
**When**: Check is removed
**Where**: Backend - `recce/apis/check_api.py` in `delete_check()`
**Properties**:
```python
{
    'check_type': str,
    'is_preset': bool,
    'had_runs': bool,
    'was_approved': bool,
}
```

#### Event: `preset_loaded`
**When**: Preset checks are loaded
**Where**: Backend - preset loading logic
**Properties**:
```python
{
    'num_presets': int,
    'preset_types': list[str],
    'source': str,              # 'default', 'custom', 'imported'
}
```

#### Event: `checklist_exported`
**When**: User exports checklist
**Where**: Frontend - export functionality
**Properties**:
```python
{
    'export_format': str,       # 'json', 'markdown', 'state_file'
    'num_checks': int,
    'num_approved': int,
    'include_runs': bool,
}
```

---

## Implementation Plan

### Phase 1: Backend Infrastructure (Week 1)
1. **Create tracking helpers** in `recce/event/__init__.py`:
   - `log_configuration_event()`
   - `log_dataset_event()`
   - `log_collaboration_event()`
   - Add property enrichment utilities (hashing, age calculation)

2. **Environment snapshot tracking**:
   - Add snapshot collection in `recce/server.py` at startup
   - Implement periodic snapshot timer
   - Add helper to extract all config properties from RecceContext

3. **Enhance API event tracking**:
   - Update `log_api_event()` to accept context-specific properties
   - Add tracking to all CRUD operations in `check_api.py`
   - Add tracking to run submission in `run_api.py`

### Phase 2: Dataset Tracking (Week 2)
1. **Lineage computation tracking**:
   - Add event emission in `recce/adapter/dbt_adapter/__init__.py`
   - Calculate node/column statistics
   - Distinguish code-changed vs propagated changes

2. **Model selection tracking**:
   - Add backend endpoint for selection events if needed
   - Or track via frontend -> backend call pattern

### Phase 3: Frontend Tracking (Week 2-3)
1. **Tab navigation tracking**:
   - Add event handlers in `js/app/page.tsx`
   - Track time spent on each tab

2. **Feature usage tracking**:
   - Add tracking to all major UI interactions:
     - Lineage graph interactions
     - Query builder actions
     - Result viewing
     - Check management UI

3. **Share tracking**:
   - Add events to share button flow
   - Track URL copy actions

### Phase 4: Collaboration Tracking (Week 3)
1. **Share URL lifecycle**:
   - Track creation in `RecceShareStateManager`
   - Track access in state loading logic
   - Add multi-user session detection

2. **Cloud auth tracking**:
   - Add events to authentication flows
   - Track drop-offs at each step

### Phase 5: Testing & Validation (Week 4)
1. **Local testing**:
   - Verify events appear in Amplitude
   - Check property values are correct
   - Test privacy (hashing works)

2. **Staging deployment**:
   - Monitor event volume
   - Check for errors/missing properties
   - Validate with real user flows

3. **Documentation**:
   - Document all events in `ANALYTICS.md`
   - Add comments in code explaining tracking purpose
   - Create dashboard templates for key questions

---

## Privacy & Security Considerations

### Data to Hash
- User IDs (already done)
- Repository names (already done)
- Branch names (already done)
- PR numbers
- Node IDs (model names)
- File paths
- Share IDs

### Data NOT to Track
- Actual SQL queries (except length/complexity metrics)
- Column names or data values
- Database credentials
- User names or emails
- Organization names

### Compliance
- All tracking respects `anonymous_tracking` flag in user profile
- Events only sent when user has opted in
- No PII in event properties
- Data retention follows Amplitude's policies

---

## Success Metrics

After implementation, we should be able to answer:

1. **Configuration**: "X% of users have cloud mode, Y% have PR integration, Z% have database connected"
2. **Dataset size**: "Median changed models: N, 95th percentile: M"
3. **Feature adoption**: "Profile diff used in X% of sessions, value diff in Y%"
4. **Collaboration**: "Z% of shared URLs are accessed by >1 user"
5. **Checklist engagement**: "Users create X checks per session, approve Y%"

---

## Technical Specifications

### Event Naming Conventions
- Use snake_case for event names
- Prefix experimental features with `[Experiment]`
- Prefix performance metrics with `[Performance]`
- Prefix web-only events with `[Web]`
- Use descriptive names: `check_created` not `check_new`

### Property Naming Conventions
- Use snake_case for property names
- Boolean properties: `has_*`, `is_*`, `was_*`
- Counts: `num_*`, `total_*`
- Durations: `*_seconds`, `*_hours`
- IDs: `*_id` (always hashed)
- Types: `*_type`, `*_method`

### Error Handling
- Wrap all tracking calls in try/except
- Never let tracking failures break app functionality
- Log tracking errors to Sentry with low priority
- Degrade gracefully if Amplitude is down

### Testing Strategy
- Unit tests for event property calculation
- Integration tests for event emission
- Manual QA with Amplitude debugger
- Monitor event validation in Amplitude UI

---

## Open Questions

1. **Frequency**: How often should we send environment snapshots? (Proposed: 15 min)
2. **Sampling**: Should we sample high-frequency events? (Proposed: No initially, add if needed)
3. **Retention**: How long should we batch events locally? (Current: ~10 events)
4. **Backend vs Frontend**: Which events should be backend vs frontend? (Proposed: Backend for data/state, frontend for UI interactions)
5. **Session definition**: How do we define a "session"? (Proposed: Server uptime for backend, tab focus for frontend)

---

## Appendix: Existing Event Audit

### Currently Tracked Events
1. `command` - CLI command execution
2. `api_event` - API endpoint calls
3. `load_state` - State file loaded
4. `codespace_instance` - GitHub Codespaces lifecycle
5. `[Experiment] single_environment` - Single env mode
6. `[Performance] {feature_name}` - Performance metrics
7. `Connect OSS to Cloud` - Cloud connection
8. `[Web] multi_nodes_action` - Multi-node UI actions
9. `[Web] history_action` - History panel actions
10. `[Experiment] preview_change` - Preview change feature
11. `Column level lineage` - CLL feature usage
12. `share_state` - Share state actions
13. `state_action` - Import/export state
14. `[Click] copy_to_clipboard` - Copy actions

### Gaps Identified
- No environment configuration snapshot
- No dataset size/change tracking
- Limited check lifecycle tracking
- No collaboration multi-user tracking
- No tab navigation tracking
- No query builder tracking
- No result viewing tracking
