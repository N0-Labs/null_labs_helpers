import zarr
from zarr.storage import LocalStore

def read_group_to_dict(g):
    out = {}
    # arrays
    for name in g.array_keys():
        out[name] = g[name][...]
    # subgroups
    for name in g.group_keys():
        out[name] = read_group_to_dict(g[name])
    # attributes
    for k, v in g.attrs.items():
        out[k] = v
    return out

def read_trajectory_metadata_zarr(trajectories_path):
    store = LocalStore(trajectories_path)
    zarr_data = zarr.open_group(store=store, mode='r')
    trajectories_data = read_group_to_dict(zarr_data)

    return trajectories_data