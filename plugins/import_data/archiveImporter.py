from rich import print
from click import secho
from sparrow.core.import_helpers import BaseImporter
from macrostrat.utils import relative_path
from yaml import load, FullLoader
from pandas import read_excel, isna, read_csv
from re import compile
from dateutil.parser import parse
import numpy as np
import glob
import os


def split_unit(name):
    """Split units (in parentheses) from the rest of the data."""
    unit_regex = compile(r"^(.+)\s\(([a-zA-Z/\%]+)\)$")
    res = unit_regex.match(name)
    g = res.groups()
    (param, unit) = g
    return param, unit


# Identify which dicts in the list 'vals' passed to create_analysis
# are data and which are attributes. Based on whether 'Value'-keyed
# item in each dict is a float
def split_attributes(vals):
    """Split data from attributes"""
    data = []
    attributes = []
    for v in vals:
        try:
            float(v["value"])
            data.append(v)
        except ValueError:
            attributes.append(v)
    return data, attributes


datum_type_fields = [
    "parameter",
    "unit",
    "error_unit",
    "error_metric",
    "is_computed",
    "is_interpreted",
    "description",
]
attribute_fields = ["parameter", "value"]

# Make dict with Datum1 schema. Requires value, uncertainty, and 'type' which gives
# parameter measured as str, unit as str, and other type fields listed above if included
def create_datum(val):
    v = val.pop("value")
    err = val.pop("error", None)

    datum_type = {k: v for k, v in val.items() if k in datum_type_fields}
    if "unit" in datum_type:
        try:
            datum_type["unit"] = datum_type["unit"].replace("~u", "\u03BC")
        except AttributeError:
            pass

    return {"value": v, "error": err, "type": datum_type}


# Make dict with Attribute schema. Parameter measured as str and value as str
def create_attribute(val):
    return {k: v for k, v in val.items() if k in attribute_fields}


# type is a str giving a descriptive name for the kind of analysis
# vals is list of dictionaries related to the analysis, selected from
# the cleaned_data variable created by itervalues method
def create_analysis(analysis_name, vals, **kwargs):
    data, attributes = split_attributes(vals)
    return {
        "analysis_type": analysis_name,
        "datum": [create_datum(d) for d in data if d is not None],
        "attribute": [create_attribute(d) for d in attributes],
    }


class TRaILarchive(BaseImporter):
    def __init__(self, app, data_dir, **kwargs):
        super().__init__(app)
        # file_list = glob.glob(str(data_dir)+'/CompleteData/*/*.xlsx')
        # print(file_list)

        exts = ["xls", "xlsx"]
        file_list = []
        for ext in exts:
            file_list.extend(
                glob.glob(str(data_dir) + "/CompleteData/**/*." + ext, recursive=True)
            )
        # file_list = [f for f in file_list if '03_12_2021' in f or '01_07_2014' in f]

        self.image_folder = data_dir / "Photographs and Measurement Data"

        self.verbose = kwargs.pop("verbose", False)

        # Generate list of expected columns. Some include dict where the
        # expected column has key 'header', along with other relevant info
        spec = relative_path(__file__, "archive_specs.yaml")
        with open(spec) as f:
            self.column_spec = load(f)

        # Open file that specifies how to handle the Owner column, when present
        owner_key_file = relative_path(__file__, "archive_owner_keys.csv")
        self.owner_keys = read_csv(
            owner_key_file,
            usecols=["id", 'Archive data "Owner"', "Lab/Owner", "Analyst", "Date"],
        )

        self.lab_IDs = [
            el
            for tup in self.db.session.query(self.db.model.sample.lab_id).all()
            for el in tup
            if el is not None
        ]

        # Calls Sparrow base code for each file in passed list and sends to import_datafile
        self.iterfiles(file_list, **kwargs)

    def import_datafile(self, fn, rec, **kwargs):
        """
        Import an original data file
        """
        # Save file name to get date
        filename = os.path.basename(fn)  # .split('\\')[-1]
        # Allow import of varying data reduction sheets
        try:
            df = read_excel(fn, sheet_name="Complete Summary Table")
            if "Unnamed: 0" in df.columns:
                df = read_excel(fn, sheet_name="Complete Summary Table", skiprows=1)
        except ValueError:
            df = read_excel(
                fn, sheet_name="Complete Data Sheet", skiprows=2, usecols=range(56)
            )

        # Assume all rows with >80% NaNs are empty and delete
        df.drop(df.index[df.isnull().sum(axis=1) / len(df.columns) > 0.8], inplace=True)

        # Clean up missing data that contains information
        df.drop(df.index[df["Full Sample Name"] == "sample"], inplace=True)
        df.drop(df.index[df["Full Sample Name"] == "sample name"], inplace=True)
        df.drop(df.index[df["Full Sample Name"] == 0], inplace=True)
        df.drop(df.index[df["Full Sample Name"] == "0"], inplace=True)
        df.drop(df.index[isna(df["Full Sample Name"])], inplace=True)
        if len(df) == 0:
            print(fn, "contains no data")
            return

        # Geomtry field is often imported as str or float-- convert here if column present
        if "Geometry" in df.columns:
            df["Geometry"] = df["Geometry"].astype(int)

        # Get column list and shorten any headers with extra spaces
        data_cols_list = list(df.columns)
        for c in range(len(data_cols_list)):
            data_cols_list[c] = " ".join(data_cols_list[c].split())
        df = df.rename(columns=dict(zip(list(df.columns), data_cols_list)))

        # Rename and rearrange columns according to the column_spec file
        self.cols = {}
        for l in range(len(self.column_spec)):
            k = list(self.column_spec[l].keys())[0]
            found = False
            for c in data_cols_list:
                if c in self.column_spec[l][k]["names"]:
                    self.cols[c] = k
                    found = True
                    break
            if not found:
                df[k] = self.column_spec[l][k]["missing"]
                self.cols[k] = k

        # Attach uncertainty columns to data columns
        df_cols = list(df.columns)
        cols_to_keep = []
        for c in self.cols:
            cols_to_keep.append(c)
            try:
                if "±" in df_cols[df_cols.index(c) + 1]:
                    cols_to_keep.append(df_cols[df_cols.index(c) + 1])
            except IndexError:
                pass

        # Restrict data to what will be imported to avoid pulling in anything extraneous
        data = df[cols_to_keep]
        # Rename columns for consistency in downstream methods
        data = data.rename(columns=self.cols)
        # get date from file name
        digit_idx = [i for i, s in enumerate(filename) if s.isdigit()]
        try:
            date = parse(filename[digit_idx[0] : digit_idx[-1] + 1].replace("_", " "))
            date = date.strftime("%Y-%m-%d %H:%M:%S")
            self.dateerr = False
        except:
            # TODO change this to None value when allowed by Sparrow
            date = "1900-01-01 00:00:00+00"
            self.dateerr = True
            print("date error:", filename)

        # data = self.split_grain_information(data)
        for ix, row in data.iterrows():
            yield self.import_row(row, date)

    # Needs to take row as series and return list of dictionaries for each entry
    def itervalues(self, row):
        # Create empty list to add to
        row_list = []

        # Start by getting the parameter and value-- this will be in every column
        for name, val in row.iteritems():
            # Apply error by column location
            if "±" in name:
                try:
                    # Get original name to track what uncertainty applies to
                    key = [k for k, v in self.cols.items() if v == name][0]
                except:
                    key = None
                # Always append error to linear uncorrected date
                if row_list[-1]["parameter"] == "Iterated Raw Date":
                    row_list[-2]["error"] = val * 2
                    row_list[-2]["error_unit"] = None
                    row_list[-1]["error"] = val * 2
                    row_list[-1]["error_unit"] = None
                # For corrected dates, apply to both iterated and linear depending on presence of data
                elif "It" in name:
                    for i in [-2, -1]:
                        if "Not" not in str(row_list[i]["value"]):
                            if ")2" in key:
                                row_list[i]["error"] = val
                                row_list[i]["error_unit"] = None
                            else:
                                row_list[i]["error"] = val * 2
                                row_list[i]["error_unit"] = None
                        else:
                            row_list[i]["error"] = None
                            row_list[i]["error_unit"] = None
                # Otherwise, if data not reported, append nothing for error
                elif "Not" in str(row_list[-1]["value"]):
                    row_list[-2]["error"] = None
                    row_list[-2]["error_unit"] = None
                    continue
                else:
                    # Default is to add 2-sigma error if none of the above conditions are met
                    row_list[-1]["error"] = val * 2
                    row_list[-1]["error_unit"] = None
                continue

            # Get column_spec dictionary for this entry
            col_spec_dict = next(
                spec for spec in self.column_spec if list(spec.keys())[0] == name
            )[name]

            col_dict = {"parameter": name, "value": val}

            # Add possible components one at a time from the column_spec file
            if "unit" in col_spec_dict:
                col_dict["unit"] = col_spec_dict["unit"]
            else:
                try:
                    param, unit = split_unit(name)
                    col_dict["parameter"] = param
                    col_dict["unit"] = unit
                except AttributeError:
                    col_dict["unit"] = ""
            if "values" in col_spec_dict:
                col_dict["values"] = col_spec_dict["values"]
                try:
                    if val != col_spec_dict["missing"]:
                        col_dict["value"] = col_spec_dict["values"][val]
                except KeyError:
                    col_dict["value"] = col_spec_dict["values"][val]

            row_list.append(col_dict)
        return row_list

    def make_labID(self, date):
        init_digits = date[2:4]
        max_num = 1
        for i in self.lab_IDs:
            if i[:2] == init_digits:
                max_num += 1
        lab_id = str(init_digits + "-" + f"{max_num:05d}")
        self.lab_IDs.append(lab_id)
        return lab_id

    # Main method to build the sample schema. The majority of the work
    # is done by the itervalues method and create_analysis function
    def import_row(self, row, date):
        # Get a semi-cleaned set of values for each row
        # row.drop(['sample_name', 'grain'], inplace=True)
        cleaned_data = self.itervalues(row)

        # set all Ft uncertainties to 0 by hand
        cleaned_data[25]["error"] = None

        for c in cleaned_data:
            if "error" in c:
                if c["error"]:
                    c["parameter"] += " (" + "\u00B1" + "2" + "\u03C3" + ")"

        # Can't import anything that has an error in a required data column
        # For the archived data, just reject these from the database
        for d in cleaned_data:
            try:
                if np.isnan(d["value"]):
                    return
                # NaN errors are generally a divide by 0 issue in excel, caused
                # by normalization of relative error so we change them to 0
                if np.isnan(d["error"]):
                    d["error"] = 0
            except (TypeError, KeyError):
                pass

        [researcher, sample] = cleaned_data[0:2]

        material = cleaned_data[8]

        # Convert missing Th and Sm values to 'N.M.'
        if cleaned_data[16]["value"] == 0 and material["value"] == "zircon":
            cleaned_data[16]["value"] = "N.M."
            cleaned_data[16]["error"] = None
            cleaned_data[20]["value"] = "N.M."
            cleaned_data[20]["error"] = None
        if cleaned_data[17]["value"] == 0 and material["value"] == "zircon":
            cleaned_data[17]["value"] = "N.M."
            cleaned_data[17]["error"] = None
            cleaned_data[21]["value"] = "N.M."
            cleaned_data[21]["error"] = None

        shape_data = cleaned_data[2:8]
        grain_data = [cleaned_data[11]]
        helium_data = cleaned_data[13:15]
        icpms_data = cleaned_data[19:22]
        ft_data = [cleaned_data[25]]
        other_data = (
            [cleaned_data[10]]
            + [cleaned_data[9]]
            + [cleaned_data[12]]
            + cleaned_data[15:19]
            + [cleaned_data[22]]
        )
        date_data = cleaned_data[23:25] + cleaned_data[26:28]

        # We should figure out how to not require meaningless dates
        meaningless_date = "1900-01-01 00:00:00+00"

        lab_id = self.make_labID(date)

        # Build sample schema using row of imported data
        sample = {
            "name": row["Full Sample Name"],
            "material": str(material["value"]),
            "lab_id": lab_id,
            "from_archive": "true",
            "embargo_date": "2150-01-01",
            # Here we pass a list of dicts instead of a single dict
            # because each (U-Th)/He analysis consists of three
            # individual sessions
            "session": [
                {
                    "technique": {"id": "Picking information"},
                    "instrument": {"name": "Leica microscope"},
                    "date": meaningless_date,
                    # analysis is passed a list of dicts, where each dict is displayed
                    # as a single box on the front end. create_analysis function is
                    # critical to the bulk of information ultimately included in Sparrow
                    "analysis": [
                        create_analysis("Grain dimensions & shape", shape_data),
                        create_analysis("Grain characteristics", grain_data),
                    ],
                },
                {
                    "technique": {"id": "Helium measurement"},
                    "instrument": {"name": "Alphachron"},
                    "date": meaningless_date,
                    "analysis": [create_analysis("Helium measurement", helium_data)],
                },
                {
                    "technique": {"id": "ICP-MS measurement"},
                    "instrument": {"name": "Agilent 7900 Quadrupole ICP-MS"},
                    "date": meaningless_date,
                    "analysis": [
                        create_analysis("Sample data (blank corrected)", icpms_data)
                    ],
                },
                {
                    "technique": {"id": "Dates and other derived data"},
                    "date": date,
                    "analysis": [
                        create_analysis("Alpha ejection correction values", ft_data),
                        create_analysis("Rs, mass, concentrations", other_data),
                        create_analysis("Date", date_data),
                    ],
                },
            ],
        }

        # Add owner and analyst to schema if present
        if researcher["value"] != "Not recorded":
            owner_values = self.owner_keys.loc[
                self.owner_keys['Archive data "Owner"'] == researcher["value"]
            ]
            if isna(owner_values["Date"].iloc[0]):
                sample["lab_owner"] = owner_values["Lab/Owner"].item()
                sample["researcher"] = [{"name": owner_values["Analyst"].item()}]
            elif not self.dateerr:
                if int(owner_values["Date"].iloc[0][-4:]) > int(date[:4]):
                    sample["lab_owner"] = owner_values["Lab/Owner"].iloc[0]
                    sample["researcher"] = [{"name": owner_values["Analyst"].iloc[0]}]
                else:
                    sample["lab_owner"] = owner_values["Lab/Owner"].iloc[1]
                    sample["researcher"] = [{"name": owner_values["Analyst"].iloc[1]}]
        else:
            sample["Lab_Owner"] = "Not recorded"

        res = self.db.load_data("sample", sample)

        print("")
        return res
