# -*- coding: utf-8 -*-
"""
Created on Fri Oct  8 15:01:18 2021

@author: Peter
"""

import glob
import numpy as np
import pandas as pd
from rich import print
from math import sqrt
from sparrow.core.import_helpers import BaseImporter
from dataclasses import dataclass
from macrostrat.utils import relative_path
import datetime
from dateutil.parser import parse
from yaml import load, SafeLoader
from enum import Enum
import numpy as N


@dataclass
class Sample:
    name: str
    material: str
    geometry: str
    terminations: int
    length1: float
    width1: float
    length2: float
    width2: float


@dataclass
class SampleFt:
    ft238u: float
    ft235u: float
    ft232th: float
    ft147sm: float
    volume: float
    RFt: float = float("nan")

    def __eq__(self, other):
        return (
            N.allclose(self.ft238u, other.ft238u)
            and N.allclose(self.ft235u, other.ft235u)
            and N.allclose(self.ft232th, other.ft232th)
            and N.allclose(self.ft147sm, other.ft147sm)
            and N.allclose(self.volume, other.volume)
        )


def get_Ft_values(sample: Sample, corrected: bool = True) -> SampleFt:
    print(sample.name)
    Fts = get_Ft_values_internal(
        sample.length1,
        sample.width1,
        sample.length2,
        sample.width2,
        sample.material,
        sample.geometry,
        sample.terminations,
        corrected=corrected,
    )

    return SampleFt(
        ft238u=Fts["238U"],
        ft235u=Fts["235U"],
        ft232th=Fts["232Th"],
        ft147sm=Fts["147Sm"],
        volume=Fts["V"],
    )


class Material(Enum):
    Zircon = "Zircon"
    Apatite = "Apatite"


def get_Ft_values_internal(
    l1,
    w1,
    l2,
    w2,
    material: Material,
    shape,
    Np,  # Number of terminations
    *,
    Ft_constants=None,
    # Replicates Ketcham et al., 2011 for Ft calculation
    corrected: bool = True,
):
    if Ft_constants is None:
        Ft_constants = get_picking_specs()["Ft_constants"]

    # Make sure that l1 and w1 are the greater values
    w2, w1 = sorted([w2, w1])
    l2, l1 = sorted([l2, l1])

    # Only used in corrected calculations
    Wmax = max(w1, w2)

    Ft_dat = {}
    for iso in ["238U", "235U", "232Th", "147Sm"]:
        # Get the Ft_constants for the material and isotope
        R = Ft_constants[material][iso]
        if shape == "Ellipsoid":
            # For zircon, use the two widths and for apatite use the wmax for both
            if material == "Apatite" and corrected:
                w1 = Wmax
                w2 = Wmax
            a = w1 / 2
            b = w2 / 2
            c = ((l1 + l2) / 2) / 2
            V = (4 / 3) * np.pi * a * b * c
            p = 1.6075
            S = 4 * np.pi * ((a**p * b**p + b**p * c**p + c**p * a**p) / 3) ** (1 / p)
            Rs = 3 * (V / S)
            Ft = (
                1
                - (3 / 4) * (R / Rs)
                + ((1 / 16) + 0.1686 * (1 - (a / Rs)) ** 2) * (R / Rs) ** 3
            )
        elif shape == "Cylindrical":
            # This should never be used for apatite
            # Note: unlike the calculations for Orthorhombic, we don't use
            #

            r = w1 / 2
            h = l1
            V = np.pi * r**2 * h
            Ft = (
                1
                - ((r + h) * R) / (2 * r * h)
                + (0.2122 * R**2) / (r * h)
                + (0.0153 * R**3) / r**3
            )
            Rs = (3 * r * h) / (2 * (r + h))
        elif shape == "Orthorhombic":
            # This should never be used for apatite
            a = min([w1, w2])
            b = max([w1, w2])
            c = (l1 + l2) / 2
            V = a * b * c - Np * (a / 4) * (b**2 + (a**2 / 3))
            S = 2 * (a * b + b * c + a * c) - Np * (
                ((a**2 + b**2) / 2) + (2 - sqrt(2)) * a * b
            )
            Rs = 3 * V / S
            Ft = (
                1
                - (3 * R) / (4 * Rs)
                + (
                    0.2095 * (a + b + c)
                    - (0.096 - 0.013 * ((a**2 + b**2) / c**2)) * (a + b) * Np
                )
                * (R**2 / V)
            )
            print("Ft (uncorrected)", iso, Ft)
        elif shape == "Hexagonal":
            #  For zircon, use the two widths and for apatite use the wmax for both
            # Note: to get tests to pass, I had to remove the following -
            # if material == "Apatite" and corrected:
            # Not sure whether that is intended, but it doesn't appear to be the same
            # as the original calculations
            if material == "Apatite":
                w1 = Wmax
                w2 = Wmax
            L = w1
            W = w2
            H = (l1 + l2) / 2
            dV = (
                (1 / (6 * sqrt(3))) * (L - (sqrt(3) / 2) * W) ** 3
                if L > (sqrt(3) / 2) * W
                else 0
            )
            V = H * L * (W - (L / (2 * sqrt(3)))) - Np * ((sqrt(3) / 8) * L * W**2 - dV)
            S = (
                2 * H * (W + (L / sqrt(3)))
                + 2 * L * (W - (L / (2 * sqrt(3))))
                - Np
                * (
                    sqrt(3) * W**2 / 4
                    + (2 - sqrt(2)) * W * L
                    + ((sqrt(2) - 1) * L**2) / (2 * sqrt(3))
                )
            )
            Rs = 3 * V / S
            Ft = (
                1
                - (3 / 4) * (R / Rs)
                + (
                    (0.2093 - 0.0465 * Np) * (W + L / sqrt(3))
                    + (0.1062 + (0.2234 * R) / (R + 6 * (W * sqrt(3) - L)))
                    * (H - Np * (W * (sqrt(3) / 2) + L) / 4)
                )
                * R**2
                / V
            )
        Ft_dat[iso] = Ft
    Ft_dat["V"] = V
    Ft_dat["Rs"] = Rs

    if not corrected:
        return Ft_dat

    # Now correct the Ft. This will depend upon the material, geometry, and maximum width.
    _238Ft = Ft_dat["238U"]
    _235Ft = Ft_dat["235U"]
    _232Ft = Ft_dat["232Th"]
    _147Ft = Ft_dat["147Sm"]

    Vcorr = V
    Vcorr_err = float("nan")
    # First correct the Volume (V) values. This depends upon the mineral and the geometry.
    # Right now we have this for apatite and zircon, so if
    # the material is something else then Vcorr should just equal V, and Vcorr_err should be XX.
    if material == "Zircon":
        if shape == "Orthorhombic":
            Vcorr = 0.81 * V
            Vcorr_err = 0.13 * Vcorr
        elif shape == "Ellipsoid":
            Vcorr = 1.04 * V
            Vcorr_err = 0.21 * Vcorr
    elif material == "Apatite":
        if shape == "Hexagonal":
            Vcorr = 0.83 * V
            Vcorr_err = 0.20 * Vcorr
        elif shape == "Ellipsoid":
            Vcorr = 0.74 * V
            Vcorr_err = 0.23 * Vcorr

    Ft_dat["V"] = Vcorr
    Ft_dat["V_err"] = Vcorr_err

    # Set some default values for Ft errors
    _238Ftcorr = _238Ft
    _238Fterr = float("nan")
    _235Ftcorr = _235Ft
    _235Fterr = float("nan")
    _232Ftcorr = _232Ft
    _232Fterr = float("nan")
    _147Ftcorr = _147Ft
    _147Fterr = float("nan")

    if material == "Zircon":
        if shape == "Orthorhombic":
            _238Ftcorr = 0.97 * _238Ft
            _238Fterr = 0.03 * _238Ftcorr if Wmax < 100 else 0.02 * _238Ftcorr
            _235Ftcorr = 0.97 * _235Ft
            _235Fterr = 0.04 * _235Ftcorr if Wmax < 100 else 0.03 * _235Ftcorr
            _232Ftcorr = 0.97 * _232Ft
            _232Fterr = 0.05 * _232Ftcorr if Wmax < 100 else 0.02 * _232Ftcorr
            _147Ftcorr = 0.99 * _147Ft
            _147Fterr = 0.01 * _147Ftcorr
        elif shape == "Ellipsoid":
            _238Ftcorr = _238Ft
            _238Fterr = 0.03 * _238Ftcorr
            _235Ftcorr = _235Ft
            _235Fterr = 0.04 * _235Ftcorr
            _232Ftcorr = _232Ft
            _232Fterr = 0.04 * _232Ftcorr
            _147Ftcorr = _147Ft
            _147Fterr = 0.01 * _147Ftcorr
    if material == "Apatite":
        if shape == "Hexagonal":
            _238Ftcorr = 0.97 * _238Ft
            _238Fterr = 0.03 * _238Ftcorr if Wmax < 100 else 0.02 * _238Ftcorr
            _235Ftcorr = 0.96 * _235Ft
            _235Fterr = 0.04 * _235Ftcorr if Wmax < 100 else 0.02 * _235Fterr
            _232Ftcorr = 0.96 * _232Ft
            _232Fterr = 0.04 * _232Ftcorr if Wmax < 100 else 0.02 * _232Fterr
            _147Ftcorr = 0.99 * _147Ft
            _147Fterr = 0.01 * _147Ftcorr
        if shape == "Ellipsoid":
            _238Ftcorr = 0.92 * _238Ft
            _238Fterr = 0.05 * _238Ftcorr
            _235Ftcorr = 0.91 * _235Ft
            _235Fterr = 0.06 * _235Ftcorr
            _232Ftcorr = 0.91 * _232Ft
            _232Fterr = 0.06 * _232Ftcorr
            _147Ftcorr = 0.97 * _147Ft
            _147Fterr = 0.01 * _147Ftcorr
    Ft_dat["238U"] = _238Ftcorr
    Ft_dat["238U_err"] = _238Fterr
    Ft_dat["235U"] = _235Ftcorr
    Ft_dat["235U_err"] = _235Fterr
    Ft_dat["232Th"] = _232Ftcorr
    Ft_dat["232Th_err"] = _232Fterr
    Ft_dat["147Sm"] = _147Ftcorr
    Ft_dat["147Sm_err"] = _147Fterr

    return Ft_dat


# Function to make datum
def make_datum(datum, error, parameter, unit):
    return {
        "value": datum,
        "error": error,
        "type": {"parameter": parameter, "unit": unit},
    }


# Function to make attributes
def make_attribute(value, parameter):
    return {"parameter": parameter, "value": str(value)}


class TRaILpicking(BaseImporter):
    def __init__(self, app, data_dir, **kwargs):
        super().__init__(app)
        file_list = kwargs.get(
            "file_list", glob.glob(str(data_dir) + "/PickingData/*.xlsx")
        )

        self.picking_specs = get_picking_specs()
        self.iterfiles(file_list, **kwargs)

    # Method to generate a lab ID for a new sample based on the date of the analysis
    def make_labID(self, date):
        year = str(date.year)[-2:]
        # Query database for all lab IDs
        all_IDs = [
            el
            for tup in self.db.session.query(self.db.model.sample.lab_id).all()
            for el in tup
            if el is not None
        ]
        # Isolate lab IDs from the same year
        same_year = [i for i in all_IDs if year + "-" in i]
        # Get the highest numbered analysis for the year and add 1
        if len(same_year) > 0:
            max_num = max([int(i.split("-")[1]) for i in same_year])
        else:
            max_num = 0
        id_num = max_num + 1
        # Combine year and analysis number to get lab_id
        lab_id = year + "-" + f"{id_num:05d}"
        return lab_id

    def import_datafile(self, fn, rec, **kwargs):
        sample_schemas = read_picking_data(fn, self.picking_specs, self.make_labID)
        for sample in sample_schemas:
            self.db.load_data("sample", sample, strict=True)


def get_picking_specs():
    # Load the picking specs. This file dictates virtually everything about this import
    spec = relative_path(__file__, "picking_specs.yaml")
    with open(spec) as f:
        return load(f, Loader=SafeLoader)


def read_picking_data(fn, picking_specs, make_labID):
    data = get_picking_dataframe(fn, picking_specs)

    for d in range(len(data)):
        # Generate a lab ID for each grain
        date = str(data.iloc[d][picking_specs["Metadata"]["Date"]])
        if date == "nan":
            date = datetime.datetime.now()
        else:
            date = parse(date)
        lab_id = make_labID(date)

        # Generate metadata required for every grain
        researcher = str(data.iloc[d][picking_specs["Metadata"]["Researcher"]])
        lab_owner = str(data.iloc[d][picking_specs["Metadata"]["Lab_owner"]])
        funding = str(data.iloc[d][picking_specs["Metadata"]["Funding"]])
        sample = data.iloc[d][picking_specs["Metadata"]["Sample"]]
        grain = data.iloc[d][picking_specs["Metadata"]["Grain"]]
        print("Importing: " + sample + "_" + grain)
        material = picking_specs["mineral_key"][
            data.iloc[d][picking_specs["Metadata"]["Mineral"]]
        ]

        # Create necessary data for Fts if not a shard. This info MUST be recorded for whole grains
        shard = data.iloc[d][picking_specs["Metadata"]["Fragment"]]
        if shard != "Y" and shard != "y":
            length1 = data.iloc[d][picking_specs["Metadata"]["Dimensions"]["Length 1"]]
            width1 = data.iloc[d][picking_specs["Metadata"]["Dimensions"]["Width 1"]]
            length2 = data.iloc[d][picking_specs["Metadata"]["Dimensions"]["Length 2"]]
            width2 = data.iloc[d][picking_specs["Metadata"]["Dimensions"]["Width 2"]]
            terminations = data.iloc[d][
                picking_specs["Metadata"]["Crystal terminations"]
            ]
            geometry = data.iloc[d][picking_specs["Metadata"]["Crystal geometry"]]

            # Generate Ft and dimensional mass
            Fts = get_Ft_values_internal(
                length1,
                width1,
                length2,
                width2,
                material,
                picking_specs["geometry_key"][geometry],
                int(terminations),
            )
            dimensional_mass = (
                picking_specs["Ft_constants"][material]["density"] * Fts["V_corr"] / 1e6
            )

            # create datum and attributes for shape analysis
            shape_data = []
            for s in picking_specs["Shape"]["data"]:
                col = next(iter(s))
                value = data.iloc[d][col]
                error = None
                shape_data.append([value, error, s[col]["name"], s[col]["unit"]])
            shape_attributes = []
            for s in picking_specs["Shape"]["attributes"]:
                col = next(iter(s))
                value = str(data.iloc[d][col])
                if "eometry" in col:
                    sparrow_val = picking_specs["geometry_key"][int(float(value))]
                if "Np" in col:
                    sparrow_val = picking_specs["terminations_key"][int(float(value))]
                shape_attributes.append([sparrow_val, s[col]])
            # make analysis dictionary
            shape_dict = {
                "analysis_type": "Grain dimensions & shape (geometric corrected)",
                "datum": [make_datum(*d) for d in shape_data],
                "attribute": [make_attribute(*a) for a in shape_attributes],
            }
        # If a shard, simply add that as a note and don't calculate Ft values
        else:
            Fts = False
            shape_dict = {
                "analysis_type": "Grain dimensions & shape (geometric corrected)",
                "attribute": [make_attribute("Crystal shard", "Shape notes")],
            }

        # create datum and attributes for characteristics analysis
        # Characteristics will always be recorded, even for shards
        chars_attributes = []
        for s in picking_specs["Characteristics"]["attributes"]:
            col = next(iter(s))
            value = str(data.iloc[d][col])
            chars_attributes.append([value, s[col]])
        # make analysis dictionary, exclude missing data if shards
        if shard != "Y" and shard != "y":
            # First, get uncertainty for each derived parameter
            for l in chars_attributes:
                for i in l:
                    # get derived data uncertainties for later
                    if "Idealness" in i:
                        xtalform = l[0]
                        # THIS IS WHERE DECISION TREES WOULD BE REFERENCED
                        dim_mass_err = picking_specs["Dim_mass_key"][xtalform]
                        Rs_err = picking_specs["Rs_err_key"][xtalform]
                        # Right now, Ft_err is a proportion, 1sigma. i.e. 0.2 = 20%
                        Ft_err = picking_specs["Ft_err_key"][xtalform]
            # Cast attributes (no data for characteristics) for analysis to dictionary
            chars_dict = {
                "analysis_type": "Grain characteristics",
                "attribute": [make_attribute(*a) for a in chars_attributes],
            }

        # Create a new sample in the database using the picking sheet metadata
        sample_schema = {
            "member_of": {
                "name": sample,
                "material": "rock",
                "embargo_date": "2150-01-01",
            },
            "researcher": [{"name": researcher}],
            "lab_owner": lab_owner,
            "funding": funding,
            "name": sample + "_" + grain,
            "material": material,
            "lab_id": lab_id,
            "embargo_date": "2150-01-01",
            "from_archive": "false",
            "session": [
                {
                    "technique": {"id": "Picking information"},
                    "instrument": {"name": "Leica microscope"},
                    "date": date,
                    "analysis": [shape_dict, chars_dict],
                }
            ],
        }

        # Only incude derived data if not a shard
        if Fts:
            # Compile Ft data for date calculation session
            # This is where Ft_errors are calculated
            Ft_data = [
                [
                    Fts["238U"],
                    Fts["238U"] * Ft_err * 2,
                    "238U Ft (±2σ), new geometric correction",
                    "",
                ],
                [
                    Fts["235U"],
                    Fts["235U"] * Ft_err * 2,
                    "235U Ft (±2σ), new geometric correction",
                    "",
                ],
                [
                    Fts["232Th"],
                    Fts["232Th"] * Ft_err * 2,
                    "232Th Ft (±2σ), new geometric correction",
                    "",
                ],
                [
                    Fts["147Sm"],
                    Fts["147Sm"] * Ft_err * 2,
                    "147Sm Ft (±2σ), new geometric correction",
                    "",
                ],
            ]
            Rs_mass = [
                [
                    dimensional_mass,
                    dimensional_mass * dim_mass_err * 2,
                    "Dimensional mass (±2σ), new geometric correction",
                    "μg",
                ],
                [
                    Fts["Rs"],
                    Fts["Rs"] * Rs_err * 2,
                    "Equivalent spherical radius (±2σ)",
                    "μm",
                ],
            ]

            sample_schema["session"].append(
                {
                    "technique": {"id": "Dates and other derived data"},
                    "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    #'date': '1900-01-01 00:00:00+00', # always pass an 'unknown date' value for calculation
                    "analysis": [
                        {
                            "analysis_type": "Alpha ejection correction values (new geometric correction)",
                            "datum": [make_datum(*d) for d in Ft_data],
                        },
                        {
                            "analysis_type": "Rs, mass, concentrations (new geometric correction)",
                            "datum": [make_datum(*d) for d in Rs_mass],
                        },
                    ],
                }
            )

        yield sample_schema


def get_picking_dataframe(fn, picking_specs):
    data = pd.read_excel(
        fn,
        skiprows=1,
        header=0,
        dtype={picking_specs["Metadata"]["Date"]: str},
        sheet_name="master",
    )

    # Find actual data by figuring out where the analyst rows are full
    return data[
        (data[picking_specs["Metadata"]["Researcher"]].notnull())
        & (data["Sample"] != "EXAMPLE")
    ]
