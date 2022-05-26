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

# Replicates Ketcham et al., 2011 for Ft calculation
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

# Function to make datum
def make_datum(datum, error, parameter, unit):
    return {'value': datum, 'error': error,
            'type': {'parameter': parameter, 'unit': unit}}

# Function to make attributes
def make_attribute(value, parameter):
    return {'parameter': parameter,
            'value': str(value)}

class TRaILpicking(BaseImporter):
    def __init__(self, app, data_dir, **kwargs):
        super().__init__(app)
        # file_list = glob.glob(str(data_dir)+'/PickingData/*.xlsx')
        file_list = glob.glob(str(data_dir)+'/PickingData/Picking_data_example.xlsx')
        self.iterfiles(file_list, **kwargs)
    
    
    # Method to generate a lab ID for a new sample based on the date of the analysis
    def make_labID(self, row):
        date = str(row['Date Packed'].year)[-2:]
        # Query database for all lab IDs
        all_IDs = [el for tup in self.db.session.query(self.db.model.sample.lab_id).all()
                   for el in tup if el is not None]
        # Isolate lab IDs from the same year
        same_year = [i for i in all_IDs if date+'-' in i]
        # Get the highest numbered analysis for the year and add 1
        if len(same_year) > 0:
            max_num = max([int(i.split('-')[1]) for i in same_year])
        else:
            max_num = 0
        id_num = max_num+1
        # Combine year and analysis number to get lab_id
        lab_id = date+'-'+f'{id_num:05d}'
        return lab_id

    def import_datafile(self, fn, rec, **kwargs):
        data = pd.read_excel(fn,
                             skiprows = range(2,6),
                             header = 1,
                             sheet_name = 'master')

        # Load the picking specs. This file dictates virtually everything about this import
        spec = relative_path(__file__, 'picking_specs.yaml')
        with open(spec) as f:
            self.picking_specs = load(f)
        
        # Find actual data by figuring out where the analyst rows are full
        data = data[data[self.picking_specs['Metadata']['Researcher']].notnull()]
        
        for d in range(len(data)):
            # Generate a lab ID for each grain
            lab_id = self.make_labID(data.iloc[d])
            
            # Generate metadata required for every grain
            researcher = str(data.iloc[d][self.picking_specs['Metadata']['Researcher']])
            sample = data.iloc[d][self.picking_specs['Metadata']['Sample']]
            grain = data.iloc[d][self.picking_specs['Metadata']['Grain']]
            print('Importing: '+sample+'_'+grain)
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
                    error = None
                    shape_data.append([value, error, s[col]['name'], s[col]['unit']])
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
                Fts = False#{'238U': 1, '235U': 1, '232Th': 1, '147Sm': 1}
                shape_dict = {
                    'analysis_type': 'Grain Shape',
                    'attribute': [make_attribute('Crystal shard', 'Shape notes')]
                    }
            
            # create datum and attributes for characteristics analysis
            # Characteristics will always be recorded, even for shards
            chars_attributes = []
            for s in self.picking_specs['Characteristics']['attributes']:
                col = next(iter(s))
                value = str(data.iloc[d][col])
                chars_attributes.append([value, s[col]])
            # make analysis dictionary, exclude missing data if shards
            if shard != 'Y' and shard != 'y':
                # First, get uncertainty for each derived parameter
                for l in chars_attributes:
                    for i in l:
                        # get derived data uncertainties for later
                        if 'Idealness' in i:
                            xtalform = l[0]
                            dim_mass_err = self.picking_specs['Dim_mass_key'][xtalform]
                            Rs_err = self.picking_specs['Rs_err_key'][xtalform]
                            Ft_err = self.picking_specs['Ft_err_key'][xtalform]
                # Cast attributes (no data for characteristics) for analysis to dictionary
                chars_dict = {
                    'analysis_type': 'Grain Characteristics',
                    'attribute': [make_attribute(*a) for a in chars_attributes]
                    }
            
            # TODO add more complicated researcher-laboratory schema from yaml/csv
            # Create a new sample in the database using the picking sheet metadata
            sample_schema = {
                'member_of': {'name': sample,
                              'material': 'rock'},
                'researcher': [{'name': researcher}],
                #'Lab_Owner': researcher,
                'name': sample+'_'+grain,
                'material': material,
                'lab_id': lab_id,
                'from_archive': 'false',
                'session': [
                    {
                    'technique': {'id': 'Picking Information'},
                    'instrument': {'name': 'Leica microscope'},
                    'date': date,
                    'analysis': [
                        shape_dict,
                        chars_dict
                        ]
                    }]
                    }
            
            # Only incude derived data if not a shard
            if Fts:
                # Compile Ft data for date calculation session
                Ft_data = [
                    [Fts['238U'], Fts['238U']*Ft_err, '238U Ft', ''],
                    [Fts['235U'], Fts['235U']*Ft_err,'235U Ft', ''],
                    [Fts['232Th'], Fts['232Th']*Ft_err,'232Th Ft', ''],
                    [Fts['147Sm'], Fts['147Sm']*Ft_err,'147Sm Ft', ''],
                    ]
                Rs_mass = [
                    [dimensional_mass, dimensional_mass*dim_mass_err, 'Dimensional mass', 'μg'],
                    [Fts['Rs'], Fts['Rs']*Rs_err, 'Equivalent Spherical Radius', 'μm']
                    ]
                
                sample_schema['session'].append({
                    'technique': {'id': 'Dates and other derived data'},
                    'date': '1900-01-01 00:00:00+00', # always pass an 'unknown date' value for calculation
                    'analysis': [
                        {
                        'analysis_type': 'Alpha ejection correction values',
                        'datum': [make_datum(*d) for d in Ft_data]
                        },
                        {
                        'analysis_type': 'Rs, mass, concentrations',
                        'datum': [make_datum(*d) for d in Rs_mass]
                        }]
                        })
            
            print(sample_schema)
            print('')
            self.db.load_data('sample', sample_schema, strict=True)