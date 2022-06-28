# -*- coding: utf-8 -*-

from sparrow.import_helpers import BaseImporter
import pandas as pd
import numpy as np

class AddLocation(BaseImporter):
    def __init__(self, app, data_dir, **kwargs):
        super().__init__(app)
        self.file = str(data_dir)+'/AddLocation/locations.xlsx'
        self.add_location(self.file, data_dir)
        
    def add_location(self, file, data_dir):
        # Load file with sample IDs
        data = pd.read_excel(self.file)
        
        for k, row in data.iterrows():
            sample_obj = self.db.session.query(self.db.model.sample).filter_by(lab_id=row['Sample ID']).first()
            # Alert user if no sample with a given ID
            if not sample_obj:
                print('No sample with Lab ID', row['Sample ID'])
            else:
                # define variables with data
                lat = row['Lattitude (decimal degrees)']
                long = row['Longitude (decimal degrees)']
                elevation = row['Elevation (m)']
                depth = row['Depth (m)']
                # add sample location if not NaN and if can be coerced to numeric
                try:
                    if ~np.isnan(lat) and ~np.isnan(long):
                        sample_obj.location = self.location(long, lat)
                except TypeError:
                    pass
                # add elevation if not NaN and if can be coerced to numeric
                try:
                    if ~np.isnan(elevation):
                        sample_obj.elevation = elevation
                except TypeError:
                    pass
                # add depth location if not NaN and if can be coerced to numeric
                try:
                    if ~np.isnan(depth):
                        sample_obj.depth = depth
                except TypeError:
                    pass
                self.db.session.commit()
        print('Locations added')