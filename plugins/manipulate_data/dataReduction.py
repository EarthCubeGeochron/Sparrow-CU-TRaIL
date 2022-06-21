# -*- coding: utf-8 -*-
import hecalc
import copy
from hecalc.main import _sample_loop
from rich import print
from sparrow.import_helpers import BaseImporter

def make_datum(val, err, data_dict, unit, TAU):
    return {'value': data_dict[val][0],
            'error': data_dict[err][0] if err else None,
            'type': {'parameter': val + TAU, 'unit': unit}}

# Make attribute using info in yaml file
def make_CI_attribute(CI_pos, CI_neg, TAU):
    return {'parameter': 'Confidence intervals',
            'value': '[+'+str(CI_pos)+', -'+str(CI_neg)+'] Ma'+TAU}

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
                if s.analysis_type == 'Raw date' or s.analysis_type == 'Date':
                    calculated_ids.append(date_sample_ids[n])
        # Find the intersection with both helium and icp data, *where date has not yet been calculated*
        to_calc = list((set(helium_ids) & set(icpms_ids)) ^ set(calculated_ids))
        if len(to_calc)==0:
            print('All data is reduced!')
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
        
        try:
            # Get 4He from database
            He4_datum = self.query_ID(sample_obj.lab_id, '4He blank corrected (±2σ)', datum_unit='ncc')
            He4 = float(He4_datum.value)
            He4_s = float(He4_datum.error)/2
            
            # Then get radionuclides
            U238_datum = self.query_ID(sample_obj.lab_id, '238U (±2σ)', datum_unit='ng')
            U238 = float(U238_datum.value)
            U238_s = float(U238_datum.error)/2
            Th232_datum = self.query_ID(sample_obj.lab_id, '232Th (±2σ)', datum_unit='ng')
            Th232 = float(Th232_datum.value)
            Th232_s = float(Th232_datum.error)/2
            Sm147_datum = self.query_ID(sample_obj.lab_id, '147Sm (±2σ)', datum_unit='ng')
            Sm147 = float(Sm147_datum.value)
            Sm147_s = float(Sm147_datum.error)/2
        # if not all necessary numbers are present in the database, don't calculate
        except TypeError:
            print('Invalid data for date calculation\n')
            # See whether date session exists (will not exist for samples without picking data)
            session_obj = (self.db.session
                           .query(self.db.model.session)
                           .filter_by(sample_id=d,
                                      technique='Dates and other derived data')
                           .first())
            if session_obj:
                date_dict = {
                    'analysis_type': 'Date',
                    'attribute': [{'parameter': 'Note',
                            'value': 'Invalid data for date calculation.'}]
                    }
                date_dict['session'] = session_obj
                self.db.load_data('analysis', date_dict)
                return
            # If no date session, create one
            else:
                date_session = {
                    'sample': sample_obj,
                    'technique': {'id': 'Dates and other derived data'},
                    'date': '1900-01-01 00:00:00+00', # always pass an 'unknown date' value for calculation
                    'analysis': [
                        {
                        'analysis_type': 'Date',
                        'attribute': [{'parameter': 'Note', 'value': 'Invalid data for date calculation.'}]
                        }]}
                self.db.load_data('session', date_session)
                return
        
        # Finally, try getting Ft
        Ft_session = (self.db.session
                      .query(self.db.model.session)
                      .filter_by(sample_id=d,
                                 technique='Dates and other derived data')
                      .all())
        if len(Ft_session) > 0:
            get_corrected = True
            Ft238_datum = self.query_ID(sample_obj.lab_id, '238U Ft (±2σ)')
            Ft238 = float(Ft238_datum.value)
            Ft238_s = float(Ft238_datum.error)/2
            Ft235_datum = self.query_ID(sample_obj.lab_id, '235U Ft (±2σ)')
            Ft235 = float(Ft235_datum.value)
            Ft235_s = float(Ft235_datum.error)/2
            Ft232_datum =  self.query_ID(sample_obj.lab_id, '232Th Ft (±2σ)')
            Ft232 = float(Ft232_datum.value)
            Ft232_s = float(Ft232_datum.error)/2
            Ft147_datum =  self.query_ID(sample_obj.lab_id, '147Sm Ft (±2σ)')
            Ft147 = float(Ft147_datum.value)
            Ft147_s = float(Ft147_datum.error)/2
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
        
        # Get total uncertainty first
        linear_uncertainty = hecalc.date_uncertainty(He4_mol, t=date['corrected date'], He_s = He4_mol_s,
                                                      U238=U238_mol, U235=None, Th232=Th232_mol, Sm147=Sm147_mol,
                                                      Ft238=Ft238, Ft235=Ft235, Ft232=Ft232, Ft147=Ft147,
                                                      U238_s=U238_mol_s, Th232_s=Th232_mol_s, Sm147_s=Sm147_mol_s,
                                                      Ft238_s=Ft238_s, Ft235_s=Ft235_s, Ft232_s=Ft232_s, Ft147_s=Ft147_s)
        precision = 0.001/100 # precision in percent
        # Check that precision doesn't require too many or too few cycles
        mc_number = int(linear_uncertainty**2/(precision*date['corrected date'])**2)
        if mc_number < 5:
            mc_number = 5
            precision = linear_uncertainty/(((mc_number)**(1/2))*date['corrected date'])
        # set uppper limit of ten million cycles in case of extremely imprecise data
        elif mc_number > 1e7:
            mc_number = int(1e7)
            precision = linear_uncertainty/(((mc_number)**(1/2))*date['corrected date'])
        
        # Then repeat for TAU ("total analytical uncertainty") -- no Ft uncertainty
        if get_corrected:
            save_out_TAU = copy.deepcopy(save_out)
            linear_uncertainty_TAU = hecalc.date_uncertainty(He4_mol, t=date['corrected date'], He_s = He4_mol_s,
                                                             U238=U238_mol, U235=None, Th232=Th232_mol, Sm147=Sm147_mol,
                                                             Ft238=Ft238, Ft235=Ft235, Ft232=Ft232, Ft147=Ft147,
                                                             U238_s=U238_mol_s, Th232_s=Th232_mol_s, Sm147_s=Sm147_mol_s,
                                                             Ft238_s=0, Ft235_s=0, Ft232_s=0, Ft147_s=0)
            sample_data_TAU = copy.deepcopy(sample_data)
            sample_data_TAU.update({'± 238Ft': 0, '± 235Ft': 0, '± 232Ft': 0, '± 147Ft': 0})
            precision_TAU = 0.001/100 # precision in percent
            mc_number_TAU = int(linear_uncertainty_TAU**2/(precision_TAU*date['corrected date'])**2)
            if mc_number_TAU < 5:
                mc_number_TAU = 5
                precision_TAU = linear_uncertainty_TAU/(((mc_number_TAU)**(1/2))*date['corrected date'])
            # set uppper limit of ten million cycles in case of extremely imprecise data
            elif mc_number_TAU > 1e7:
                mc_number_TAU = int(1e7)
                precision_TAU = linear_uncertainty_TAU/(((mc_number_TAU)**(1/2))*date['corrected date'])
        else:
            mc_number_TAU = 0
        
        measured_U235 = False
        linear = True
        monteCarlo = True
        histograms = False
        parameterize = False
        decimals = 2
        print('Number of MC cycles: '+str(mc_number + mc_number_TAU)+'\nStarting Monte Carlo\n')
        
        reduced_data = _sample_loop(save_out, sample_data, measured_U235, linear, monteCarlo,
                                    histograms, parameterize, decimals, precision)
        for dat in reduced_data:
            if reduced_data['Number of Monte Carlo simulations'][0] == 'NaN':
                reduced_data['Number of Monte Carlo simulations'][0] = 0
            elif reduced_data[dat][0] == 'NaN':
                reduced_data[dat][0] = None
        
        if get_corrected:
            reduced_data_TAU = _sample_loop(save_out_TAU, sample_data_TAU, measured_U235, linear, monteCarlo,
                                            histograms, parameterize, decimals, precision_TAU)
            
            for dat in reduced_data_TAU:
                if reduced_data_TAU['Number of Monte Carlo simulations'][0] == 'NaN':
                    reduced_data_TAU['Number of Monte Carlo simulations'][0] = 0
                elif reduced_data_TAU[dat][0] == 'NaN':
                    reduced_data_TAU[dat][0] = None
        
            session_obj = (self.db.session
                           .query(self.db.model.session)
                           .filter_by(sample_id=d,
                                      technique='Dates and other derived data')
                           .first())
            raw_dict = {
                'analysis_type': 'Raw date',
                'datum': [
                    make_datum('Raw date', 'MC average CI, raw', reduced_data, 'Ma', ' (±2σ)'),
                    make_datum('Number of Monte Carlo simulations', None, reduced_data, '', '')],
                'attribute': [
                        make_CI_attribute(reduced_data['MC +68% CI, raw'][0],
                                          reduced_data['MC -68% CI, raw'][0],
                                          '')]
                }
            corr_dict = {
                'analysis_type': 'Corrected date',
                'datum': [
                    make_datum('Corrected date', 'MC average CI, corrected', reduced_data_TAU, 'Ma', ' (±2σ, TAU)'),
                    make_datum('Corrected date', 'MC average CI, corrected', reduced_data, 'Ma', ' (±2σ, TAU+Ft)'),
                    make_datum('Number of Monte Carlo simulations', None, reduced_data, '', '')
                    ],
                'attribute': [
                    make_CI_attribute(reduced_data_TAU['MC +68% CI, corrected'][0],
                                      reduced_data_TAU['MC -68% CI, corrected'][0],
                                      ', TAU'),
                    make_CI_attribute(reduced_data['MC +68% CI, corrected'][0],
                                      reduced_data['MC -68% CI, corrected'][0],
                                      ', TAU+Ft'),
                    ]
                }
            raw_dict['session'] = session_obj
            corr_dict['session'] = session_obj
            self.db.load_data('analysis', raw_dict)
            self.db.load_data('analysis', corr_dict)
        else:
            session_dict={
                'technique': {'id': 'Dates and other derived data'},
                'date': '1900-01-01 00:00:00+00', # always pass an 'unknown date' value for calculation
                'analysis': [{
                    'analysis_type': 'Raw date',
                    'datum': [
                        make_datum('Raw date', 'MC average CI, raw', reduced_data, 'Ma', ' (±2σ)'),
                        make_datum('Number of Monte Carlo simulations', None, reduced_data, '', '')
                        ],
                    'attribute': [
                        make_CI_attribute(reduced_data['MC +68% CI, raw'][0],
                                          reduced_data['MC -68% CI, raw'][0],
                                          '')
                        ]
                    }]
                }
            session_dict['sample'] = sample_obj
            self.db.load_data('session', session_dict)