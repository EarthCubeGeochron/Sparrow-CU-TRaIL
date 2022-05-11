# -*- coding: utf-8 -*-
from sparrow.import_helpers import BaseImporter
import glob
from rich import print
import pandas as pd
import re

# Make datum using info in yaml file
def make_datum(row, isotope):
    unit = re.search(r"\((\w+)\)", isotope).group(1)
    return {'value': row[isotope],
            'error': row.iloc[row.index.get_loc(isotope)+1],
            'type': {'parameter': isotope.split(' (')[0], 'unit': unit}}

class TRaILicpms(BaseImporter):
    def __init__(self, app, data_dir, **kwargs):
        super().__init__(app)
        file_list = glob.glob(str(data_dir)+'/icpmsData/*.xlsx')
        file_list = [f for f in file_list if '$' not in f]
        
        # Get Dimensional mass ID
        self.dim_mass_id = self.db.session.query(self.db.model.datum_type).filter_by(parameter='Dimensional mass').all()[0].id
        
        self.iterfiles(file_list, **kwargs)
        
    def import_datafile(self, fn, rec, **kwargs):
        data = pd.read_excel(fn)
        
        # Iterate through rows
        for ix, row in data.iterrows():
            print('Importing:', row['Sample'].split(' ')[1])
            # Get sample ID and do checks to ensure that it's in the database
            sample_id = row['Sample'].split(' ')[0]
            try:
                # get the same sample ID from the database
                sample_obj = self.db.session.query(self.db.model.sample).filter_by(lab_id=sample_id).all()[0]
                # Check that the sample name in the database matches the sample name in the data file
                if sample_obj.name != row['Sample'].split(' ')[1]:
                    print('Mimatched name:\n', sample_obj.name, 'in database, but\n', row['Sample'].split(' ')[1],
                           'in importing sheet. Double-check that sample ID is correct')
            # If no lab ID is found, alert the user and skip uploading
            except IndexError:
                print('Sample ID for', row['Sample name'], 'not found. Double-check that the IDs match.\n')
                return
            # Genearate correct date format
            date = row['Date'].to_pydatetime().isoformat()
            # Get list of columns to make datum with. Identify which columns are isotopes based on presence
            # of prentheses, which indicate that there is a unit to pull out
            isotopes = [i for i in row.index if '(' in i]
            raw_data = [make_datum(row, isotope) for isotope in isotopes]
            
            # Make session dictionary
            session_dict = {
                "technique": {'id': "Trace element measurement"},
                "instrument": {"name": "Agilent 7900 Quadrupole ICP-MS"},
                "date": date,
                'analysis': [{
                    'analysis_type': 'Element data',
                        # Here we call the make datum and make_attribute functions
                        'datum': raw_data,
                    }]
                }
            
            # look for whether a dimensional mass is recorded in Sparrow to permit ppm conversion
            try:
                make_ppm = True
                sample_int_id = self.db.session.query(self.db.model.sample).filter_by(lab_id=sample_id).all()[0].id
                picking = self.db.session.query(self.db.model.session).filter_by(sample_id=sample_int_id, technique='Picking Information').all()
                analysis = self.db.session.query(self.db.model.analysis).filter_by(session_id = picking[0].id, analysis_type='Grain Characteristics').all()
                dim_mass = self.db.session.query(self.db.model.datum).filter_by(type = self.dim_mass_id, analysis=analysis[0].id).all()[0]
                dim_mass_val = float(dim_mass.value)
                dim_mass_err = float(dim_mass.error)
            except IndexError:
                make_ppm = False
            
            # Generate ppm values
            if make_ppm:
                ppm_data = []
                for dat in raw_data:
                    if dat['type']['unit'] == 'ng' and 'lank' not in dat['type']['parameter']:
                        ppm = (dat['value']/dim_mass_val)*1000
                        # Get ppm uncertainty from combination of mass and nuclide amount uncertainty
                        ppm_s = ppm*((dat['error']/dat['value'])**2+(dim_mass_err/dim_mass_val)**2)**(1/2)
                        ppm_data.append({'value': ppm,
                                         'error': ppm_s,
                                         'type': {'parameter': dat['type']['parameter'], 'unit': 'ppm'}})
                # Calculate eU and uncertainty from ppm values just created
                eU = 0
                eU_err = []
                for d in ppm_data:
                    if 'U' in d['type']['parameter']:
                        eU += d['value']
                        eU_err.append(d['error']**2)
                    elif 'Th' in d['type']['parameter']:
                        eU += 0.238*d['value']
                        eU_err.append((0.238*d['error'])**2)
                    elif 'Sm' in d['type']['parameter']:
                        eU += 0.0012*d['value']
                        eU_err.append((0.0012*d['error'])**2)
                ppm_data.append({'value': eU,
                                 'error': sum(eU_err)**(1/2),
                                 'type': {'parameter': 'eU', 'unit': 'ppm'}})
                # Add the ppm data to the ICPMS session
                session_dict['analysis'].append({'analysis_type': 'Derived Data',
                                                 'datum': ppm_data})
            
            # Add the sample to the session dictionary for database update
            session_dict['sample'] = sample_obj
            # Print an empty line to keep the command line clean
            print('')
            # Upload session-- this has the sample info attached, so the sample will be updated as well
            self.db.load_data("session", session_dict)