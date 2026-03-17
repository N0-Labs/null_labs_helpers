import argparse
import json
from concurrent import futures
from pathlib import Path

import grpc

from null_labs_helpers.next_state_plugin.sdk import PluginRuntime, load_plugin_from_file

try:
    from null_labs_helpers.next_state_plugin import next_state_pb2, next_state_pb2_grpc
except Exception as e:  # pragma: no cover
    raise RuntimeError(
        "gRPC stubs are missing. Run: python -m null_labs_helpers.next_state_plugin.generate_proto"
    ) from e


class NextStateGrpcService(next_state_pb2_grpc.NextStateServiceServicer):
    def __init__(self, runtime: PluginRuntime):
        self.runtime = runtime

    @staticmethod
    def _entity_state_to_dict(entity_state):
        return {
            "position_m": list(entity_state.position_m),
            "euler_rpy_rad": list(entity_state.euler_rpy_rad),
        }

    @staticmethod
    def _dict_to_entity_state(state):
        return next_state_pb2.EntityState(
            position_m=[float(x) for x in state.get("position_m", [])],
            euler_rpy_rad=[float(x) for x in state.get("euler_rpy_rad", [])],
        )

    def Health(self, request, context):
        out = self.runtime.health()
        return next_state_pb2.HealthResponse(
            status=str(out.get("status", "ok")),
            provider_version=str(out.get("provider_version", "unknown")),
            capabilities=[str(x) for x in (out.get("capabilities", []) or [])],
        )

    def Initialize(self, request, context):
        payload = {
            "session_id": request.session_id,
            "scenario_id": request.scenario_id,
            "dt_seconds": request.dt_seconds,
            "sim_entity_ids": list(request.sim_entity_ids),
            "metadata": dict(request.metadata),
        }
        try:
            out = self.runtime.initialize(payload)
            resp = next_state_pb2.InitializeResponse(status=str(out.get("status", "ok")))
            assignments = out.get("stack_assignments", {}) or {}
            for stack_id, entity_ids in assignments.items():
                resp.stack_assignments[stack_id].values.extend([str(x) for x in entity_ids])
            for k, v in (out.get("metadata", {}) or {}).items():
                resp.metadata[str(k)] = str(v)
            return resp
        except Exception as e:
            return next_state_pb2.InitializeResponse(status="error", error=str(e))

    def NextState(self, request, context):
        cur_state = {
            entity_id: self._entity_state_to_dict(state)
            for entity_id, state in request.cur_state.items()
        }
        sensor_packets = []
        for pkt in request.sensor_packets:
            sensor_packets.append(
                {
                    "sensor_id": pkt.sensor_id,
                    "capture_label": pkt.capture_label,
                    "scene_id": pkt.scene_id,
                    "modality": pkt.modality,
                    "format": pkt.format,
                    "image_bytes": bytes(pkt.image_bytes),
                    "path_hint": pkt.path_hint,
                }
            )

        payload = {
            "session_id": request.session_id,
            "step_index": int(request.step_index),
            "dt_seconds": float(request.dt_seconds),
            "cur_state": cur_state,
            "sensor_packets": sensor_packets,
        }

        try:
            out = self.runtime.next_state(payload)
            resp = next_state_pb2.NextStateResponse(status=str(out.get("status", "ok")))
            for entity_id, state in (out.get("next_state", {}) or {}).items():
                resp.next_state[entity_id].CopyFrom(self._dict_to_entity_state(state))
            return resp
        except Exception as e:
            return next_state_pb2.NextStateResponse(status="error", error=str(e))

    def Shutdown(self, request, context):
        try:
            out = self.runtime.shutdown({"session_id": request.session_id})
            return next_state_pb2.ShutdownResponse(status=str(out.get("status", "ok")))
        except Exception as e:
            return next_state_pb2.ShutdownResponse(status="error", error=str(e))


def run_grpc_server(plugin_file, host="0.0.0.0", port=50051, factory_name="create_next_state_plugin", config=None, max_workers=8):
    plugin = load_plugin_from_file(plugin_file, factory_name=factory_name, config=config)
    runtime = PluginRuntime(plugin)
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=int(max_workers)))
    next_state_pb2_grpc.add_NextStateServiceServicer_to_server(NextStateGrpcService(runtime), server)
    bind_addr = f"{host}:{int(port)}"
    server.add_insecure_port(bind_addr)
    server.start()
    print(f"[next-state-sdk] gRPC serving on {bind_addr}", flush=True)
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        server.stop(grace=3)


def main():
    parser = argparse.ArgumentParser(description="Run next-state plugin as managed gRPC service")
    parser.add_argument("--plugin-file", required=True)
    parser.add_argument("--factory-name", default="create_next_state_plugin")
    parser.add_argument("--config-json", default=None)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=50051)
    parser.add_argument("--max-workers", type=int, default=8)
    args = parser.parse_args()

    config = {}
    if args.config_json:
        with open(args.config_json, "r", encoding="utf-8") as f:
            config = json.load(f)

    run_grpc_server(
        plugin_file=args.plugin_file,
        host=args.host,
        port=args.port,
        factory_name=args.factory_name,
        config=config,
        max_workers=args.max_workers,
    )


if __name__ == "__main__":
    main()
