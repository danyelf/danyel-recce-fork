# Recce Development Guide

This document contains Recce-specific development practices and architecture reference.

## Personal Workspace Configuration

If `~/.claude/claude.md` exists, read it to find the personal workspace location for this project. The workspace contains:
- `working-with-you.md` - User's personal workflow preferences
- `journal.md` - Working notes and insights
- `sessions/` - Session summaries
- `plans/` - Planning documents
- `docs/` - Reference documentation

If `~/.claude/claude.md` doesn't exist, proceed without personal preferences.

Custom agents are located in `.claude/agents/` and are shared across the team.

## Recce-Specific Development Practices

### Server Management

**Standing Permission**: You have explicit permission to restart the recce server without asking. Use the provided helper script:

```bash
# Restart server without debug logging
bash bin/restart-server.sh

# Restart server with debug event logging
bash bin/restart-server.sh true /tmp/server.log
```

The script located at `bin/restart-server.sh`:

- Kills any existing recce processes (pkill -9)
- Activates the venv
- Starts the server with optional RECCE_DEBUG_EVENTS=true
- Waits 3 seconds for startup
- Works from any directory (uses absolute paths)

This eliminates the need to ask permission for each server restart during development and testing cycles.

### TDD for Instrumentation and Analytics

Instrumentation work (adding analytics tracking) has special testing considerations because it's fundamentally about side effects rather than application behavior.

**Workflow**: Instrumentation is "complex/nuanced work" - follow the propose → approve → implement → demonstrate workflow:

1. **Propose**: Describe the event to add with expected structure and sample output
2. **Get approval** from Danyel before implementing
3. **Write/update integration test** that expects the analytics event
4. **Run test** to confirm it fails (event not emitted or wrong data)
5. **Add instrumentation code**
6. **Run test** to confirm event is captured with correct structure
7. **Manually verify and demonstrate**: Show Danyel both the code changes AND actual event output from logs/console
8. **Commit** after review

**Testing Tools**:

- Backend events: Use curl/API calls to trigger events, observe server logs
- Frontend events: Use Playwright test (`js/test-frontend-tracking.js`) or manual browser testing with console logs
- Integration tests should verify event structure, hashing, and privacy controls

**Known Limitation**: Integration tests verify instrumentation at implementation time but don't prevent all regressions (e.g., new code paths that bypass tracking). We accept this tradeoff and rely on thorough integration test coverage for major user flows.

---

# Recce Codebase Architecture Guide

## Overview

Recce is a **monorepo** that combines a Python backend with a TypeScript/React frontend to help data teams review dbt model changes through diff comparisons and validation checks. It's designed to work with dbt projects and support both local usage and cloud-based collaboration.

## High-Level Architecture

### Monorepo Structure

```
recce/
├── recce/              # Python backend (pip package)
├── js/                 # TypeScript/React frontend (Next.js)
├── tests/              # Python tests
├── integration_tests/  # Integration tests
└── macros/             # dbt macros
```

### Tech Stack

**Backend (Python)**

- **Framework**: FastAPI with Uvicorn (async HTTP server)
- **Key Libraries**: Pydantic (validation), deepdiff, GitPython, PyGithub
- **dbt Integration**: Uses dbt-core SDK to parse projects and artifacts
- **State Management**: In-memory with JSON serialization and S3/cloud persistence
- **Event Tracking**: Sentry for error tracking and custom telemetry

**Frontend (TypeScript/React)**

- **Framework**: Next.js 15 with App Router
- **UI Library**: Chakra UI
- **Data Fetching**: TanStack React Query
- **Routing**: Wouter (hash-based routing)
- **Visualization**: ReactFlow (DAG visualization), Chart.js
- **Build**: pnpm, Next.js static export to `/recce/data/`

## Python Backend Architecture (`/recce`)

### Core Entry Points

- **`cli.py`**: Command-line interface using Click. Entry point: `recce server`, `recce run`, etc.
- **`server.py`**: FastAPI application setup with middleware, static file serving, WebSocket support
- **`core.py`**: `RecceContext` - central context object holding adapter, state loader, runs, and checks

### Main Components

#### 1. **Adapter Layer** (`recce/adapter/`)

Abstract interface for different data tools. Currently implemented:

- **`DbtAdapter`** (`dbt_adapter/__init__.py`): Primary adapter for dbt projects
  - Loads dbt manifests and parses project metadata
  - Compares base vs. current dbt states for lineage diffs
  - Maps RunType to corresponding Task classes for execution
  - Supports node selection, model retrieval, SQL generation
- **`SqlmeshAdapter`**: Experimental adapter (early stage)
- **`BaseAdapter`**: Abstract base class defining interface

#### 2. **Models** (`recce/models/`)

Pydantic data models:

- **`Check`**: Validation rule with name, type, parameters, status
- **`Run`**: Execution result with type, result data, status, error info
- **`RunType`** enum: QUERY, QUERY_DIFF, PROFILE_DIFF, VALUE_DIFF, SCHEMA_DIFF, HISTOGRAM_DIFF, etc.

#### 3. **State Management** (`recce/state/`)

Handles persisting checks, runs, and artifacts across sessions:

- **`RecceState`**: Root state object (checks, runs, artifacts, metadata, PR info)
- **`RecceStateLoader`** (abstract): Base for state loading strategies
  - **`FileStateLoader`**: Local JSON file storage
  - **`CloudStateLoader`**: Recce Cloud S3-backed storage with sync capabilities
- **`RecceShareStateManager`**: Handles sharing state via URLs
- **`RecceCloudStateManager`**: Manages cloud sync, PR integration, team features
- State includes git/PR metadata for tracking change context

#### 4. **Tasks** (`recce/tasks/`)

Execution units that perform actual diffs and comparisons:

- **`Task`** (abstract base): `execute()` method, cancellation, progress reporting
- **`QueryTask`/`QueryDiffTask`**: Run SQL queries (base and current)
- **`ProfileTask`/`ProfileDiffTask`**: Column statistics (min, max, null %, distinct)
- **`RowCountTask`/`RowCountDiffTask`**: Compare row counts
- **`ValueDiffTask`**: Find added/removed/changed rows
- **`TopKDiffTask`**: Compare top-K distinct values
- **`HistogramDiffTask`**: Distribution comparisons
- **`SchemaDiffTask`**: Column/type changes

Each task:

- Takes parameters (model_id, node_id, queries, etc.)
- Connects to dbt-managed data warehouse via adapter
- Returns structured result data
- Supports progress reporting and cancellation

#### 5. **APIs** (`recce/apis/`)

FastAPI routers handling HTTP endpoints:

- **`check_api.py`**: Create, list, update, delete checks; approve/unapprove
- **`run_api.py`**: Submit runs (execute tasks), list runs, get results
- Server endpoints mount these routers at `/api/` prefix

Data flow:

1. Frontend sends check/run request to `/api/checks` or `/api/runs`
2. API handler creates Check/Run objects
3. Task instance is created with params
4. Task executes via adapter (queries warehouse)
5. Result stored in Run object
6. Response sent to frontend

#### 6. **Event System** (`recce/event/`)

Telemetry and tracking:

- **`track.py`**: Custom event tracking (CLI commands, user actions)
- **`collector.py`**: Event collection logic
- Integrates with Sentry and Amplitude for analytics
- Tracks: version updates, CI environment detection, Recce Cloud usage

### Key File Structure Summary

```
recce/
├── cli.py               # Command entry points
├── server.py            # FastAPI app + endpoints
├── core.py              # RecceContext - central state holder
├── run.py               # CLI run logic, preset checks loading
├── config.py            # Configuration file handling
├── adapter/
│   ├── base.py          # BaseAdapter interface
│   └── dbt_adapter/
│       └── __init__.py  # DbtAdapter implementation (2000+ lines)
├── apis/
│   ├── check_api.py     # Check endpoints
│   └── run_api.py       # Run/task submission endpoints
├── models/
│   ├── types.py         # Run, Check, RunType enums
│   ├── check.py         # CheckDAO
│   └── run.py           # RunDAO
├── state/
│   ├── state.py         # RecceState model
│   ├── state_loader.py  # RecceStateLoader abstract class
│   ├── local.py         # FileStateLoader
│   └── cloud.py         # CloudStateLoader, sync logic
├── tasks/
│   ├── core.py          # Task abstract base
│   ├── query.py         # Query execution tasks
│   ├── profile.py       # Column profiling
│   ├── valuediff.py     # Row-level diffs
│   └── ...
├── event/               # Telemetry and analytics
└── data/                # Built static frontend files
```

## JavaScript Frontend Architecture (`/js`)

### Structure

```
js/
├── app/                 # Next.js App Router pages
│   ├── page.tsx         # Main layout with routing logic
│   ├── layout.tsx       # Root layout
│   └── Providers.tsx    # Context providers setup
├── lib/
│   ├── api/             # API client methods (axios instances, cache keys)
│   └── hooks/           # React hooks (RecceContextProvider, LineageGraphContext, etc.)
├── components/
│   ├── check/           # Check creation/management UI
│   ├── run/             # Run execution/results display
│   ├── query/           # Query builder and results
│   ├── lineage/         # Lineage graph visualization
│   └── app/             # Global UI (nav, settings, sharing)
├── public/              # Static assets
└── next.config.js       # Next.js configuration
```

### Build Process

1. **Development**: `pnpm dev` runs Next.js dev server
2. **Production Build**: `pnpm build` → Next.js static export
3. **Output**: Generated files → `/recce/data/` (served by Python backend)
4. **Serving**: FastAPI serves `/recce/data/` as static files via `app.mount("/", StaticFiles(...))`

### Key Integration Points

**API Communication**:

- Frontend uses Axios to call `/api/*` endpoints (Python backend)
- React Query manages server state (caching, invalidation)
- Hash-based routing (Wouter) preserves API state in URL fragments

**Context Providers** (`Providers.tsx`):

- `QueryClientProvider`: React Query setup
- `RecceContextProvider`: Recce-specific state (checks, runs, lineage)
- `Router`: URL-based routing

**Main Entry Point** (`page.tsx`):

- Renders tab-based UI: Lineage, Checks, Query, Run
- Fetches checks on mount, manages run progress
- WebSocket connection for real-time updates

## Data Flow Architecture

### Server Initialization Flow

1. **CLI** (`cli.py`) parses args → calls `server` command
2. **Server setup** (`server.py`):
   - Creates `AppState` (config holder)
   - Initializes `RecceContext` via `load_context()`
   - Loads adapter (DbtAdapter for dbt projects)
   - Loads state (local file or cloud)
   - Starts file monitors for artifact changes
3. **FastAPI app** starts on port 8000 with middleware (CORS, gzip, sessions)

### Check/Run Execution Flow

1. **Frontend** creates check → POST `/api/checks`
2. **Backend** (`check_api.py`):
   - Stores Check in context
   - If run_id provided, retrieves existing Run
   - Otherwise creates new Run placeholder
3. **Frontend** submits run → POST `/api/runs/submit`
4. **Backend** (`run_api.py`):
   - Creates Task instance based on RunType
   - Executes task in background (or WebSocket stream)
   - Task queries warehouse via adapter
   - Result serialized, stored in Run object
   - Run returned to frontend
5. **Frontend** displays results, allows check approval

### State Persistence Flow

**Local Mode** (`FileStateLoader`):

- State persisted to `recce-state.yml` in project root
- On server shutdown, `export_state()` writes current state
- On server start, state loaded from file

**Cloud Mode** (`CloudStateLoader`):

- State synced to Recce Cloud (AWS S3)
- PR metadata fetched from GitHub
- Real-time sync enables multi-environment collaboration
- Share URLs allow preview access without permissions

## Critical Architectural Patterns

### 1. **Adapter Pattern**

- **Why**: Decouple Recce from dbt implementation details
- **Implementation**: `BaseAdapter` interface, `DbtAdapter` implementation
- **Future**: Easy to add Airflow, SQLMesh, Great Expectations adapters

### 2. **Task Registry**

- **Why**: Extensible execution model for new check types
- **Implementation**: `dbt_supported_registry` maps `RunType` → `Task` class
- **Pattern**: Tasks are instantiated per-run, execute independently

### 3. **State as Immutable Snapshots**

- **Why**: Enable time-travel debugging, offline access, sharing
- **Implementation**: `RecceState` serialized to JSON/YAML
- **Pattern**: Loads full state on init, exports on changes

### 4. **Context Singleton**

- **Why**: Global access to adapter, state, runs, checks from any API handler
- **Implementation**: `default_context()` retrieves thread-local context
- **Pattern**: Avoids parameter threading through deep call stacks

### 5. **Frontend-Backend Separation**

- **Why**: Independent deployment, technology choices
- **Implementation**: REST API between React and FastAPI
- **Pattern**: Static frontend built to `/recce/data/`, served by Python

## Key Design Decisions

1. **In-Memory Storage**: Runs/checks kept in-memory, persisted to state file on shutdown

   - Rationale: Speed, simplicity; state file acts as database

2. **JSON State Files**: Human-readable, diffable, version-controllable

   - Rationale: Easy to debug, share, and integrate with git workflows

3. **Next.js Static Export**: Frontend built as static HTML/JS, no Node.js needed at runtime

   - Rationale: Simpler deployment, single Python process

4. **dbt Adapter Coupling**: Recce tightly integrated with dbt SDK

   - Rationale: Access to internals (manifests, artifacts, schema); hard to decouple

5. **Metadata-Driven Checks**: Checks describe "what to compare", not SQL
   - Rationale: Safe, composable, enables AI-assisted check generation

## Entry Points for Future Developers

**Adding a New Check Type**:

1. Add `RunType` to `recce/models/types.py`
2. Create `Task` subclass in `recce/tasks/`
3. Register in `dbt_supported_registry` in `dbt_adapter/__init__.py`
4. Add API handler in `recce/apis/run_api.py`
5. Add UI component in `js/components/check/`

**Extending to New Data Tool**:

1. Create `NewToolAdapter` extending `BaseAdapter`
2. Implement required methods (get_lineage, select_nodes, get_model, etc.)
3. Adapt Task classes to use new adapter
4. Update CLI to support `--newtool` flag

**Modifying Frontend State**:

1. Update types in `js/lib/api/types.ts`
2. Add API call in `js/lib/api/*.ts`
3. Update React context in `js/lib/hooks/RecceContextProvider.tsx`
4. Use in component via `useRecceContext()` hook

---

**Last Updated**: October 2024
**Main Branch**: `main`
**Current Version**: Check `recce/VERSION` file
