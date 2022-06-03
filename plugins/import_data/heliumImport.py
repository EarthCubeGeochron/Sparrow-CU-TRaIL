# -*- coding: utf-8 -*-
from sparrow.import_helpers import BaseImporter
from sparrow.util import relative_path
from rich import print
import pandas as pd
import glob
from dateutil import parser
from yaml import load

# Make datum using info in yaml file
def make_datum(row, name, data_info):
    if data_info[1] == None:
        error = None
    elif pd.isna(row[data_info[1]]):
        error = None
    else:
        error = row[data_info[1]]
    return {'value': row[data_info[0]],
            'error': error,
            'type': {'parameter': name, 'unit': data_info[2]}}

# Make attribute using info in yaml file
def make_attribute(row, name, data_info):
    return {'parameter': name,
            'value': str(row[data_info[0]])}


class TRaILhelium(BaseImporter):
    def __init__(self, app, data_dir, **kwargs):
        super().__init__(app)
        file_list = glob.glob(str(data_dir)+'/heliumData/21HE39_2022_05_19_sparrow.txt')
        self.iterfiles(file_list, **kwargs)

    # Method to generate a lab ID for a new sample based on the date of the analysis
    def make_labID(self, row):
        date = str(parser.parse(row['Date'][:-5]).year)[-2:]
        # Query database for all lab IDs
        all_IDs = [el for tup in self.db.session.query(self.db.model.sample.lab_id).all()
                   for el in tup if el is not None]
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
        data = pd.read_csv(fn, delimiter = '\t')
        
        # Load the column specs; structure is {parameter: [value col, error col, unit str]}
        spec = relative_path(__file__, 'helium-specs.yaml')
        with open(spec) as f:
            self.picking_specs = load(f)
        
        # Split data according to whether each sample has picking information
        # the column PickingInfo is read in as a boolean, so pandas slicing can happen implicitly.
        data_new_sample = data.loc[~data['PickingInfo']]
        data_add_he = data.loc[data['PickingInfo']]
        # First, upload the new samples (no picking info)
        for ix, row in data_new_sample.iterrows():
            print('Importing:', row['SampleName'].split(' ')[0])
            self.create_sample(row)
        # Then, upload the samples where we expect picking info
        for ix, row in data_add_he.iterrows():
            print('Importing:', row['SampleName'].split(' ')[1])
            self.add_he(row)
    
    # Method to generate the helium session dictionary
    def make_session_dict(self, row):
        return {
            'technique': {'id': 'Helium measurement'},
            'instrument': {'name': 'Alphachron'},
            'date': str(parser.parse(row['Date'][:-5])),
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
            'from_archive': 'false',
            'material': row['Mineral'],
            'session': [session_dict]
            }
        # Print an empty line to keep the command line clean
        print('')
        # Load the data
        self.db.load_data('sample', sample_schema)
    
    # For samples with picking info, add he data to existing sample
    def add_he(self, row):
        # Get the sample ID from the sample name column
        sample_id = row['SampleName'].split(' ')[0]
        try:
            # get the same sample ID from the database
            sample_obj = (self.db.session
                          .query(self.db.model.sample)
                          .filter_by(lab_id=sample_id)
                          .all())[0]
            # Check that the sample name in the database matches the sample name in the data file
            if sample_obj.name != row['SampleName'].split(' ')[1]:
                print('Mimatched name:\n',
                      sample_obj.name, 'in database, but\n',
                      row['SampleName'].split(' ')[1],
                       'in importing sheet. Double-check that sample ID is correct')
        # If no lab ID is found, altert the user and skip uploading
        except IndexError:
            print('Sample ID for', row['SampleName'].split(' ')[1],
                  'not found. Double-check that the IDs match.\n')
            return
        # Make session dictionary
        session_dict = self.make_session_dict(row)
        # Add the sample to the session dictionary for database update
        session_dict['sample'] = sample_obj
        # look for derived data session; if present, not a shard, and can add nmol/g He
        derived_session_obj = (self.db.session
                               .query(self.db.model.session)
                               .filter_by(sample_id=sample_obj.id,
                                          technique='Dates and other derived data')
                               .all())
        if len(derived_session_obj)>0:
            self.add_nmol_g(derived_session_obj[0], session_dict)
        # Print an empty line to keep the command line clean
        print('')
        # Upload session-- this has the sample info attached, so the sample will be updated as well
        self.db.load_data('session', session_dict)
    
    # Get dimensionsal mass for a given sample based on session pulled above
    def query_shard(self, session_obj):
        Session = self.db.model.session
        Analysis = self.db.model.analysis
        Datum = self.db.model.datum
        DatumType = self.db.model.datum_type
        res = (self.db.session.query(Datum)
               .join(Analysis)
               .join(Session)
               .join(DatumType)
               .filter(Session.id == session_obj.id)
               .filter(DatumType.parameter == 'Dimensional mass')
               .first())
        return res
    
    # TODO add method to add ng/mol He to the derived data session if not a shard
    def add_nmol_g(self, derived_session_obj, session_dict):
        ncc_he = session_dict['analysis'][0]['datum'][0]['value']
        ncc_he_s = session_dict['analysis'][0]['datum'][0]['error']
        nmol_he = ncc_he/22413.6
        ug_mass = self.query_shard(derived_session_obj)
        nmol_g = (nmol_he*1e6)/float(ug_mass.value)
        # Upload None to database if NaN in uncertainty column
        try:
            nmol_g_s = (((float(ug_mass.error)/float(ug_mass.value))**2+
                        (ncc_he_s/ncc_he)**2)**(1/2))*nmol_g
        except TypeError:
            nmol_g_s = None
        
        analysis_obj = (self.db.session
                        .query(self.db.model.analysis)
                        .filter_by(session_id=derived_session_obj.id,
                                   analysis_type='Rs, mass, concentrations')
                        .first())
        datum_dict = {'value': nmol_g, 'error': nmol_g_s,
                      'type': {'parameter': '4He', 'unit': 'nmol/g'},
                      'analysis': analysis_obj}
        self.db.load_data('datum', datum_dict)