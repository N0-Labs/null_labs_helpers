import importlib.util
import os
from abc import ABC, abstractmethod


class BaseNextStatePlugin(ABC):
    """
    Customer plugins must implement this interface.

    Required methods:
    - initialize(session_id, scenario_id, dt_seconds, metadata) -> dict | None
    - get_entity_assignments(session_id, sim_entity_ids, metadata) -> dict[str, list[str]]
    - next_state_for_stack(session_id, stack_id, step_index, dt_seconds, cur_state, sensor_packets, assigned_entity_ids) -> dict
    - shutdown(session_id) -> dict | None

    Optional method:
    - health() -> dict
    """

    @abstractmethod
    def initialize(self, session_id, scenario_id, dt_seconds, metadata):
        raise NotImplementedError

    @abstractmethod
    def get_entity_assignments(self, session_id, sim_entity_ids, metadata):
        raise NotImplementedError

    @abstractmethod
    def next_state_for_stack(
        self,
        session_id,
        stack_id,
        step_index,
        dt_seconds,
        cur_state,
        sensor_packets,
        assigned_entity_ids,
    ):
        raise NotImplementedError

    @abstractmethod
    def shutdown(self, session_id):
        raise NotImplementedError

    def health(self):
        return {"status": "ok", "provider_version": "plugin-unknown"}


def validate_plugin_next_state_result(result):
    if not isinstance(result, dict):
        raise ValueError("plugin next_state_for_stack() must return a dict")
    status = result.get("status", "ok")
    if status != "ok":
        err = result.get("error", "plugin returned non-ok status")
        raise RuntimeError(str(err))
    next_state = result.get("next_state")
    if not isinstance(next_state, dict):
        raise ValueError("plugin next_state_for_stack() result must include dict field 'next_state'")
    for entity_id, state in next_state.items():
        if not isinstance(state, dict):
            raise ValueError(f"next_state[{entity_id}] must be a dict")
        pos = state.get("position_m")
        rpy = state.get("euler_rpy_rad")
        if not (isinstance(pos, list) and len(pos) == 3):
            raise ValueError(f"next_state[{entity_id}].position_m must be a 3-element list")
        if not (isinstance(rpy, list) and len(rpy) == 3):
            raise ValueError(f"next_state[{entity_id}].euler_rpy_rad must be a 3-element list")
    return {
        "status": "ok",
        "next_state": next_state,
        "diagnostics": result.get("diagnostics", {}),
    }


def validate_entity_assignments(assignments, sim_entity_ids):
    if not isinstance(assignments, dict) or not assignments:
        raise ValueError("get_entity_assignments() must return a non-empty dict")

    expected = set(sim_entity_ids)
    seen = set()
    normalized = {}
    for stack_id, entity_ids in assignments.items():
        if not isinstance(stack_id, str) or not stack_id.strip():
            raise ValueError("stack ids in assignments must be non-empty strings")
        if not isinstance(entity_ids, list):
            raise ValueError(f"assignments[{stack_id}] must be a list of entity ids")
        stack_entities = []
        for entity_id in entity_ids:
            if entity_id not in expected:
                raise ValueError(f"assignments[{stack_id}] contains unknown entity id: {entity_id}")
            if entity_id in seen:
                raise ValueError(f"entity id assigned to multiple stacks: {entity_id}")
            seen.add(entity_id)
            stack_entities.append(entity_id)
        if not stack_entities:
            raise ValueError(f"assignments[{stack_id}] must not be empty")
        normalized[stack_id] = stack_entities

    missing = expected - seen
    if missing:
        missing_sorted = ", ".join(sorted(missing))
        raise ValueError(f"Unassigned sim entities: {missing_sorted}")

    return normalized


class PluginRuntime:
    """Runtime adapter shared by HTTP/gRPC transports."""

    def __init__(self, plugin):
        self.plugin = plugin
        self._assignments_by_session = {}

    def health(self):
        fn = getattr(self.plugin, "health", None)
        if callable(fn):
            out = fn()
            return out if isinstance(out, dict) else {"status": "ok"}
        return {"status": "ok", "provider_version": "plugin-runtime"}

    def initialize(self, payload):
        session_id = payload.get("session_id")
        scenario_id = payload.get("scenario_id")
        dt_seconds = payload.get("dt_seconds")
        metadata = payload.get("metadata", {}) or {}
        sim_entity_ids = payload.get("sim_entity_ids", []) or []

        result = self.plugin.initialize(
            session_id=session_id,
            scenario_id=scenario_id,
            dt_seconds=dt_seconds,
            metadata=metadata,
        )
        assignments = self.plugin.get_entity_assignments(
            session_id=session_id,
            sim_entity_ids=sim_entity_ids,
            metadata=metadata,
        )
        normalized = validate_entity_assignments(assignments, sim_entity_ids)
        self._assignments_by_session[session_id] = normalized

        out = {"status": "ok", "stack_assignments": normalized}
        if isinstance(result, dict):
            out.update(result)
            out["status"] = out.get("status", "ok")
            out["stack_assignments"] = normalized
        return out

    def next_state(self, payload):
        session_id = payload.get("session_id")
        stack_assignments = self._assignments_by_session.get(session_id)
        if not stack_assignments:
            raise ValueError(f"session not initialized: {session_id}")

        step_index = payload.get("step_index")
        dt_seconds = payload.get("dt_seconds")
        cur_state = payload.get("cur_state", {}) or {}
        sensor_packets = payload.get("sensor_packets", []) or []

        merged_next_state = {}
        stack_diagnostics = {}
        for stack_id, assigned_entity_ids in stack_assignments.items():
            stack_cur_state = {
                entity_id: cur_state[entity_id]
                for entity_id in assigned_entity_ids
                if entity_id in cur_state
            }
            result = self.plugin.next_state_for_stack(
                session_id=session_id,
                stack_id=stack_id,
                step_index=step_index,
                dt_seconds=dt_seconds,
                cur_state=stack_cur_state,
                sensor_packets=sensor_packets,
                assigned_entity_ids=list(assigned_entity_ids),
            )
            validated = validate_plugin_next_state_result(result)
            stack_next = validated["next_state"]
            for entity_id in stack_next.keys():
                if entity_id not in assigned_entity_ids:
                    raise ValueError(
                        f"Stack '{stack_id}' returned unassigned entity '{entity_id}'"
                    )
            for entity_id in assigned_entity_ids:
                merged_next_state[entity_id] = stack_next.get(entity_id, cur_state.get(entity_id))
            stack_diagnostics[stack_id] = validated.get("diagnostics", {})

        return {
            "status": "ok",
            "next_state": merged_next_state,
            "diagnostics": {"stacks": stack_diagnostics},
        }

    def shutdown(self, payload):
        session_id = payload.get("session_id")
        result = self.plugin.shutdown(session_id=session_id)
        self._assignments_by_session.pop(session_id, None)
        if result is None:
            return {"status": "ok"}
        if not isinstance(result, dict):
            raise ValueError("plugin shutdown() must return dict or None")
        return result


def load_plugin_from_file(plugin_file, factory_name="create_next_state_plugin", config=None):
    plugin_file = os.path.abspath(plugin_file)
    spec = importlib.util.spec_from_file_location("customer_next_state_plugin_runtime", plugin_file)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load plugin module from: {plugin_file}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    factory = getattr(module, factory_name, None)
    if not callable(factory):
        raise RuntimeError(f"Plugin must define callable: {factory_name}(config=None)")
    plugin = factory(config or {})
    for method_name in ("initialize", "get_entity_assignments", "next_state_for_stack", "shutdown"):
        if not callable(getattr(plugin, method_name, None)):
            raise RuntimeError(f"Plugin instance missing required method: {method_name}")
    return plugin
