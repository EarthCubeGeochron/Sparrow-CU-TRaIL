# -*- coding: utf-8 -*-
"""
Created on Mon Aug 23 11:37:56 2021

@author: Peter
"""

from sparrow.import_helpers import BaseImporter
from rich import print
import pandas as pd
import numpy as np
from uncertainties import ufloat
import re
import glob

# Function to find the average 4/3 Q value and
# the number of Q shots taken
def get_Q(Qs, Q_nums):
    Q_4_3s = []
    for q in Qs:
        Q_4_3s.append(get_4_3(q))
    Q = sum(Q_4_3s)/len(Q_4_3s)
    shots = int(np.median(Q_nums))
    return {'Q_4_3': Q, 'shots': shots}

# Get all cold blanks for a given analytical session
# and return them as a dictionary with the analysis
# number as a key to identify which should be used
# for which samples
def get_blanks(CBs):
    blanks = {}
    for b in CBs:
        blanks[b['analysis number']] = get_4_3(b['data'])
    return blanks

# Function to get a sample's RE(s) 4/3 ratio(s)
def get_REs(sample_id, data):
    REs = []
    for d in data:
        if sample_id in d and ' RE' in d:
            REs.append(get_4_3(data[d]['data']))
    return REs

# Function to calculate the 4/3 ratio from standard data output
def get_4_3(data):
    background_4He = np.average(data['4'][:2])
    background_3He = np.average(data['3'][:2])
    
    He4_measured = data['4'][2:]-background_4He
    He3_measured = data['3'][2:]-background_3He
    
    ratios = He4_measured/He3_measured
    He4_3 = ufloat(np.average(ratios), np.std(ratios, ddof=1))*1000
    return He4_3

# Calculate nano-cc's for a given 4/3 ratio, Q measurement,
# and the number of shots taken
def get_ncc(rat_4_3, Q, shots, Q21, QDF):
    ncc = (rat_4_3/Q)*Q21*QDF**(shots-21)
    return ncc

class TRaILhelium(BaseImporter):
    def __init__(self, app, data_dir, **kwargs):
        super().__init__(app)
        file_list = glob.glob(str(data_dir)+'/heliumData/data_2020_01_28.txt')
        self.iterfiles(file_list, **kwargs)

    def import_datafile(self, fn, rec, **kwargs):
        Q21 = 15.809
        QDF = 0.9999029186
        
        #TODO need user input here to figure out what analysis numbers to use
        start = input('Enter starting analysis number: ')#40924
        end =  input('Enter ending analysis number: ')#'40986'
        end = int(end)+1
        end = str(end)
        
        data_load = []
        with open(fn) as infile:
            record = False
            for line in infile:
                if 'He '+ start in line:
                    record = True
                if 'He '+ end in line:
                    record = False
                if record:
                    line = line.rstrip('\n')
                    data_load.append(line.split('\t'))
        
        cols = ['time', '2', '3', '4', '5', '40']
        
        data = {}
        sample = []
        for line in data_load:
            sample.append(line)
            if line[-1] == '':
                sample = sample[:-2]
                if len(sample)>0:
                    sample_info = {}
                    sample_id = sample[0][1]
                    sample_info['analysis number'] = int(sample[0][0][2:])
                    sample_info['datetime'] = sample[0][2]
                    sample = pd.DataFrame(sample[1:], columns=sample[0])
                    sample = sample.iloc()[:,3:]
                    sample = sample.astype(float)
                    sample.columns = cols
                    sample_info['data'] = sample
                    data[sample_id] = sample_info
                    sample = []
        
        Qs = []
        Q_nums = []
        CBs = []
        for d in list(data.keys()):
            if '_Q' in d:
                Qs.append(data[d]['data'])
                Q_nums.append(int(re.findall(r'\d+', d)[0]))
                del data[d]
            elif 'CB ' in d:
                CBs.append(data[d])
                del data[d]
        Q = get_Q(Qs, Q_nums)
        blanks = get_blanks(CBs)
        blank_nums = np.array(list(blanks.keys()))
        
        nccs=[]
        # Only proceed if measured value was a sample of interest
        # (i.e., not a Q, cold blank, or reextract)
        for d in data:
            if ' RE' not in d:
                sample_id = d.split(' ')[0]
                blank_num = blank_nums[blank_nums<data[d]['analysis number']].max()
                
                ncc_blank = get_ncc(blanks[blank_num], Q['Q_4_3'], Q['shots'], Q21, QDF)
                
                REs = get_REs(sample_id, data)
                ncc_REs = [get_ncc(re, Q['Q_4_3'], Q['shots'], Q21, QDF) for re in REs]
                       
                He_4_3 = get_4_3(data[d]['data'])
                ncc_sample = get_ncc(He_4_3, Q['Q_4_3'], Q['shots'], Q21, QDF)
                
                total_ncc = ncc_sample-ncc_blank
                
                RE_added = False
                for RE in ncc_REs:
                    if RE > ncc_blank:
                        RE_added = True
                        total_ncc = total_ncc + RE - ncc_blank
                print(sample_id, total_ncc, 'ncc')
                if RE_added:
                    total_RE = sum(ncc_REs).n
                    print('Reextract %:', abs(1-(total_RE/total_ncc.n)*100)) 
                else:
                    print('Reextract %: 100')
                    total_RE = 0
                nccs.append(total_ncc)
                self.import_he(sample_id, total_ncc, total_RE, data[d]['datetime'])
    
    def import_he(self, sample_id, total_ncc, total_RE, date):
        # sample_obj = self.db.session.query(self.db.model.sample).filter_by(name=sample_name).all()
        sample_obj = self.db.session.query(self.db.model.sample).filter_by(lab_id=sample_id).all()
        if len(sample_obj) == 0:
            #TODO figure out how to handle creating a new sample if necessary
            print('No sample with the name or ID '+sample_id+' exists')
            opt = input('Would you like to [1] create a new sample, [2] find an existing sample to add helium data to, or [3] skip these He data?: ')
            # opt = '3'
            while not opt in ['1', '2', '3']:
                opt = input('Please enter a number 1-3 to choose whether to [1] create a new sample, [2] find an existing sample to add helium data to, or [3] skip these He data: ')
            if opt == '1':
                print('')
                # TODO recover the sample name indpendently or find a way to add it
                sample_name = sample_id
                self.create_sample(sample_name, total_ncc, total_RE, date)
            # Need to figure out way of allowing user to choose sample
            if opt == '2':
                print('')
                return
            if opt == '3':
                print('')
                return
        if len(sample_obj) == 1:
            sample_obj = sample_obj[0]
            # SampleSchema = self.db.interface.sample(many=False, allowed_nests="all")
            # target_json = SampleSchema.dump(sample_obj)
            # print(target_json)
            print('')
            self.add_he(sample_obj, total_ncc, total_RE, date)
        # elif len(sample_obj) > 1:
        #     #TODO figure out how to allow user to choose between samples from list
        #     print('Multiple samples with that name.\nPlease choose which should be used.')
        #     return
    
    # If creating a sample with no picking information, assume nothing
    # about the owner, aliquot number, etc.
    # TODO decide if we want to prompt the user for some info here, espcially
    # things like a project to attach to (for the case of Durango e.g.)
    def create_sample(self, sample_name, total_ncc, total_RE, date):
        if total_RE == 0:
            reextract = 100
        else:
            reextract = abs(1-(total_RE/total_ncc.n)*100)
        
        # TODO make sample ID here somewhere
        
        session_dict = {
            'technique': {'id': 'Helium measurement'},
            'instrument': {'name': 'Alphachron'},
            'date': date,
            'analysis': [{
                'analysis_type': 'Helium measurement',
                    'datum': [
                        {'value': total_ncc.n,
                         'error': total_ncc.s,
                         'type': {'parameter': '4He', 'unit': 'ncc'}},
                        {'value': reextract,
                         'error': None,
                         'type': {'parameter': '% initial extraction', 'unit': '%'}}
                    ]
                }]
            }
        
        sample_schema = {
            'name': sample_name,
            'session': [session_dict]
            }

        self.db.load_data("sample", sample_schema)
    
    def add_he(self, sample_obj, total_ncc, total_RE, date):
        if total_RE == 0:
            reextract = 100
        else:
            reextract = abs(1-(total_RE/total_ncc.n)*100)
        
        session_dict = {
            'sample': sample_obj,
            'technique': {'id': 'Helium measurement'},
            'instrument': {'name': 'Alphachron'},
            'date': date,
            'analysis': [{
                'analysis_type': 'Helium measurement',
                    'datum': [
                        {'value': total_ncc.n,
                         'error': total_ncc.s,
                         'type': {'parameter': '4He', 'unit': 'ncc'}},
                        {'value': reextract,
                         'error': None,
                         'type': {'parameter': '% initial extraction', 'unit': '%'}}
                    ]
                }]
            }
        
        helium_session = self.db.load_data("session", session_dict)