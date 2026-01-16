"""
Explore H5 data structure to understand how to read meter readings
"""
import h5py
import os

def explore_h5_structure():
    __location__ = os.path.realpath(
        os.path.join(os.getcwd(), os.path.dirname(__file__)))
    h5_file = os.path.join(__location__, 'config/examplemeterdata/load_data.h5')

    print(f"Exploring: {h5_file}\n")

    with h5py.File(h5_file, 'r') as hf:
        # Get first meter
        meters_group = hf['meters']
        first_meter_key = list(meters_group.keys())[0]
        first_meter = meters_group[first_meter_key]

        print(f"First meter: {first_meter_key}")
        print(f"Attributes: {dict(first_meter.attrs)}")
        print(f"\nStructure in meter:")

        for key in first_meter.keys():
            item = first_meter[key]
            print(f"  {key}: {type(item).__name__}")

            if isinstance(item, h5py.Group):
                # It's a group, explore it
                print(f"    Group contents:")
                for subkey in item.keys():
                    subitem = item[subkey]
                    if isinstance(subitem, h5py.Dataset):
                        print(f"      {subkey}: shape={subitem.shape}, dtype={subitem.dtype}")
                        if len(subitem) > 0:
                            print(f"        First 3: {subitem[:3]}")
            elif isinstance(item, h5py.Dataset):
                # It's a dataset
                print(f"    Shape: {item.shape}")
                print(f"    Dtype: {item.dtype}")
                if len(item) > 0:
                    print(f"    First 3 values: {item[:3]}")

if __name__ == "__main__":
    explore_h5_structure()

