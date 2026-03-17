"""
Customer plugin template for managed next-state gRPC runtime. This example demonstrates a simple plugin that assigns 
all entities to a single stack and returns the current state as the next state for each step. The plugin also includes a health method that reports its capabilities.

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
from pathlib import Path

from null_labs_helpers.metadata_reader import read_metadata_zarr

class NextStatePlugin:
    def __init__(self, config=None):
        self.config = config or {}
        self.sessions = {}

        self.trajectories_data = read_metadata_zarr("C:\\Users\\user\\Documents\\n0_data_saves\\dbae0dc4-6c36-481e-a3fb-8edaeb1c8475\\trajectories.zarr")
        self.entities = self.trajectories_data["entities"]
        self.cameras = self.trajectories_data["cameras"]

    @staticmethod
    def _safe_name(value):
        return "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "_" for ch in str(value or "unknown"))

    @staticmethod
    def _ext_from_format(fmt):
        lowered = str(fmt or "").lower()
        if "png" in lowered:
            return ".png"
        if "jpeg" in lowered or "jpg" in lowered:
            return ".jpg"
        return ".bin"

    def _save_sensor_packets(self, session_id, stack_id, step_index, sensor_packets):
        out_dir = Path("C://Users//user//Documents//null_test_sitl//sensor_debug")
        base = out_dir / self._safe_name(session_id) / self._safe_name(stack_id) / f"step_{int(step_index):06d}"
        base.mkdir(parents=True, exist_ok=True)

        saved = 0

        for idx, pkt in enumerate(sensor_packets or []):
            sensor_id = self._safe_name(pkt.get("sensor_id", f"sensor_{idx}"))
            capture = self._safe_name(pkt.get("capture_label", "capture"))
            ext = self._ext_from_format(pkt.get("format", ""))
            raw_path = base / f"{idx:03d}_{sensor_id}_{capture}{ext}"

            image_bytes = pkt.get("image_bytes", b"") or b""
            if not isinstance(image_bytes, (bytes, bytearray)):
                image_bytes = bytes(image_bytes)

            raw_path.write_bytes(image_bytes)
            saved += 1

        return {
            "sensor_packets_saved": saved,
            "sensor_packets_dir": str(base.resolve()),
        }

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

        sensor_debug = self._save_sensor_packets(
            session_id=session_id,
            stack_id=stack_id,
            step_index=step_index,
            sensor_packets=sensor_packets,
        )

        stack_state["camera_1"]["position_m"] = self.cameras["camera_1"]["pos"][step_index].tolist()
        stack_state["camera_1"]["euler_rpy_rad"] = self.cameras["camera_1"]["euler_rpy"][step_index].tolist()

        stack_state["smalldrone_1"]["position_m"] = self.entities["smalldrone_1"]["pos"][step_index].tolist()
        stack_state["smalldrone_1"]["euler_rpy_rad"] = self.entities["smalldrone_1"]["euler_rpy"][step_index].tolist()

        return {
            "status": "ok",
            "next_state": stack_state,
            "diagnostics": {
                "stack_id": stack_id,
                "step_index": int(step_index),
                "sensor_packet_count": len(sensor_packets or []),
                **sensor_debug,
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
