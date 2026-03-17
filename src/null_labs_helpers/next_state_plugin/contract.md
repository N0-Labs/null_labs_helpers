# Next-State Plugin Contract (gRPC)

Customers provide a Python plugin file with export:

`create_next_state_plugin(config=None) -> plugin_instance`

Required plugin methods:

1. `initialize(session_id, scenario_id, dt_seconds, metadata)`
2. `get_entity_assignments(session_id, sim_entity_ids, metadata)`
3. `next_state_for_stack(session_id, stack_id, step_index, dt_seconds, cur_state, sensor_packets, assigned_entity_ids)`
4. `shutdown(session_id)`

Optional:

5. `health()`

## Managed gRPC Runtime

The SDK hosts the protocol; customers do not build a server.

1. Generate stubs once:

```bash
null-next-state-generate-proto
```

2. Start the managed gRPC service:

```bash
null-next-state-grpc --plugin-file /path/to/customer_plugin.py --host 0.0.0.0 --port 50051
```

## gRPC Methods

- `Health`
- `Initialize`
- `NextState`
- `Shutdown`

Protocol schema:
- `next_state.proto`

## Sensor Images

`NextStateRequest.sensor_packets` carries raw image bytes in:
- `sensor_packets[i].image_bytes`

So yes, with gRPC enabled, images are sent over gRPC as bytes (not base64 JSON).

## Entity Ownership

`get_entity_assignments(...)` must assign every sim entity exactly once.

Example:

```json
{
  "planner_stack": ["vessel_1", "vessel_2"],
  "traffic_stack": ["boat_7"]
}
```

At runtime, the SDK calls `next_state_for_stack(...)` once per stack each step and merges responses.
