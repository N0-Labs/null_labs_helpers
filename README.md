# null_labs_helpers
Helper code for null labs, especially in post processing.

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
