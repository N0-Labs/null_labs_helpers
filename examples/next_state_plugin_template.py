"""
Customer plugin template for managed next-state gRPC runtime.

Run managed gRPC service:
1) Generate stubs once:
   null-next-state-generate-proto
2) Start service:
   null-next-state-grpc --plugin-file /path/to/this_file.py --host 0.0.0.0 --port 50051

Required export:
  create_next_state_plugin(config=None) -> plugin_instance

Required plugin methods:
  initialize(session_id, scenario_id, dt_seconds, metadata) -> dict | None
  get_entity_assignments(session_id, sim_entity_ids, metadata) -> dict[str, list[str]]
  next_state_for_stack(session_id, stack_id, step_index, dt_seconds, cur_state, sensor_packets, assigned_entity_ids) -> dict
  shutdown(session_id) -> dict | None
"""


class NextStatePlugin:
    def __init__(self, config=None):
        self.config = config or {}
        self.sessions = {}

    def initialize(self, session_id, scenario_id, dt_seconds, metadata):
        self.sessions[session_id] = {
            "scenario_id": scenario_id,
            "dt_seconds": float(dt_seconds),
            "metadata": metadata or {},
        }
        return {"status": "ok", "session_id": session_id}

    def get_entity_assignments(self, session_id, sim_entity_ids, metadata):
        return {"default_stack": list(sim_entity_ids)}

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
        if session_id not in self.sessions:
            raise ValueError(f"unknown session_id: {session_id}")

        # sensor_packets include raw image bytes under packet["image_bytes"]
        stack_state = {entity_id: cur_state[entity_id] for entity_id in assigned_entity_ids if entity_id in cur_state}
        return {
            "status": "ok",
            "next_state": stack_state,
            "diagnostics": {
                "stack_id": stack_id,
                "step_index": int(step_index),
                "sensor_packet_count": len(sensor_packets or []),
            },
        }

    def shutdown(self, session_id):
        self.sessions.pop(session_id, None)
        return {"status": "ok", "session_id": session_id}

    def health(self):
        return {
            "status": "ok",
            "provider_version": "customer-template-0.3",
            "capabilities": ["multi_entity_batch", "stack_assignment", "grpc"],
        }


def create_next_state_plugin(config=None):
    return NextStatePlugin(config=config)
