# -*- coding: utf-8 -*-
"""
Created on Fri Oct  8 15:01:18 2021

@author: Peter
"""

import glob
import numpy as np
import pandas as pd
from rich import print
from math import sqrt
from sparrow.core.import_helpers import BaseImporter
from macrostrat.utils import relative_path
import datetime
from dateutil.parser import parse
from yaml import load

from .pickingImport import get_picking_specs, read_picking_data

class TRaILpicking(BaseImporter):
    def __init__(self, app, data_dir, **kwargs):
        super().__init__(app)
        file_list = kwargs.get('file_list', glob.glob(str(data_dir)+'/PickingData/*.xlsx'))

        self.picking_specs = get_picking_specs()
        self.iterfiles(file_list, **kwargs)


    # Method to generate a lab ID for a new sample based on the date of the analysis
    def make_labID(self, date):
        year = str(date.year)[-2:]
        # Query database for all lab IDs
        all_IDs = [el for tup in self.db.session.query(self.db.model.sample.lab_id).all()
                   for el in tup if el is not None]
        # Isolate lab IDs from the same year
        same_year = [i for i in all_IDs if year+'-' in i]
        # Get the highest numbered analysis for the year and add 1
        if len(same_year) > 0:
            max_num = max([int(i.split('-')[1]) for i in same_year])
        else:
            max_num = 0
        id_num = max_num+1
        # Combine year and analysis number to get lab_id
        lab_id = year+'-'+f'{id_num:05d}'
        return lab_id

    def import_datafile(self, fn, rec, **kwargs):
        sample_schema = read_picking_data(fn, self.picking_data)
        print('')
        self.db.load_data('sample', sample_schema, strict=True)
