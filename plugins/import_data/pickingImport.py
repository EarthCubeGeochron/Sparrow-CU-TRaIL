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
            Rs = (3*r*h)/(2*(r+h))
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
    Ft_dat['Rs'] = Rs
    return Ft_dat

def make_datum(datum, parameter, unit):
    return {'value': datum,
            'error': None,
            'type': {'parameter': parameter, 'unit': unit}}

def make_attribute(value, parameter):
    return {'parameter': parameter,
            'value': str(value)}

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
        if len(same_year) > 0:
            max_num = max([int(i.split('-')[1]) for i in same_year])
        else:
            max_num = 0
        id_num = max_num+1
        lab_id = date+'-'+f'{id_num:05d}'
        return lab_id

    def import_datafile(self, fn, rec, **kwargs):
        data = pd.read_excel(fn,
                             skiprows = range(2,6),
                             header = 1,
                             sheet_name = 'master')

        # Load the picking specs. This file dictates virtually everything about this import
        spec = relative_path(__file__, "picking_specs.yaml")
        with open(spec) as f:
            self.picking_specs = load(f)
        
        # Find actual data by figuring out where the analyst rows are full
        data = data[data[self.picking_specs['Metadata']['Researcher']].notnull()]
        
        for d in range(len(data)):
            # Generate a lab ID for each grain
            lab_id = self.make_labID(data.iloc[d])
            
            # Generate metadata required for every grain
            project = data.iloc[d][self.picking_specs['Metadata']['Researcher']]
            sample = data.iloc[d][self.picking_specs['Metadata']['Sample']]
            grain = data.iloc[d][self.picking_specs['Metadata']['Grain']]
            print(sample+'_'+grain)
            date = str(data.iloc[d]['Date Packed'])
            material = self.picking_specs['mineral_key'][data.iloc[d][self.picking_specs['Metadata']['Mineral']]]
            
            # Create necessary data for Fts if not a shard. This info MUST be recorded for whole grains
            shard = data.iloc[d][self.picking_specs['Metadata']['Fragment']]
            if shard != 'Y' and shard != 'y':
                length1 = data.iloc[d][self.picking_specs['Metadata']['Dimensions']['Length 1']]
                width1 = data.iloc[d][self.picking_specs['Metadata']['Dimensions']['Width 1']]
                length2 = data.iloc[d][self.picking_specs['Metadata']['Dimensions']['Length 2']]
                width2 = data.iloc[d][self.picking_specs['Metadata']['Dimensions']['Width 2']]
                terminations = data.iloc[d][self.picking_specs['Metadata']['Terminations']]
                geometry = data.iloc[d][self.picking_specs['Metadata']['Geometry']]
                
                # Generate Ft and dimensional mass
                Fts = get_Ft(length1, width1, length2, width2,
                             int(terminations), self.picking_specs['geometry_key'][geometry],
                             self.picking_specs['Ft_constants'], material)
                dimensional_mass = self.picking_specs['Ft_constants'][material]['density']*Fts['V']/1e6

                # create datum and attributes for shape analysis
                shape_data = []
                for s in self.picking_specs['Shape']['data']:
                    col = next(iter(s))
                    value = data.iloc[d][col]
                    shape_data.append([value, s[col]['name'], s[col]['unit']])
                shape_attributes = []
                for s in self.picking_specs['Shape']['attributes']:
                    col = next(iter(s))
                    value = str(data.iloc[d][col])
                    shape_attributes.append([value, s[col]])
                # make analysis dictionary
                shape_dict = {
                    'analysis_type': 'Grain Shape',
                    'datum': [make_datum(*d) for d in shape_data],
                    'attribute': [make_attribute(*a) for a in shape_attributes]
                    }
            # If a shard, simply add that as a note and don't calculate Ft values
            else:
                Fts = {'238U': 1, '235U': 1, '232Th': 1, '147Sm': 1}
                shape_dict = {
                    'analysis_type': 'Grain Shape',
                    'attribute': [make_attribute('Crystal shard', 'Shape notes')]
                    }
            
            # create datum and attributes for characteristics analysis
            if shard != 'Y' and shard != 'y':
                # If not a shard, all data here are calculated above, so declare explicitly
                chars_data =[
                    [dimensional_mass, 'Dimensional mass', 'μg'],
                    [Fts['Rs'], 'Equivalent Spherical Radius', 'μg']
                    ]
            # Characteristics will always be recorded, even for shards
            chars_attributes = []
            for s in self.picking_specs['Characteristics']['attributes']:
                col = next(iter(s))
                value = str(data.iloc[d][col])
                chars_attributes.append([value, s[col]])
            # make analysis dictionary, exclude missing data if shards
            if shard != 'Y' and shard != 'y':
                chars_dict = {
                    'analysis_type': 'Grain Characteristics',
                    'datum': [make_datum(*d) for d in chars_data],
                    'attribute': [make_attribute(*a) for a in chars_attributes]
                    }
            else:
                chars_dict = {
                    'analysis_type': 'Grain Characteristics',
                    'attribute': [make_attribute(*a) for a in chars_attributes]
                    }
            
            # Compile data for new Ft session
            Ft_data = [
                [Fts['238U'], '238U Ft', ''],
                [Fts['235U'], '235U Ft', ''],
                [Fts['232Th'], '232Th Ft', ''],
                [Fts['147Sm'], '147Sm Ft', '']
                ]
            
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
                    'analysis': [
                        shape_dict,
                        chars_dict
                        ]
                    },
                    {
                    'technique': {'id': "(U-Th)/He date calculation"},
                    'date': "1900-01-01 00:00:00+00", # always pass an "unknown date value for calculation
                    'analysis': [
                        {
                        'analysis_type': 'Alpha Ejection Correction',
                        'datum': [make_datum(*d) for d in Ft_data]
                        }]
                    }]}
                        
            self.db.load_data("sample", sample_schema)