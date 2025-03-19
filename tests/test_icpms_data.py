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

picking_data = Path(__file__).parent.parent / "test_data"


geometry_key = {1: "Ellipsoid", 2: "Cylindrical", 3: "Orthorhombic", 4: "Hexagonal"}


def test_picking_data_ingestion():
    picking_sheet = picking_data / "icpms_test" / "Picking_Test.xlsx"
    df = read_excel(picking_sheet, header=1)
    df = df.iloc[4:, :]
    df = df[df["Lab/Owner"].notna()]

    assert len(df) == 31


def test_icpms_data_ingestion():
    icpms_sheet = picking_data / "icpms_test" / "ICPMS_Data_Test.txt"
    df = read_csv(icpms_sheet, delimiter="\t")

    assert len(df) == 31


def test_he_data_ingestion():
    he_sheet = picking_data / "icpms_test" / "He_Data_Test.txt"
    df = read_csv(he_sheet, delimiter="\t")

    assert len(df) == 31


def test_load_results():
    results_sheet = picking_data / "icpms_test" / "Test_Data_Results.xlsx"
    df = read_excel(results_sheet)
    df = df[df.iloc[:, 0].notna()]

    assert len(df) == 31
