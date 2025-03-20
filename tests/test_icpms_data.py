"""
Integrated tests of ICP-MS and picking calculations
"""

# Add plugins to sys.path
from pathlib import Path
import re
from unittest.mock import inplace

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
from plugins.manipulate_data.dataReduction import calculate_date

test_data = Path(__file__).parent.parent / "test_data" / "icpms_test"

geometry_key = {1: "Ellipsoid", 2: "Cylindrical", 3: "Orthorhombic", 4: "Hexagonal"}


def _create_picking_data_frame():
    picking_sheet = test_data / "Picking_Test.xlsx"
    df = read_excel(picking_sheet, header=1)
    df = df.iloc[4:, :]
    # Remove "Sample" integer index
    df.drop("Sample", axis=1, inplace=True)
    df.rename(columns={"Sample.1": "Sample"}, inplace=True)

    df = standardize_table(df, "Packet Identifier")

    return df


def _create_icpms_data_frame():
    df = read_csv(test_data / "ICPMS_Data_Test.txt", delimiter="\t")
    return standardize_table(df, "Sample")


def _create_he_data_frame():
    he_sheet = test_data / "He_Data_Test.txt"
    df = read_csv(he_sheet, delimiter="\t")
    return standardize_table(df, "SampleName")


def _create_results_data_frame():
    results_sheet = test_data / "Test_Data_Results.xlsx"
    df = read_excel(results_sheet)
    return standardize_table(df, "Sample Name")


def standardize_table(df_input, index_col):
    # Trim whitespace in all text cells
    df = df_input.applymap(lambda x: x.strip() if isinstance(x, str) else x)
    # If cell contains only whitespace, None, or underscore, replace with NaN
    df.replace(r"^\s*$", N.nan, regex=True, inplace=True)
    for replacement in ["-", "_", "_"]:
        df.replace(replacement, N.nan, inplace=True)

    df.rename(columns={index_col: "id"}, inplace=True)
    df.fillna(value=N.nan, inplace=True)

    # Delete rows with an empty index
    df = df.loc[df["id"].notna()]

    df.set_index("id", inplace=True)

    # Get rid of rows where all values are null
    df = df.loc[df.notna().any(axis=1)]

    # Get rid of columns where all rows are null
    df = df.loc[:, df.notna().any()]
    # Clean up column names
    df.columns = [clean_column_name(c) for c in df.columns]

    # Refer error columns to their respective value columns
    err_regex = re.compile("err(\.d+)?")
    for i, c in enumerate(df.columns):
        if err_regex.match(c) and i > 0:
            # Get the value column name
            vc = df.columns[i - 1]
            # Rename the error column
            df.rename(columns={c: f"{vc} err"}, inplace=True)

    return df


def clean_column_name(name):
    # Clean up a column name by removing parenthetical statements and spaces
    n1 = re.sub(r"\(.*\)", "", name)
    n1 = re.sub(r"\[.*\]", "", n1)
    n2 = n1.strip()
    return n2.replace("+/-", "err").replace("±", "err")


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
    dfs = {
        "Picking": _create_picking_data_frame(),
        "ICPMS": _create_icpms_data_frame(),
        "He": _create_he_data_frame(),
    }

    # merge all data frames
    df = None
    for key, frame in dfs.items():
        if df is None:
            df = frame
        else:
            df = df.join(frame, how="inner", rsuffix=f" ({key})")

    assert len(df) == 31

    res_df = _create_results_data_frame()
    assert len(res_df) == 31

    # Ensure that there are the same index values in the results and the merged data frame
    assert N.all(df.index == res_df.index)

    # Input cols
    # ['Lab/Owner', 'Analyst', 'Funding', 'Sample', 'Aliquot', 'Mineral',
    #        'Color', 'Surface Color or Staining', 'Surface Roughness',
    #        'Idealness of xtal form', 'Geometry', 'Shard ?', 'Mineral Inclusions?',
    #        'Fluid Inclusions?', 'Additional descriptive notes', 'L1', 'W1', 'L2',
    #        'W2', 'Np', 'Special Analytical Instructions', 'Priority?',
    #        'Date Packed', 'Apatite Ft', 'Zircon Ft', 'Definitions', 'Bap', 'Bz',
    #        'Lavg', 'R', 'Ap Uft', 'Ap ThFt', 'Z Uft', 'Z ThFt', 'Date', '238U',
    #        '238U err', '238U blank', '238U blank err', '235U', '235U err', '232Th',
    #        '232Th err', '232Th blank', '232Th blank err', '147Sm', '147Sm err',
    #        'HeNumber', 'PickingInfo', 'Mineral (He)', 'Date (He)', '4He',
    #        '4He err', 'IE', 'Q', 'Q err', 'Blank', 'Blank err']

    min_index = {
        "a": "Apatite",
        "z": "Zircon",
    }

    for (ix, d), (ix1, res) in zip(df.iterrows(), res_df.iterrows()):
        assert ix == ix1

        sample = Sample(
            name=d.index,
            material=min_index[d["Mineral"]],
            geometry=geometry_key[d["Geometry"]],
            terminations=d["Np"],
            length1=d["L1"],
            width1=d["W1"],
            length2=d["L2"],
            width2=d["W2"],
        )

        ft_vals = get_Ft_values(sample, corrected=True)

        date = calculate_date(
            d["4He"],
            d["4He err"],
            d["238U"],
            d["238U err"],
            d["232Th"],
            d["232Th err"],
            d["147Sm"],
            d["147Sm err"],
            ft_vals.ft238u,
            ft_vals.errors.ft238u,
            ft_vals.ft235u,
            ft_vals.errors.ft235u,
            ft_vals.ft232th,
            ft_vals.errors.ft232th,
            ft_vals.ft147sm,
            ft_vals.errors.ft147sm,
            True
        )

    assert False
