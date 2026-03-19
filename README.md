# null_labs_helpers
Helper code for null labs, especially in post processing.

## Metadata Reader

Utilities for reading scene-builder metadata stored as `.zarr` directories.

Example:

```python
from null_labs_helpers.metadata_reader import (
    read_metadata_zarr,
    get_entity_states,
    get_camera_states,
)

data = read_metadata_zarr("/path/to/trajectories.zarr")
entity_states = get_entity_states(data, "ego_vehicle")
camera_states = get_camera_states(data, "front_camera")
```

The `get_entity_states` and `get_camera_states` helpers return dictionaries keyed by timestep,
with `pos` and `euler_rpy` as NumPy arrays of shape `(3,)`.

## Next-State gRPC Helper

This repo includes a managed gRPC runtime for customer next-state plugins.

1) Install package deps (includes grpc):

```bash
pip install -e .
```

2) Generate protocol stubs:

```bash
null-next-state-generate-proto
```

3) Start from the provided template in `examples/next_state_plugin_template.py`, then run the managed gRPC service with your plugin file:

```bash
null-next-state-grpc --plugin-file ./examples/next_state_plugin_template.py --host 0.0.0.0 --port 50051
```

The service exposes gRPC methods:
- `Health`
- `Initialize`
- `NextState`
- `Shutdown`

`NextState` sensor packets include raw image bytes in `image_bytes`.
