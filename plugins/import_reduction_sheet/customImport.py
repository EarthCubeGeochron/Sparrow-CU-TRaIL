# -*- coding: utf-8 -*-
"""
Created on Mon Aug 23 11:37:56 2021

@author: Peter
"""

from sparrow.import_helpers import BaseImporter

class TRaILpartial(BaseImporter):
    def __init__(self, app, data_dir, **kwargs):
        super().__init__(app)
        self.build_sample()
    
    def build_sample(self):
        project = {"name": 'test_project'}
        parent_sample = {
            "project": [project],
            "name": 'test_arent',
            "material": "rock", 
        }
        sample = {
            'member_of': parent_sample,
            'name':'Test_sample'
        }
        print(sample)
        self.basic_import(sample)
        
    def basic_import(self, sample):
        self.db.load_data("sample", sample)
