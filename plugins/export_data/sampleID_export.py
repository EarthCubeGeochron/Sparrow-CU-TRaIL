# -*- coding: utf-8 -*-
"""
Created on Sun Apr 17 16:51:18 2022

@author: Peter
"""

from sparrow.import_helpers import BaseImporter
import pandas as pd

class LabID_exporter(BaseImporter):
    def __init__(self, app, data_dir, **kwargs):
        super().__init__(app)
        self.file = str(data_dir)+'/ExportSampleID/exportID.xlsx'
        self.get_IDs(self.file, data_dir)
        
    def get_IDs(self, file, data_dir):
        samples = pd.read_excel(self.file)
        
        lab_ids = []
        sample_ids = []
        picking_dates = []
        for name in samples['Name']:
            lab_id = (self.db.session
                      .query(self.db.model.sample.lab_id)
                      .filter_by(name=name)
                      .all())
            sample_id = (self.db.session
                         .query(self.db.model.sample.id)
                         .filter_by(name=name)
                         .all())
            lab_ids.append(lab_id)
            sample_ids.append(sample_id)
        for n, l in enumerate(sample_ids):
            picking_dates.append([])
            for i in l:
                picking_date = (self.db.session
                                .query(self.db.model.session.date)
                                .filter_by(sample_id=i[0],
                                           technique='Picking information')
                                .all())
                picking_dates[n].append(picking_date[0][0])
        for n, l in enumerate(picking_dates):
            picking_dates[n] = ', '.join([i.strftime('%Y-%m-%d') for i in l])
        for n, l in enumerate(lab_ids):
            # remove extraneous tuples and join to string for easier reading
            lab_ids[n] = ', '.join([i[0] for i in l])
        samples['lab_id'] = lab_ids
        samples['picking date(s)'] = picking_dates
        # print(samples)
        samples.to_excel(str(data_dir)+'/ExportSampleID/sample_ids.xlsx')
        
        return