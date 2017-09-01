import IPython
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.interpolate import interp1d
import scipy.optimize as opt
import os
from bluesky.plans import scan, baseline_decorator, subs_decorator,abs_set,adaptive_scan,spiral_fermat,spiral,scan_nd,mv
from bluesky.callbacks import LiveTable,LivePlot, CallbackBase
from pyOlog.SimpleOlogClient import SimpleOlogClient
from esm import ss_csv
from cycler import cycler
from collections import ChainMap
import math
import re
from boltons.iterutils import chunked
import sys
from suitcase import hdf5
from builtins import input as pyinput
ip=IPython.get_ipython()


###Utilities
###    The following set of code is used to create a series of utility functiosn for use at ESM.

def ESM_export(scan_ID,filename):
        '''
        This routine is used to export a data file to an HDF5 file for transfer to other analysis 
        software.

        PARAMETERS
        ----------

        scan_ID : list.
            The scan id numbers (as a list) for the data to export, can be -1, -2 to indicate the last
            or second to last scan etc.
 
        filename : str.
            The filename to use for the output data file.

        filestring : str, output
            The file path, and file name, of the file that was created.

        '''
        #reference the header file for the scan to be saved.
        hdr=db[scan_ID]

        # check if the filename includes the '.h5' extension and add it if not.
        if not filename.endswith('.h5'):
                filename+='.h5'

        # give the filepath of where to store the h5 file
        filepath='/direct/XF21ID1/hdf5_files/'+datetime.today().strftime('%Y_%m')
        
        #check if a current month directory exists, if not create it.
        if not os.path.exists(filepath):
            os.makedirs(filepath)

        #create the file path and file name string
        filestring=filepath+'/'+filename

        #check if the file already exists, if so ask user if overwrite is necesary.
        if os.path.isfile(filestring):
                if ask_user_continue('The file already exists, continuing will overwrite it')==0:
                    raise RuntimeError('user quit save')

                else:
                    os.remove(filestring)

        # actually write the new file
        hdf5.export(hdr,filestring)

        # return the file path and file name so the user can find it.
        return filestring

def channel_list_unpack(DETS_str):
        ''' 
        This function is used to unpack the detector input string and return a list of channels

        This function is used to unpack the detector list string used as an input into our "scans" 
        and "notebook" routines and returns a list of channels that it relates to for plotting and/
        or data analysis.

        PARAMETERS
        ----------
        
        DETS_str : str
            The input string that is to be "unpacked" into a channel list. This needs to have the 
                format definitions: 
                    - DETX is the name of 'Xth' detector.
                    - every '@' symbol defines a new channel number for the preceeding detector.
                    - ChX is the channel number of the 'Xth' channel.
                    -    if ChX is 0 then it returns no channels for this detector.
                    -    if ChX is -1 then it returns all channels for this detector.
                    - every '-' symbol defines a new value for the preceeding channel number.
                    - ValX is the name of the 'Xth' value, and can be 'total', 'max' or 'min'.

                format1:  'DET1@Ch1-Val1-Val2-...@Ch2-Val1-...., DET2@Ch1-Val1-...@.... ,....'
                    If no '@' is present for a detector then it reverts to the default of channel 1.
                    If no '-' is present it reverts to the default 'Total'.

                format2: 'DET1,    DET2    ,......,   @Ch1-val1-val2-...@Ch2-val2-...@...'
                    This returns The channels and values defined by the last list entry for all 
                    detectors.
                    If no '-' is present it reverts to the default 'Total'.               


                            
 
        name_list : list, output
            The output list of channels.
        '''
        name_list=[]
        #define the empty output list

        #split the detectors str into a list of detector strs
        DET_list=DETS_str.split(',')

        # check if format 1 or format 2 is being used.

        if  DET_list[-1].startswith('@'):
            #If format 2 is used
            Channel_list=DET_list[-1][1:].split('@')    
            DET_list=DET_list[:-1]
            Format = 2
        else:
            Format = 1
            
        for i,DET_str in enumerate(DET_list):
            DET=DET_str.partition('@')[0]
            if Format == 1:
            #If format 1 is used
                Channel_list=DET_str.partition('@')[2].split('@')
   
            if len(Channel_list[0]) == 0:
                #if no channels are defined for this detector.
                name_list.append(format_channel_name(DET,1,Value='total'))

            elif '-1' in Channel_list:
                #if all channels are defined. for this detector.
                name_list+= format_channel_name(DET,-1).split(',')
                    
            elif '0' not in Channel_list:
                #if some channels are defined for this detector. 
                for j,Channel_str in enumerate(Channel_list):
                    Channel=Channel_str.partition('-')[0]
                    Value_list=Channel_str.partition('-')[2].split('-')

                    if len(Value_list[0]) == 0:
                        #if no valuess are defined for this detector.
                        name_list.append(format_channel_name(DET,Channel))
                    else:
                        #if there are values listed for this channel.
                        for k,Value in enumerate(Value_list):
                            name_list.append(format_channel_name(DET,Channel,Value))
                            


        return name_list

def format_channel_name(DET,Channel,Value='total'):
        ''' 
        This function formats the channel name for a given detector type.
        
        This function takes in the detctor name, channel number, and an optional channel value
        and returns a formated channel name string for this type of detector. If 'Channel' is -1 
        then it returns a string containg all the possible channel names for the detector, 
        seperated by commas.

        PARAMETERS
        ----------
        DET: str
            The name of the detector for which the channel is to be formatted        

        Channel: integer
            The channel number for the  channel to be formatted

        Value: str,optional
            The optional "value" for the channel number. 

        channel_name : str
            The output string that is the formatted channel name.
        '''


        if 'qem' in DET.lower():
            #if the detector is a qem.
            if Channel == -1:
                channel_name=''
                for i in range(1,5):
                    if i > 1: channel_name+=','
                    channel_name+=DET+'_current'+str(i)+'_mean_value'

            else:        
                channel_name=DET+'_current'+str(Channel)+'_mean_value'
            
        elif 'cam' in DET.lower():
            #if the detctor is a camera.
            if Channel == -1:
                channel_name=''
                for i in range(1,5):
                    if i > 1: channel_name+=','
                    channel_name+=DET+'_stats'+str(i)+'_total,'
                    channel_name+=DET+'_stats'+str(i)+'_max_value,'
                    channel_name+=DET+'_stats'+str(i)+'_min_value'
            else:
                if 'max' in Value or 'min' in Value:
                    Value+='_value'
                channel_name=DET+'_stats'+str(Channel)+'_'+Value

        else:
            #If the detcor type has not been determined.
            raise ValueError("Detector type not recognised, name must contain 'qem' or 'cam'.")

        

        return channel_name
        
            
def ask_user_continue(request_str):
        ''' 
        This function asks the user to confirm that the current process should be completed.
        
        This function asks the user, using the request_str to give specifics, if they should continue.

        PARAMETERS
        ----------
        
        request_str : str
            The output string given with the user prompt.
        '''

        valid={'yes':1,'no':0}
        prompt_str = ', continue(yes or no):'

        while True:
            sys.stdout.write(request_str + prompt_str)
            choice = pyinput().lower()
            if choice in valid:
                return valid[choice]

        

def SiC2F(photon_energy, current):
        '''
        This routine is used to convert an XUV Si-diode current to flux.
   
        Given the photon energy (in eV) and the XUV Si-diode current (in microAmp), returns the flux 
        (ph/sec). It uses the QY for a typical XUV Si-diode.

        PARAMETERS
        ----------

        photon_energy : float
            The photon energy that was incidnent on the diode.

        current : float
            The measured current on the diode.

        flux : float, output
            The flux that is returned. 

        '''



        # XUV QY data: number of electrons per 1 photons of a given photon energy
        SiC2F_data={ 'E_eV' : [1,1.25,2,2.75,3,4,5,6,7,8,9,10,20,40,60,80,100,120,140,160,180,200,220,
                               240,260,280,300,320,340,360,380,400,420,440,460,480,500, 520, 540,560,
                               580,600,620,640,740,760,780,800,820,840,860,880,900,920,940,960,980,1000,
                               1200,1400,1600,1800,2000,2200,2400,2600,2800, 3000,3200,3400,3600,3800,
                               4000,4200,4400,4600,4800,5000,5200,5400,5600,5800,6000] ,
                     'QY' : [0.023, 0.32 ,0.64,0.57,0.49,0.432,0.45,0.5,0.7,1,1.05,1.1,3.25,8.38,12.18,
                             17.85,22.72,26.42,31.37,33.5,42.95,50.68,60.61,66.12,71.63,77.13, 82.64,
                             88.15,93.66,99.17,104.68,110.19,115.7,121.21,126.72,132.23,137.74,143.25,
                             148.76,154.27,159.78,165.29,170.8,176.31,203.86,209.37, 214.88,220.39,
                             225.9,231.41,236.91,242.42,247.94,253.44,258.95,264.46,269.97,275.48,
                             330.58,385.67,440.77,495.87,550.96,606.06,661.18,716.35, 771.35,826.45,
                             881.54,936.64,991.74,1046.83,1101.93,1157.02,1212.12,1267.22,1322.31,
                             1377.41,1432.51,1487.6,1542.7,1597.8,1652.89]}
        SiCtoF = interp1d(SiC2F_data['E_eV'],SiC2F_data['QY'])
        
        if (photon_energy < min(SiC2F_data('E_eV')) or photon_energy > max(SiC2F_data('E_eV'))):
                raise RuntimeError('photon energy outside of range of conversion data')
        else:
            flux =  (current)/(1.6E-19)/SiCtoF(photon_energy)
            return flux


def gaussian_1D(x,params):
    '''This function defines a 2D gaussian that is used for fitting.
    Parameters
    ----------
    x : variable
        the axis variable for the 1D gaussian.
    params : variables
        the list of "fitting" variables for the 2D gaussian
            Parameters:

            1. amp  =  the amplitude of the 1D guassian
            2. cen =  the centre of the first axis gaussian
            4. std = the width of the first axis gaussian
            6. bkg  = height of the constant background for the gaussian
    '''
    amp,cen,std,bkg = params
    return amp*np.exp(-(x-cen)**2/2/std**2)+bkg

def gaussian_1D_error(params,y,x):
    '''This function defines the difference between a fitted gaussian and the raw data.
    Parameters
    ----------
    params : variables
        the list of "fitting" variables for the 2D gaussian
            Parameters:

            1. amp  =  the amplitude of the 1D guassian
            2. cen =  the centre of the first axis gaussian
            4. std = the width of the first axis gaussian
            6. bkg  = height of the constant background for the gaussian

    y  : variable 
        the value of the raw data at (x)
    x : variable
        the axis variable for the 1D gaussian.
    '''

    return gaussian_1D(x, params)-y
                      
    
def gaussian_2D(x1,x2,params):
    '''This function defines a 2D gaussian that is used for fitting.
    Parameters
    ----------
    x1 : variable
        the first axis variable for the 2D gaussian.
    x2 : variable
        the second axis variable for the 2D gaussian.
    params : variables
        the list of "fitting" variables for the 2D gaussian
            Parameters:

            1. amp  =  the amplitude of the 2D guassian
            2. cen1 =  the centre of the first axis gaussian
            3. cen2 = the centre of the 2nd axis guassian 
            4. std1 = the width of the first axis gaussian
            5. std2 = the width of the second axis gaussian
            6. bkg  = height of the constant background for the gaussian
    '''
    amp,cen1,cen2,std1,std2,bkg = params
    return amp*np.exp(-(x1-cen1)**2/2/std1**2-(x2-cen2)**2/2/std2**2)+bkg

def gaussian_2D_error(params,y,x1,x2):
    '''This function defines the difference between a fitted gaussian and the raw data.
    Parameters
    ----------
    params : variables
        the list of "fitting" variables for the 2D gaussian
            Parameters:

            1. amp  =  the amplitude of the 2D guassian
            2. cen1 =  the centre of the first axis gaussian
            3. cen2 = the centre of the 2nd axis guassian 
            4. std1 = the width of the first axis gaussian
            5. std2 = the width of the second axis gaussian
            6. bkg  = height of the constant background for the gaussian
    y  : variable 
        the value of the raw data at (x1, y1)
    x1 : variable
        the first axis variable for the 2D gaussian.
    x2 : variable
        the second axis variable for the 2D gaussian.
    '''

    return gaussian_2D(x1, x2, params)-y


def fit_Gauss_1Dseries(uid,initial_guess):
    ''' 
    This scan fits 1D Gaussian curves o each line in a 2D dataset giben by uid.
        
    This scan is used to fit to a 1D Gaussian to each line in a 2D dataset, the output is then a set of 1D data corresponding to the
    amplitude, position and linewidth as a fucntion of the Y axis of the dataset. The function returns a list with 4 items, the items 
    being the data for amplitude,position, linewidth, background offset and y_sequence number.                   

    Parameters
    ----------
    uid : number
        This is the uid used to extract the data from the databroker.
                                       
    initial_guess : list
        This is the initial guess for the amplitude, centre, width and background offset, in a list in this order.

    '''  

    #reference the data
    hdr=db[uid]
    
    #find out the shape of the data
    x_num = hdr.start.X_num
    y_num = hdr.start.Y_num
        
    #Load the data from the databroker.
   
    amplitude=[]
    linewidth=[]
    position=[]
    background=[]
    y_seq=[]
        
    #step through each "row" and fit a gaussian.
    for y_step in range(0,y_num):
        x = db.get_table(hdr,[hdr.start.plot_Xaxis])[x_num*y_step:x_num*(y_step+1)-1] 
        y_seq.append(y_step)
        data = db.get_table(hdr,[hdr.start.plot_Zaxis])[x_num*y_step:x_num*(y_step+1)-1]

        popt_row, pcov_row = opt.leastsq(gaussian_1D_error,x0=initial_guess,args=(data[hdr.start.plot_Zaxis],x[hdr.start.plot_Xaxis]))
        amplitude.append(popt_row[0])
        position.append(popt_row[1])
        linewidth.append(popt_row[2])
        background.append(popt_row[3])

        initial_guess[0]=popt_row[0]
        initial_guess[1]=popt_row[1]
        initial_guess[2]=popt_row[2]
        initial_guess[3]=popt_row[3]

        
    return [amplitude,linewidth,position,background,y_seq]
    

def max_in_1D(uid):
    ''' 
    This scan is used to find the maximum value in a 1D data set and return the max value, and the x co-ordinate.
        
    This scan is used to find the maximum value in a 1D dataset and return the max value, and the x co-ordinate.
    It returns a list containing the x and y values for the maximum y value in the dataset.                   

    Parameters
    ----------
    uid : number
        This is the uid used to extract the data from the databroker.

    '''
    
    scan = db[scan_id]
    if scan.start.plot_Xaxis.startswith('FE'):
        Xname = scan.start.plot_Xaxis.replace('_readback', '_setpoint')
    else:
        Xname = scan.start.plot_Xaxis+'_user_setpoint'
        
    data2D = db.get_table(scan,[Xname, scan.start.plot_Yaxis])
    del data2D['time']

    max_idx = np.argmax(data3D[scan.start.plot_Yaxis], axis=None)

    return [data2D[Xname][max_idx],data2D[scan.start.plot_Yaxis][max_idx]]


def max_in_2D(uid):
    ''' 
    This scan is used to find the maximum value in a 2D data set and return the max value, and the x and y co-ordinates.
        
    This scan is used to find the maximum value in a 2D dataset and return the max value, and the x and y co-ordinates.
    It returns a list containg the x, y and z values for the maximum z value in the dataset.                   

    Parameters
    ----------
    uid : number
        This is the uid used to extract the data from the databroker.

    '''
    
    scan = db[scan_id]
    if scan.start.plot_Xaxis.startswith('FE'):
        Xname = scan.start.plot_Xaxis.replace('_readback', '_setpoint')
        Yname = scan.start.plot_Yaxis.replace('_readback', '_setpoint')
    else:
        Xname = scan.start.plot_Xaxis+'_user_setpoint'
        Yname = scan.start.plot_Yaxis+'_user_setpoint'
        
    data3D = db.get_table(scan,[Xname, Yname, scan.start.plot_Zaxis])
    del data3D['time']

    max_idx = np.argmax(data3D[scan.start.plot_Zaxis], axis=None)

    return [data3D[Xname][max_idx],data3D[Yname][max_idx],data3D[scan.start.plot_Zaxis][max_idx]]