# -*- coding: utf-8 -*-
from sparrow.import_helpers import BaseImporter
from sparrow.util import relative_path
from rich import print
import pandas as pd
import glob
from yaml import load

# Make datum using info in yaml file
def make_datum(row, name, data_info):
    return {'value': row[data_info[0]],
            'error': None if data_info[1] == None else row[data_info[1]],
            'type': {'parameter': name, 'unit': data_info[2]}}

# Make attribute using info in yaml file
def make_attribute(row, name, data_info):
    return {'parameter': name,
            'value': str(row[data_info[0]])}


class TRaILhelium(BaseImporter):
    def __init__(self, app, data_dir, **kwargs):
        super().__init__(app)
        file_list = glob.glob(str(data_dir)+'/heliumData/test_He_import.xlsx')
        self.iterfiles(file_list, **kwargs)

    # Method to generate a lab ID for a new sample based on the date of the analysis
    def make_labID(self, row):
        date = str(row['Date'].year)[-2:]
        # Query database for all lab IDs
        all_IDs = [el for tup in self.db.session.query(self.db.model.sample.lab_id).all() for el in tup if el is not None]
        # Isolate lab IDs from the same year
        same_year = [i for i in all_IDs if date+'-' in i]
        # Get the highest numbered analysis for the year and add 1
        if len(same_year) > 0:
            max_num = max([int(i.split('-')[1]) for i in same_year])
        else:
            max_num = 0
        id_num = max_num+1
        # Combine year and analysis number to get lab_id
        lab_id = date+'-'+f'{id_num:05d}'
        return lab_id

    def import_datafile(self, fn, rec, **kwargs):
        data = pd.read_excel(fn)
        
        # Load the column specs; structure is {parameter: [value col, error col, unit str]}
        spec = relative_path(__file__, "helium-specs.yaml")
        with open(spec) as f:
            self.picking_specs = load(f)
        
        # Split data according to whether each sample has picking information
        data_new_sample = data.loc[data['Expect picking?'] == 'N']
        data_add_he = data.loc[data['Expect picking?'] == 'Y']
        # First, upload the new samples (no picking info)
        for ix, row in data_new_sample.iterrows():
            print('Importing:', row['Sample'].split(' ')[0])
            self.create_sample(row)
        # Then, upload the samples where we expect picking info
        for ix, row in data_add_he.iterrows():
            print('Importing:', row['Sample'].split(' ')[1])
            self.add_he(row)
    
    # Method to generate the helium session dictionary
    def make_session_dict(self, row):
        return {
            'technique': {'id': 'Helium measurement'},
            'instrument': {'name': 'Alphachron'},
            'date': row['Date'].to_pydatetime().isoformat(),
            'analysis': [{
                'analysis_type': 'Helium measurement',
                    # Here we call the make datum and make_attribute functions
                    'datum': [make_datum(row, k, v) for k, v in self.picking_specs.items() if v[2]],
                    'attribute': [make_attribute(row, k, v) for k, v in self.picking_specs.items() if not v[2]]
                }]
            }
    
    # For samples without picking info, make a new sample
    def create_sample(self, row):
        # Generate the lab ID
        lab_id = self.make_labID(row)
        # create the session dictionary
        session_dict = self.make_session_dict(row)
        # Create the barebones sample to add the session to
        sample_name = row['Sample'].split(' ')[0]
        sample_schema = {
            'lab_id': lab_id,
            'name': sample_name,
            'material': row['Mineral'],
            'session': [session_dict]
            }
        # Print an empty line to keep the command line clean
        print('')
        # Load the data
        self.db.load_data("sample", sample_schema)
    
    # For samples with picking info, add he data to existing sample
    def add_he(self, row):
        # Get the sample ID from the sample name column
        sample_id = row['Sample'].split(' ')[0]
        try:
            # get the same sample ID from the database
            sample_obj = self.db.session.query(self.db.model.sample).filter_by(lab_id=sample_id).all()[0]
            # Check that the sample name in the database matches the sample name in the data file
            if sample_obj.name != row['Sample'].split(' ')[1]:
                print('Mimatched name:\n', sample_obj.name, 'in database, but\n', row['Sample'].split(' ')[1],
                       'in importing sheet. Double-check that sample ID is correct')
        # If no lab ID is found, altert the user and skip uploading
        except IndexError:
            print('Sample ID for', row['Sample'].split(' ')[1], 'not found. Double-check that the IDs match.\n')
            return
        # Make session dictionary
        session_dict = self.make_session_dict(row)
        # Add the sample to the session dictionary for database update
        session_dict['sample'] = sample_obj
        # Print an empty line to keep the command line clean
        print('')
        # Upload session-- this has the sample info attached, so the sample will be updated as well
        self.db.load_data("session", session_dict)