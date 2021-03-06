#! /usr/bin/env python
############################################################
# Program is part of PySAR v1.0                            #
# Copyright(c) 2013, Heresh Fattahi                        #
# Author:  Heresh Fattahi                                  #
############################################################
# Yunjun, Aug 2015: Add minDate/maxDate/excludeDateList/contour option
#                   Add radius option and errorbar in the plot
# Yunjun, Sep 2015: Add x/y/dispVelFig/dispTsFig option
# Yunjun, Jun 2016: Add date_list2vector(), check_yx(), read_dis()
#                   Add reference point display
#                   Add plot_ts(), auto_adjust_xaxis_date()
# Yunjun, Jul 2016: Support reference date input
#                   Support Zoom in for figure 1
#                   Support lalo input
# Yunjun, Dec 2016: Add read_dis_lalo()


import sys
import os
import getopt
import time
import datetime

import h5py
import numpy as np
import scipy.io as sio
import scipy.stats as stats

import matplotlib.dates as mdates
import matplotlib.patches as patches      # need for draw rectangle of points selected on VelFig
import matplotlib.pyplot as plt

import pysar._readfile as readfile
import pysar._datetime as ptime
import pysar.subset as subset
import pysar.view as view


################################## Sub Functions ###################################
################################################################
def check_yx(xsub,ysub,radius,ax,rectColor='black'):
    ##### Read Y/X
    try:     xmin=xsub[0];         xmax=xsub[1];
    except:  xmin=xsub[0]-radius;  xmax=xsub[0]+radius;
    try:     ymin=ysub[0];         ymax=ysub[1];       
    except:  ymin=ysub[0]-radius;  ymax=ysub[0]+radius;

    ## mark x/y in Fig 1
    rectSelect=patches.Rectangle((xmin,ymin),xmax-xmin,ymax-ymin,color=rectColor,fill=False,lw=1.5)
    ax.add_patch(rectSelect)

    return [xmin,xmax],[ymin,ymax]

################################################################
def read_dis_xy(xsub,ysub,dateList,h5file,unit='cm'):
    global ref_date

    ## Unit and Scale
    if   unit == 'm' :  unitFac=1.0
    elif unit == 'mm':  unitFac=1000.0
    elif unit == 'km':  unitFac=0.001
    else:unit =  'cm';  unitFac=100.0   # cm by default

    ## read displacement
    try:
        ref_date
        dis_ref = h5file['timeseries'].get(ref_date)[ysub[0]:ysub[1]+1,xsub[0]:xsub[1]+1]
    except: pass

    dis=[]
    for date in dateList:
        dis0 = h5file['timeseries'].get(date)[ysub[0]:ysub[1]+1,xsub[0]:xsub[1]+1]
        try: dis0 -= dis_ref
        except: pass
        dis.append(dis0)
    dis=np.array(dis)*unitFac;
    dis=np.reshape(dis,(len(dateList),-1))

    ## calculate mean
    dis_mean=np.nanmean(dis,1)
    ## calculate standard deviation
    if (xsub[1]-xsub[0])*(ysub[1]-ysub[0]) == 1:
        dis_std = np.array([0]*len(dateList))
    else:
        dis_std = np.nanstd(dis,1)

    ## display
    print 'spatial averaged displacement ['+unit+']:'
    print dis_mean
    print 'standard deviation ['+unit+']:'
    print dis_std

    ## calculate linear velocity
    try:
        dates, datevector = ptime.date_list2vector(dateList)
        dis_slope = stats.linregress(np.array(datevector),dis_mean)
        print 'linear velocity ['+unit+'/yr]:'
        print str(dis_slope[0])+'+/-'+str(dis_slope[4])
    except:  pass

    try:     return dis, dis_mean, dis_std, dis_slope
    except:  return dis, dis_mean, dis_std

################################################################
def read_dis_lalo(lat,lon,dateList,timeseriesFile,radius=0,unit='cm'):
    atr = readfile.read_attribute(timeseriesFile)
    h5 = h5py.File(timeseriesFile,'r')

    x = subset.coord_geo2radar(lon,atr,'longitude');
    y = subset.coord_geo2radar(lat,atr,'latitude');
    if radius == 0:  radius = 3
    xsub = [x-radius,x+radius]
    ysub = [y-radius,y+radius]

    dis,dis_mean,dis_std = read_dis_xy(xsub,ysub,dateList,h5,unit)[0:3]
    h5.close()
 
    return dis,dis_mean,dis_std
    
################################################################
def update_lim(disp_min,disp_max,data_mean,data_std):
    disp_min = np.nanmin([np.nanmin(data_mean-data_std), disp_min])
    disp_max = np.nanmax([np.nanmax(data_mean+data_std), disp_max])
    return disp_min,disp_max


########################## Usage ###############################
def usage():
    print '''
*******************************************************************************************************
  Time-series Viewer

  Usage:
      tsviewer.py -f timeseriesFile.h5 -v velocityFile.h5 -l lower bound -h higher bound
                  -s fontsize -m Marker Size -c marker color -w linewidth -u unit

      -f : file of the timeseries
      -f2: 
      -v : velocity file, or epoch_date (if not specified then the last time-series epoch is displayed)
      -v2: 
      -l : lower bound of the displacement [default is min of the displacemen]
      -h : higher bound of the displacemet [default is max of the displacemen]
      -a : lower bound of the colorscale to display the velocity to display
      -b : higher bound of the colorscale to display the velocity to display
      -F : another  timeseries file (can be used to compare 2 time-series)
      --opposite     : show opposite value in velocity figure
      --displacement : show displacement instead of phase, work only for interferogram

    Figure Setting
      -s : size of font used x and y labels [default = 22]
      -m : marker size [default = 16]
      -c : color of the markers [default = green]. some options are: orange, black, yellow, blue, green...
      -w : width of lines to connect the points [default = 2].
           set to 0 (-l 0) if you don't want any line connecting the points
      -u/--unit    : unit of the displacement [default = cm]. Other optons are: mm and m
      --rect-color : color of rectangle that mark the selection in velocity figure, 'crimson' by default
      --zoomx      : subset/zoom in x/range/longtitude direction
      --zoomy      : subset/zoom in y/azimuth/latitude direction

    XY Input (both input ends are included)
      -r : radius of selecting square in pixels, display mean value from (+/-radius,+/-radius).
           [default is 0 - one point]
      -x : x coordinate (range) of selection
      -y : y coordinate (range) of selection
      -X : x coordinate (range) of reference / comparison
      -Y : y coordinate (range) of reference / comparison
      --lalo : latitude and longitude of selection (recommend to use it with -r option for now)
               i.e.  --lalo 32.12,130.59
      --LALO : latitude and longitude of reference/comparison

    DEM
      -D : dem file
      --dem-nocontour  : do not show DEM contour
      --dem-noshade    : do not show DEM shaded relief
      --contour-step   : contour step                      (default is 200 meters)
      --contour-smooth : contour smooth ( Sigma of Gaussian Filter, default is 3.0; Set to 0 for no smoothing) 


    Date Input
      -t : minimum date for display
      -T : maximum date for display
      -E/--exclude : exclude dates list for display
      --ref-date   : reference date for time series displacement
      --zero-start : set the first displacement as zero, yes or no [yes by default]

    Save and Output
      --save       : save data and plot                     - save timeseries data/plot
      --nodisplay  : save data and plots and do not display - save timeseries data/plot and velocity plot
                     default output filename:
                     x100_110y230_240_ts.mat
                     x100_110y230_240_ts.pdf
                     x100_110y230_240_vel.png

  Example:
      tsviewer.py timeseries.h5
      tsviewer.py -f timeseries.h5 -v velocity.h5 -a -0.01 -b 0.01
      tsviewer.py -f timeseries.h5 -v 20080929
      tsviewer.py -f timeseries.h5 -s 24 -m 12 -c orange -l -10 -h 10 -w 4 -u mm 

      tsviewer.py -f timeseries.h5 -v velocity.h5 -a -0.01 -b 0.02 -l -10 -h 10 -D Andreas.dem -C yes --save

    Exclude dates:
      tsviewer.py -f timeseries.h5 -v velocity.h5 -t 20100102 -T 20101120 -E '20100520,20100705'
      tsviewer.py -f timeseries.h5 -v velocity.h5 -E drop_date.txt

    Compare two timeseries files:
      tsviewer.py -f timeseries.h5 -v velocity.h5 -F timeseries_tropCor.h5 
      tsviewer.py -f timeseries.h5 -v velocity.h5 -F timeseries.h5        -E '20100520,20100705'  

    X/Y Input:
      tsviewer.py -f timeseries.h5 -v velocity.h5 -r 10
      tsviewer.py -f timeseries.h5 -v velocity.h5 -x 300     -y 500      -r 10
      tsviewer.py -f timeseries.h5 -v velocity.h5 -x 300:330 -y 500:530
      tsviewer.py -f timeseries.h5 -v velocity.h5 -a -0.02 -b 0.02 -l -5 -h 5 -D Andreas.dem
                  -x 300:330 -y 500:530 --nodisplay --zoom-x 300:800 --zoom-y 500:1500

*******************************************************************************************************
    '''


###############################  Main Function  ####################################

def main(argv):

    ## Default settings
    contour_step  = 200.0
    contour_sigma = 3.0
    demShade   = 'yes'
    demContour = 'yes'

    global markerSize, markderSize2, markerColor, markerColor2, rectColor
    global lineWidth, lineWidth2, edgeWidth, fontSize
    #global markerColor_ref, markerColor_ref2

    markerSize   = 16
    markerSize2  = 16
    markerColor  = 'crimson'     # g
    markerColor2 = 'lightgray'
    markerColor_ref  = 'white'
    markerColor_ref2 = 'lightgray'
    rectColor    = 'black'
    lineWidth    = 0
    lineWidth2   = 0
    edgeWidth    = 1.5
    fontSize     = 16

    global unit, radius, saveFig, dispFig, fig_dpi

    fig_dpi = 300
    radius  = 0
    saveFig = 'no'
    dispFig = 'yes'
    unit    = 'cm'

    dispDisplacement = 'no'
    dispOpposite  = 'no'
    dispContour   = 'only'
    smoothContour = 'no'
    contour_step  = 200
    showRef       = 'yes'
    vel_alpha     = 1.0
    zero_start    = 'yes'

    global ref_xsub, ref_ysub, ref_date
    global h5timeseries_2, dates_2, dateList_2
    global lbound, hbound

    ############### Check Inputs ##################
    if   len(sys.argv)< 2:   usage(); sys.exit(1)
    elif len(sys.argv)==2:
        if argv[0]=='-h':      usage(); sys.exit(1)
        elif os.path.isfile(argv[0]):
            timeSeriesFile = argv[0];
            h5timeseries = h5py.File(timeSeriesFile);
            k = h5timeseries.keys();
            if not 'timeseries' in k:
                print 'ERROR: Input file is '+k[0]+'.\n\tOnly timeseries is supported.\n';
                sys.exit(1)
        else:  usage(); sys.exit(1)

    elif len(sys.argv)>2:
        try:   opts, args = getopt.getopt(argv,"f:F:v:a:b:s:m:c:w:u:l:h:D:V:t:T:d:r:x:y:X:Y:o:E:",
                                              ['save','nodisplay','unit=','exclude=','ref-date=','rect-color=',\
                                               'zero-start=','zoom-x=','zoom-y=','zoom-lon','zoom-lat','lalo=',\
                                               'opposite','dem-nocontour','dem-noshade','displacement','contour-step=',\
                                               'contour-smooth=','LALO='])
        except getopt.GetoptError:    usage() ; sys.exit(1)

        for opt,arg in opts:
            if   opt == '-f':     timeSeriesFile   = arg
            elif opt == '-F':     timeSeriesFile_2 = arg
            elif opt == '-v':     velocityFile     = arg
            elif opt == '-a':     vmin             = float(arg)
            elif opt == '-b':     vmax             = float(arg)
            elif opt == '-s':     fontSize         = int(arg)
            elif opt == '-m':     markerSize       = int(arg);       markerSize2=int(arg)
            elif opt == '-c':     markerColor      = arg
            elif opt == '-w':     lineWidth        = int(arg)
            elif opt == '-u':     unit             = arg
            elif opt == '-l':     lbound           = float(arg)
            elif opt == '-h':     hbound           = float(arg)
            elif opt == '-D':     demFile          = arg
            elif opt == '-V':     contour_step     = float(arg)
            elif opt == '-t':     minDate          = arg
            elif opt == '-T':     maxDate          = arg
            elif opt == '-r':     radius           = abs(int(arg))
            elif opt == '-x':     xsub = sorted([int(i) for i in arg.split(':')])
            elif opt == '-y':     ysub = sorted([int(i) for i in arg.split(':')])
            elif opt == '-X':     ref_xsub = sorted([int(i) for i in arg.split(':')])
            elif opt == '-Y':     ref_ysub = sorted([int(i) for i in arg.split(':')])

            elif opt == '--contour-step'   : contour_step    = float(arg)
            elif opt == '--contour-smooth' : contour_sigma   = float(arg)
            elif opt == '--dem-nocontour'  : demContour      = 'no'
            elif opt == '--dem-noshade'    : demShade        = 'no'
            elif opt == '--displacement'   : dispDisplacement= 'yes'
            elif opt in ['-E','--exclude'] : datesNot2show   = arg.split(',')
            elif opt in '--lalo'           : lalosub         = [float(i) for i in arg.split(',')]
            elif opt in '--LALO'           : ref_lalosub     = [float(i) for i in arg.split(',')]
            elif opt in ['--rect-color']   : rectColor       = arg
            elif opt in ['--ref-date']     : ref_date        = ptime.yyyymmdd(arg)
            elif opt in ['-u','--unit']    : unit            = arg.lower()
            elif opt == '--save'           : saveFig         = 'yes'
            elif opt == '--nodisplay'      : dispFig         = 'no';   saveFig='yes'
            elif opt == '--opposite'       : dispOpposite    = 'yes'
            elif opt == '--zero-start'     : zero_start      = arg.lower()
            elif opt == '--zoom-x'         : win_x           = sorted([int(i)   for i in arg.split(':')])
            elif opt == '--zoom-y'         : win_y           = sorted([int(i)   for i in arg.split(':')])
            elif opt == '--zoom-lon'       : win_lon         = sorted([float(i) for i in arg.split(':')])
            elif opt == '--zoom-lat'       : win_lat         = sorted([float(i) for i in arg.split(':')])


    ##############################################################
    ## Read time series file info
    if not os.path.isfile(timeSeriesFile):
        print '\nERROR: Input time series file does not exist: '+timeSeriesFile+'\n'
        sys.exit(1)
    h5timeseries = h5py.File(timeSeriesFile,'r')
    k = h5timeseries.keys();       # read h5 file and its group type
    if not 'timeseries' in k:
        print 'ERROR: Input file is '+k[0]+'.\n\tOnly timeseries is supported.\n';
        sys.exit(1)

    atr = readfile.read_attribute(timeSeriesFile)
    dateList1 = sorted(h5timeseries['timeseries'].keys())
    dates1,datevector1 = ptime.date_list2vector(dateList1)
    print '\n************ Time Series Display - Point *************'

    ##### Select Check
    try:
        lalosub
        xsub = subset.coord_geo2radar([lalosub[1]],atr,'longitude')
        ysub = subset.coord_geo2radar([lalosub[0]],atr,'latitude')
        xsub = [xsub]
        ysub = [ysub]
        if radius == 0:  radius = 3
    except: pass

    try:
        ref_lalosub
        ref_xsub = subset.coord_geo2radar([ref_lalosub[1]],atr,'longitude')
        ref_ysub = subset.coord_geo2radar([ref_lalosub[0]],atr,'latitude')
        ref_xsub = [ref_xsub]
        ref_ysub = [ref_ysub]
        if radius == 0:  radius = 3
    except: pass

    ##############################################################
    global dates, dateList, datevector_all, dateListMinMax

    print '*******************'
    print 'All dates existed:'
    print dateList1
    print '*******************'

    ## Check exclude date input
    try:
        datesNot2show
        if os.path.isfile(datesNot2show[0]):
            try:  datesNot2show = ptime.read_date_list(datesNot2show[0])
            except:  print 'Can not read date list file: '+datesNot2show[0]
        print 'dates not to show: '+str(datesNot2show)
    except:  datesNot2show=[]

    ## Check Min / Max Date
    dateListMinMax = []
    try:
        minDate
        minDate   = ptime.yyyymmdd(minDate)
        dateListMinMax.append(minDate)
        minDateyy = ptime.yyyymmdd2years(minDate)
        print 'minimum date: '+minDate
        for date in dateList1:
            yy=ptime.yyyymmdd2years(date)
            if yy < minDateyy:
                datesNot2show.append(date)
    except:  pass
    try:
        maxDate
        maxDate   = ptime.yyyymmdd(maxDate)
        dateListMinMax.append(maxDate)
        maxDateyy = ptime.yyyymmdd2years(maxDate)
        print 'maximum date: '+maxDate
        for date in dateList1:
            yy=ptime.yyyymmdd2years(date)
            if yy > maxDateyy:
                datesNot2show.append(date)
    except:  pass
    
    dateListMinMax = sorted(dateListMinMax)
    if not dateListMinMax:  print 'no min/max date input.'
    else:  datesMinMax, dateVecMinMax = ptime.date_list2vector(dateListMinMax)

    ## Finalize Date List
    try:
        dateList=[]
        for date in dateList1:
            if date not in datesNot2show:
                dateList.append(date)
        print '--------------------------------------------'
        print 'dates used to show time series displacements:'
        print dateList
        print '--------------------------------------------'
    except:
        dateList=dateList1
        print 'using all dates to show time series displacement'

    ## Read Date Info (x axis for time series display)
    dates,datevector = ptime.date_list2vector(dateList)
    datevector_all = list(datevector)

    ## Check reference date input
    try:
        ref_date
        if not ref_date in dateList:
            print 'Reference date - '+ref_date+' - is not included in date list to show.'
            sys.exit(1)
        else: print 'reference date: '+ref_date
    except:
        if zero_start == 'yes':
            ref_date = dateList[0];
            print 'set the 1st date as reference for displacement display.'
        else: pass

    ##############################################################
    ##### Plot Fig 1 - Velocity / last epoch of time series / DEM
    fig = plt.figure(1)
    ax=fig.add_subplot(111)

    ##### Check subset range
    width  = int(atr['WIDTH'])
    length = int(atr['FILE_LENGTH'])
    print 'file size: '+str(length)+', '+str(width)
    try: win_y = subset.coord_geo2radar(win_lat,atr,'latitude')
    except:
        try:    win_y
        except: win_y = [0,length]
    try: win_x = subset.coord_geo2radar(win_lon,atr,'longitude')
    except:
        try:    win_x
        except: win_x = [0,width]
    win_box = (win_x[0], win_y[0], win_x[1], win_y[1])
    win_box = subset.check_box_within_data_coverage(win_box, atr)

    try:
        velocityFile
        try:    vel, vel_atr = readfile.read(velocityFile)
        except: vel, vel_atr = readfile.read(timeSeriesFile,velocityFile)
        ax.set_title(velocityFile)
        print 'display: ' + velocityFile
    except:
        vel, vel_atr = readfile.read(timeSeriesFile,dateList1[-1])
        ax.set_title('epoch: '+dateList1[-1])
        print 'display last epoch'

    ##### show displacement instead of phase
    if vel_atr['FILE_TYPE'] in ['interferograms','.unw'] and dispDisplacement == 'yes':
        print 'show displacement'
        phase2range = -float(vel_atr['WAVELENGTH']) / (4*np.pi)
        vel *= phase2range
    else: dispDisplacement = 'no'

    ## Reference Point
    if showRef == 'yes':
        try: ax.plot(int(atr['ref_x']),int(atr['ref_y']),'ks',ms=6)
        except: pass

    if dispOpposite == 'yes':
        print 'show opposite value in figure/map 1'
        vel *= -1

    ## Flip
    try:        flip_lr
    except:
        try:    flip_ud
        except: flip_lr, flip_ud = view.auto_flip_direction(atr)

    ## Status bar
    ## Geo coordinate
    try:
        ullon    = float(atr['X_FIRST'])
        ullat    = float(atr['Y_FIRST'])
        lon_step = float(atr['X_STEP'])
        lat_step = float(atr['Y_STEP'])
        lon_unit = atr['Y_UNIT']
        lat_unit = atr['X_UNIT']
        geocoord='yes'
        print 'Input file is Geocoded'
    except:  geocoord='no'


    def format_coord(x,y):
        col = int(x+0.5)
        row = int(y+0.5)
        if col>=0 and col<=width and row>=0 and row<=length:
            z = vel[row,col]
            try:
                lon = ullon + x*lon_step
                lat = ullat + y*lat_step
                return 'x=%.1f, y=%.1f, value=%.4f, lon=%.4f, lat=%.4f'%(x,y,z,lon,lat)
            except:
                return 'x=%.1f, y=%.1f, value=%.4f'%(x,y,z)
    ax.format_coord = format_coord

    ## DEM 
    try:
        demFile
        dem,demRsc = readfile.read(demFile)
        ax = view.plot_dem_yx(ax,dem,demShade,demContour,contour_step,contour_sigma)
        vel_alpha = 0.8
    except: print 'No DEM file'

    try:     img=ax.imshow(vel,vmin=vmin,vmax=vmax, alpha=vel_alpha)
    except:  img=ax.imshow(vel,alpha=vel_alpha)
    plt.colorbar(img)

    ## Zoom In (subset)
    if flip_lr == 'yes':  ax.set_xlim(win_box[2], win_box[0])
    else:                 ax.set_xlim(win_box[0], win_box[2])
    if flip_ud == 'yes':  ax.set_ylim(win_box[1], win_box[3])
    else:                 ax.set_ylim(win_box[3], win_box[1])

    ## Flip
    #if flip_lr == 'yes':  fig.gca().invert_xaxis()
    #if flip_ud == 'yes':  fig.gca().invert_yaxis()

    ########################################## 
    ##### Plot Fig 2 - Time series plot
    #fig2 = plt.figure(num=2,figsize=(12,6))
    fig2 = plt.figure(2,figsize=(12,6))
    ax2  = fig2.add_subplot(111) 

    try:
        timeSeriesFile_2
        h5timeseries_2=h5py.File(timeSeriesFile_2)
        dateList_2 = sorted(h5timeseries_2['timeseries'].keys())
        dates_2,datevector_2 = ptime.date_list2vector(dateList_2)
        datevector_all += list(set(datevector_2) - set(datevector_all))
        datevector_all = sorted(datevector_all)
    except:  pass


    ################################  Plot Code Package <start> #################################
    def plot_ts(ax,ax2,fig2,xsub,ysub,h5timeseries):
        ax2.cla()
        print '\n-------------------------------------------------------------------------------'
        disp_min = 0
        disp_max = 0

        ############################# Plot Time Series ##############################
        global ref_xsub, ref_ysub
        ##### 1.1 Plot Reference time series
        try:
            ref_xsub
            ref_ysub
            ref_xsub,ref_ysub = check_yx(ref_xsub,ref_ysub,radius,ax,rectColor)
            print '----------------------------------------------------'
            print 'Reference Point:'
            print 'ref_x='+str(ref_xsub[0])+':'+str(ref_xsub[1])
            print 'ref_y='+str(ref_ysub[0])+':'+str(ref_ysub[1])

            print '-----------------------------'
            print 'Time series with all dates:'
            dis1, dis1_mean, dis1_std, dis1_vel = read_dis_xy(ref_xsub,ref_ysub,dateList1,h5timeseries,unit)
            (_, caps, _)=ax2.errorbar(dates1,dis1_mean,yerr=dis1_std,fmt='-ks',\
                                      ms=markerSize2, lw=0, alpha=1,mfc=markerColor_ref,mew=edgeWidth,\
                                      elinewidth=edgeWidth,ecolor='black',capsize=markerSize*0.5)
            for cap in caps:  cap.set_markeredgewidth(edgeWidth)
            disp_min,disp_max = update_lim(disp_min,disp_max,dis1_mean,dis1_std)

            if not len(dateList) == len(dateList1):
                print '-----------------------------'
                print 'Time series with dates of interest:'
                dis12, dis12_mean, dis12_std, dis12_vel = read_dis_xy(ref_xsub,ref_ysub,dateList,h5timeseries,unit)
                (_, caps, _)=ax2.errorbar(dates,dis12_mean,yerr=dis12_std,fmt='-ks',\
                                          ms=markerSize2, lw=0, alpha=1,mfc=markerColor_ref2,mew=edgeWidth,\
                                          elinewidth=edgeWidth,ecolor='black',capsize=markerSize*0.5)
                for cap in caps:  cap.set_markeredgewidth(edgeWidth)
                disp_min,disp_max = update_lim(disp_min,disp_max,dis12_mean,dis12_std)
            
        except: pass

        ##### 1.2.0 Read y/x
        print '\n----------------------------------------------------'
        print 'Point of Interest:'
        xsub,ysub = check_yx(xsub,ysub,radius,ax,rectColor)
        print 'x='+str(xsub[0])+':'+str(xsub[1])
        print 'y='+str(ysub[0])+':'+str(ysub[1])

        ##### 1.2.1 Plot 2nd time series
        try:
            timeSeriesFile_2
            print '-----------------------------'
            print '2nd Time Series:'
            dis2, dis2_mean, dis2_std, dis2_vel = read_dis_xy(xsub,ysub,dateList_2,h5timeseries_2,unit)
            (_, caps, _)=ax2.errorbar(dates_2,dis2_mean,yerr=dis2_std,fmt='-ko',\
                                      ms=markerSize2, lw=0, alpha=1, mfc=markerColor2,\
                                      elinewidth=0,ecolor='black',capsize=0)
            for cap in caps:  cap.set_markeredgewidth(edgeWidth)
            disp_min,disp_max = update_lim(disp_min,disp_max,dis2_mean,dis2_std)
        except: pass

        ##### 1.2.2 Plot 1st time series
        print '-----------------------------'
        print 'Time Series:'
        dis, dis_mean, dis_std, dis_vel = read_dis_xy(xsub,ysub,dateList,h5timeseries,unit)
        (_, caps, _)=ax2.errorbar(dates,dis_mean,yerr=dis_std,fmt='-ko',\
                                  ms=markerSize, lw=lineWidth, alpha=1, mfc=markerColor,\
                                  elinewidth=edgeWidth,ecolor='black',capsize=markerSize*0.5)
        for cap in caps:  cap.set_markeredgewidth(edgeWidth)
        disp_min,disp_max = update_lim(disp_min,disp_max,dis_mean,dis_std)

        ####################### Figure Format #######################
        ## x axis format
        try:    ax2 = ptime.auto_adjust_xaxis_date(ax2,dateVecMinMax, fontSize)
        except: ax2 = ptime.auto_adjust_xaxis_date(ax2,datevector_all,fontSize)

        ## y axis format
        ax2.set_ylabel('Displacement ['+unit+']',fontsize=fontSize)
        try:
            lbound
            hbound
            ax2.set_ylim(lbound,hbound)
        except:
            disp_buf = 0.2*(disp_max - disp_min)
            ax2.set_ylim(disp_min-disp_buf,disp_max+disp_buf)
        for tick in ax2.yaxis.get_major_ticks():  tick.label.set_fontsize(fontSize)

        ## title
        figTitle = 'x='+str(xsub[0])+':'+str(xsub[1])+', y='+str(ysub[0])+':'+str(ysub[1])
        try:
            lonc = ullon + (xsub[0]+xsub[1])/2.0*lon_step
            latc = ullat + (ysub[0]+ysub[1])/2.0*lat_step
            figTitle += ', lalo='+'%.4f,%.4f'%(latc,lonc)
        except: pass
        ax2.set_title(figTitle)

        ################## Save and Output #####################
        if saveFig == 'yes':
            print '-----------------------------'
            Delay={}
            Delay['displacement'] = dis
            Delay['unit']         = unit
            Delay['time']         = datevector
            Delay['velocity']     = dis_vel[0]
            Delay['velocity_unit']= unit+'/yr'
            Delay['velocity_std'] = dis_vel[4]
            figBase = 'x'+str(xsub[0])+'_'+str(xsub[1]-1)+'y'+str(ysub[0])+'_'+str(ysub[1]-1)
            sio.savemat( figBase+'_ts.mat', {'displacement': Delay});
            print 'saved '+figBase+'_ts.mat'
            fig2.savefig(figBase+'_ts.pdf',bbox_inches='tight',transparent=True,dpi=fig_dpi);
            print 'saved '+figBase+'_ts.pdf'
            if dispFig == 'no':
                fig.savefig(figBase+'_vel.png',bbox_inches='tight',transparent=True,dpi=fig_dpi);
                print 'saved '+figBase+'_vel.png'
    ################################  Plot Code Package <end> #################################


    ########### 1. Plot Time Series with x/y ##########
    try:
        xsub
        ysub
        plot_ts(ax,ax2,fig2,xsub,ysub,h5timeseries)
    except:  print 'No x/y input' ; pass

    ########### 2. Plot Time Series with Click ##########
    ## similar to 1. Plot Time Series with x/y

    def onclick(event):
        ax2.cla()
        xsub = [int(event.xdata)]
        ysub = [int(event.ydata)]
        plot_ts(ax,ax2,fig2,xsub,ysub,h5timeseries)

        if dispFig == 'yes':  plt.show()

    try: cid = fig.canvas.mpl_connect('button_press_event', onclick)
    except: pass

    if dispFig == 'yes':  plt.show()


####################################################################################
if __name__ == '__main__':
    main(sys.argv[1:])





