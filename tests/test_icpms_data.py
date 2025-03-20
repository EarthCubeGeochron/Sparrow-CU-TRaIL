"""
Integrated tests of ICP-MS and picking calculations
"""

# Add plugins to sys.path
from pathlib import Path

from pandas import read_excel, read_csv
import numpy as N

from plugins.import_data.pickingImport import (
    read_picking_data,
    get_picking_specs,
    get_picking_dataframe,
    get_Ft_values,
    Sample,
    SampleFt,
)

test_data = Path(__file__).parent.parent / "test_data" / "icpms_test"

geometry_key = {1: "Ellipsoid", 2: "Cylindrical", 3: "Orthorhombic", 4: "Hexagonal"}


def _create_picking_data_frame():
    picking_sheet = test_data / "Picking_Test.xlsx"
    df = read_excel(picking_sheet, header=1)
    df = df.iloc[4:, :]
    df = df[df["Lab/Owner"].notna()]
    df.set_index("Packet Identifier", inplace=True)
    return df


def _create_icpms_data_frame():
    df = read_csv(test_data / "ICPMS_Data_Test.txt", delimiter="\t")
    df.set_index("Sample", inplace=True)
    return df


def _create_he_data_frame():
    he_sheet = test_data / "He_Data_Test.txt"
    df = read_csv(he_sheet, delimiter="\t")
    df.set_index("SampleName", inplace=True)
    return df


def _create_results_data_frame():
    results_sheet = test_data / "Test_Data_Results.xlsx"
    df = read_excel(results_sheet)
    df = df[df.iloc[:, 0].notna()]
    df.set_index("Sample Name", inplace=True)
    return df


def test_picking_data_ingestion():
    df = _create_picking_data_frame()
    assert len(df) == 31


def test_icpms_data_ingestion():
    df = _create_icpms_data_frame()
    assert len(df) == 31


def test_he_data_ingestion():
    df = _create_he_data_frame()
    assert len(df) == 31


def test_load_results():
    df = _create_results_data_frame()
    assert len(df) == 31


def test_correlate_data_frame():
    # Ensure that all data frames have the same samples
    dfs = [
        _create_picking_data_frame(),
        _create_icpms_data_frame(),
        _create_he_data_frame(),
        _create_results_data_frame(),
    ]

    # merge all data frames
    df = dfs[0]
    for i, d in enumerate(dfs[1:]):
        df = df.join(d, how="inner", rsuffix=f"_{i+1}")

    assert len(df) == 31
