"""
Integrated tests of ICP-MS and picking calculations
"""

# Add plugins to sys.path
from pathlib import Path

from pandas import read_excel
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
