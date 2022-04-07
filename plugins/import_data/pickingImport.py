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
from sparrow.import_helpers import BaseImporter
from sparrow.util import relative_path
from yaml import load

def get_Ft(l1, w1, l2, w2, Np, shape, Ft_constants, material):
    Ft_dat = {}
    for iso in ['238U', '235U','232Th', '147Sm']:
        R = Ft_constants[material][iso]
        if shape == 'Ellipsoid':
            a = w1/2
            b = w2/2
            c = ((l1+l2)/2)/2
            V = (4/3)*np.pi*a*b*c
            p = 1.6075
            S = 4*np.pi*((a**p*b**p+b**p*c**p+c**p*a**p)/3)**(1/p)
            Rs = 3*(V/S)
            Ft = 1-(3/4)*(R/Rs)+((1/16)+0.1686*(1-(a/Rs))**2)*(R/Rs)**3
        elif shape == 'Cylindrical':
            r = w1/2
            h = l1
            V = np.pi*r**2*h
            Ft = 1-((r+h)*R)/(2*r*h)+(0.2122*R**2)/(r*h)+(0.0153*R**3)/r**3
        elif shape == 'Orthorhombic':
            a = min([w1,w2])
            b = max([w1,w2])
            c = (l1+l2)/2
            V = a*b*c-Np*(a/4)*(b**2+(a**2/3))
            S = 2*(a*b+b*c+a*c)-Np*(((a**2+b**2)/2)+(2-sqrt(2))*a*b)
            Rs = 3*V/S
            Ft = 1-(3*R)/(4*Rs)+(0.2095*(a+b+c)-(0.096-0.013*((a**2+b**2)/c**2))*(a+b)*Np)*(R**2/V)
        elif shape == 'Hexagonal':
            L = w1
            W = w2
            H = (l1+l2)/2
            dV = (1/(6*sqrt(3)))*(L-(sqrt(3)/2)*W)**3 if L > (sqrt(3)/2)*W else 0
            V = H*L*(W-(L/(2*sqrt(3))))-Np*((sqrt(3)/8)*L*W**2-dV)
            S = (2*H*(W+(L/sqrt(3)))+
                 2*L*(W-(L/(2*sqrt(3))))-
                 Np*(sqrt(3)*W**2/4+(2-sqrt(2))*W*L+((sqrt(2)-1)*L**2)/(2*sqrt(3))))
            Rs = 3*V/S
            Ft = (1-(3/4)*(R/Rs)+
                  ((0.2093-0.0465*Np)*(W+L/sqrt(3))+
                   (0.1062+(0.2234*R)/(R+6*(W*sqrt(3)-L)))*
                   (H-Np*(W*(sqrt(3)/2)+L)/4))*R**2/V)
        Ft_dat[iso] = Ft
    Ft_dat['V'] = V
    return Ft_dat

class TRaILpicking(BaseImporter):
    def __init__(self, app, data_dir, **kwargs):
        super().__init__(app)
        # file_list = glob.glob(str(data_dir)+'/PickingData/*.xlsx')
        file_list = glob.glob(str(data_dir)+'/PickingData/Picking_data_example.xlsx')
        self.iterfiles(file_list, **kwargs)
        
    def make_labID(self, row):
        date = str(row['Date Packed'].year)[-2:]
        all_IDs = [el for tup in self.db.session.query(self.db.model.sample.lab_id).all() for el in tup if el is not None]
        same_year = [i for i in all_IDs if date+'-' in i]
        print(len(same_year))
        max_num = max([int(i.split('-')[1]) for i in same_year])
        print(max_num)
        id_num = max_num+1
        lab_id = date+'-'+f'{id_num:05d}'
        return lab_id

    def import_datafile(self, fn, rec, **kwargs):
        data = pd.read_excel(fn,
                             skiprows = range(2,6),
                             header = 1,
                             sheet_name = 'master')
        
        data.rename(columns={'Aliquot             (label a01, a02, z01, z02, etc.)':'Aliquot',
                             'Surface Roughness (GEM chart)': 'Roughness',
                             'Idealness of xtal form (GEM chart)': 'Xtal form',
                             'Mineral Inclusions? (should be avoided for apatite, see notes for zircons)': 'Mineral Inclusions',
                             'Fluid Inclusions? (should be avoided for all grains)': 'Fluid Inclusions'},
                    inplace=True)
        
        data = data[data['Analyst'].notnull()]
        
        spec = relative_path(__file__, "picking_specs.yaml")
        with open(spec) as f:
            self.picking_specs = load(f)
        
        for d in range(len(data)):
            lab_id = self.make_labID(data.iloc[d])
            print(lab_id)
            
            project = data.iloc[d]['Analyst']
            sample = data.iloc[d]['Sample.1']
            grain = data.iloc[d]['Aliquot']
            length1 = data.iloc[d]['L1']
            width1 = data.iloc[d]['W1']
            length2 = data.iloc[d]['L2']
            width2 = data.iloc[d]['W2']
            terminations = self.picking_specs['terminations_key'][int(data.iloc[d]['Np (0,1, or 2)'])]
            date = str(data.iloc[d]['Date Packed'])
            geometry = self.picking_specs['geometry_key'][int(data.iloc[d]['Geometry (1,2,3, or 4, see chart)'])]
            note = data.iloc[d]['Additional descriptive notes']
            if type(note) != str:
                note = ''
            material = self.picking_specs['mineral_key'][data.iloc[d]['Mineral (a, z, t, or m)']]
            Fts = get_Ft(length1, width1, length2, width2, 
                           int(data.iloc[d]['Np (0,1, or 2)']), geometry, self.picking_specs['Ft_constants'], material)
            dimensional_mass = self.picking_specs['Ft_constants'][material]['density']*Fts['V']/1e6
            sample_schema = {
                'member_of': {'project': [{'name': project}],
                              'name': sample,
                              'material': 'rock'},
                'name': sample+'_'+grain,
                'material': material,
                "lab_id": lab_id,
                'session': [
                    {
                    'technique': {'id': 'Picking Information'},
                    'instrument': {'name': 'Leica microscope'},
                    'date': date,
                    'analysis': [{
                        'analysis_type': 'Grain geometry',
                        'datum': [
                            {'value': length1,
                             'error': None,
                             'type': {'parameter': 'Length 1', 'unit': 'μm'}},
                            {'value': width1,
                              'error': None,
                              'type': {'parameter': 'Width 1', 'unit': 'μm'}},
                            {'value': length2,
                              'error': None,
                              'type': {'parameter': 'Length 2', 'unit': 'μm'}},
                            {'value': width2,
                              'error': None,
                              'type': {'parameter': 'Width 2', 'unit': 'μm'}},
                            {'value': Fts['238U'],
                              'error': None, 'type': {'parameter': '238U Ft', 'unit': ''}},
                            {'value': Fts['235U'],
                              'error': None, 'type': {'parameter': '235U Ft', 'unit': ''}},
                            {'value': Fts['232Th'],
                              'error': None, 'type': {'parameter': '232Th Ft', 'unit': ''}},
                            {'value': Fts['147Sm'],
                              'error': None, 'type': {'parameter': '147Sm Ft', 'unit': ''}},
                            {'value': dimensional_mass,
                              'error': None,
                              'type': {'parameter': 'Dimensional mass', 'unit': 'μg'}}
                            ],
                        'attribute': [
                            {'parameter': 'Geometry',
                             'value': geometry},
                            {'parameter': 'Crystal terminations',
                             'value': terminations},
                            {'parameter': 'Notes',
                             'value': note}
                            ]
                        }]
                    }]}
            
            self.db.load_data("sample", sample_schema)