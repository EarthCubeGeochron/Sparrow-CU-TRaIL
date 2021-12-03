# -*- coding: utf-8 -*-
"""
Created on Tue Nov 16 13:51:09 2021

@author: Peter
"""

from sparrow.import_helpers import BaseImporter
import glob

class TRaILicpms(BaseImporter):
    def __init__(self, app, data_dir, **kwargs):
        super().__init__(app)
        file_list = glob.glob(str(data_dir)+'/icpmsData/*/*.xlsx')
        self.iterfiles(file_list, **kwargs)
        
    def import_datafile(self, fn, rec, **kwargs):
        return