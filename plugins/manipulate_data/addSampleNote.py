# -*- coding: utf-8 -*-
"""
Created on Wed May 11 16:00:25 2022

@author: Peter
"""

from rich import print
from sparrow.core.import_helpers import BaseImporter


class AddSampleNote(BaseImporter):
    def __init__(self, app, data_dir, id_, note, **kwargs):
        super().__init__(app)
        if not id_ and not note:
            try:
                sample_id = str(input("Sample ID to add note to: "))
                add_note = str(input("Enter note: "))
            except:
                print("Please enter the Sample ID and Note to add.")
                return
        else:
            sample_id = id_
            add_note = note
        try:
            sample_obj = (
                self.db.session.query(self.db.model.sample)
                .filter_by(lab_id=sample_id)
                .all()[0]
            )
            print("Adding note to sample", sample_obj.name)
        except IndexError:
            print("No sample with ID " + sample_id + " found.")
            return
        if sample_obj.note:
            print(sample_obj.name, "already has a note. Adding to existing note.")
            sample_obj.note = sample_obj.note + "\n" + add_note
        else:
            sample_obj.note = add_note
        self.db.session.commit()
