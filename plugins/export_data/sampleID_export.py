# -*- coding: utf-8 -*-
"""
Created on Sun Apr 17 16:51:18 2022

@author: Peter
"""

import shutil
from sparrow.import_helpers import BaseImporter
import pandas as pd
from sparrow import task, get_database
import glob
import datetime
from typing import List


def lab_id_export_core(samples: pd.DataFrame):
    db = get_database()

    lab_ids = []
    sample_ids = []
    picking_dates = []

    for name in samples["Name"]:
        lab_id = db.session.query(db.model.sample.lab_id).filter_by(name=name).all()
        sample_id = db.session.query(db.model.sample.id).filter_by(name=name).all()
        lab_ids.append(lab_id)
        sample_ids.append(sample_id)
    for n, l in enumerate(sample_ids):
        picking_dates.append([])
        for i in l:
            picking_date = (
                db.session.query(db.model.session.date)
                .filter_by(sample_id=i[0], technique="Picking Information")
                .all()
            )
            picking_dates[n].append(picking_date[0][0])
    for n, l in enumerate(picking_dates):
        picking_dates[n] = ", ".join([i.strftime("%Y-%m-%d") for i in l])
    for n, l in enumerate(lab_ids):
        # remove extraneous tuples and join to string for easier reading
        lab_ids[n] = ", ".join([i[0] for i in l])
    samples["lab_id"] = lab_ids
    samples["picking date(s)"] = picking_dates
    # print(samples)
    # samples.to_excel(str(data_dir)+'/ExportSampleID/sample_ids.xlsx')
    return samples


class LabID_exporter(BaseImporter):
    def __init__(self, app, data_dir, **kwargs):
        super().__init__(app)
        self.file = glob.glob(str(data_dir) + "/ExportSampleID/exportID.xlsx")[0]
        self.get_IDs(self.file, data_dir)

    def get_IDs(self, file, data_dir):
        samples = pd.read_excel(self.file)

        samples = lab_id_export_core(samples)
        # print(samples)
        samples.to_excel("/tmp/sample_ids.xlsx")
        shutil.move(
            "/tmp/sample_ids.xlsx", str(data_dir) + "/ExportSampleID/sample_ids.xlsx"
        )
        print("Lab IDs exported")

        return


@task(name="export-ID-with-args")
def labid_export(sample_names: List[str]):
    samples = pd.DataFrame({"Name": sample_names})
    samples = lab_id_export_core(samples)
    print(samples.to_csv(delimiter="\t"))
