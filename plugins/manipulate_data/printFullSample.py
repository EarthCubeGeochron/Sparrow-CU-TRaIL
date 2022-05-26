# -*- coding: utf-8 -*-
"""
Created on Thu May 26 14:46:56 2022

@author: Peter
"""

from sparrow.import_helpers import BaseImporter
from rich import print

class TRaILprintsample(BaseImporter):
    def __init__(self, app, data_dir, **kwargs):
        super().__init__(app)
        lab_id = input('Enter lab ID: ')
        SampleSchema = self.db.interface.sample(many=False, allowed_nests="all")
        sample = self.db.session.query(self.db.model.sample).filter_by(lab_id=lab_id).first()
        target_json = SampleSchema.dump(sample)
        print(target_json)