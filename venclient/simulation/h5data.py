import h5py
import os
import pandas as pd
import logging

import environ

logger = logging.getLogger(__name__)
def locating_h5file():
    __location__ = os.path.realpath(
        os.path.join(os.getcwd(), os.path.dirname(__file__)))

    h5_file = os.path.join(__location__, '../../config/examplemeterdata/load_data.h5')
    return h5_file


def list_meters(h5_file=locating_h5file()):
    """List all available meters in the H5 database"""
    logging.debug(f"\n{'='*60}")
    logging.debug(f"Available meters in: {h5_file}")
    logging.debug(f"{'='*60}\n")

    with h5py.File(h5_file, 'r') as hf:
        if 'meters' not in hf:
            logging.debug("No meters found in file.")
            return []

        meters_group = hf['meters']
        meter_list = []

        for meter_key in sorted(meters_group.keys()):
            meter_group = meters_group[meter_key]
            meter_id = meter_group.attrs.get('meter_id', 'unknown')
            company = meter_group.attrs.get('company', 'unknown')
            num_loads = meter_group.attrs.get('num_load_components', 0)

            meter_list.append(meter_id)

            logging.debug(f"{meter_key}:")
            logging.debug(f"  Meter ID: {meter_id}")
            logging.debug(f"  Company: {company}")
            logging.debug(f"  Load Components: {num_loads}")

        return meter_list