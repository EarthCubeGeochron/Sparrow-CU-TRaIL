# -*- coding: utf-8 -*-
"""
Created on Tue Nov 16 13:51:09 2021

@author: Peter
"""

from sparrow.import_helpers import BaseImporter
import glob
import pandas as pd

Uatnorm = (0.000000001/238)*6.022e23
Uratnorm = 139.52
Thatnorm = (0.000000001/232)*6.022e23
Thratnorm = 1e99
Smatnorm = (0.00000001/150.36)*(6.022E+23)

def ICPMS_mols(atnorm, ratnorm, norm, spkblk, Nb_blk, R_meas):
    atoms_shot = (atnorm*(ratnorm-norm))/(ratnorm*(norm-spkblk))
    Atoms = (spkblk-R_meas)/(R_meas/ratnorm-1)*atoms_shot
    Nbat_blk = (spkblk-Nb_blk)/(Nb_blk/ratnorm-1)*atoms_shot
    mols = (Atoms-Nbat_blk)/6.022e23
    return mols


def Sm_ICPMS_mols(Smatnorm, NdSm, SmNdRat, Nb_Smblk):
    Nd145_shot = (1/NdSm)*Smatnorm*0.1502
    atoms147 = SmNdRat*Nd145_shot
    Nbat_Smblk = Nd145_shot*Nb_Smblk
    mols_147Sm = (atoms147-Nbat_Smblk)/6.022e23
    return mols_147Sm

class TRaILicpms(BaseImporter):
    def __init__(self, app, data_dir, **kwargs):
        super().__init__(app)
        file_list = glob.glob(str(data_dir)+'/icpmsData/*/FULL.xlsx')
        self.iterfiles(file_list, **kwargs)
        
    def import_datafile(self, fn, rec, **kwargs):
        data = pd.read_excel(fn,
                             header = None)
        data.iloc[0:2] = data.iloc[0:2].fillna(method='ffill', axis = 1)
        data.iloc[0:2] = data.iloc[0:2].fillna('')
        data.columns = data.iloc[0:2].apply(lambda x: '.'.join([y for y in x if y]), axis=0)
        data = data.iloc[2:]
        print(data)
        return