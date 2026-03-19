# For reading .zarr files from scene builder

import zarr
from zarr.storage import LocalStore
import numpy as np

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

def read_metadata_zarr(data_path: str):
    store = LocalStore(data_path)
    zarr_data = zarr.open_group(store=store, mode='r')
    metadata_data = read_group_to_dict(zarr_data)

    return metadata_data

def get_state_helper(data: dict, attribute_type: str, attribute_name: str):
    """
    Returns a dictionary where the keys are the timesteps and the values are dictionaries
    containing the position and euler_rpy of the entity at that timestep. 
    Returns:
    {
        timestep1: { # timestep is np.int64
            "pos": [x, y, z], # np.ndarray of shape (3,)
            "euler_rpy": [roll, pitch, yaw] # np.ndarray of shape (3,)
        },
        timestep2: {
            "pos": [x, y, z],
            "euler_rpy": [roll, pitch, yaw]
        },
        ...
    }
    """

    attribute = data[attribute_type][attribute_name]

    positions = attribute["pos"]
    euler_rpy = attribute["euler_rpy"]

    timesteps = attribute['pulse_idx']
    state_dict = {}
    for t in timesteps:
        state_dict[t] = {
            "pos": positions[t],
            "euler_rpy": euler_rpy[t]
        }

    return state_dict

def get_entity_states(data: dict, entity_name: str):
    """
    Returns a dictionary where the keys are the timesteps and the values are dictionaries
    containing the position and euler_rpy of the entity at that timestep. 
    Returns:
    {
        timestep1: { # timestep is np.int64
            "pos": [x, y, z], # np.ndarray of shape (3,)
            "euler_rpy": [roll, pitch, yaw] # np.ndarray of shape (3,)
        },
        timestep2: {
            "pos": [x, y, z],
            "euler_rpy": [roll, pitch, yaw]
        },
        ...
    }
    """

    state_dict = get_state_helper(data, "entities", entity_name)

    return state_dict

def get_camera_states(data: dict, camera_name: str):
    """
    Returns a dictionary where the keys are the timesteps and the values are dictionaries
    containing the position and euler_rpy of the camera at that timestep. 
    Returns:
    {
        timestep1: { # timestep is np.int64
            "pos": [x, y, z], # np.ndarray of shape (3,)
            "euler_rpy": [roll, pitch, yaw] # np.ndarray of shape (3,)
        },
        timestep2: {
            "pos": [x, y, z],
            "euler_rpy": [roll, pitch, yaw]
        },
        ...
    }
    """

    state_dict = get_state_helper(data, "cameras", camera_name)

    return state_dict