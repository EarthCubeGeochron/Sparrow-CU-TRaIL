# -*- coding: utf-8 -*-
from sparrow.import_helpers import BaseImporter
import glob
from rich import print
import pandas as pd
import re
from dateutil import parser

# Make datum using info in yaml file
def make_datum(row, isotope):
    unit = re.search(r'\((\w+)\)', isotope).group(1)
    return {'value': row[isotope],
            'error': row.iloc[row.index.get_loc(isotope)+1],
            'type': {'parameter': isotope.split(' (')[0]+ ' (±2σ)', 'unit': unit}}

def make_ppm(data, dim_mass_val, dim_mass_err):
    ppm = (data['value']/dim_mass_val)*1000
    # Get ppm uncertainty from combination of mass and nuclide amount uncertainty
    try:
        ppm_s = ppm*(((data['error']/2)/data['value'])**2+((dim_mass_err/2)/dim_mass_val)**2)**(1/2)
    except:
        ppm_s = 0
    return {'value': ppm, 'error': ppm_s*2,
            'type': {'parameter': data['type']['parameter'], 'unit': 'ppm'}}

class TRaILicpms(BaseImporter):
    def __init__(self, app, data_dir, **kwargs):
        super().__init__(app)
        file_list = glob.glob(str(data_dir)+'/IcpmsData/*.txt')
        
        self.iterfiles(file_list, **kwargs)
    
    def query_analysis(self, lab_id, analysis_name):
        Session = self.db.model.session
        Sample = self.db.model.sample
        Analysis = self.db.model.analysis
        res = (self.db.session.query(Analysis)
               .join(Session)
               .join(Sample)
               .filter(Sample.lab_id == lab_id)
               .filter(Analysis.analysis_type == analysis_name)
               .first())
        return res

    def query_datum(self, lab_id, datum_param):
        Session = self.db.model.session
        Sample = self.db.model.sample
        Analysis = self.db.model.analysis
        Datum = self.db.model.datum
        DatumType = self.db.model.datum_type
        res = (self.db.session.query(Datum)
               .join(Analysis)
               .join(Session)
               .join(Sample)
               .join(DatumType)
               .filter(Sample.lab_id == lab_id)
               .filter(DatumType.parameter == datum_param)
               .first())
        return res

    def import_datafile(self, fn, rec, **kwargs):
        # data = pd.read_excel(fn)
        data = pd.read_csv(fn, delimiter = '\t')
        # trim extraneous rows (assume empty if >80% are null)
        data.drop(data.index[data.isnull().sum(axis=1)/len(data.columns)>0.8], inplace=True)
        
        # Iterate through rows
        for ix, row in data.iterrows():
            print('Importing:', row['Sample'].split(' ')[1])
            # Get sample ID and do checks to ensure that it's in the database
            sample_id = row['Sample'].split(' ')[0]
            try:
                # get the same sample ID from the database
                sample_obj = (self.db.session
                              .query(self.db.model.sample)
                              .filter_by(lab_id=sample_id)
                              .all())[0]
                # Check that the sample name in the database matches the sample name in the data file
                if sample_obj.name != row['Sample'].split(' ')[1]:
                    print('Mimatched name:\n',
                          sample_obj.name, 'in database, but\n',
                          row['Sample'].split(' ')[1],
                          'in importing sheet. Double-check that sample ID is correct')
            # If no lab ID is found, alert the user and skip uploading
            except IndexError:
                print('Sample ID for', row['Sample name'],
                      'not found. Double-check that the IDs match.\n')
                return
            # Genearate correct date format
            date = parser.parse(row['Date'])
            # Get list of columns to make datum with. Identify which columns are isotopes based on presence
            # of prentheses, which indicate that there is a unit to pull out
            isotopes = [i for i in row.index if '(' in i and 'lank' not in i]
            blanks = [i for i in row.index if '(' in i and 'lank' in i]
            raw_data = [make_datum(row, isotope) for isotope in isotopes]
            blank_data = [make_datum(row, blank) for blank in blanks]
            
            # Make session dictionary
            session_dict = {
                'technique': {'id': 'ICP-MS measurement'},
                'instrument': {'name': 'Agilent 7900 Quadrupole ICP-MS'},
                'date': date,
                'analysis': [{
                    'analysis_type': 'Sample data (blank corrected)',
                    # Here we call the make datum and make_attribute functions
                    'datum': raw_data
                    },
                    {
                    'analysis_type': 'Blank data',
                    # Here we call the make datum and make_attribute functions
                    'datum': blank_data
                    }]
                }
            session_dict['sample'] = sample_obj
            self.db.load_data('session', session_dict)
            
            # look for whether a dimensional mass is recorded in Sparrow to permit ppm conversion
            ppm_analysis = self.query_analysis(sample_id, 'Rs, mass, concentrations')
            dim_mass = self.query_datum(sample_id, 'Dimensional mass (±2σ)')
            ft_analysis = self.query_analysis(sample_id, 'Alpha ejection correction values')
            Fts = {'238U Ft (±2σ)': None, '235U Ft (±2σ)': None, '232Th Ft (±2σ)': None, '147Sm Ft (±2σ)': None}
            for Ft in Fts:
                Fts[Ft] = self.query_datum(sample_id, Ft)
            if dim_mass:
                self.add_ppm(raw_data, dim_mass, ppm_analysis)
                self.add_Ft_comb(ft_analysis, Fts)
                print('')
            else:
                print('')

    # Generate ppm values and add to existing derived data session
    def add_ppm(self, raw_data, dim_mass, analysis_obj):
        dim_mass_val = float(dim_mass.value)
        dim_mass_err = float(dim_mass.error)
        
        radionuclides = [d for d in raw_data if d['type']['unit'] == 'ng']
        
        # Generate ppm values
        eU = 0
        eU_err = []
        self.ppms = {}
        
        for r in radionuclides:
            if 'U' in r['type']['parameter']:
                ppm_dict = make_ppm(r, dim_mass_val, dim_mass_err)
                ppm_dict['analysis'] = analysis_obj
                self.ppms[r['type']['parameter']] = ppm_dict
                self.db.load_data('datum', ppm_dict)
                eU += ppm_dict['value']
                eU_err.append((ppm_dict['error']/2)**2)
            elif 'Th' in r['type']['parameter']:
                ppm_dict = make_ppm(r, dim_mass_val, dim_mass_err)
                ppm_dict['analysis'] = analysis_obj
                self.ppms[r['type']['parameter']] = ppm_dict
                self.db.load_data('datum', ppm_dict)
                eU += 0.238*ppm_dict['value']
                eU_err.append((0.238*(ppm_dict['error']/2))**2)
            elif 'Sm' in r['type']['parameter']:
                ppm_dict = make_ppm(r, dim_mass_val, dim_mass_err)
                ppm_dict['analysis'] = analysis_obj
                self.db.load_data('datum', ppm_dict)
                eU += 0.0012*ppm_dict['value']
                eU_err.append((0.0012*(ppm_dict['error']/2))**2)
        eU_dict = {'value': eU, 'error': eU*0.15, #sum(eU_err)**(1/2),
                   'type': {'parameter': 'eU', 'unit': 'ppm'},# (±2σ)', 'unit': 'ppm'},
                   'analysis': analysis_obj}
        self.db.load_data('datum', eU_dict)

    def add_Ft_comb(self, analysis_obj, Fts):
        a_238 = (1.04+0.247*(self.ppms['232Th (±2σ)']['value']/self.ppms['238U (±2σ)']['value']))**-1
        a_232 = (1.+4.21*(self.ppms['238U (±2σ)']['value']/self.ppms['232Th (±2σ)']['value']))**-1
        Ft_comb = (a_238*float(Fts['238U Ft (±2σ)'].value) +
                   a_232*float(Fts['232Th Ft (±2σ)'].value) +
                   (1-a_238-a_232)*float(Fts['235U Ft (±2σ)'].value))
        Ft_comb_dict= {'value': Ft_comb, 'error': None,
                       'type': {'parameter': 'Combined Ft', 'unit': ''},
                       'analysis': analysis_obj}
        self.db.load_data('datum', Ft_comb_dict)