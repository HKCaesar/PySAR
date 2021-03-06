#! /usr/bin/env python
############################################################
# Program is part of PySAR v1.0                            #
# Copyright(c) 2016, Yunjun Zhang                          #
# Author:  Yunjun Zhang                                    #
############################################################
# Based on scripts writen by Heresh Fattahi
# Yunjun, Aug 2016: add read_date_list()
# Yunjun, Oct 2016: update yymmdd() for string and list input
#
# Recommended Usage:
#   import pysar._datetime as ptime
#   dateList = ptime.igram_date_list('unwrapIfgram.h5')


import sys
import time
import datetime
from datetime import datetime as dt

import h5py
import numpy as np
import matplotlib.dates as mdates


################################################################
def yyyymmdd2years(dates):
    if isinstance(dates, basestring):
        d = dt(*time.strptime(dates,"%Y%m%d")[0:5])
        day_of_year = d.timetuple().tm_yday
        yy = float(d.year)+float(day_of_year-1)/365.25
        #yy = float(d.year) + float(d.month-1)/12 + float(d.day-1)/365.25
    elif isinstance(dates, list):
        yy = []
        for date in dates:
            d = dt(*time.strptime(date,"%Y%m%d")[0:5])
            day_of_year = d.timetuple().tm_yday
            yy.append(float(d.year)+float(day_of_year-1)/365.25)
    else:
        print 'Unrecognized date format. Only string and list supported.'
        sys.exit(1)
    return yy


def yymmdd2yyyymmdd(date):
    if date[0] == '9':      date = '19'+date
    else:                   date = '20'+date
    return date


def yyyymmdd(dates):
    if isinstance(dates,basestring):
        if len(dates) == 6:  datesOut = yymmdd2yyyymmdd(dates)
        else:                datesOut = dates
    elif isinstance(dates,list):
        datesOut = []
        for date in dates:
            if len(date) == 6:   date = yymmdd2yyyymmdd(date)
            datesOut.append(date)
    else:
        print 'Unrecognized date format. Only string and list supported.'
        sys.exit(1)
    return datesOut


def yymmdd(dates):
    if isinstance(dates,basestring):
        if len(dates) == 8:  datesOut = date[2:8]
        else:                datesOut = dates
    elif isinstance(dates,list):
        datesOut = []
        for date in dates:
            if len(date) == 8:   date = date[2:8]
            datesOut.append(date)
    else:
        print 'Unrecognized date format. Only string and list supported.'
        sys.exit(1)
    return datesOut


#################################################################
def igram_date_list(igramFile):
    '''Read Date List from Interferogram file
        for timeseries file, use h5file['timeseries'].keys() directly
    '''

    h5file = h5py.File(igramFile,'r')
    k = h5file.keys()
    if 'interferograms' in k: k[0] = 'interferograms'
    elif 'coherence'    in k: k[0] = 'coherence'
    if k[0] not in  ['interferograms','coherence','wrapped']:
        print 'Only interferograms / coherence / wrapped are supported.';  sys.exit(1)
    #print 'reading date list from '+k[0]
  
    dateList = []
    ifgramList = h5file[k[0]].keys()
    for ifgram in  ifgramList:
        dates = h5file[k[0]][ifgram].attrs['DATE12'].split('-')
        dates = yyyymmdd(dates)
        if not dates[0] in dateList: dateList.append(dates[0])
        if not dates[1] in dateList: dateList.append(dates[1])
    dateList.sort()
  
    #dateList6 = yymmdd(dateList)

    return dateList


#################################################################
def read_date_list(date_list_file):
    '''Read Date List from txt file'''
    fl = open(date_list_file,'r')
    dateList = fl.read().splitlines()
    fl.close()

    dateList = yyyymmdd(dateList)
    dateList.sort()

    return dateList


################################################################
def date_index(dateList):
    dateIndex={}
    for ni in range(len(dateList)):
        dateIndex[dateList[ni]] = ni
    return dateIndex

################################################################
def date_list2tbase(dateList):
    '''Get temporal Baseline in days with respect to the 1st date'''
    tbase=[]
    d1 = dt(*time.strptime(dateList[0],"%Y%m%d")[0:5])
    for ni in range(len(dateList)):
        d2 = dt(*time.strptime(dateList[ni],"%Y%m%d")[0:5])
        diff = d2-d1
        tbase.append(diff.days)
    ## Dictionary: key - date, value - temporal baseline
    dateDict = {}
    for i in range(len(dateList)):
        dateDict[dateList[i]] = tbase[i]
  
    return tbase, dateDict


################################################################
def date_list2vector(dateList):
    '''Get time in datetime format: datetime.datetime(2006, 5, 26, 0, 0)'''
    dates=[]
    for ni in range(len(dateList)):
        d = dt(*time.strptime(dateList[ni],"%Y%m%d")[0:5])
        dates.append(d)

    ## date in year - float format
    datevector=[]
    for i in range(len(dates)):
        dvector = dates[i].year + (dates[i].month-1)/12.0 + (dates[i].day-1)/365.0
        datevector.append(dvector)
    datevector2=[round(i,2) for i in datevector]
  
    return dates, datevector


################################################################
def auto_adjust_xaxis_date(ax, datevector, fontSize=12):
    '''Adjust X axis
    Input:
        ax : matplotlib figure axes object
        datevector : list of float, date in years
                     i.e. [2007.013698630137, 2007.521917808219, 2007.6463470319634]
    Output:
        ax : matplotlib figure axes object
    '''
    
    # Min/Max
    ts=datevector[0] -0.2;  ys=int(ts);  ms=int((ts-ys)*12.0)
    te=datevector[-1]+0.3;  ye=int(te);  me=int((te-ye)*12.0)
    if ms>12:   ys = ys+1;   ms=1
    if me>12:   ye = ye+1;   me=1
    if ms<1:    ys = ys-1;   ms=12
    if me<1:    ye = ye-1;   me=12
    dss=datetime.date(ys,ms,1)
    dee=datetime.date(ye,me,1)
    ax.set_xlim(dss,dee)
    
    # Label/Tick format
    ax.fmt_xdata = mdates.DateFormatter('%Y-%m-%d %H:%M:%S')
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
    ax.xaxis.set_minor_locator(mdates.MonthLocator())
    
    # Label font size
    for tick in ax.xaxis.get_major_ticks():
        tick.label.set_fontsize(fontSize)
    #fig2.autofmt_xdate()     #adjust x overlap by rorating, may enble again
    return ax

