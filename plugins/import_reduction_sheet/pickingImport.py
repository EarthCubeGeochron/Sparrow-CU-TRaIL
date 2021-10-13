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

Ft_constants = {
    'Apatite': {'density': 3.20, '238U': 18.81, '235U': 21.8, '232Th': 22.25, '147Sm': 5.93},
    'Zircon': {'density': 4.65, '238U': 15.55, '235U': 18.05, '232Th': 18.43, '147Sm': 4.76},
    'Titanite': {'density': 3.53, '238U': 17.46, '235U': 20.25, '232Th': 20.68, '147Sm': 5.47},
    'Miscellaneous': {'density': 4.25, '238U': 15.30, '235U': 17.76, '232Th': 18.14, '147Sm': 4.77}
    }

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
        file_list = glob.glob(str(data_dir)+'/PickingData/*.xlsx')
        self.iterfiles(file_list, **kwargs)

    def import_datafile(self, fn, rec, **kwargs):
        # direc = r'C:\Users\pemar\Documents\FlowersResearch\FRES\Data\Picking-Packing_info\\'
        # file = 'He_Packing_7-12-2021.xlsx'
        
        # file_list = glob.glob(str(data_dir)+'/*.xlsx')
        
        data = pd.read_excel(fn,
                             skiprows = range(2,6),
                             header = 1,
                             sheet_name = 'master')
        
        data.rename(columns={'Aliquot             (label a01, a02, z01, z02, etc.)':'Aliquot'},
                    inplace=True)
        
        data = data[data['Analyst'].notnull()]
        terminations_key = {2: 'Doubly terminated', 1: 'Single termination', 0: 'No terminations'}
        geometry_key = {1: 'Ellipsoid', 2: 'Cylindrical', 3: 'Orthorhombic', 4: 'Hexagonal'}
        mineral_key = {'a': 'Apatite', 'z': 'Zircon', 't': 'Titanite', 'm': 'Miscellaneous'}
        
        for d in range(len(data)):
            project = data.iloc[d]['Analyst']
            sample = data.iloc[d]['Sample.1']
            grain = data.iloc[d]['Aliquot']
            length1 = data.iloc[d]['L1']
            width1 = data.iloc[d]['W1']
            length2 = data.iloc[d]['L2']
            width2 = data.iloc[d]['W2']
            terminations = terminations_key[int(data.iloc[d]['Np (0,1, or 2)'])]
            date = str(data.iloc[d]['Date Packed'])
            geometry = geometry_key[int(data.iloc[d]['Geometry (1,2,3, or 4, see chart)'])]
            note = data.iloc[d]['Additional descriptive notes']
            material = mineral_key[data.iloc[d]['Mineral (a, z, t, or m)']]
            Fts = get_Ft(length1, width1, length2, width2, 
                           int(data.iloc[d]['Np (0,1, or 2)']), geometry, Ft_constants, material)
            dimensional_mass = Ft_constants[material]['density']*Fts['V']/1e6
            sample_schema = {
                'member_of': {'project': [{'name': project}],
                              'name': sample,
                              'material': 'rock'},
                'name': sample+'_'+grain,
                'material': material,
                'session': [
                    {
                    'technique': {'id': 'Picking Information'},
                    'instrument': {'name': 'Leica microscope'},
                    'date': date,
                    'analysis': [{
                        'analysis_type': 'Grain Shape',
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
            print(sample_schema)
            self.db.load_data("sample", sample_schema)





# length1=156.5
# width1= 147.7
# length2=151.5
# width2=115.9
# Np=2
# geometry = 'Hexagonal'
# material = 'Apatite'
# Fts = get_Ft(length1, width1, length2, width2,
#                 Np, geometry, Ft_constants)
# Ft235 = get_Ft(length1, width1, length2, width2, Ft_constants[material]['235U'],
#                Np, geometry)
# Ft232 = get_Ft(length1, width1, length2, width2, Ft_constants[material]['232Th'],
#                Np, geometry)
# Ft147 = get_Ft(length1, width1, length2, width2, Ft_constants[material]['147Sm'],
#                Np, geometry)

# U = 4.24217712E-13
# Th = 1.3915948830E-13

# Th_U = Th/(U+U/137.818)
# a238 = 1/(1.04+0.245*Th_U)

# Ft_eff = a238*Ft238+(1-a238)*Ft232
