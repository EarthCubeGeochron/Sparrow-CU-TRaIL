# -*- coding: utf-8 -*-
"""
Created on Tue Nov 16 13:22:37 2021

@author: Peter
"""

import hecalc
from sparrow.import_helpers import BaseImporter

class TRaILpicking(BaseImporter):
    def __init__(self, app, data_dir, **kwargs):
        super().__init__(app)
        sample_obj = self.db.session.query(self.db.model.sample).filter_by(name=sample_name).all()