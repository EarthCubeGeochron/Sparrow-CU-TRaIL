# -*- coding: utf-8 -*-
import hecalc
from hecalc.main import _sample_loop
from rich import print
from sparrow.import_helpers import BaseImporter

def make_datum(val, err, data_dict, unit):
    return {'value': data_dict[val][0],
            'error': data_dict[err][0] if err else None,
            'type': {'parameter': val, 'unit': unit}}

# Make attribute using info in yaml file
def make_CI_attribute(CI_pos, CI_neg):
    return {'parameter': 'Confidence intervals',
            'value': '[+'+str(CI_pos)+', -'+str(CI_neg)+']'}

class TRaILdatecalc(BaseImporter):
    def __init__(self, app, data_dir, **kwargs):
        super().__init__(app)
        
        # Get the full list of sessions with helium and icpms data
        helium_sessions = (self.db.session
                           .query(self.db.model.session)
                           .filter_by(technique='Helium measurement')
                           .all())
        helium_ids = [s.sample_id for s in helium_sessions]
        icpms_sessions = (self.db.session
                          .query(self.db.model.session)
                          .filter_by(technique='ICP-MS measurement')
                          .all())
        icpms_ids = [s.sample_id for s in icpms_sessions]
        date_sessions = (self.db.session
                         .query(self.db.model.session)
                         .filter_by(technique='Dates and other derived data')
                         .all())
        date_sample_ids = [s.sample_id for s in date_sessions]
        date_analysis_ids = [s.id for s in date_sessions]
        calculated_ids = []
        # Check for the presence of a raw date in any existing date calculation sessions
        for n, id_ in enumerate(date_analysis_ids):
            date_analyses = (self.db.session
                             .query(self.db.model.analysis)
                             .filter_by(session_id=id_)
                             .all())
            for s in date_analyses:
                if s.analysis_type == 'Raw date':
                    calculated_ids.append(date_sample_ids[n])
        for c in calculated_ids:
            print(self.db.session
                  .query(self.db.model.sample)
                  .filter_by(id=c)
                  .first()
                  .name)
        # Find the intersection with both helium and icp data, *where date has not yet been calculated*
        to_calc = list((set(helium_ids) & set(icpms_ids)) ^ set(calculated_ids))
        for d in to_calc:
            self.get_input_data(d)

    def query_ID(self, lab_id, datum_param, datum_unit=None):
        Session = self.db.model.session
        Sample = self.db.model.sample
        Analysis = self.db.model.analysis
        Datum = self.db.model.datum
        DatumType = self.db.model.datum_type
        if datum_unit:
            res = (self.db.session.query(Datum)
                   .join(Analysis)
                   .join(Session)
                   .join(Sample)
                   .join(DatumType)
                   .filter(Sample.lab_id == lab_id)
                   .filter(DatumType.parameter == datum_param)
                   .filter(DatumType.unit == datum_unit)
                   .first())
            return res
        else:
            res = (self.db.session.query(Datum)
                   .join(Analysis)
                   .join(Session)
                   .join(Sample)
                   .join(DatumType)
                   .filter(Sample.lab_id == lab_id)
                   .filter(DatumType.parameter == datum_param)
                   .first())
            return res

    def get_input_data(self, d):
        # Get He data first
        sample_obj = (self.db.session
                      .query(self.db.model.sample)
                      .filter_by(id=d)
                      .first())
        print('Reducing sample', sample_obj.name)

        # Get 4He from database
        He4_datum = self.query_ID(sample_obj.lab_id, '4He')
        He4 = float(He4_datum.value)
        He4_s = float(He4_datum.error)
        
        # Then get radionuclides
        U238_datum = self.query_ID(sample_obj.lab_id, '238U', datum_unit='ng')
        U238 = float(U238_datum.value)
        U238_s = float(U238_datum.error)
        Th232_datum = self.query_ID(sample_obj.lab_id, '232Th', datum_unit='ng')
        Th232 = float(Th232_datum.value)
        Th232_s = float(Th232_datum.error)
        Sm147_datum = self.query_ID(sample_obj.lab_id, '147Sm', datum_unit='ng')
        Sm147 = float(Sm147_datum.value)
        Sm147_s = float(Sm147_datum.error)
        
        # Finally, try getting Ft
        Ft_session = (self.db.session
                      .query(self.db.model.session)
                      .filter_by(sample_id=d,
                                 technique='Dates and other derived data')
                      .all())
        if len(Ft_session) > 0:
            get_corrected = True
            Ft238_datum = self.query_ID(sample_obj.lab_id, '238U Ft')
            Ft238 = float(Ft238_datum.value)
            Ft238_s = float(Ft238_datum.error)
            Ft235_datum = self.query_ID(sample_obj.lab_id, '235U Ft')
            Ft235 = float(Ft235_datum.value)
            Ft235_s = float(Ft235_datum.error)
            Ft232_datum =  self.query_ID(sample_obj.lab_id, '232Th Ft')
            Ft232 = float(Ft232_datum.value)
            Ft232_s = float(Ft232_datum.error)
            Ft147_datum =  self.query_ID(sample_obj.lab_id, '147Sm Ft')
            Ft147 = float(Ft147_datum.value)
            Ft147_s = float(Ft147_datum.error)
        # If no Fts in database, sample is a fragment and only raw dates should be calculated
        else:
            get_corrected = False
            Ft238, Ft235, Ft232, Ft147 = [1, 1, 1, 1]
            Ft238_s, Ft235_s, Ft232_s, Ft147_s = [0, 0, 0, 0]
        self.calculate_date(He4, He4_s, U238, U238_s, Th232, Th232_s, Sm147, Sm147_s,
                            Ft238, Ft238_s, Ft235, Ft235_s, Ft232, Ft232_s, Ft147, Ft147_s, get_corrected, d, sample_obj)
            
    def calculate_date(self, He4, He4_s, U238, U238_s, Th232, Th232_s, Sm147, Sm147_s,
                       Ft238, Ft238_s, Ft235, Ft235_s, Ft232, Ft232_s, Ft147, Ft147_s, get_corrected, d, sample_obj):
        U328_mol_per_ng = 1/(238.03*1e9)
        Th232_mol_per_ng = 1/(232*1e9)
        Sm147_mol_per_ng = 1/(157*1e9)
        He_mol_per_ncc = 1/(1000000000*22413.6)
        
        U238_mol = U238*U328_mol_per_ng
        U238_mol_s = U238_s*U328_mol_per_ng
        Th232_mol = Th232*Th232_mol_per_ng
        Th232_mol_s = Th232_s*Th232_mol_per_ng
        Sm147_mol = Sm147*Sm147_mol_per_ng
        Sm147_mol_s = Sm147_s*Sm147_mol_per_ng
        He4_mol = He4*He_mol_per_ncc
        He4_mol_s = He4_s*He_mol_per_ncc

        # Use the _sample_loop helper function from HeCalc to more
        # smoothly take care of the date calculation aspects
        # Use necessary data structure for _sample_loop. Keeping
        # This in-line here to make it simpler to trace dictionary keys to use
        save_out =  {
            'Sample': ['_'],
            'Raw date': [],
            'Linear raw uncertainty': [],
            'MC average CI, raw': [],
            'MC +68% CI, raw': [],
            'MC -68% CI, raw': [],
            'Corrected date': [],
            'Linear corrected uncertainty': [],
            'MC average CI, corrected': [],
            'MC +68% CI, corrected': [],
            'MC -68% CI, corrected': [],
            'Number of Monte Carlo simulations': []
        }
        
        # Set up actual data with some defaults in place; these can change later
        sample_data = {
            'Sample': '_',
            '238U': U238_mol,
            '± 238U': U238_mol_s,
            '232Th': Th232_mol,
            '± 232Th': Th232_mol_s,
            '147Sm': Sm147_mol,
            '± 147Sm': Sm147_mol_s,
            '4He': He4_mol,
            '± 4He': He4_mol_s,
            '238Ft': Ft238,
            '± 238Ft': Ft238_s,
            '235Ft': Ft235,
            '± 235Ft': Ft235_s,
            '232Ft': Ft232,
            '± 232Ft': Ft232_s,
            '147Ft': Ft147,
            '± 147Ft': Ft147_s,
            '238U-235U': 0,
            '238U-232Th': 0,
            '238U-147Sm': 0,
            '235U-232Th': 0,
            '235U-147Sm': 0,
            '232Th-147Sm': 0,
            # default to correlation of 1
            '238Ft-235Ft': Ft238_s*Ft235_s,
            '238Ft-232Ft': Ft238_s*Ft232_s,
            '238Ft-147Ft': Ft238_s*Ft147_s,
            '235Ft-232Ft': Ft235_s*Ft232_s,
            '235Ft-147Ft': Ft235_s*Ft147_s,
            '232Ft-147Ft': Ft232_s*Ft147_s
        }
        
        
        date = hecalc.get_date(He4_mol, U238=U238_mol, U235=None, Th232=Th232_mol, Sm147=Sm147_mol,
                              Ft238=Ft238, Ft235=Ft235, Ft232=Ft232, Ft147=Ft147)
        
        linear_uncertainty = hecalc.date_uncertainty(He4_mol, t=date['corrected date'], He_s = He4_mol_s,
                                                      U238=U238_mol, U235=None, Th232=Th232_mol, Sm147=Sm147_mol,
                                                      Ft238=Ft238, Ft235=Ft235, Ft232=Ft232, Ft147=Ft147,
                                                      U238_s=U238_mol_s, Th232_s=Th232_mol_s, Sm147_s=Sm147_mol_s,
                                                      Ft238_s=Ft238_s, Ft235_s=Ft235_s, Ft232_s=Ft232_s, Ft147_s=Ft147_s)
        precision = 0.01#0.01/100 # precision in percent
        mc_number = linear_uncertainty**2/(precision*date['corrected date'])**2
        if mc_number < 5:
            mc_number = 5
        else:
            mc_number = int(mc_number)
        print('Number of MC cycles:', mc_number)
        
        measured_U235 = False
        linear = True
        monteCarlo = True
        histograms = False
        parameterize = False
        decimals = 2
        print('Starting Monte Carlo')
        
        reduced_data = _sample_loop(save_out, sample_data, measured_U235, linear, monteCarlo,
                                    histograms, parameterize, decimals, precision)
        
        print('')
        
        # if get_corrected:
        #     session_obj = self.db.session.query(self.db.model.session).filter_by(sample_id=d, technique='(U-Th)/He date calculation').first()
        #     print(session_obj.technique)
        #     raw_dict = {
        #         'analysis_type': 'Raw date',
        #         'datum': [
        #             make_datum('Raw date', 'MC average CI, raw', reduced_data, 'Ma'),
        #             make_datum('Number of Monte Carlo simulations', None, reduced_data, '')],
        #         'attribute': [
        #                 make_CI_attribute(reduced_data['MC +68% CI, raw'], reduced_data['MC -68% CI, raw'])]
        #         }
        #     corr_dict = {
        #         'analysis_type': 'Corrected date',
        #         'datum': [
        #             make_datum('Corrected date', 'MC average CI, corrected', reduced_data, 'Ma'),
        #             make_datum('Number of Monte Carlo simulations', None, reduced_data, '')
        #             ],
        #         'attribute': [
        #             make_CI_attribute(reduced_data['MC +68% CI, corrected'][0], reduced_data['MC -68% CI, corrected'][0])]
        #         }
        #     raw_dict['session_id'] = session_obj.id
        #     corr_dict['session'] = session_obj
        #     self.db.load_data('analysis', raw_dict)
        #     self.db.load_data('analysis', corr_dict)
        # else:
        if True:
            session_dict={
                'technique': {'id': '(U-Th)/He date calculation'},
                'date': '1900-01-01 00:00:00+00', # always pass an 'unknown date' value for calculation
                'analysis': [{
                    'analysis_type': 'Raw date',
                    'datum': [
                        make_datum('Raw date', 'MC average CI, raw', reduced_data, 'Ma'),
                        make_datum('Number of Monte Carlo simulations', None, reduced_data, '')
                        ],
                    'attribute': [
                        make_CI_attribute(reduced_data['MC +68% CI, raw'][0], reduced_data['MC -68% CI, raw'][0])
                        ]
                    }]
                }
            session_dict['sample'] = sample_obj
            self.db.load_data('session', session_dict)