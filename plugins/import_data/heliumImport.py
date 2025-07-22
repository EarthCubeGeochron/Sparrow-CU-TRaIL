# -*- coding: utf-8 -*-
from sparrow.core.import_helpers import BaseImporter
from macrostrat.utils import relative_path
from rich import print
import pandas as pd
import glob
from dateutil import parser
from yaml import load

from .utils import make_labID


class TRaILhelium(BaseImporter):
    def __init__(self, app, data_dir, **kwargs):
        super().__init__(app)
        file_list = glob.glob(str(data_dir) + "/HeliumData/*.txt")
        self.iterfiles(file_list, **kwargs)

    def import_datafile(self, fn, rec, **kwargs):
        data = pd.read_csv(fn, delimiter="\t")
        # trim extraneous rows (assume empty if >80% are null)
        data.drop(
            data.index[data.isnull().sum(axis=1) / len(data.columns) > 0.8],
            inplace=True,
        )

        # Load the column specs; structure is {parameter: [value col, error col, unit str]}
        spec = relative_path(__file__, "helium_specs.yaml")
        with open(spec) as f:
            self.helium_specs = load(f)

        # Split data according to whether each sample has picking information
        # the column PickingInfo is read in as a boolean, so pandas slicing can happen implicitly.
        data_new_sample = data.loc[~data["PickingInfo"]]
        data_add_he = data.loc[data["PickingInfo"]]
        # First, upload the new samples (no picking info)
        for ix, row in data_new_sample.iterrows():
            print("Importing:", row["SampleName"].split(" ")[0])
            self.create_sample(row)
        # Then, upload the samples where we expect picking info
        for ix, row in data_add_he.iterrows():
            print("Importing:", row["SampleName"].split(" ")[1])
            self.add_he(row)

    # Method to generate the helium session dictionary
    def make_session_dict(self, row):
        return {
            "technique": {"id": "Helium measurement"},
            "instrument": {"name": "Alphachron"},
            "date": str(parser.parse(row["Date"][:-5])),
            "analysis": [
                {
                    "analysis_type": "Helium measurement",
                    # Here we call the make datum and make_attribute functions
                    "datum": [
                        make_datum(row, k, v)
                        for k, v in self.helium_specs.items()
                        if v[2]
                    ],
                    "attribute": [
                        make_attribute(row, k, v)
                        for k, v in self.helium_specs.items()
                        if not v[2]
                    ],
                }
            ],
        }

    # For samples without picking info, make a new sample
    def create_sample(self, row):
        # Generate the lab ID
        date = parser.parse(row["Date"][:-5])
        lab_id = make_labID(self.db, date)
        # create the session dictionary
        session_dict = self.make_session_dict(row)
        # Create the barebones sample to add the session to
        sample_name = row["SampleName"].split(" ")[0]
        sample_schema = {
            "lab_id": lab_id,
            "name": sample_name,
            "from_archive": "false",
            "material": row["Mineral"],
            "embargo_date": "2150-01-01",
            "session": [session_dict],
        }
        # Print an empty line to keep the command line clean
        print("")
        # Load the data
        self.db.load_data("sample", sample_schema)

    # For samples with picking info, add he data to existing sample
    def add_he(self, row):
        # Get the sample ID from the sample name column
        sample_id = row["SampleName"].split(" ")[0]
        try:
            # get the same sample ID from the database
            sample_obj = (
                self.db.session.query(self.db.model.sample)
                .filter_by(lab_id=sample_id)
                .all()
            )[0]
            # Check that the sample name in the database matches the sample name in the data file
            if sample_obj.name != row["SampleName"].split(" ")[1]:
                print(
                    "Mismatched name:\n",
                    sample_obj.name,
                    "in database, but\n",
                    row["SampleName"].split(" ")[1],
                    "in importing sheet. Double-check that sample ID is correct",
                )
        # If no lab ID is found, altert the user and skip uploading
        except IndexError:
            print(
                "Sample ID for",
                row["SampleName"].split(" ")[1],
                "not found. Double-check that the IDs match.\n",
            )
            return
        # Make session dictionary
        session_dict = self.make_session_dict(row)
        # Add the sample to the session dictionary for database update
        session_dict["sample"] = sample_obj
        # look for derived data session; if present, not a shard, and can add nmol/g He
        derived_session_obj = (
            self.db.session.query(self.db.model.session)
            .filter_by(
                sample_id=sample_obj.id, technique="Dates and other derived data"
            )
            .all()
        )
        if len(derived_session_obj) > 0:
            # TODO: this add_nmol_g function contains the only place where
            # the data should change depending on geometric correction.
            self.add_nmol_g(derived_session_obj[0], session_dict)
        # Print an empty line to keep the command line clean
        print("")
        # Upload session -- this has the sample info attached, so the sample will be updated as well
        self.db.load_data("session", session_dict)

    # TODO add method to add ng/mol He to the derived data session if not a shard
    def add_nmol_g(self, derived_session_obj, session_dict):
        # This value isn't actually nano-ccs
        # This should get exactly the value that is labeled "fmols He/g" in the database...
        fmol_he = session_dict["analysis"][0]["datum"][0]["value"]
        fmol_he_s = session_dict["analysis"][0]["datum"][0]["error"]

        nmol_he = fmol_he / 1e6
        nmol_he_s = fmol_he_s / 1e6

        # This depends on picking import, which will be either corrected or
        # uncorrected
        for geo_corr in [False, True]:
            ug_mass = get_dimensional_mass(self.db, derived_session_obj, corrected=geo_corr)

            if ug_mass is None:
                _corr = "corrected" if geo_corr else "uncorrected"
                print(f"Could not find {_corr} dimensional mass in picking data sheet")

            g_mass = float(ug_mass.value) / 1e6
            nmol_g = nmol_he / g_mass
            # Upload None to database if NaN in uncertainty column
            try:
                nmol_g_s = (
                    (
                        (float(ug_mass.error) / float(ug_mass.value)) ** 2
                        + (nmol_he_s / nmol_he) ** 2
                    )
                    ** (1 / 2)
                ) * nmol_g
            except TypeError:
                nmol_g_s = None

            # Calculate/save both corrected and uncorrected values here.
            analysis_obj = (
                self.db.session.query(self.db.model.analysis)
                .filter_by(
                    session_id=derived_session_obj.id,
                    analysis_type="Rs, mass, concentrations",
                )
                .first()
            )

            name = "4He (±2σ)"
            if geo_corr:
                name += ", new geometric correction"

            datum_dict = {
                "value": nmol_g,
                "error": nmol_g_s,
                "type": {"parameter": name, "unit": "nmol/g"},
                "analysis": analysis_obj,
            }
            self.db.load_data("datum", datum_dict)


def get_dimensional_mass(db, session_obj, corrected=False):
    """
    Get dimensionsal mass for a given sample based on session pulled above
    """
    Session = db.model.session
    Analysis = db.model.analysis
    Datum = db.model.datum
    DatumType = db.model.datum_type

    suffix = ""
    if corrected:
        suffix = ", new geometric correction"

    return (
        db.session.query(Datum)
        .join(Analysis)
        .join(Session)
        .join(DatumType)
        .filter(Session.id == session_obj.id)
        .filter(DatumType.parameter == "Dimensional mass (±2σ)"+suffix)
        .first()
    )


# Make datum using info in yaml file
def make_datum(row, name, data_info):
    if data_info[1] == None:
        error = None
    elif pd.isna(row[data_info[1]]):
        error = None
    else:
        error = row[data_info[1]]
    return {
        "value": row[data_info[0]],
        "error": error,
        "type": {"parameter": name, "unit": data_info[2]},
    }


# Make attribute using info in yaml file
def make_attribute(row, name, data_info):
    return {"parameter": name, "value": str(row[data_info[0]])}
