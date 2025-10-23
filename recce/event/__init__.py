import hashlib
import logging
import os
import re
import sys
import threading
import uuid
from datetime import datetime, timezone
from hashlib import sha256
from typing import Dict

import sentry_sdk

logger = logging.getLogger(__name__)

from recce import get_runner, get_version, is_ci_env, is_recce_cloud_instance
from recce import yaml as pyml
from recce.event.collector import Collector
from recce.git import current_branch, hosting_repo
from recce.github import (
    get_github_codespace_available_at,
    get_github_codespace_info,
    get_github_codespace_name,
    is_github_codespace,
)

USER_HOME = os.path.expanduser("~")
RECCE_USER_HOME = os.path.join(USER_HOME, ".recce")
RECCE_USER_PROFILE = os.path.join(RECCE_USER_HOME, "profile.yml")
RECCE_USER_EVENT_PATH = os.path.join(RECCE_USER_HOME, ".unsend_events.json")

__version__ = get_version()
_collector = Collector()
user_profile_lock = threading.Lock()


def init():
    api_key = _get_api_key()
    user_profile = load_user_profile()

    # Amplitude init
    _collector.set_api_key(api_key)
    _collector.set_user_id(user_profile.get("user_id"))
    _collector.set_unsend_events_file(RECCE_USER_EVENT_PATH)

    # Sentry init
    sentry_env = _get_sentry_env()
    sentry_dns = _get_sentry_dns()
    release_version = __version__ if sentry_env != "development" else None
    sentry_sdk.init(
        dsn=sentry_dns,
        environment=sentry_env,
        release=release_version,
        # Set traces_sample_rate to 1.0 to capture 100%
        # of transactions for performance monitoring.
        # We recommend adjusting this value in production.
        traces_sample_rate=1.0,
    )
    sentry_sdk.set_tag("recce.version", __version__)
    sentry_sdk.set_tag("platform", sys.platform)
    sentry_sdk.set_tag("is_ci_env", is_ci_env())
    sentry_sdk.set_tag("is_github_codespace", is_github_codespace())
    sentry_sdk.set_tag("is_recce_cloud_instance", is_recce_cloud_instance())
    sentry_sdk.set_tag("system_timezone", get_system_timezone())


def get_user_id():
    return load_user_profile().get("user_id")


def get_recce_api_token():
    return load_user_profile().get("api_token")


def update_recce_api_token(token):
    return update_user_profile({"api_token": token})


def is_anonymous_tracking():
    return load_user_profile().get("anonymous_tracking", False)


def _get_sentry_dns():
    dns_file = os.path.normpath(os.path.join(os.path.dirname(__file__), "SENTRY_DNS"))
    with open(dns_file, encoding="utf-8") as f:
        dns = f.read().strip()
        return dns


def _get_sentry_env():
    if ".dev" in __version__:
        return "development"
    elif re.match(r"^\d+\.\d+\.\d+\.\d{8}[a|b|rc]?.*$", __version__):
        return "nightly"
    elif "a" in __version__:
        return "alpha"
    elif "b" in __version__:
        return "beta"
    elif "rc" in __version__:
        return "release-candidate"
    return "production"


def _get_api_key():
    if os.getenv("RECCE_EVENT_API_KEY"):
        # For local testing purpose
        return os.getenv("RECCE_EVENT_API_KEY")

    config_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "CONFIG"))
    try:
        with open(config_file, encoding="utf-8") as fh:
            config = pyml.load(fh)
            return config.get("event_api_key")
    except Exception:
        return None


def _generate_user_profile():
    try:
        os.makedirs(RECCE_USER_HOME, exist_ok=True)
    except Exception:
        # TODO: should show warning message but not raise exception
        print("Please disable command tracking to continue.")
        exit(1)
    if is_github_codespace() is True:
        salted_name = f"codespace-{get_github_codespace_name()}"
        user_id = hashlib.sha256(salted_name.encode()).hexdigest()
    else:
        user_id = uuid.uuid4().hex
    with open(RECCE_USER_PROFILE, "w+", encoding="utf-8") as f:
        pyml.dump({"user_id": user_id, "anonymous_tracking": True}, f)
    return dict(user_id=user_id, anonymous_tracking=True)


def load_user_profile():
    with user_profile_lock:
        if not os.path.exists(RECCE_USER_PROFILE):
            user_profile = _generate_user_profile()
        else:
            with open(RECCE_USER_PROFILE, "r", encoding="utf-8") as f:
                user_profile = pyml.load(f)
                if user_profile is None or user_profile.get("user_id") is None:
                    user_profile = _generate_user_profile()

        return user_profile


def update_user_profile(update_values):
    original = load_user_profile()
    original.update(update_values)
    with open(RECCE_USER_PROFILE, "w+", encoding="utf-8") as f:
        pyml.dump(original, f)
    return original


def flush_events(command=None):
    _collector.send_events()


def should_log_event():
    with open(RECCE_USER_PROFILE, "r", encoding="utf-8") as f:
        user_profile = pyml.load(f)
    # TODO: default anonymous_tracking to false if field is not present
    tracking = user_profile.get("anonymous_tracking", False)
    tracking = tracking and isinstance(tracking, bool)
    if not tracking:
        return False

    if not _collector.is_ready():
        return False

    return True


def log_event(prop, event_type, **kwargs):
    if should_log_event() is False:
        return

    # Debug logging for development/testing
    if os.getenv("RECCE_DEBUG_EVENTS"):
        print(f"[RECCE_DEBUG] Logging event: {event_type} {prop}")

    repo = hosting_repo()
    if repo is not None:
        prop["repository"] = sha256(repo.encode()).hexdigest()

    branch = current_branch()
    if branch is not None:
        prop["branch"] = sha256(branch.encode()).hexdigest()

    runner = get_runner()
    if runner is not None:
        prop["runner_type"] = runner

        if runner == "github codespaces":
            prop["codespaces_name"] = get_github_codespace_name()

    payload = dict(
        **prop,
    )

    _collector.log_event(payload, event_type)


def log_api_event(endpoint_name, prop):
    prop = dict(
        **prop,
        endpoint_name=endpoint_name,
    )
    log_event(prop, "api_event")
    _collector.schedule_flush()


def log_load_state(command="server", single_env=False):
    from recce.models import CheckDAO

    checks = 0
    preset_checks = 0

    for check in CheckDAO().list():
        checks += 1
        if check.is_preset:
            preset_checks += 1

    prop = dict(
        command=command,
        checks=checks,
        preset_checks=preset_checks,
    )

    if command == "server":
        prop["single_env"] = single_env

    log_event(prop, "[User] load_state")
    if command == "server":
        _collector.schedule_flush()


def log_codespaces_events(command):
    # Only log when the recce is running in GitHub Codespaces
    codespace = get_github_codespace_info()
    if codespace is None:
        return

    user_prop = dict(
        location=codespace.get("location"),
        is_prebuild=codespace.get("prebuild", False),
    )

    prop = dict(
        machine=codespace.get("machine", {}).get("display_name"),
        codespaces_name=get_github_codespace_name(),
    )

    # Codespace created event, send once
    codespace_created_at = load_user_profile().get("codespace_created_at")
    if codespace_created_at is None:
        created_at = datetime.fromisoformat(codespace.get("created_at"))
        prop["state"] = "created"
        _collector.log_event(prop, "codespace_instance", event_triggered_at=created_at, user_properties=user_prop)
        update_user_profile({"codespace_created_at": codespace.get("created_at")})

    # Codespace available event, send multiple times as start/stop it
    available_at = get_github_codespace_available_at(codespace)
    if available_at and available_at.isoformat() != load_user_profile().get("codespace_available_at"):
        prop["state"] = "available"
        _collector.log_event(prop, "codespace_instance", event_triggered_at=available_at, user_properties=user_prop)
        update_user_profile({"codespace_available_at": available_at.isoformat()})

    # Codespace instance event should be flushed immediately
    _collector.send_events()


def log_single_env_event():
    prop = dict(
        action="launch_server",
    )
    log_event(prop, "[Experiment] single_environment")
    _collector.schedule_flush()


def log_performance(feature_name: str, metrics: Dict):
    prop = metrics
    log_event(prop, f"[Performance] {feature_name}")
    _collector.schedule_flush()


def log_connected_to_cloud():
    log_event({"action": "connected_to_cloud"}, "Connect OSS to Cloud")
    _collector.schedule_flush()


def capture_exception(e):
    user_id = load_user_profile().get("user_id")
    if is_ci_env() is True:
        user_id = f"{user_id}_CI"

    sentry_sdk.set_tag("user_id", user_id)
    sentry_sdk.capture_exception(e)


def flush_exceptions():
    sentry_sdk.flush()


def set_exception_tag(key, value):
    sentry_sdk.set_tag(key, value)


def get_system_timezone():
    return datetime.now(timezone.utc).astimezone().tzinfo


def log_environment_snapshot():
    """Log environment configuration at server startup"""
    from recce.core import default_context

    try:
        context = default_context()
    except Exception as e:
        logger.debug(f"Context not ready for environment snapshot: {e}")
        return

    prop = {}

    # Cloud and file mode
    prop["has_cloud"] = context.state_loader.cloud_mode if context.state_loader else False
    prop["cloud_mode"] = "cloud" if prop["has_cloud"] else "local"

    # PR information - collapsed into pr_info object
    state = context.export_state() if context else None
    pr_info = {}
    if state and state.pull_request:
        prop["has_pr"] = True
        pr = state.pull_request
        # Hash PR number for privacy
        if pr.id:
            pr_info["number"] = sha256(str(pr.id).encode()).hexdigest()
        pr_info["state"] = getattr(pr, "state", None)

        # Calculate PR age if created_at available
        if hasattr(pr, "created_at") and pr.created_at:
            try:
                from dateutil import parser

                pr_created = parser.parse(pr.created_at)
                now = datetime.now(timezone.utc)
                pr_info["age_hours"] = (now - pr_created).total_seconds() / 3600
            except (ValueError, TypeError) as e:
                logger.debug(f"Could not parse PR created_at date: {e}")
                pr_info["age_hours"] = None
        else:
            pr_info["age_hours"] = None
    else:
        prop["has_pr"] = False
        pr_info = None

    if pr_info:
        prop["pr_info"] = pr_info

    # Adapter information
    prop["adapter_type"] = context.adapter_type

    # Database/warehouse type
    if context.adapter_type == "dbt":
        try:
            from recce.adapter.dbt_adapter import DbtAdapter

            dbt_adapter: DbtAdapter = context.adapter
            prop["warehouse_type"] = dbt_adapter.adapter.type()
            prop["has_database"] = True  # If adapter initialized, assume DB configured
        except AttributeError as e:
            logger.debug(f"Could not determine warehouse type: {e}")
            prop["warehouse_type"] = None
            prop["has_database"] = False
    else:
        prop["warehouse_type"] = None
        prop["has_database"] = False

    # Catalog ages (collapsed from manifest and catalog - they're created together in dbt)
    if context.adapter_type == "dbt":
        try:
            from recce.adapter.dbt_adapter import DbtAdapter

            dbt_adapter: DbtAdapter = context.adapter

            # Base environment
            if dbt_adapter.base_manifest:
                prop["has_base_env"] = True
                if (
                    dbt_adapter.base_catalog
                    and dbt_adapter.base_catalog.metadata
                    and dbt_adapter.base_catalog.metadata.generated_at
                ):
                    gen_at = dbt_adapter.base_catalog.metadata.generated_at
                    now = datetime.now(timezone.utc)
                    prop["catalog_age_hours_base"] = (now - gen_at).total_seconds() / 3600
                else:
                    prop["catalog_age_hours_base"] = None
            else:
                prop["has_base_env"] = False
                prop["catalog_age_hours_base"] = None

            # Current environment
            if dbt_adapter.curr_manifest:
                prop["has_current_env"] = True
                if (
                    dbt_adapter.curr_catalog
                    and dbt_adapter.curr_catalog.metadata
                    and dbt_adapter.curr_catalog.metadata.generated_at
                ):
                    gen_at = dbt_adapter.curr_catalog.metadata.generated_at
                    now = datetime.now(timezone.utc)
                    prop["catalog_age_hours_current"] = (now - gen_at).total_seconds() / 3600
                else:
                    prop["catalog_age_hours_current"] = None
            else:
                prop["has_current_env"] = False
                prop["catalog_age_hours_current"] = None
        except AttributeError as e:
            logger.debug(f"Could not get catalog metadata: {e}")
            prop["has_base_env"] = False
            prop["has_current_env"] = False
            prop["catalog_age_hours_base"] = None
            prop["catalog_age_hours_current"] = None
    else:
        prop["has_base_env"] = False
        prop["has_current_env"] = False
        prop["catalog_age_hours_base"] = None
        prop["catalog_age_hours_current"] = None

    log_event(prop, "[User] environment_snapshot")
    _collector.schedule_flush()




def log_viewed_checks():
    """Log when user views the checks panel"""
    log_event({}, "[User] viewed_checks")


def log_viewed_query():
    """Log when user views the query builder"""
    log_event({}, "[User] viewed_query")


def log_ran_check(check_id: str = None, check_type: str = None, check_position: int = None):
    """Log when user executes a check"""
    prop = {}
    if check_id is not None:
        prop["check_id"] = check_id
    if check_type is not None:
        prop["check_type"] = check_type
    if check_position is not None:
        prop["check_position"] = check_position
    log_event(prop, "[User] ran_check")


def log_approved_check(check_id: str = None, check_type: str = None, check_position: int = None):
    """Log when user approves a check result"""
    prop = {}
    if check_id is not None:
        prop["check_id"] = check_id
    if check_type is not None:
        prop["check_type"] = check_type
    if check_position is not None:
        prop["check_position"] = check_position
    log_event(prop, "[User] approved_check")


def log_created_check(check_id: str = None, check_type: str = None, check_position: int = None):
    """Log when user creates a check"""
    prop = {}
    if check_id is not None:
        prop["check_id"] = check_id
    if check_type is not None:
        prop["check_type"] = check_type
    if check_position is not None:
        prop["check_position"] = check_position
    log_event(prop, "[User] created_check")


def log_run_completed(run_id: str, run_type: str, status: str, duration_seconds: float, error: str = None, result=None, check_id: str = None, check_position: int = None):
    """Log run completion with outcome"""
    prop = {
        "run_id": sha256(str(run_id).encode()).hexdigest(),
        "run_type": run_type,
        "status": status,  # 'success', 'error', 'cancelled'
        "duration_seconds": duration_seconds,
    }

    # Add check lifecycle information if available
    if check_id is not None:
        prop["check_id"] = check_id
    if check_position is not None:
        prop["check_position"] = check_position

    # Add error information
    if error:
        # Categorize error type
        error_lower = error.lower()
        if "connection" in error_lower or "connect" in error_lower:
            prop["error_type"] = "connection"
        elif "timeout" in error_lower:
            prop["error_type"] = "timeout"
        elif "query" in error_lower or "sql" in error_lower:
            prop["error_type"] = "query_error"
        elif "validation" in error_lower:
            prop["error_type"] = "validation_error"
        else:
            prop["error_type"] = "other"

        # Truncate error message (no sensitive data)
        prop["error_message"] = str(error)[:200]
    else:
        prop["error_type"] = None
        prop["error_message"] = None

    # Add result size/differences if available
    if result and isinstance(result, dict):
        if "data" in result and isinstance(result["data"], list):
            prop["result_size"] = len(result["data"])

        # Check for differences in diff operations
        if "diff" in result:
            prop["has_differences"] = bool(result["diff"])
        elif "data" in result and isinstance(result["data"], dict):
            # For some diff types, data itself might indicate differences
            prop["has_differences"] = len(result["data"]) > 0
    else:
        prop["result_size"] = None
        prop["has_differences"] = None

    log_event(prop, "[User] run_completed")
    _collector.schedule_flush()


def log_model_lineage_changes(total_nodes: int, model_nodes: int, source_nodes: int, change_status: Dict):
    """Log model lineage changes detected"""
    prop = {
        "total_nodes": total_nodes,
        "model_nodes": model_nodes,
        "source_nodes": source_nodes,
        "change_status": change_status,
    }
    log_event(prop, "[User] model_lineage")
    _collector.schedule_flush()
