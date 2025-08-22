# -*- coding: utf-8 -*-
from dataclasses import dataclass

from sparrow.core.import_helpers import BaseImporter
import glob
from rich import print
from sqlalchemy import exc
import pandas as pd
import re
from dateutil import parser


# Make datum using info in yaml file
def make_datum(row, isotope):
    unit = re.search(r"\((\w+)\)", isotope).group(1)
    return {
        "value": row[isotope],
        "error": row.iloc[row.index.get_loc(isotope) + 1],
        "type": {"parameter": isotope.split(" (")[0] + " (±2σ)", "unit": unit},
    }


def make_ppm(data, dim_mass_val, dim_mass_err, corrected=False):
    ppm = (data["value"] / dim_mass_val) * 1000
    # Get ppm uncertainty from combination of mass and nuclide amount uncertainty
    parameter_name = data["type"]["parameter"]
    if corrected:
        parameter_name += ", new geometric correction"

    try:
        ppm_s = ppm * (
            ((data["error"] / 2) / data["value"]) ** 2
            + ((dim_mass_err / 2) / dim_mass_val) ** 2
        ) ** (1 / 2)
    except:
        ppm_s = 0
    return {
        "value": ppm,
        "error": ppm_s * 2,
        "type": {"parameter": parameter_name, "unit": "ppm"},
    }


@dataclass
class FTCombResult:
    S_238: float
    S_235: float
    S_232: float
    a_238: float
    a_235: float
    a_232: float
    Ft_comb: float


class TRaILicpms(BaseImporter):
    def __init__(self, app, data_dir, **kwargs):
        super().__init__(app)
        file_list = glob.glob(str(data_dir) + "/IcpmsData/*.txt")

        self.iterfiles(file_list, **kwargs)

    def query_analysis(self, lab_id, analysis_name):
        Session = self.db.model.session
        Sample = self.db.model.sample
        Analysis = self.db.model.analysis
        res = (
            self.db.session.query(Analysis)
            .join(Session)
            .join(Sample)
            .filter(Sample.lab_id == lab_id)
            .filter(Analysis.analysis_type == analysis_name)
            .first()
        )
        return res

    def query_datum(self, lab_id, datum_param):
        Session = self.db.model.session
        Sample = self.db.model.sample
        Analysis = self.db.model.analysis
        Datum = self.db.model.datum
        DatumType = self.db.model.datum_type
        res = (
            self.db.session.query(Datum)
            .join(Analysis)
            .join(Session)
            .join(Sample)
            .join(DatumType)
            .filter(Sample.lab_id == lab_id)
            .filter(DatumType.parameter == datum_param)
            .first()
        )
        return res

    def query_attribute(self, lab_id, attribute_name):
        Session = self.db.model.session
        Sample = self.db.model.sample
        Analysis = self.db.model.analysis
        Attribute = self.db.model.attribute
        res = (
            self.db.session.query(Attribute)
            .join(Analysis)
            .join(Session)
            .join(Sample)
            .filter(Sample.lab_id == lab_id)
            .filter(Attribute.parameter == attribute_name)
        )

        return res

    def import_datafile(self, fn, rec, **kwargs):
        # data = pd.read_excel(fn)
        data = pd.read_csv(fn, delimiter="\t")
        # trim extraneous rows (assume empty if >80% are null)
        data.drop(
            data.index[data.isnull().sum(axis=1) / len(data.columns) > 0.8],
            inplace=True,
        )

        # Iterate through rows
        for ix, row in data.iterrows():
            print("Importing:", row["Sample"].split(" ")[1])
            # Get sample ID and do checks to ensure that it's in the database
            sample_id = row["Sample"].split(" ")[0]
            try:
                # get the same sample ID from the database
                sample_obj = (
                    self.db.session.query(self.db.model.sample)
                    .filter_by(lab_id=sample_id)
                    .all()
                )[0]
                # Check that the sample name in the database matches the sample name in the data file
                if sample_obj.name != row["Sample"].split(" ")[1]:
                    print(
                        "Mismatched name:\n",
                        sample_obj.name,
                        "in database, but\n",
                        row["Sample"].split(" ")[1],
                        "in importing sheet. Double-check that sample ID is correct",
                    )
            # If no lab ID is found, alert the user and skip uploading
            except IndexError:
                print(
                    "Sample ID for",
                    row["Sample name"],
                    "not found. Double-check that the IDs match.\n",
                )
                return
            # Genearate correct date format
            date = parser.parse(row["Date"])
            # Get list of columns to make datum with. Identify which columns are isotopes based on presence
            # of prentheses, which indicate that there is a unit to pull out
            isotopes = [i for i in row.index if "(" in i and "lank" not in i]
            blanks = [i for i in row.index if "(" in i and "lank" in i]
            raw_data = [make_datum(row, isotope) for isotope in isotopes]
            blank_data = [make_datum(row, blank) for blank in blanks]

            # Make session dictionary
            session_dict = {
                "technique": {"id": "ICP-MS measurement"},
                "instrument": {"name": "Agilent 7900 Quadrupole ICP-MS"},
                "date": date,
                "analysis": [
                    {
                        "analysis_type": "Sample data (blank corrected)",
                        # Here we call the make datum and make_attribute functions
                        "datum": raw_data,
                    },
                    {
                        "analysis_type": "Blank data",
                        # Here we call the make datum and make_attribute functions
                        "datum": blank_data,
                    },
                ],
            }
            session_dict["sample"] = sample_obj
            self.db.load_data("session", session_dict)

            # TODO: This entire calculation will be re-done for corrected and uncorrected values
            # look for whether a dimensional mass is recorded in Sparrow to permit ppm conversion
            for corrected in [False, True]:
                ppm_analysis = self.query_analysis(
                    sample_id, "Rs, mass, concentrations"
                )

                suffix = ""
                if corrected:
                    suffix = ", new geometric correction"


                dim_mass = self.query_datum(
                    sample_id, "Dimensional mass (±2σ)" + suffix
                )
                ft_analysis = self.query_analysis(
                    sample_id, "Alpha ejection correction values"
                )
                Fts = {
                    "238U Ft (±2σ)": None,
                    "235U Ft (±2σ)": None,
                    "232Th Ft (±2σ)": None,
                    "147Sm Ft (±2σ)": None,
                }

                for Ft in Fts:
                    # Load the Ft values from the database, using only those with the new geometric correction applied
                    Fts[Ft] = self.query_datum(sample_id, Ft + suffix)
                if dim_mass:
                    ppm_full = self.add_ppm(raw_data, dim_mass, ppm_analysis, corrected=corrected)
                    if ppm_full:
                        # Store the combined Ft value in the database
                        data = self.calc_Ft_comb(Fts)
                        self.add_Ft_comb(ft_analysis, data, corrected=corrected)

                        # Get material and shape from sample
                        material = str(sample_obj.material)
                        shape = self.query_attribute(sample_id, "Crystal geometry")

                        # Note: should separate calculation and addition to Sparrow
                        if corrected:
                            self.add_ESR_Ft(ft_analysis, data, material, shape)
                    print("")
                else:
                    print("")

    # Generate ppm values and add to existing derived data session
    def add_ppm(self, raw_data, dim_mass, analysis_obj, corrected=False):
        # analysis_obj = Rs, mass, concentrations
        dim_mass_val = float(dim_mass.value)
        dim_mass_err = float(dim_mass.error)

        radionuclides = [d for d in raw_data if d["type"]["unit"] == "ng"]

        # Generate ppm values
        eU = 0
        eU_err = []
        self.ppms = {}

        try:
            # Accumulate eU values and squared errors
            # Do calculation for both corrected and uncorrected values
            for r in radionuclides:
                if "U" in r["type"]["parameter"]:
                    ppm_dict = make_ppm(r, dim_mass_val, dim_mass_err, corrected=corrected)
                    ppm_dict["analysis"] = analysis_obj
                    self.ppms[r["type"]["parameter"]] = ppm_dict
                    self.db.load_data("datum", ppm_dict)
                    eU += ppm_dict["value"]
                    eU_err.append((ppm_dict["error"] / 2) ** 2)
                elif "Th" in r["type"]["parameter"]:
                    ppm_dict = make_ppm(r, dim_mass_val, dim_mass_err, corrected=corrected)
                    ppm_dict["analysis"] = analysis_obj
                    self.ppms[r["type"]["parameter"]] = ppm_dict
                    self.db.load_data("datum", ppm_dict)
                    eU += 0.238 * ppm_dict["value"]
                    eU_err.append((0.238 * (ppm_dict["error"] / 2)) ** 2)
                elif "Sm" in r["type"]["parameter"]:
                    ppm_dict = make_ppm(r, dim_mass_val, dim_mass_err, corrected=corrected)
                    ppm_dict["analysis"] = analysis_obj
                    self.db.load_data("datum", ppm_dict)
                    eU += 0.0012 * ppm_dict["value"]
                    eU_err.append((0.0012 * (ppm_dict["error"] / 2)) ** 2)

            eu_param_name = "eU (±2σ)"
            if corrected:
                eu_param_name += ", new geometric correction"
            eU_dict = {
                "value": eU,
                # "error": eU * 0.15,
                "error": sum(eU_err) ** (1 / 2),
                "type": {
                    "parameter": eu_param_name,
                    "unit": "ppm",
                },  # (±2σ)', 'unit': 'ppm'},
                "analysis": analysis_obj,
            }
            self.db.load_data("datum", eU_dict)
            return True
        except exc.IntegrityError:
            print("Cannot overwrite existing data. Skipping sample.")
            return False

    def calc_Ft_comb(self, Fts) -> FTCombResult:
        """Calculate the combined Ft value for the sample."""
        S_238 = self.ppms["238U (±2σ)"]["value"]
        S_232 = self.ppms["232Th (±2σ)"]["value"]

        S_235 = self.ppms["235U (±2σ)"]["value"]

        a_238 = (1.04 + 0.247 * (S_232 / S_238)) ** -1
        a_232 = (1.0 + 4.21 * (S_238 / S_232)) ** -1

        # Not sure if this is correct
        a_235 = 1 - a_238 - a_232

        #suffix = ", new geometric correction"

        Ft_comb = (
            a_238 * float(Fts["238U Ft (±2σ)"].value)
            + a_232 * float(Fts["232Th Ft (±2σ)"].value)
            + a_235 * float(Fts["235U Ft (±2σ)"].value)
        )
        return FTCombResult(
            S_238=S_238,
            S_235=S_235,
            S_232=S_232,
            a_238=a_238,
            a_235=a_235,
            a_232=a_232,
            Ft_comb=Ft_comb,
        )

    def add_Ft_comb(self, analysis_obj, data: FTCombResult, corrected=False):
        # Add the combined Ft value to the database
        # Store  Ft_comb in the database
        # and then use the values to calculate ESR_Ft
        # TODO: do this for both corrected and uncorrected. We can do this by adding a suffix...
        parameter_name = "Combined Ft"
        if corrected:
            parameter_name += ", new geometric correction"

        Ft_comb_dict = {
            "value": data.Ft_comb,
            "error": None,
            "type": {"parameter": parameter_name, "unit": ""},
            "analysis": analysis_obj,
        }

        self.db.load_data("datum", Ft_comb_dict)

    def add_ESR_Ft(self, analysis_obj, data: FTCombResult, material, shape):
        # Use the values of Ft_comb to calculate ESR_Ft (R_Ft)

        # Here we will calculate ESR_Ft and it's associated uncertainty. It will call upon FT_constants defined in picking_specs.yaml
        # which are material (mineral) and isotope specific. I'll refer to these as S_238, etc, but they will need to vary depending on the mineral.

        # This should only be added for the new geometric correction
        print(material, shape)

        Sbar = (
            data.a_238 * data.S_238
            + data.a_232 * data.S_232
            + (1 - data.a_238 - data.a_235) * data.S_235
        )
        S_R = (
            1.681
            - 2.428 * data.Ft_comb
            + 1.153 * (data.Ft_comb ** 2)
            - 0.406 * (data.Ft_comb ** 3)
        )
        ESR_Ft = Sbar / S_R
        ESR_Ft_Corr = float("nan")
        ESR_Ft_Corr_err = float("nan")
        if material == "apatite":
            if shape == "Hexagonal":
                ESR_Ft_Corr = 0.93 * ESR_Ft
                ESR_Ft_Corr_err = 0.06 * ESR_Ft_Corr
            elif shape == "Ellipsoid":
                ESR_Ft_Corr = 0.85 * ESR_Ft
                ESR_Ft_Corr_err = 0.10 * ESR_Ft_Corr
        elif material == "zircon":
            if shape == "Tetragonal":
                ESR_Ft_Corr = 0.92 * ESR_Ft
                ESR_Ft_Corr_err = 0.08 * ESR_Ft_Corr
            elif shape == "Ellipsoid":
                ESR_Ft_Corr = 0.98 * ESR_Ft
                ESR_Ft_Corr_err = 0.08 * ESR_Ft_Corr
        else:
            print(f"Invalid material {material} or shape {shape}")
            return

        print(ESR_Ft_Corr, ESR_Ft_Corr_err)
        ESR_Ft_dict = {
            "value": ESR_Ft_Corr,
            "error": ESR_Ft_Corr_err,
            "type": {
                "parameter": "ESR Ft (±2σ), new geometric correction",
                "unit": "µm",
            },
            "analysis": analysis_obj,
        }

        self.db.load_data("datum", ESR_Ft_dict)
