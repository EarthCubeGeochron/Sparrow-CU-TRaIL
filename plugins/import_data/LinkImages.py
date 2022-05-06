# -*- coding: utf-8 -*-
"""
Created on Fri May  6 08:52:49 2022

@author: Peter
"""

    # Never used in current version
    def link_image_files(self, row, session):
        if row["grain"] is None:
            return
        sample = row["Full Sample Name"]
        grain_images = list(self.image_folder.glob(sample+'*.tif'))

        for f in grain_images:
            rec, added = self._create_data_file_record(f)
            model = {
                "data_file": rec.uuid,
                "session": session.id
            }
            self.db.load_data("data_file_link", model)