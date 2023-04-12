# -*- coding: utf-8 -*-

from sparrow.core.import_helpers import BaseImporter
import pandas as pd


class RemoveEmbargo(BaseImporter):
    def __init__(self, app, data_dir, **kwargs):
        super().__init__(app)
        self.file = str(data_dir) + "/RemoveEmbargo/sample_ids.xlsx"
        self.remove_embargo(self.file, data_dir)

    def remove_embargo(self, file, data_dir):
        # Load file with sample IDs
        sample_ids = pd.read_excel(self.file, header=None, names=["IDs"])

        for sample_id in sample_ids["IDs"]:
            sample_obj = (
                self.db.session.query(self.db.model.sample)
                .filter_by(lab_id=sample_id)
                .first()
            )
            # Alert user if no sample with a given ID
            if not sample_obj:
                print("No sample with Lab ID", sample_id)
            else:
                # Update both sample and parent to make visible on frontend
                sample_obj.embargo_date = "2000-01-01"
                if sample_obj.member_of:
                    parent_sample = (
                        self.db.session.query(self.db.model.sample)
                        .filter_by(id=sample_obj.member_of)
                        .first()
                    )
                    parent_sample.embargo_date = "2000-01-01"
                self.db.session.commit()
        print("Embargoes removed.")
