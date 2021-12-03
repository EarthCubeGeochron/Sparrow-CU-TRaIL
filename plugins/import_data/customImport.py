# -*- coding: utf-8 -*-
"""
Created on Mon Aug 23 11:37:56 2021

@author: Peter
"""

from sparrow.import_helpers import BaseImporter
from rich import print

class TRaILpartial(BaseImporter):
    def __init__(self, app, data_dir, **kwargs):
        super().__init__(app)
        self.build_sample()
    
    def build_sample(self):
        sample_name = '28-3'
        sample_obj = self.db.session.query(self.db.model.sample).filter_by(name=sample_name).all()
        if len(sample_obj) == 0:
            print('No sample with that name!')
        if len(sample_obj) == 1:
            SampleSchema = self.db.interface.sample(many=False, allowed_nests="all")
            target_json = SampleSchema.dump(sample_obj)
            
            
            Fts = {}
            if '232Th Ft' in target_json:
                print('yes')
            for p in target_json['session'][0]['analysis'][0]['datum']:
                if 'Ft' in p['type']['parameter']['id']:
                    Fts[p['type']['parameter']['id']] = float(p['value'])
            print(Fts)
            
        elif len(sample_obj) > 1:
            print('Multiple samples with that name!')
        
        
        # Fts = {}
        # if '232Th Ft' in target_json:
        #     print('yes')
        # for p in target_json['session'][0]['analysis'][0]['datum']:
        #     if 'Ft' in p['type']['parameter']['id']:
        #         Fts[p['type']['parameter']['id']] = float(p['value'])
        # print(Fts)
        
        sample = self.db.model.sample
        sample_list = self.db.session.query(sample.name).all()
        sample_list = [s[0] for s in sample_list]
        print(sample_list)
        
        project = {"name": 'test_project'}
        parent_sample = {
            "project": [project],
            "name": 'test_parent2',
            "material": "rock",
        }
        sample = {
            'member_of': parent_sample,
            'name':'JT7_a02'
        }
        self.basic_import(sample)
        
    def basic_import(self, sample):
        self.db.load_data("sample", sample)
