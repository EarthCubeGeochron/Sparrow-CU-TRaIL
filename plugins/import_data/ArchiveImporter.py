from rich import print
from click import secho
from sparrow.import_helpers import BaseImporter
from sparrow.util import relative_path
from sparrow.import_helpers.util import ensure_sequence
from yaml import load, FullLoader
from pandas import read_excel, isna
from re import compile
from IPython import embed
from dateutil.parser import parse
import datetime
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

# Identify which dicts in the list "vals" passed to create_analysis
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

# Make dict with Datum1 schema. Requires value, uncertainty, and "type" which gives
# parameter measured as str, unit as str, and other type fields listed above if included
def create_datum(val):
    v = val.pop("value")
    err = val.pop("error", None)

    datum_type = {k: v for k, v in val.items() if k in datum_type_fields}
    if 'unit' in datum_type:
        try:
            datum_type['unit'] = datum_type['unit'].replace('~u', '\u03BC')
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
        'analysis_type': analysis_name,
        'datum': [create_datum(d) for d in data if d is not None],
        'attribute': [create_attribute(d) for d in attributes]
    }

class TRaILImporter(BaseImporter):
    def __init__(self, app, data_dir, **kwargs):
        super().__init__(app)
        # file_list = glob.glob(str(data_dir)+'/CompleteData/*/*.xlsx')
        # print(file_list)
        
        exts = ['xls', 'xlsx']
        file_list = []
        for ext in exts:
            file_list.extend(glob.glob(str(data_dir)+'/CompleteData/**/*.'+ext, recursive=True))
        file_list = [f for f in file_list if '03_12_2021' in f or '01_07_2014' in f]
        
        self.image_folder = data_dir / "Photographs and Measurement Data"

        self.verbose = kwargs.pop("verbose", False)
        
        # Generate list of expected columns. Some include dict where the
        # expected column has key "header", along with other relevant info
        spec = relative_path(__file__, "column-spec.yaml")
        with open(spec) as f:
            self.column_spec = load(f)
                
        self.lab_IDs = [el for tup in self.db.session.query(self.db.model.sample.lab_id).all() for el in tup if el is not None]
                
        # Calls Sparrow base code for each file in passed list and sends to import_datafile
        self.iterfiles(file_list, **kwargs)

    def import_datafile(self, fn, rec, **kwargs):
        """
        Import an original data file
        """
        # Save file name to get date
        filename = os.path.basename(fn)#.split('\\')[-1]
        # Allow import of varying data reduction sheets
        try:
            df = read_excel(fn, sheet_name="Complete Summary Table")
            if 'Unnamed: 0' in df.columns:
                df = read_excel(fn, sheet_name="Complete Summary Table", skiprows=1)
        except ValueError:
            df = read_excel(fn, sheet_name="Complete Data Sheet", skiprows=2, usecols=range(56))
        
        # Assume all rows with >80% NaNs are empty and delete
        df.drop(df.index[df.isnull().sum(axis=1)/len(df.columns)>0.8], inplace=True)

        # Clean up missing data that contains information
        df.drop(df.index[df['Full Sample Name'] == 'sample'], inplace=True)
        df.drop(df.index[df['Full Sample Name'] == 'sample name'], inplace=True)
        df.drop(df.index[df['Full Sample Name'] == 0], inplace=True)
        df.drop(df.index[df['Full Sample Name'] == '0'], inplace=True)
        df.drop(df.index[isna(df['Full Sample Name'])], inplace=True)
        if len(df) == 0:
            print(fn, 'contains no data')
            return
        
        # Geomtry field is often imported as str or float-- convert here if column present
        if 'Geometry' in df.columns:
            df['Geometry'] = df['Geometry'].astype(int)
            
        # Get column list and shorten any headers with extra spaces
        data_cols_list = list(df.columns)
        for c in range(len(data_cols_list)):
            data_cols_list[c] = ' '.join(data_cols_list[c].split())
        df = df.rename(columns=dict(zip(list(df.columns),data_cols_list)))
                
        # Rename and rearrange columns according to the column_spec file
        cols = {}
        for l in range(len(self.column_spec)):
            k = list(self.column_spec[l].keys())[0]
            found = False
            for c in data_cols_list:
                if c in self.column_spec[l][k]['names']:
                    cols[c] = k
                    found = True
                    break
            if not found:
                df[k] = self.column_spec[l][k]['missing']
                cols[k] = k
        
        # Attach uncertainty columns to data columns
        df_cols = list(df.columns)
        cols_to_keep = []
        for c in cols:
            cols_to_keep.append(c)
            try:
                if '±' in df_cols[df_cols.index(c)+1]:
                    cols_to_keep.append(df_cols[df_cols.index(c)+1])
            except IndexError:
                pass

        # Restrict data to what will be imported to avoid pulling in anything extraneous
        data = df[cols_to_keep]
        # Rename columns for consistency in downstream methods
        data = data.rename(columns=cols)
        
        # get date from file name
        digit_idx = [i for i, s in enumerate(filename) if s.isdigit()]
        try:
            date = parse(filename[digit_idx[0]:digit_idx[-1]+1].replace('_', ' '))
            date = date.strftime('%Y-%m-%d %H:%M:%S')
        except:
            # TODO change this to None value when allowed by Sparrow
            date = "1900-01-01 00:00:00+00"
            print('date error:', filename)
        
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
            if '±' in name:
                # Always append error to linear uncorrected date
                if row_list[-1]['parameter'] == 'Iterated Raw Date':
                    row_list[-2]['error'] = val
                    row_list[-2]['error_unit'] = None
                    row_list[-1]['error'] = val
                    row_list[-1]['error_unit'] = None
                # For corrected dates, apply to both iterated and linear depending on presence of data
                elif 'It' in name:
                    for i in [-2, -1]:
                        if 'Not' not in str(row_list[i]['value']):
                            row_list[i]['error'] = val
                            row_list[i]['error_unit'] = None
                        else:
                            row_list[i]['error'] = None
                            row_list[i]['error_unit'] = None
                # Otherwise, if data not reported, append nothing for error
                elif 'Not' in str(row_list[-1]['value']):
                    row_list[-2]['error'] = None
                    row_list[-2]['error_unit'] = None
                    continue
                else:
                    # Default is to add error if none of the above conditions are met
                    row_list[-1]['error'] = val
                    row_list[-1]['error_unit'] = None
                continue
            
            # Get column_spec dictionary for this entry
            col_spec_dict = next(spec for spec in self.column_spec if list(spec.keys())[0] == name)[name]
            
            col_dict = {'parameter': name,
                        'value': val}
            
            # Add possible components one at a time from the column_spec file
            if 'unit' in col_spec_dict:
                col_dict['unit'] = col_spec_dict['unit']
            else:
                try:
                    col_dict['unit'] = split_unit(name)[1]
                except AttributeError:
                    col_dict['unit'] = 'Dimensionless'
            if 'values' in col_spec_dict:
                col_dict['values'] = col_spec_dict['values']
                try:
                    if val != col_spec_dict['missing']:
                        col_dict['value'] = col_spec_dict['values'][val]
                except KeyError:
                    col_dict['value'] = col_spec_dict['values'][val]
            
            row_list.append(col_dict)
        return row_list
    
    def make_labID(self, date):
        init_digits = date[2:4]
        max_num = 1
        for i in self.lab_IDs:
            if i[:2] == init_digits:
                max_num +=1
        lab_id = str(init_digits+'-'+f'{max_num:05d}')
        self.lab_IDs.append(lab_id)
        return lab_id

    # Main method to build the sample schema. The majority of the work
    # is done by the itervalues method and create_analysis function
    def import_row(self, row, date):
        # Get a semi-cleaned set of values for each row
        # row.drop(['sample_name', 'grain'], inplace=True)
        cleaned_data = self.itervalues(row)
        
        # Can't import anything that has an error in a required data column
        # For the archived data, just reject these from the database
        for d in cleaned_data:
            try:
                if np.isnan(d['value']):
                    return
                # NaN errors are generally a divide by 0 issue in excel, caused
                # by normalization of relative error so we change them to 0
                if np.isnan(d['error']):
                    d['error'] = 0
            except (TypeError, KeyError):
                pass
        
        [researcher, sample] = cleaned_data[0:2]
        
        # Split the data into groups (with known index) to load
        picking_info = cleaned_data[2:12]
        shape_data = picking_info[:6]
        grain_data = picking_info[6:]
        noble_gas_data = cleaned_data[12:15]
        icp_ms_data = cleaned_data[15:23]
        if icp_ms_data[2]['value'] == 0 and grain_data[0]['value'] == 'zircon':
            icp_ms_data[2]['value'] = 'N.M.'
            icp_ms_data[2]['error'] = None
            icp_ms_data[6]['value'] = 'N.M.'
            icp_ms_data[6]['error'] = None
        if icp_ms_data[1]['value'] == 0 and grain_data[0]['value'] == 'zircon':
            icp_ms_data[1]['value'] = 'N.M.'
            icp_ms_data[1]['error'] = None
            icp_ms_data[5]['value'] = 'N.M.'
            icp_ms_data[5]['error'] = None
        date_data = cleaned_data[23:]
        ft_data = [date_data[2]]
        raw_date = date_data[:2]
        corr_date = date_data[3:]

        material = grain_data.pop(0)

        # We should figure out how to not require meaningless dates
        meaningless_date = "1900-01-01 00:00:00+00"
        
        lab_id = self.make_labID(date)

        # Build sample schema using row of imported data
        sample = {
            "name": row["Full Sample Name"],
            "material": str(material["value"]),
            "lab_id": lab_id,
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
                        create_analysis("Grain shape", shape_data),
                        create_analysis("Grain characteristics", grain_data)
                    ]
                },
                {
                    "technique": {"id": "Noble gas mass spectrometry"},
                    "instrument": {"name": "ASI Alphachron → Pfeiffer Balzers QMS"},
                    "date": meaningless_date,
                    "analysis": [
                        create_analysis("Noble gas measurements", noble_gas_data)
                    ]
                },
                {
                    "technique": "Trace element measurement",
                    "instrument": {"name": "Agilent 7900 Quadrupole ICP-MS"},
                    "date": meaningless_date,
                    "analysis": [
                        create_analysis("Element data", icp_ms_data)
                    ]
                },
                {
                    # Ideally we'd provide a date but we don't really have one
                    "technique": {"id": "(U-Th)/He date calculation"},
                    "date": date,
                    "analysis": [
                        create_analysis("Alpha Ejection Correction", ft_data),
                        create_analysis("Raw date", raw_date),
                        create_analysis("Corrected date", corr_date)
                    ],
                }
            ]
        }
        
        # Add owner and analyst to schema if present
        # TODO make this more advanced by reference to researcher values csv/yaml
        if researcher != 'Not recorded':
            sample['laboratory'] = researcher['value']
            sample['researcher'] = {'name': researcher['value']}
        
        res = self.db.load_data("sample", sample)

        print("")
        return res
