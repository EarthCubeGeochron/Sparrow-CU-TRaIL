"""
Integrated tests of ICP-MS and picking calculations
"""

# Add plugins to sys.path
from pathlib import Path
import re
from pytest import mark, approx
from pytest_steps import test_steps
import hecalc

from pandas import read_excel, read_csv
import numpy as N

from plugins.import_data.pickingImport import (
    get_Ft_values,
    Sample,
)
from plugins.manipulate_data.dataReduction import calculate_date

test_data = (
    Path(__file__).parent.parent
    / "test_data"
    / "icpms_test"
    / "synthetic_data_2025_04_21_simple.xlsx"
)

geometry_key = {1: "Ellipsoid", 2: "Cylindrical", 3: "Orthorhombic", 4: "Hexagonal"}


def _create_base_data_frame():
    df = read_excel(test_data, sheet_name="Data")
    df = standardize_table(df, "Packet Identifier")
    return df


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

    return df


input_df = _create_base_data_frame()

grain_ids = input_df.index

res_df = input_df


@mark.parametrize("grain_id", grain_ids)
@mark.parametrize("corrected", [False, True])
def test_correct_ft_values(grain_id, corrected):
    """Ensure that calculated FT values from Picking data match the expected values"""

    # Get the row from the input data frame
    d = input_df.loc[grain_id]
    res = res_df.loc[grain_id]

    min_index = {
        "a": "Apatite",
        "z": "Zircon",
    }

    sample = Sample(
        name=grain_id,
        material=min_index[d["Mineral"]],
        geometry=geometry_key[d["Geometry"]],
        terminations=d["Np"],
        length1=d["Length 1"],
        width1=d["Width 1"],
        length2=d["Length 2"],
        width2=d["Width 2"],
    )

    # Basic sanity checks
    assert sample.material in ["Apatite", "Zircon"]
    ft_vals = get_Ft_values(sample, corrected=corrected)
    _check_ft_vals(ft_vals, res, corrected=corrected)


def _check_ft_vals(ft_vals, res, corrected=False, tolerance=1e-7):
    prefix = "GeoCorr" if corrected else "UnCorr"
    # Test that we have the right FT values
    assert ft_vals.ft238u == approx(res[f"{prefix} Ft 238U"], rel=tolerance)
    assert ft_vals.ft235u == approx(res[f"{prefix} Ft 235U"], rel=tolerance)
    assert ft_vals.ft232th == approx(res[f"{prefix} Ft 232Th"], rel=tolerance)
    assert ft_vals.ft147sm == approx(res[f"{prefix} Ft 147Sm"], rel=tolerance)

    # Check that Ft errors are not NaN
    if ft_vals.errors is not None:
        assert N.isfinite(ft_vals.errors.ft238u)
        assert N.isfinite(ft_vals.errors.ft235u)
        assert N.isfinite(ft_vals.errors.ft232th)
        assert N.isfinite(ft_vals.errors.ft147sm)


@mark.parametrize("grain_id", grain_ids)
@test_steps("ft_vals", "raw", "corrected")
def test_calculate_date(grain_id):

    # Get the row from the input data frame
    d = input_df.loc[grain_id]
    res = res_df.loc[grain_id]

    min_index = {
        "a": "Apatite",
        "z": "Zircon",
    }

    sample = Sample(
        name=grain_id,
        material=min_index[d["Mineral"]],
        geometry=geometry_key[d["Geometry"]],
        terminations=d["Np"],
        length1=d["Length 1"],
        width1=d["Width 1"],
        length2=d["Length 2"],
        width2=d["Width 2"],
    )

    # Basic sanity checks
    assert sample.material in ["Apatite", "Zircon"]

    # Get FT values based on geometry and picking data
    ft_vals = get_Ft_values(sample, corrected=True)

    _check_ft_vals(ft_vals, res, corrected=True)

    yield "ft_vals"

    # assert N.allclose(d["147Sm"], res["147Sm"], atol=1e-3)

    # totalU = d["238U"] + d["235U"]
    # assert N.allclose(totalU, res["U"][0], rtol=1e-6)

    # assert ft_vals.RFt == res["Rs"]

    # Do I need to use the ESR_Ft values here to calculate the date?
    # ...

    # Apparently we have to ignore errors to get the "raw" date as calculated
    Ft238U_err = ft_vals.errors.ft238u
    Ft235U_err = ft_vals.errors.ft235u
    Ft232Th_err = ft_vals.errors.ft232th
    Ft147Sm_err = ft_vals.errors.ft147sm

    # This calculates date without Monte Carlo or errors at this point
    date, tau_date = calculate_date(
        d["4He"],
        d["4He err"],
        d["238U"],
        d["238U err"],
        d["232Th"],
        d["232Th err"],
        d["147Sm"],
        d["147Sm err"],
        ft_vals.ft238u,
        Ft238U_err,
        ft_vals.ft235u,
        Ft235U_err,
        ft_vals.ft232th,
        Ft232Th_err,
        ft_vals.ft147sm,
        Ft147Sm_err,
        False,
        do_monte_carlo=True,
        mols=True,
    )

    raw_date = date["Raw date"][0]

    assert raw_date == approx(res["Raw date"], rel=0.0001)

    yield "raw"

    Ft238U_err = ft_vals.errors.ft238u
    Ft235U_err = ft_vals.errors.ft235u
    Ft232Th_err = ft_vals.errors.ft232th
    Ft147Sm_err = ft_vals.errors.ft147sm

    # This calculates date without Monte Carlo or errors at this point
    date, tau_date = calculate_date(
        d["4He"],
        d["4He err"],
        d["238U"],
        d["238U err"],
        d["232Th"],
        d["232Th err"],
        d["147Sm"],
        d["147Sm err"],
        ft_vals.ft238u,
        Ft238U_err,
        ft_vals.ft235u,
        Ft235U_err,
        ft_vals.ft232th,
        Ft232Th_err,
        ft_vals.ft147sm,
        Ft147Sm_err,
        True,
        do_monte_carlo=True,
        mols=True,
    )

    corrected_date = date["Corrected date"][0]

    assert corrected_date == approx(res["Corrected date"], rel=0.0001)

    yield "corrected"
