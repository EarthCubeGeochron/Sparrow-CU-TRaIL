# -*- coding: utf-8 -*-
from sparrow.import_helpers import BaseImporter
import glob
from rich import print
import pandas as pd

# Make datum using info in yaml file
def make_datum(row, isotope):
    return {'value': row[isotope],
            'error': row.iloc[row.index.get_loc(isotope)+1],
            'type': {'parameter': isotope, 'unit': 'ng'}}

class TRaILicpms(BaseImporter):
    def __init__(self, app, data_dir, **kwargs):
        super().__init__(app)
        file_list = glob.glob(str(data_dir)+'/icpmsData/*.xlsx')
        file_list = [f for f in file_list if '$' not in f]
        self.iterfiles(file_list, **kwargs)
        
    def import_datafile(self, fn, rec, **kwargs):
        data = pd.read_excel(fn)
        
        # Iterate through rows
        for ix, row in data.iterrows():
            print('Importing:', row['Sample name'])
            # Get sample ID and do checks to ensure that it's in the database
            sample_id = row['Lab ID']
            try:
                # get the same sample ID from the database
                sample_obj = self.db.session.query(self.db.model.sample).filter_by(lab_id=sample_id).all()[0]
                # Check that the sample name in the database matches the sample name in the data file
                if sample_obj.name != row['Sample name']:
                    print('Mimatched name:\n', sample_obj.name, 'in database, but\n', row['Sample name'],
                           'in importing sheet. Double-check that sample ID is correct')
            # If no lab ID is found, altert the user and skip uploading
            except IndexError:
                print('Sample ID for', row['Sample name'], 'not found. Double-check that the IDs match.\n')
                return
            # Genearate correct date format
            date = row['Date'].to_pydatetime().isoformat()
            # Get list of columns to make datum with
            isotopes = [i for i in row.index if '(ng)' in i]
            # Make session dictionary
            session_dict = {
                "technique": {'id': "Trace element measurement"},
                "instrument": {"name": "Agilent 7900 Quadrupole ICP-MS"},
                "date": date,
                'analysis': [{
                    'analysis_type': 'Element data',
                        # Here we call the make datum and make_attribute functions
                        'datum': [make_datum(row, isotope) for isotope in isotopes],
                    }]
                }
            # Add the sample to the session dictionary for database update
            session_dict['sample'] = sample_obj
            # Print an empty line to keep the command line clean
            print('')
            # Upload session-- this has the sample info attached, so the sample will be updated as well
            self.db.load_data("session", session_dict)