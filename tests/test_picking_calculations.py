# Add plugins to sys.path
from pathlib import Path
from uuid import uuid4

import pytest
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


picking_tests = [
    (
        Sample(
            name="sampleap",
            material="Apatite",
            geometry="Hexagonal",
            terminations=2,
            length1=150,
            width1=90,
            length2=160,
            width2=80,
        ),
        SampleFt(
            ft238u=0.713279445,
            ft235u=0.670587315,
            ft232th=0.664232629,
            ft147sm=0.906304307,
        ),
    ),
    (
        Sample(
            name="samplezir",
            material="Zircon",
            geometry="Orthorhombic",
            terminations=2,
            length1=150,
            width1=90,
            length2=160,
            width2=80,
        ),
        SampleFt(
            ft238u=0.746981664,
            ft235u=0.713487494,
            ft232th=0.708453638,
            ft147sm=0.9175819211,
        ),
    ),
]

# Other corrections to test
# - Volume corrections
# - R_ft correction


@pytest.mark.parametrize("input, result", picking_tests)
def test_picking_calcs(input, result):
    """Picking calculations test based on data provided by Jim Metcalf on 2024-09-19"""
    res = get_Ft_values(input)
    assert res == result


def test_picking_calcs_from_table():
    ft_data = picking_data / "Jan2025TestData" / "Test_Data_Correct_Values.xlsx"
    df = read_excel(ft_data, header=1)
    for ix, row in df.iterrows():
        name = row[0]
        material = None
        geometry = None
        if "zr" in name.lower():
            material = "Zircon"
            # Note: this is just a guess, it's not in the file
            geometry = "Orthorhombic"

        elif "ap" in name.lower():
            material = "Apatite"
            geometry = "Hexagonal"

        sample = Sample(
            name=name,
            material=material,
            geometry=geometry,
            terminations=row[5],
            length1=row[1],
            width1=row[2],
            length2=row[3],
            width2=row[4],
        )

        fts = SampleFt(ft238u=row[7], ft235u=row[9], ft232th=row[11], ft147sm=row[13])

        res = get_Ft_values(sample)
        assert res == fts


def random_lab_id(date) -> str:
    return uuid4().hex[:6]


@pytest.mark.skip()
def test_picking_data():
    """Basic test of reading picking data"""

    specs = get_picking_specs()
    fn = picking_data / "PickingData" / "Test_Picking_Sheet.xlsx"

    # Do the calculations of picking data
    picking = list(read_picking_data(fn, specs, random_lab_id))
    assert len(picking) == 8

    assert len(picking[0]["lab_id"]) == 6

    # Check that the first row is correct

    # Load results table
    res1 = read_pub_table(
        picking_data / "ExportPublicationTable" / "Test_Results_Table_new.xlsx"
    )
    assert len(res1) == 8

    # Get names from picking input
    names = set([x["name"] for x in picking])
    # new names
    new_names = set(res1.iloc[:, 0])

    # Check that the names are the same
    assert names == new_names

    df = get_picking_dataframe(fn, specs)

    # Get the last few samples which are zircons matching testzirc1
    # df = df[df["Packet Identifier"].str.contains("testzirc1")]
    #
    # assert len(df) == 3

    # Now check that all grain dimensions are the same
    for sample in picking:
        print(sample["name"])

        name = res1.iloc[:, 0]
        row = res1[name == sample["name"]].iloc[0]
        sess = sample["session"][0]
        has_aec = False
        for sess in sample["session"]:
            if sess["technique"]["id"] == "Picking info":
                for analysis in sess["analysis"]:
                    if analysis["analysis_type"] == "Grain dimensions & shape":
                        data = {
                            x["type"]["parameter"]: x["value"]
                            for x in analysis["datum"]
                        }
                        for param in ["Length 1", "Length 2", "Width 1", "Width 2"]:
                            value = data[param]
                            assert N.allclose(
                                value, row[param.lower() + " (µm) [c]"], atol=0.01
                            )

            if sess["technique"]["id"] == "Dates and other derived data":
                for analysis in sess["analysis"]:
                    if (
                        analysis["analysis_type"]
                        == "Alpha ejection correction values (new geometric correction)"
                    ):
                        data = {
                            x["type"]["parameter"]: x["value"]
                            for x in analysis["datum"]
                        }

                        min = "Ap"
                        if "zirc" in sample["name"].lower():
                            min = "Z"

                        d1 = df[df["Packet Identifier"] == sample["name"]].iloc[0]

                        field = f"{min} ThFt"

                        assert N.allclose(
                            d1[field],
                            data["232Th Ft (±2σ), new geometric correction"],
                            atol=0.01,
                        )
                        has_aec = True

        if not has_aec:
            raise ValueError("No Alpha Ejection Correction found")

        # assert row.iloc[1] == sample["age"]


def read_pub_table(fn):
    """
    Read a publication table, and return it as a DataFrame
    :param fn:
    :return:
    """
    tbl = read_excel(fn, skiprows=1, engine="openpyxl")

    # Remove all rows after the last empty row (these are comments and instructions generally)
    last_empty = tbl[tbl.iloc[:, 0].isna()].index[0]
    tbl = tbl.iloc[:last_empty]
    # Interpret all rows with only one value as sample IDs, and append them to the grain indexes
    curr_prefix = ""
    for i, row in tbl.iterrows():
        if len(row.dropna()) == 1:
            curr_prefix = f"{row[0]}_"
        else:
            tbl.iloc[i, 0] = curr_prefix + tbl.iloc[i, 0]

    # Drop rows with data only in first column
    tbl = tbl.dropna(subset=[tbl.columns[1]])

    return tbl
