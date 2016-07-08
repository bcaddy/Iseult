#! /usr/bin/env python

import re # regular expressions
import os, sys # Used to make the code portable
import h5py # Allows us the read the data files
import time,string
import matplotlib
matplotlib.use('TkAgg')
import new_cmaps
import numpy as np
from collections import deque
import matplotlib.colors as mcolors
import matplotlib.gridspec as gridspec
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2TkAgg
from matplotlib.figure import Figure
from phase_plots import PhasePanel
from fields_plots import FieldsPanel
from density_plots import DensPanel
from spectra import SpectralPanel
from mag_plots import BPanel
from energy_plots import EnergyPanel
from fft_plots import FFTPanel
#from ThreeD_mag_plots import ThreeDBPanel STILL TESTING
import multiprocessing

# I don't think that matplotlib allows multi-threading, in the interactive mode.
# This is a flag that i have so I can mess around trying to get it to work.
Use_MultiProcess = False # DO NOT SET TO TRUE!
import time
import Tkinter as Tk
import ttk as ttk
import tkFileDialog

matplotlib.rcParams['mathtext.fontset'] = 'stix'
matplotlib.rcParams['font.family'] = 'STIXGeneral'

def destroy(e):
    sys.exit()

class MyCustomToolbar(NavigationToolbar2TkAgg):
    def __init__(self, plotCanvas, parent):
        # create the default toolbar
        # plotCanvas is the tk Canvas we want to link to the toolbar,
        # parent is the iseult main app
        NavigationToolbar2TkAgg.__init__(self, plotCanvas, parent)


class Spinbox(ttk.Entry):
    def __init__(self, master=None, **kw):
        ttk.Entry.__init__(self, master, "ttk::spinbox", **kw)

    def current(self, newindex=None):
        return self.tk.call(self._w, 'current', index)

    def set(self, value):
        return self.tk.call(self._w, 'set', value)

class SubPlotWrapper:
    """A simple class that will eventually hold all of the information
    about each sub_plot in the Figure"""

    def __init__(self, parent, figure=None, pos = None, subplot_spec = None, ctype=None, graph = None):
        self.parent = parent
        self.chartType = 'PhasePlot'
        # A dictionary that contains all of the plot types.
        self.PlotTypeDict = {'PhasePlot': PhasePanel,
                             'EnergyPlot': EnergyPanel,
                             'FieldsPlot': FieldsPanel,
                             'DensityPlot': DensPanel,
                             'SpectraPlot': SpectralPanel,
                             'MagPlots': BPanel,
#                             '3dMagPlots': ThreeDBPanel,
                             'FFTPlots': FFTPanel
                             }
        # A dictionary that will store where everything is in Hdf5 Files
        self.GenParamDict()
        self.figure = figure
        self.subplot_spec = subplot_spec
        self.pos = pos
        self.graph = graph
        self.Changedto1D = False
        self.Changedto2D = False
        #
    def GetKeys(self):
        return self.graph.set_plot_keys()

    def LoadKey(self, h5key):
        return self.parent.DataDict[h5key]
    def LoadData(self):
        self.graph.LoadData()
    def ChangeGraph(self, str_arg):
        # Change the graph type
        self.chartType = str_arg
        # put a list of the previous chart types in iseult

        self.graph = self.PlotTypeDict[self.chartType](self.parent, self)
        self.parent.RenewCanvas(ForceRedraw = True)

    def GenParamDict(self):
        # Generate a dictionary that will store all of the params at dict['ctype']['param_name']
        self.PlotParamsDict = {plot_type: '' for plot_type in self.PlotTypeDict.keys()}
        for elm in self.PlotTypeDict.keys():
            self.PlotParamsDict[elm] = {key: self.PlotTypeDict[elm].plot_param_dict[key] for key in self.PlotTypeDict[elm].plot_param_dict.keys()}

    def RestoreDefaultPlotParams(self, ctype = None, RestoreAll = False):
        if ctype is None:
            ctype = self.chartType
        if RestoreAll:
            self.GenParamDict()
        else:
            self.PlotParamsDict[ctype] = {key: self.PlotTypeDict[ctype].plot_param_dict[key] for key in self.PlotTypeDict[ctype].plot_param_dict.keys()}

    def SetPlotParam(self, pname, val, ctype = None, update_plot = True, NeedsRedraw = False):
        if ctype is None:
            ctype = self.chartType
        # Check to see if a plot is changed from 1d to 2d
        if pname =='twoD':
            if self.PlotParamsDict[ctype][pname] == 1 and val == 0:
                self.Changedto1D = True
                NeedsRedraw = True
            if self.PlotParamsDict[ctype][pname] == 0 and val == 1:
                self.Changedto2D = True
                NeedsRedraw = True

        self.PlotParamsDict[ctype][pname] = val
        if update_plot or NeedsRedraw:
            self.parent.RenewCanvas(ForceRedraw = NeedsRedraw)


    def GetPlotParam(self, pname, ctype = None):
        if ctype is None:
            ctype = self.chartType
        return self.PlotParamsDict[ctype][pname]

    def SetGraph(self, ctype = None):
        if ctype:
            self.chartType = ctype
        self.graph = self.PlotTypeDict[self.chartType](self.parent, self)

    def DrawGraph(self):
        self.graph.draw()

    def RefreshGraph(self):
        self.graph.refresh()

    def OpenSubplotSettings(self):
        self.graph.OpenSettings()
class Knob:
    """
    Knob - simple class with a "setKnob" method.
    A Knob instance is attached to a Param instance, e.g., param.attach(knob)
    Base class is for documentation purposes.
    """
    def setKnob(self, value):
        pass

class Param:

    """
    The idea of the "Param" class is that some parameter in the GUI may have
    several knobs that both control it and reflect the parameter's state, e.g.
    a slider, text, and dragging can all change the value of the frequency in
    the waveform of this example.
    The class allows a cleaner way to update/"feedback" to the other knobs when
    one is being changed.  Also, this class handles min/max constraints for all
    the knobs.
    Idea - knob list - in "set" method, knob object is passed as well
      - the other knobs in the knob list have a "set" method which gets
        called for the others.
    """
    def __init__(self, initialValue=None, minimum=0., maximum=1.):
        self.minimum = minimum
        self.maximum = maximum
        if initialValue != self.constrain(initialValue):
            raise ValueError('illegal initial value')
        self.value = initialValue
        self.knobs = []

    def attach(self, knob):
        self.knobs += [knob]

    def set(self, value, knob=None):
        if self.value != self.constrain(value):
            self.value = self.constrain(value)
            for feedbackKnob in self.knobs:
                if feedbackKnob != knob:
                    feedbackKnob.setKnob(self.value)
        # Adding a new feature that allows one to loop backwards or forwards:
        elif self.maximum != self.minimum:
            if self.value == self.maximum:
                self.value = self.minimum
                for feedbackKnob in self.knobs:
                    if feedbackKnob != knob:
                        feedbackKnob.setKnob(self.value)
            elif self.value == self.minimum:
                self.value = self.maximum
                for feedbackKnob in self.knobs:
                    if feedbackKnob != knob:
                        feedbackKnob.setKnob(self.value)
        return self.value

    def setMax(self, max_arg, knob=None):
        self.maximum = max_arg
        self.value = self.constrain(self.value)
        for feedbackKnob in self.knobs:
            if feedbackKnob != knob:
                feedbackKnob.setKnob(self.value)
        return self.value
    def constrain(self, value):
        if value <= self.minimum:
            value = self.minimum
        if value >= self.maximum:
            value = self.maximum
        return value


class PlaybackBar(Tk.Frame):

    """A Class that will handle the time-stepping in Iseult, and has the
    following, a step left button, a play/pause button, a step right button, a
    playbar, and a settings button."""

    def __init__(self, parent, param, canvas = None):
        Tk.Frame.__init__(self)
        self.parent = parent

        self.skipSize = 5
        self.waitTime = .01
        self.playPressed = False

        # This param should be the time-step of the simulation
        self.param = param

        # make a button that skips left
        self.skipLB = ttk.Button(self, text = '<', command = self.SkipLeft)
        self.skipLB.pack(side=Tk.LEFT, fill=Tk.BOTH, expand=0)

        # make the play button
        self.playB = ttk.Button(self, text = 'Play', command = self.PlayHandler)
        self.playB.pack(side=Tk.LEFT, fill=Tk.BOTH, expand=0)

        # a button that skips right
        self.skipRB = ttk.Button(self, text = '>', command = self.SkipRight)
        self.skipRB.pack(side=Tk.LEFT, fill=Tk.BOTH, expand=0)

        # An entry box that will let us choose the time-step
        ttk.Label(self, text='n= ').pack(side=Tk.LEFT, fill=Tk.BOTH, expand=0)

        # A StringVar for a box to type in a frame num, linked to self.param
        self.tstep = Tk.StringVar()
        # set it to the param value
        self.tstep.set(str(self.param.value))

        # the entry box
        self.txtEnter = ttk.Entry(self, textvariable=self.tstep, width=6)
        self.txtEnter.pack(side=Tk.LEFT, fill = Tk.BOTH, expand = 0)

        # A slider that will show the progress in the simulation as well as
        # allow us to select a time. Now the slider just changes the tstep box
        self.slider = ttk.Scale(self, from_=self.param.minimum, to=self.param.maximum, command = self.ScaleHandler)
        self.slider.set(self.param.value)
        self.slider.pack(side=Tk.LEFT, fill=Tk.BOTH, expand=1)
        # bind releasing the moust button to updating the plots.
        self.slider.bind("<ButtonRelease-1>", self.UpdateValue)


        self.LoopVar = Tk.IntVar()
        self.LoopVar.set(self.parent.LoopPlayback)
        self.LoopVar.trace('w', self.LoopChanged)
        self.RecordFrames = ttk.Checkbutton(self, text = 'Loop',
                                            variable = self.LoopVar)
        self.RecordFrames.pack(side=Tk.LEFT, fill=Tk.BOTH, expand=0)


        self.RecVar = Tk.IntVar()
        self.RecVar.set(self.parent.recording)
        self.RecVar.trace('w', self.RecChanged)
        self.RecordFrames = ttk.Checkbutton(self, text = 'Record',
                                            variable = self.RecVar)
        self.RecordFrames.pack(side=Tk.LEFT, fill=Tk.BOTH, expand=0)


        # a measurement button that should lauch a window to take measurements.
        self.MeasuresB= ttk.Button(self, text='Measure', command=self.OpenMeasures)
        self.MeasuresB.pack(side=Tk.LEFT, fill=Tk.BOTH, expand=0)


        # a settings button that should lauch some global settings.
        self.SettingsB= ttk.Button(self, text='Settings', command=self.OpenSettings)
        self.SettingsB.pack(side=Tk.LEFT, fill=Tk.BOTH, expand=0)

        # a reload button that reloads the files and then refreshes the plot
        ttk.Button(self, text = 'Reload', command = self.OnReload).pack(side=Tk.LEFT, fill=Tk.BOTH, expand=0)
        #attach the parameter to the Playbackbar
        self.param.attach(self)

    def OnReload(self, *args):
        self.parent.findDir()
        self.parent.RenewCanvas()

    def RecChanged(self, *args):
        if self.RecVar.get() == self.parent.recording:
            pass
        else:
            self.parent.recording = self.RecVar.get()
            if self.parent.recording == 1:
                self.parent.PrintFig()
    def LoopChanged(self, *args):
        if self.LoopVar.get() == self.parent.LoopPlayback:
            pass
        else:
            self.parent.LoopPlayback = self.LoopVar.get()

    def SkipLeft(self, e = None):
        self.param.set(self.param.value - self.skipSize)

    def SkipRight(self, e = None):
        self.param.set(self.param.value + self.skipSize)

    def PlayHandler(self, e = None):
        if not self.playPressed:
            # Set the value of play pressed to true, change the button name to
            # pause, turn off clear_fig, and start the play loop.
            self.playPressed = True
            self.parent.clear_fig = False
            self.playB.config(text='Pause')
            self.after(int(self.waitTime*1E3), self.blink)
        else:
            # pause the play loop, turn clear fig back on, and set the button name back to play
            self.playPressed = False
            self.parent.clear_fig = True
            self.playB.config(text='Play')

    def OpenSettings(self):
        if self.parent.settings_window is None:
            self.parent.settings_window = SettingsFrame(self.parent)
        else:
            self.parent.settings_window.destroy()
            self.parent.settings_window = SettingsFrame(self.parent)

    def OpenMeasures(self):
        if self.parent.measure_window is None:
            self.parent.measure_window = MeasureFrame(self.parent)
        else:
            self.parent.measure_window.destroy()
            self.parent.measure_window = MeasureFrame(self.parent)


    def blink(self):
        if self.playPressed:
            # First check to see if the timestep can get larger
            if self.param.value == self.param.maximum and not self.parent.LoopPlayback:
                # push pause button
                self.PlayHandler()

            # otherwise skip right by size skip size
            else:
                self.param.set(self.param.value + self.skipSize)

            # start loopin'
            self.after(int(self.waitTime*1E3), self.blink)


    def TextCallback(self):
        try:
            #make sure the user types in a int
            if int(self.tstep.get()) != self.param.value:
                self.param.set(int(self.tstep.get()))
        except ValueError:
            #if they type in random stuff, just set it ot the param value
            self.tstep.set(str(self.param.value))

    def ScaleHandler(self, e):
        # if changing the scale will change the value of the parameter, do so
        if self.tstep.get() != int(self.slider.get()):
            self.tstep.set(int(self.slider.get()))
    def UpdateValue(self, *args):
        if int(self.slider.get()) != self.param.value:
            self.param.set(int(self.slider.get()))
    def setKnob(self, value):
        #set the text entry value
        self.tstep.set(str(value))
        #set the slider
        self.slider.set(value)

class SettingsFrame(Tk.Toplevel):
    def __init__(self, parent):

        Tk.Toplevel.__init__(self)
        self.wm_title('General Settings')
        self.protocol('WM_DELETE_WINDOW', self.OnClosing)

        self.bind('<Return>', self.SettingsCallback)

        self.parent = parent
        frm = ttk.Frame(self)
        frm.pack(fill=Tk.BOTH, expand=True)

        # Make an entry to change the skip size
        self.skipSize = Tk.StringVar(self)
        self.skipSize.set(self.parent.playbackbar.skipSize) # default value
        self.skipSize.trace('w', self.SkipSizeChanged)
        ttk.Label(frm, text="Skip Size:").grid(row=0)
        self.skipEnter = ttk.Entry(frm, textvariable=self.skipSize, width = 6)
        self.skipEnter.grid(row =0, column = 1, sticky = Tk.W + Tk.E)

        # Make an button to change the wait time
        self.waitTime = Tk.StringVar(self)
        self.waitTime.set(self.parent.playbackbar.waitTime) # default value
        self.waitTime.trace('w', self.WaitTimeChanged)
        ttk.Label(frm, text="Playback Wait Time:").grid(row=1)
        self.waitEnter = ttk.Entry(frm, textvariable=self.waitTime, width = 6)
        self.waitEnter.grid(row =1, column = 1, sticky = Tk.W + Tk.E)

        # Have a list of the color maps
        self.cmapvar = Tk.StringVar(self)
        self.cmapvar.set(self.parent.cmap) # default value
        self.cmapvar.trace('w', self.CmapChanged)

        ttk.Label(frm, text="Color map:").grid(row=2)
        cmapChooser = apply(ttk.OptionMenu, (frm, self.cmapvar, self.parent.cmap) + tuple(new_cmaps.sequential))
        cmapChooser.grid(row =2, column = 1, sticky = Tk.W + Tk.E)

        # Have a list of the color maps
        self.divcmapList = new_cmaps.cmaps.keys()
        self.div_cmapvar = Tk.StringVar(self)
        self.div_cmapvar.set(self.parent.div_cmap) # default value
        self.div_cmapvar.trace('w', self.DivCmapChanged)

        ttk.Label(frm, text="Diverging Cmap:").grid(row=3)
        cmapChooser = apply(ttk.OptionMenu, (frm, self.div_cmapvar, self.parent.div_cmap) + tuple(new_cmaps.diverging))
        cmapChooser.grid(row =3, column = 1, sticky = Tk.W + Tk.E)


        # Make an entry to change the number of columns
        self.columnNum = Tk.StringVar(self)
        self.columnNum.set(self.parent.numOfColumns.get()) # default value
        self.columnNum.trace('w', self.ColumnNumChanged)
        ttk.Label(frm, text="# of columns:").grid(row=4)
        self.ColumnSpin = Spinbox(frm,  from_=1, to=self.parent.maxCols, textvariable=self.columnNum, width = 6)
        self.ColumnSpin.grid(row =4, column = 1, sticky = Tk.W + Tk.E)

        # Make an entry to change the number of columns
        self.rowNum = Tk.StringVar(self)
        self.rowNum.set(self.parent.numOfRows.get()) # default value
        self.rowNum.trace('w', self.RowNumChanged)
        ttk.Label(frm, text="# of rows:").grid(row=5)
        self.RowSpin = Spinbox(frm, from_=1, to=self.parent.maxRows, textvariable=self.rowNum, width = 6)
        self.RowSpin.grid(row =5, column = 1, sticky = Tk.W + Tk.E)

        # Control whether or not Title is shown
        self.TitleVar = Tk.IntVar()
        self.TitleVar.set(self.parent.show_title)
        self.TitleVar.trace('w', self.TitleChanged)

        self.LimVar = Tk.IntVar()
        self.LimVar.set(self.parent.xlim[0])
        self.LimVar.trace('w', self.LimChanged)



        self.xleft = Tk.StringVar()
        self.xleft.set(str(self.parent.xlim[1]))
        self.xright = Tk.StringVar()
        self.xright.set(str(self.parent.xlim[2]))


        ttk.Label(frm, text = 'min').grid(row= 6, column = 1, sticky = Tk.N)
        ttk.Label(frm, text = 'max').grid(row= 6, column = 2, sticky = Tk.N)
        cb = ttk.Checkbutton(frm, text ='Set xlim',
                        variable = self.LimVar)
        cb.grid(row = 7, sticky = Tk.N)
        ttk.Entry(frm, textvariable=self.xleft, width = 8).grid(row = 7, column =1, sticky = Tk.N)
        ttk.Entry(frm, textvariable=self.xright, width = 8).grid(row = 7, column =2, sticky = Tk.N)



        self.yLimVar = Tk.IntVar()
        self.yLimVar.set(self.parent.ylim[0])
        self.yLimVar.trace('w', self.yLimChanged)



        self.yleft = Tk.StringVar()
        self.yleft.set(str(self.parent.ylim[1]))
        self.yright = Tk.StringVar()
        self.yright.set(str(self.parent.ylim[2]))


        ttk.Checkbutton(frm, text ='Set ylim',
                        variable = self.yLimVar).grid(row = 8, sticky = Tk.N)
        ttk.Entry(frm, textvariable=self.yleft, width = 8 ).grid(row = 8, column =1, sticky = Tk.N)
        ttk.Entry(frm, textvariable=self.yright, width =8 ).grid(row = 8, column =2, sticky = Tk.N)

        self.kLimVar = Tk.IntVar()
        self.kLimVar.set(self.parent.klim[0])
        self.kLimVar.trace('w', self.kLimChanged)



        self.kleft = Tk.StringVar()
        self.kleft.set(str(self.parent.klim[1]))
        self.kright = Tk.StringVar()
        self.kright.set(str(self.parent.klim[2]))


        ttk.Checkbutton(frm, text ='Set klim', variable = self.kLimVar).grid(row = 9, sticky = Tk.N)
        ttk.Entry(frm, textvariable=self.kleft, width = 8 ).grid(row = 9, column =1, sticky = Tk.N)
        ttk.Entry(frm, textvariable=self.kright, width =8 ).grid(row = 9, column =2, sticky = Tk.N)

        self.xRelVar = Tk.IntVar()
        self.xRelVar.set(self.parent.xLimsRelative)
        self.xRelVar.trace('w', self.xRelChanged)
        ttk.Checkbutton(frm, text = "x limits & zooms relative to shock",
                        variable = self.xRelVar).grid(row = 10, columnspan = 3, sticky = Tk.W)

        cb = ttk.Checkbutton(frm, text = "Show Title",
                        variable = self.TitleVar)
        cb.grid(row = 11, sticky = Tk.W)
        # Control whether or not axes are shared with a radio box:
        self.toLinkList = ['None', 'All spatial', 'All non p-x', 'All 2-D spatial']
        self.LinkedVar = Tk.IntVar()
        self.LinkedVar.set(self.parent.LinkSpatial)

        ttk.Label(frm, text='Share spatial axes:').grid(row = 0, column = 2, sticky = Tk.W)

        for i in range(len(self.toLinkList)):
            ttk.Radiobutton(frm,
                    text=self.toLinkList[i],
                    variable=self.LinkedVar,
                    command = self.RadioLinked,
                    value=i).grid(row = 1+i, column = 2, sticky =Tk.N)

        self.AspectVar = Tk.IntVar()
        self.AspectVar.set(self.parent.plot_aspect)
        self.AspectVar.trace('w', self.AspectVarChanged)

        cb = ttk.Checkbutton(frm, text = "Aspect = 1",
                                variable = self.AspectVar)
        cb.grid(row = 11, column = 1, sticky = Tk.W)

        self.CbarOrientation = Tk.IntVar()
        self.CbarOrientation.set(self.parent.HorizontalCbars)
        self.CbarOrientation.trace('w', self.OrientationChanged)

        cb = ttk.Checkbutton(frm, text = "Horizontal Cbars",
                                variable = self.CbarOrientation)
        cb.grid(row = 12, sticky = Tk.W)


        self.LinkKVar = Tk.IntVar()
        self.LinkKVar.set(self.parent.Linkk)
        self.CbarOrientation.trace('w', self.LinkKChanged)

        cb = ttk.Checkbutton(frm, text = "Share k-axes",
                                variable = self.LinkKVar)
        cb.grid(row = 12, column =1, sticky = Tk.W)


        self.LorentzBoostVar = Tk.IntVar()
        self.LorentzBoostVar.set(self.parent.DoLorentzBoost)
        self.LorentzBoostVar.trace('w', self.LorentzBoostChanged)
        cb = ttk.Checkbutton(frm, text='Boost PhasePlots', variable =  self.LorentzBoostVar).grid(row = 13, sticky = Tk.W)
        ttk.Label(frm, text='Gamma/Beta = \r (- for left boost)').grid(row= 13, rowspan = 2,column =1, sticky = Tk.E)
        self.GammaVar = Tk.StringVar()
        self.GammaVar.set(str(self.parent.GammaBoost))
        ttk.Entry(frm, textvariable=self.GammaVar, width = 7).grid(row = 13, column = 2, sticky = Tk.N)

    def AspectVarChanged(self, *args):
        if self.AspectVar.get() == self.parent.plot_aspect:
            pass

        else:
            self.parent.plot_aspect = self.AspectVar.get()
            self.parent.RenewCanvas(ForceRedraw = True)

    def OrientationChanged(self, *args):
        if self.CbarOrientation.get() == self.parent.HorizontalCbars:
            pass

        else:
            if self.CbarOrientation.get():
                self.parent.axes_extent = [18,92,0,-1]
                self.parent.cbar_extent = [0,4,0,-1]
                self.parent.SubPlotParams = {'left':0.06, 'right':0.92, 'top':.91, 'bottom':0.06, 'wspace':0.15, 'hspace':0.3}

            else:
                self.parent.axes_extent = [4,90,0,92]
                self.parent.cbar_extent = [4,90,95,98]
                self.parent.SubPlotParams = {'left':0.06, 'right':0.95, 'top':.93, 'bottom':0.06, 'wspace':0.23, 'hspace':0.15}
            self.parent.HorizontalCbars = self.CbarOrientation.get()
            self.parent.f.subplots_adjust( **self.parent.SubPlotParams)
            self.parent.RenewCanvas(ForceRedraw=True)

    def LorentzBoostChanged(self, *args):
        if self.LorentzBoostVar.get() == self.parent.DoLorentzBoost:
            pass

        else:
            self.parent.DoLorentzBoost = self.LorentzBoostVar.get()
            self.parent.RenewCanvas()

    def TitleChanged(self, *args):
        if self.TitleVar.get()==self.parent.show_title:
            pass
        else:
            self.parent.show_title = self.TitleVar.get()
            if self.TitleVar.get() == False:
                self.parent.f.suptitle('')

            self.parent.RenewCanvas()

    def RadioLinked(self, *args):
        # If the shared axes are changed, the whole plot must be redrawn
        if self.LinkedVar.get() == self.parent.LinkSpatial:
            pass
        else:
            self.parent.LinkSpatial = self.LinkedVar.get()
            self.parent.RenewCanvas(ForceRedraw = True)


    def LinkKChanged(self, *args):
        # If the shared axes are changed, the whole plot must be redrawn
        if self.LinkKVar.get() == self.parent.Linkk:
            pass
        else:
            self.parent.Linkk = self.LinkKVar.get()
            self.parent.RenewCanvas(ForceRedraw = True)

    def xRelChanged(self, *args):
        # If the shared axes are changed, the whole plot must be redrawn
        if self.xRelVar.get() == self.parent.xLimsRelative:
            pass
        else:
            self.parent.xLimsRelative = self.xRelVar.get()
            self.parent.RenewCanvas()


    def CmapChanged(self, *args):
    # Note here that Tkinter passes an event object to onselect()
        if self.cmapvar.get() == self.parent.cmap:
            pass
        else:
            self.parent.cmap = self.cmapvar.get()
            if self.parent.cmap in self.parent.cmaps_with_green:
                self.parent.ion_color =  new_cmaps.cmaps['plasma'](0.55)
                self.parent.electron_color = new_cmaps.cmaps['plasma'](0.8)
                self.parent.ion_fit_color = 'r'
                self.parent.electron_fit_color = 'yellow'

            else:
                self.parent.ion_color = new_cmaps.cmaps['viridis'](0.45)
                self.parent.electron_color = new_cmaps.cmaps['viridis'](0.75)
                self.parent.ion_fit_color = 'mediumturquoise'
                self.parent.electron_fit_color = 'lime'


            self.parent.RenewCanvas(ForceRedraw = True)

    def DivCmapChanged(self, *args):
    # Note here that Tkinter passes an event object to onselect()
        if self.div_cmapvar.get() == self.parent.div_cmap:
            pass
        else:
            self.parent.div_cmap = self.div_cmapvar.get()
            self.parent.RenewCanvas(ForceRedraw = True)


    def SkipSizeChanged(self, *args):
    # Note here that Tkinter passes an event object to SkipSizeChange()
        try:
            if self.skipSize.get() == '':
                pass
            else:
                self.parent.playbackbar.skipSize = int(self.skipSize.get())
        except ValueError:
            self.skipSize.set(self.parent.playbackbar.skipSize)

    def RowNumChanged(self, *args):
        try:
            if self.rowNum.get() == '':
                pass
            if int(self.rowNum.get())<1:
                self.rowNum.set(1)
            if int(self.rowNum.get())>self.parent.maxRows:
                self.rowNum.set(self.parent.maxRows)
            if int(self.rowNum.get()) != self.parent.numOfRows:
                self.parent.numOfRows.set(int(self.rowNum.get()))

        except ValueError:
            self.rowNum.set(self.parent.numOfRows.get())

    def ColumnNumChanged(self, *args):
        try:
            if self.columnNum.get() == '':
                pass
            if int(self.columnNum.get())<1:
                self.columnNum.set(1)
            if int(self.columnNum.get())>self.parent.maxCols:
                self.columnNum.set(self.parent.maxCols)
            if int(self.columnNum.get()) != self.parent.numOfColumns.get():
                self.parent.numOfColumns.set(int(self.columnNum.get()))

        except ValueError:
            self.columnNum.set(self.parent.numOfColumns.get())

    def WaitTimeChanged(self, *args):
    # Note here that Tkinter passes an event object to onselect()
        try:
            if self.waitTime.get() == '':
                pass
            else:
                self.parent.playbackbar.waitTime = float(self.waitTime.get())
        except ValueError:
            self.waitTime.set(self.parent.playbackbar.waitTime)

    def CheckIfXLimChanged(self):
        to_reload = False
        tmplist = [self.xleft, self.xright]
        for j in range(2):

            try:
            #make sure the user types in a a number and that it has changed.
                if np.abs(float(tmplist[j].get()) - self.parent.xlim[j+1]) > 1E-4:
                    self.parent.xlim[j+1] = float(tmplist[j].get())
                    to_reload += True

            except ValueError:
                #if they type in random stuff, just set it ot the param value
                tmplist[j].set(str(self.parent.xlim[j+1]))
        return to_reload*self.parent.xlim[0]

    def CheckIfYLimChanged(self):
        to_reload = False
        tmplist = [self.yleft, self.yright]
        for j in range(2):

            try:
            #make sure the user types in a int
                if np.abs(float(tmplist[j].get()) - self.parent.ylim[j+1]) > 1E-4:
                    self.parent.ylim[j+1] = float(tmplist[j].get())
                    to_reload += True

            except ValueError:
                #if they type in random stuff, just set it ot the param value
                tmplist[j].set(str(self.parent.ylim[j+1]))
        return to_reload*self.parent.ylim[0]

    def CheckIfkLimChanged(self):
        to_reload = False
        tmplist = [self.kleft, self.kright]
        for j in range(2):

            try:
            #make sure the user types in a int
                if np.abs(float(tmplist[j].get()) - self.parent.klim[j+1]) > 1E-4:
                    self.parent.klim[j+1] = float(tmplist[j].get())
                    to_reload += True

            except ValueError:
                #if they type in random stuff, just set it ot the param value
                tmplist[j].set(str(self.parent.klim[j+1]))
        return to_reload*self.parent.klim[0]


    def CheckIfGammaChanged(self):
        to_reload = False
        try:
        #make sure the user types in a float
            if np.abs(float(self.GammaVar.get()) - self.parent.GammaBoost) > 1E-8:
                self.parent.GammaBoost = float(self.GammaVar.get())
                to_reload += True

        except ValueError:
            #if they type in random stuff, just set it to the param value
            self.GammaVar.set(str(self.parent.GammaBoost))
        return to_reload*self.parent.DoLorentzBoost


    def LimChanged(self, *args):
        if self.LimVar.get()==self.parent.xlim[0]:
            pass
        else:
            self.parent.xlim[0] = self.LimVar.get()
            self.parent.RenewCanvas()

    def yLimChanged(self, *args):
        if self.yLimVar.get()==self.parent.ylim[0]:
            pass
        else:
            self.parent.ylim[0] = self.yLimVar.get()
            self.parent.RenewCanvas()

    def kLimChanged(self, *args):
        if self.kLimVar.get()==self.parent.klim[0]:
            pass
        else:
            self.parent.klim[0] = self.kLimVar.get()
            self.parent.RenewCanvas()


    def SettingsCallback(self, e):
        to_reload = self.CheckIfXLimChanged()
        to_reload += self.CheckIfYLimChanged()
        to_reload += self.CheckIfkLimChanged()

        to_reload += self.CheckIfGammaChanged()
        if to_reload:
            self.parent.RenewCanvas()



    def OnClosing(self):
        self.parent.settings_window = None
        self.destroy()

class MeasureFrame(Tk.Toplevel):
    def __init__(self, parent):

        Tk.Toplevel.__init__(self)
        self.wm_title('Take Measurements')
        self.protocol('WM_DELETE_WINDOW', self.OnClosing)


        self.parent = parent

        self.bind('<Return>', self.TxtEnter)
        frm = ttk.Frame(self)
        frm.pack(fill=Tk.BOTH, expand=True)

        # Make an entry to change the integration region
        # A StringVar for a box to type in a value for the left ion region
        self.ileft = Tk.StringVar()
        # set it to the left value
        self.ileft.set(str(self.parent.i_L.get()))

        # A StringVar for a box to type in a value for the right ion region
        self.iright = Tk.StringVar()
        # set it to the right value
        self.iright.set(str(self.parent.i_R.get()))

        # Now the electrons
        self.eleft = Tk.StringVar()
        self.eleft.set(str(self.parent.e_L.get()))
        self.eright = Tk.StringVar()
        self.eright.set(str(self.parent.e_R.get()))

        ttk.Label(frm, text='Energy Int region:').grid(row = 0, sticky = Tk.W)
        ttk.Label(frm, text='left').grid(row = 0, column = 1, sticky = Tk.N)
        ttk.Label(frm, text='right').grid(row = 0, column = 2, sticky = Tk.N)

        # the ion row
        ttk.Label(frm, text='ions').grid(row= 1, sticky = Tk.N)
        # Make an button to change the wait time

        self.iLEnter = ttk.Entry(frm, textvariable=self.ileft, width=7)
        self.iLEnter.grid(row =1, column = 1, sticky = Tk.W + Tk.E)

        self.iREnter = ttk.Entry(frm, textvariable=self.iright, width=7)
        self.iREnter.grid(row = 1, column =2, sticky = Tk.W + Tk.E)

        ttk.Label(frm, text='electrons').grid(row= 2, sticky = Tk.N)
        self.eLEnter = ttk.Entry(frm, textvariable=self.eleft, width=7)
        self.eLEnter.grid(row = 2, column =1, sticky = Tk.W + Tk.E)
        self.eREnter = ttk.Entry(frm, textvariable=self.eright, width=7)
        self.eREnter.grid(row = 2, column =2, sticky = Tk.W + Tk.E)

        self.RelVar = Tk.IntVar()
        self.RelVar.set(self.parent.e_relative)
        self.RelVar.trace('w', self.RelChanged)
        cb = ttk.Checkbutton(frm, text = "Energy Region relative to shock?",
                        variable = self.RelVar)
        cb.grid(row = 3, columnspan = 3, sticky = Tk.W)

        self.SetTeVar = Tk.IntVar()
        self.SetTeVar.set(self.parent.set_Te)
        self.SetTeVar.trace('w', self.SetTeChanged)
        cb = ttk.Checkbutton(frm, text='Show T_e', variable =  self.SetTeVar)
        cb.grid(row = 5, sticky = Tk.W)

        ttk.Label(frm, text=u'\u0394'+u'\u0263' + ' =').grid(row= 5, column =1, sticky = Tk.N)

        self.SetTpVar = Tk.IntVar()
        self.SetTpVar.set(self.parent.set_Tp)
        self.SetTpVar.trace('w', self.SetTpChanged)

        cb = ttk.Checkbutton(frm, text='Show T_i', variable =  self.SetTpVar)
        cb.grid(row = 6, sticky = Tk.W)
        ttk.Label(frm, text=u'\u0394'+u'\u0263' + ' =').grid(row= 6, column =1, sticky = Tk.N)

        self.delgameVar = Tk.StringVar()
        self.delgameVar.set(str(self.parent.delgam_e))
        self.delgampVar = Tk.StringVar()
        self.delgampVar.set(str(self.parent.delgam_p))


        ttk.Entry(frm, textvariable=self.delgameVar, width = 7).grid(row = 5, column = 2, sticky = Tk.N)
        ttk.Entry(frm, textvariable=self.delgampVar, width = 7).grid(row = 6, column =2, sticky = Tk.N)

        ttk.Label(frm, text='Powerlaw fits:').grid(row = 8, sticky = Tk.W)
        ttk.Label(frm, text='E_min [mc^2]').grid(row = 8, column = 1, sticky = Tk.N)
        ttk.Label(frm, text='E_max [mc^2]').grid(row = 8, column = 2, sticky = Tk.N)

        self.PLFitEVar = Tk.IntVar()
        self.PLFitEVar.set(self.parent.PowerLawFitElectron[0])
        self.PLFitEVar.trace('w', self.PLFitEChanged)
        ttk.Checkbutton(frm, text='Electrons', variable =  self.PLFitEVar).grid(row = 9, sticky = Tk.W)

        self.E1Var = Tk.StringVar()
        self.E1Var.set(str(self.parent.PowerLawFitElectron[1]))
        self.E2Var = Tk.StringVar()
        self.E2Var.set(str(self.parent.PowerLawFitElectron[2]))


        ttk.Entry(frm, textvariable=self.E1Var, width = 7).grid(row = 9, column = 1, sticky = Tk.N)
        ttk.Entry(frm, textvariable=self.E2Var, width = 7).grid(row = 9, column =2, sticky = Tk.N)


        self.PLFitPVar = Tk.IntVar()
        self.PLFitPVar.set(self.parent.PowerLawFitIon[0])
        self.PLFitPVar.trace('w', self.PLFitPChanged)
        ttk.Checkbutton(frm, text='Ions', variable =  self.PLFitPVar).grid(row = 10, sticky = Tk.W)

        self.P1Var = Tk.StringVar()
        self.P1Var.set(str(self.parent.PowerLawFitIon[1]))
        self.P2Var = Tk.StringVar()
        self.P2Var.set(str(self.parent.PowerLawFitIon[2]))

        ttk.Entry(frm, textvariable=self.P1Var, width = 7).grid(row = 10, column = 1, sticky = Tk.N)
        ttk.Entry(frm, textvariable=self.P2Var, width = 7).grid(row = 10, column =2, sticky = Tk.N)


        ttk.Label(frm, text='Measure eps:').grid(row = 11, column = 0, sticky = Tk.W)
        ttk.Label(frm, text='E_inj [mc^2]').grid(row = 11, column = 1, sticky = Tk.N)
        ttk.Label(frm, text='eps').grid(row = 11, column = 2, sticky = Tk.N)

        self.eps_p_fitVar = Tk.IntVar()
        self.eps_p_fitVar.set(self.parent.measure_eps_p)
        self.eps_p_fitVar.trace('w', self.eps_pFitChanged)
        ttk.Checkbutton(frm, text='protons', variable =  self.eps_p_fitVar).grid(row = 12, sticky = Tk.W)

        self.EinjPVar = Tk.StringVar()
        self.EinjPVar.set(str(self.parent.e_ion_injection))
        ttk.Entry(frm, textvariable=self.EinjPVar, width = 7).grid(row = 12, column = 1, sticky = Tk.N)
        ttk.Entry(frm, textvariable=self.parent.eps_pVar, width = 7, state = 'readonly').grid(row = 12, column =2, sticky = Tk.N)

        self.eps_e_fitVar = Tk.IntVar()
        self.eps_e_fitVar.set(self.parent.measure_eps_e)
        self.eps_e_fitVar.trace('w', self.eps_eFitChanged)
        ttk.Checkbutton(frm, text='electrons', variable =  self.eps_e_fitVar).grid(row = 13, sticky = Tk.W)

        self.EinjEVar = Tk.StringVar()
        self.EinjEVar.set(str(self.parent.e_electron_injection))
        ttk.Entry(frm, textvariable=self.EinjEVar, width = 7).grid(row = 13, column = 1, sticky = Tk.N)
        ttk.Entry(frm, textvariable=self.parent.eps_eVar, width = 7, state = 'readonly').grid(row = 13, column =2, sticky = Tk.N)


        ttk.Label(frm, text='NOTE: You must have one \'spectra\' plot' +'\r' + 'showing to measure eps_e or eps_p').grid(row = 14, rowspan = 2,columnspan = 3, sticky = Tk.W)



        # Make an entry to change the integration region
        # A StringVar for a box to type in a value for the left ion region
        self.FFTLVar = Tk.StringVar()
        # set it to the left value
        self.FFTLVar.set(str(self.parent.FFT_L.get()))

        # A StringVar for a box to type in a value for the right ion region
        self.FFTRVar = Tk.StringVar()
        # set it to the right value
        self.FFTRVar.set(str(self.parent.FFT_R.get()))

        ttk.Label(frm, text='left').grid(row = 16, column = 1, sticky = Tk.N)
        ttk.Label(frm, text='right').grid(row = 16, column = 2, sticky = Tk.N)

        ttk.Label(frm, text='FFT region:').grid(row = 17, sticky = Tk.W)
        ttk.Entry(frm, textvariable=self.FFTLVar, width=7).grid(row =17, column = 1, sticky = Tk.W + Tk.E)

        ttk.Entry(frm, textvariable=self.FFTRVar, width=7).grid(row = 17, column =2, sticky = Tk.W + Tk.E)

        self.FFTRelVar = Tk.IntVar()
        self.FFTRelVar.set(self.parent.FFT_relative)
        self.FFTRelVar.trace('w', self.FFTRelChanged)
        cb = ttk.Checkbutton(frm, text = "FFT Region relative to shock?",
                        variable = self.FFTRelVar)
        cb.grid(row = 18, columnspan = 3, sticky = Tk.W)




    def eps_pFitChanged(self, *args):
        if self.eps_p_fitVar.get() == self.parent.measure_eps_p:
            pass
        else:
            self.parent.measure_eps_p = self.eps_p_fitVar.get()
            self.parent.RenewCanvas()

    def eps_eFitChanged(self, *args):
        if self.eps_e_fitVar.get() == self.parent.measure_eps_e:
            pass
        else:
            self.parent.measure_eps_e = self.eps_e_fitVar.get()
            self.parent.RenewCanvas()


    def PLFitEChanged(self, *args):
        if self.PLFitEVar.get() == self.parent.PowerLawFitElectron[0]:
            pass
        else:
            self.parent.PowerLawFitElectron[0] = self.PLFitEVar.get()
            self.parent.RenewCanvas()

    def PLFitPChanged(self, *args):
        if self.PLFitPVar.get() == self.parent.PowerLawFitIon[0]:
            pass
        else:
            self.parent.PowerLawFitIon[0] = self.PLFitPVar.get()
            self.parent.RenewCanvas()

    def CheckIfTeChanged(self):
        to_reload = False
        try:
        #make sure the user types in a int
            if np.abs(float(self.delgameVar.get()) - self.parent.delgam_e) > 1E-4:
                self.parent.delgam_e = float(self.delgameVar.get())
                to_reload += True*self.parent.set_Te

        except ValueError:
            #if they type in random stuff, just set it ot the param value
            self.delgameVar.set(str(self.parent.delgam_e))
        return to_reload

    def CheckIfTpChanged(self):
        to_reload = False
        try:
        #make sure the user types in a flof
            if np.abs(float(self.delgampVar.get()) - self.parent.delgam_p) > 1E-4:
                    self.parent.delgam_p = float(self.delgampVar.get())
                    to_reload += True*self.parent.set_Tp

        except ValueError:
            #if they type in random stuff, just set it ot the param value
            self.delgampVar.set(str(self.parent.delgam_p))
        return to_reload

    def CheckIfEpsChanged(self):
        to_reload = False

        # The protons first
        try:
            # First check if the injection energy changed
            if np.abs(float(self.EinjPVar.get()) -self.parent.e_ion_injection)>1E-6:
                # Set the parent value to the var value
                self.parent.e_ion_injection = float(self.EinjPVar.get())
                to_reload += self.parent.measure_eps_p
        except ValueError:
            #if they type in random stuff, just set it to the value
            self.EinjPVar.set(str(self.parent.e_ion_injection))

        # Now the electrons
        try:
            # First check if the injection energy changed
            if np.abs(float(self.EinjEVar.get()) -self.parent.e_electron_injection)>1E-6:
                # Set the parent value to the var value
                self.parent.e_electron_injection = float(self.EinjEVar.get())
                to_reload += self.parent.measure_eps_e
        except ValueError:
            #if they type in random stuff, just set it to the value
            self.EinjEVar.set(str(self.parent.e_electron_injection))


        return to_reload

    def CheckIfPLChanged(self):
        to_reload = False

        PLList = [self.parent.PowerLawFitElectron, self.parent.PowerLawFitIon]
        VarList = [[self.E1Var, self.E2Var], [self.P1Var, self.P2Var]]

        for j in range(2):
            try:
                # First check if the left index changed
                if np.abs(float(VarList[j][0].get())- PLList[j][1])>1E-6:
                    # See if the left index is larger than the right index
                    if float(VarList[j][0].get()) > float(VarList[j][1].get()):
                        # it is, so make it larger:
                        VarList[j][1].set(str(float(VarList[j][0].get())*2))
                        #set the parent value to the right var value
                        PLList[j][2] = float(VarList[j][1].get())

                    # Set the parent value to the left var value
                    PLList[j][1] = float(VarList[j][0].get())
                    to_reload += True
            except ValueError:
                #if they type in random stuff, just set it to the value
                VarList[j][k].set(str(PLList[j][k+1]))

            try:
                # First check if the left index changed
                if np.abs(float(VarList[j][1].get())- PLList[j][2])>1E-6:
                    # See if the left index is larger than the right index
                    if float(VarList[j][1].get()) < float(VarList[j][0].get()):
                        # it is, so make it smaller:
                        VarList[j][0].set(str(float(VarList[j][1].get())*.5))
                        #set the parent value to the left var value
                        PLList[j][1] = float(VarList[j][0].get())

                    # Set the parent value to the right var value
                    PLList[j][2] = float(VarList[j][1].get())
                    to_reload += True

            except ValueError:
                #if they type in random stuff, just set it to the value
                VarList[j][k].set(str(PLList[j][k+1]))
        return to_reload

    def CheckIfIntChanged(self, tkVar, valVar):
        to_reload = False
        try:
            #make sure the user types in a int
            if int(tkVar.get()) != valVar.get():
                valVar.set(int(tkVar.get()))
                to_reload = True
            return to_reload
        except ValueError:
            #if they type in random stuff, just set it ot the param value
            tkVar.set(str(valVar.get()))
            return to_reload

    def SetTeChanged(self, *args):
        if self.SetTeVar.get()==self.parent.set_Te:
            pass
        else:
            self.parent.set_Te = self.SetTeVar.get()
            self.parent.RenewCanvas()

    def SetTpChanged(self, *args):
        if self.SetTpVar.get()==self.parent.set_Tp:
            pass
        else:
            self.parent.set_Tp = self.SetTpVar.get()
            self.parent.RenewCanvas()

    def TxtEnter(self, e):
        self.MeasuresCallback()

    def RelChanged(self, *args):
        if self.RelVar.get()==self.parent.e_relative:
            pass
        else:
            self.parent.e_relative = self.RelVar.get()
            self.parent.RenewCanvas()

    def FFTRelChanged(self, *args):
        if self.FFTRelVar.get()==self.parent.FFT_relative:
            pass
        else:
            self.parent.FFT_relative = self.FFTRelVar.get()
            self.parent.RenewCanvas()



    def MeasuresCallback(self):
        tkvarIntList = [self.ileft, self.iright, self.eleft, self.eright, self.FFTLVar, self.FFTRVar]
        IntValList = [self.parent.i_L, self.parent.i_R, self.parent.e_L, self.parent.e_R, self.parent.FFT_L, self.parent.FFT_R]

        to_reload = False



        for j in range(len(tkvarIntList)):
            to_reload += self.CheckIfIntChanged(tkvarIntList[j], IntValList[j])

        to_reload += self.CheckIfTeChanged()
        to_reload += self.CheckIfTpChanged()
        to_reload += self.CheckIfPLChanged()
        to_reload += self.CheckIfEpsChanged()
        if to_reload:
            self.parent.RenewCanvas()

    def OnClosing(self):
        self.parent.settings_window = None
        self.destroy()


class MainApp(Tk.Tk):
    """ We simply derive a new class of Frame as the man frame of our app"""
    def __init__(self, name):

        Tk.Tk.__init__(self)
        self.update_idletasks()
        menubar = Tk.Menu(self)
        self.wm_title(name)
        self.settings_window = None
        self.measure_window = None

        # A parameter that pushes the timestep to the last value if reload is pressed.
        self.Reload2End = True

        # A paramter that causes the play button to go to back to the beginning
        # after reaching the end
        self.LoopPlayback = True

        # A parameter that causes the graph to when it is redrawn
        self.clear_fig = True

        self.num_of_graphs_refreshed = 0
        self.first_x = None
        self.first_y = None

        self.num_font_size = 11
        self.recording = False
        #
        # Set the number of rows and columns in the figure
        # (As well as the max rows)
        self.maxRows = 5
        self.maxCols = 3

        # a list of cmaps with orange prtl colors
        self.cmaps_with_green = ['viridis', 'Rainbow + White', 'Blue/Green/Red/Yellow', 'Cube YF', 'Linear_L']

        # A param to define whether to share axes
        # 0 : No axes are shared
        # 1 : All axes are shared
        # 2 : All non p-x plots are shared
        # 3 : All 2-D, non p-x plots are shared
        self.LinkSpatial = 2

        # A param to decide whether to link k_axis
        self.Linkk = True
        # Should cbars be horizontal?
        self.HorizontalCbars = False
        # A param that will hold the the main axes extent
        if self.HorizontalCbars:
            self.axes_extent = [18,92,0,-1]
            self.cbar_extent = [0,4,0,-1]
            self.SubPlotParams = {'left':0.06, 'right':0.95, 'top':.91, 'bottom':0.06, 'wspace':0.15, 'hspace':0.3}

        else:
            self.axes_extent = [4,90,0,92]
            self.cbar_extent = [4,90,95,97]
            self.SubPlotParams = {'left':0.06, 'right':0.95, 'top':.93, 'bottom':0.06, 'wspace':0.23, 'hspace':0.15}
        matplotlib.rc('figure.subplot', **self.SubPlotParams)
        # A param that sets the aspect ratio for the spatial, 2d plots
        self.plot_aspect = 0

        # A param that will tell us if we want to set the E_temp
        self.set_Te = False
        self.delgam_e = 0.03

        # A param that will tell us if we want to set the p_temp
        self.set_Tp = False
        self.delgam_p = 0.06

        # The eps_e & eps_p sections
        self.measure_eps_p = False
        self.e_ion_injection = 1.0
        self.eps_pVar = Tk.StringVar(self)
        self.eps_pVar.set('N/A')

        self.measure_eps_e = False
        self.e_electron_injection = 30.0
        self.eps_eVar = Tk.StringVar(self)
        self.eps_eVar.set('N/A')

        # A param that will be capable of Lorenz boosting the phase plots
        self.DoLorentzBoost = False
        # A parameter that is interpreted as beta if it is <1 and gamma if it is >=1
        self.GammaBoost = 0.0

        # A Param the will set the xlims relative to the shock location
        self.xLimsRelative = True

        self.numOfRows = Tk.IntVar(self)
        self.numOfRows.set(3)
#        self.numOfRows.set(2)
        self.numOfRows.trace('w', self.UpdateGridSpec)
        self.numOfColumns = Tk.IntVar(self)
        self.numOfColumns.set(2)
        self.numOfColumns.trace('w', self.UpdateGridSpec)


        self.show_title = True
        self.xlabel_pad = 0
        self.ylabel_pad = 0
        fileMenu = Tk.Menu(menubar, tearoff=False)
        presetMenu = Tk.Menu(menubar, tearoff=False)
        menubar.add_cascade(label="File", underline=0, menu=fileMenu)
        fileMenu.add_command(label= 'Open Directory', command = self.OnOpen, accelerator='Command+o')
        fileMenu.add_command(label="Exit", underline=1,
                             command=quit, accelerator="Ctrl+Q")
        menubar.add_cascade(label='Preset Views', underline=0, menu = presetMenu)
        presetMenu.add_command(label = 'Default View', command = self.MakeDefaultGraphs)
        presetMenu.add_command(label = 'All Phase Plots', command = self.MakeAllPhase)
        self.config(menu=menubar)

        self.bind_all("<Control-q>", self.quit)
        self.bind_all("<Command-o>", self.OnOpen)


        # create a bunch of regular expressions used to search for files
        f_re = re.compile('flds.tot.*')
        prtl_re = re.compile('prtl.tot.*')
        s_re = re.compile('spect.*')
        param_re = re.compile('param.*')
        self.re_list = [f_re, prtl_re, s_re, param_re]


        # A list that will keep track of whether a given axes is a colorbar or not:
        self.IsCbarList = []

        # The dictionary that holdsd the paths
        self.PathDict = {'Flds': [], 'Prtl': [], 'Param': [], 'Spect': []}

        # A dictionary that allows use to see in what HDF5 file each key is stored.
        # i.e. {'ui': 'Prtl', 'ue': 'Flds', etc...},  Originally I generated the
        # key dictionary automatically, but I don't think that is safe anymore.

        self.H5KeyDict = {u'mx0': 'Param',
                          u'teststarti': 'Param',
                          u'teststartl': 'Param',
                          u'sizex': 'Param',
                          u'sizey': 'Param',
                          u'c_omp': 'Param',
                          u'qi': 'Param',
                          u'istep1': 'Param',
                          u'my0': 'Param',
                          u'dlapion': 'Param',
                          u'testendion': 'Param',
                          u'caseinit': 'Param',
                          u'pltstart': 'Param',
                          u'stride': 'Param',
                          u'ntimes': 'Param',
                          u'cooling': 'Param',
                          u'btheta': 'Param',
                          u'c': 'Param',
                          u'acool': 'Param',
                          u'istep': 'Param',
                          u'delgam': 'Param',
                          u'me': 'Param',
                          u'dlaplec': 'Param',
                          u'mi': 'Param',
                          u'torqint': 'Param',
                          u'mx': 'Param',
                          u'mz0': 'Param',
                          u'yi': 'Prtl',
                          u'proci': 'Prtl',
                          u'proce': 'Prtl',
                          u'ye': 'Prtl',
                          u'zi': 'Prtl',
                          u'ze': 'Prtl',
                          u'xsl': 'Spect',
                          u'umean': 'Spect',
                          u'spece': 'Spect',
                          u'v3xi': 'Flds',
                          u'ey': 'Flds',
                          u'ex': 'Flds',
                          u'ez': 'Flds',
                          u'specp': 'Spect',
                          u'densi': 'Flds',
                          u'specprest': 'Spect',
                          u'we': 'Prtl',
                          u'jx': 'Flds',
                          u'jy': 'Flds',
                          u'jz': 'Flds',
                          u'gmax': 'Spect',
                          u'gmin': 'Spect',
                          'spect_dens': 'Spect',
                          u'wi': 'Prtl',
                          u'bx': 'Flds',
                          u'by': 'Flds',
                          u'bz': 'Flds',
                          u'dgam': 'Spect',
                          u'gamma': 'Spect',
                          u'xi': 'Prtl',
                          u'xe': 'Prtl',
                          u'che': 'Prtl',
                          u'chi': 'Prtl',
                          u'ui': 'Prtl',
                          u'ue': 'Prtl',
                          u've': 'Prtl',
                          u'gamma0': 'Param',
                          u'vi': 'Prtl',
                          u'my': 'Param',
                          u'specerest': 'Spect',
                          u'v3yi': 'Flds',
                          u'walloc': 'Param',
                          u'testendlec': 'Param',
                          u'v3x': 'Flds',
                          u'v3y': 'Flds',
                          u'v3z': 'Flds',
                          u'xinject2': 'Param',
                          u'gammae': 'Prtl',
                          u'bphi': 'Param',
                          u'gammai': 'Prtl',
                          u'dummy': 'Param',
                          u'dens': 'Flds',
                          u'sigma': 'Param',
                          u'interval': 'Param',
                          u'inde': 'Prtl',
                          u'v3zi': 'Flds',
                          u'time': 'Param',
                          u'splitratio': 'Param',
                          u'indi': 'Prtl',
                          u'ppc0': 'Param'}

        # Set the default color map

        self.cmap = 'viridis'
        self.div_cmap = 'BuYlRd'

        # Create the figure
        self.f = Figure(figsize = (2,2), dpi = 100)

        # a tk.DrawingArea
        self.canvas = FigureCanvasTkAgg(self.f, master=self)


        # Make the object hold the timestep info
        self.TimeStep = Param(1, minimum=1, maximum=1000)
        self.playbackbar = PlaybackBar(self, self.TimeStep, canvas = self.canvas)

        # Add the toolbar
        self.toolbar =  MyCustomToolbar(self.canvas, self)
        self.toolbar.update()
        self.canvas._tkcanvas.pack(side=Tk.RIGHT, fill=Tk.BOTH, expand=1)

        # Look for the tristan output files and load the file paths into
        # previous objects
        self.dirname = os.curdir
        self.findDir()

        # Choose the integration region for the particles
        self.e_relative = True
        self.i_L = Tk.IntVar()
        self.i_L.set(-1E4)
        self.i_R = Tk.IntVar()
        self.i_R.set(0)
        self.e_L = Tk.IntVar()
        self.e_L.set(-1E4)
        self.e_R = Tk.IntVar()
        self.e_R.set(0)

        # Choose the region for the FFT
        self.FFT_relative = True #relative to the shock?
        self.FFT_L = Tk.IntVar()
        self.FFT_L.set(0)
        self.FFT_R = Tk.IntVar()
        self.FFT_R.set(200)


        # Whether or not to set a xlim, ylim, or klim
        self.xlim = [False, 0, 100]
        self.ylim = [False, 0, 100]
        self.klim = [False, 0.01, 0.1]

        self.PowerLawFitElectron = [False, 1.0, 10.0]
        self.PowerLawFitIon = [False, 1.0, 10.0]
        # Set the particle colors
        if self.cmap in self.cmaps_with_green:
            self.shock_color = 'w'
            self.ion_color =  new_cmaps.cmaps['plasma'](0.55)
            self.electron_color = new_cmaps.cmaps['plasma'](0.8)
            self.ion_fit_color = 'r'
            self.electron_fit_color = 'yellow'
            self.FFT_color = 'k'

        else:
            self.shock_color = 'w'
            self.ion_color = new_cmaps.cmaps['viridis'](0.45)
            self.electron_color = new_cmaps.cmaps['viridis'](0.75)
            self.ion_fit_color = 'mediumturquoise'
            self.electron_fit_color = 'limegreen'
            self.FFT_color = 'k'


        self.TimeStep.attach(self)
        self.DrawCanvas()


        self.playbackbar.pack(side=Tk.TOP, fill=Tk.BOTH, expand=0)
        self.update()
        # now root.geometry() returns valid size/placement
        self.minsize(self.winfo_width(), self.winfo_height())
        self.geometry("1200x700")
        self.bind('<Return>', self.TxtEnter)
        self.bind('<Left>', self.playbackbar.SkipLeft)
        self.bind('<Right>', self.playbackbar.SkipRight)
        self.bind('r', self.playbackbar.OnReload)
        self.bind('<space>', self.playbackbar.PlayHandler)

    def quit(self, event):
        print("quitting...")
        sys.exit(0)

    def GenH5Dict(self):
        '''Loads all of the files and then finds all of the keys in
        the file to load data. Deprecated'''
        for pkey in self.PathDict.keys():
            with h5py.File(os.path.join(self.dirname,self.PathDict[pkey][0]), 'r') as f:
                # Because dens is in both spect* files and flds* files,
                for h5key in f.keys():
                    if h5key == 'dens' and pkey == 'Spect':
                        self.H5KeyDict['spect_dens'] = pkey
                    else:
                        self.H5KeyDict[h5key] = pkey

        print self.H5KeyDict

    def pathOK(self):
        """ Test to see if the current path contains tristan files
        using regular expressions, then generate the lists of files
        to iterate over"""
        dirlist = os.listdir(self.dirname)
        if 'output' in dirlist:
            self.dirname = os.path.join(self.dirname, 'output')

        is_okay = True

        # Create a dictionary of all the paths to the files
        self.PathDict = {'Flds': [], 'Prtl': [], 'Param': [], 'Spect': []}

        # create a bunch of regular expressions used to search for files
        f_re = re.compile('flds.tot.*')
        prtl_re = re.compile('prtl.tot.*')
        s_re = re.compile('spect.*')
        param_re = re.compile('param.*')
        self.PathDict['Flds']= filter(f_re.match, os.listdir(self.dirname))
        self.PathDict['Flds'].sort()

        self.PathDict['Prtl']= filter(prtl_re.match, os.listdir(self.dirname))
        self.PathDict['Prtl'].sort()

        self.PathDict['Spect']= filter(s_re.match, os.listdir(self.dirname))
        self.PathDict['Spect'].sort()

        self.PathDict['Param']= filter(param_re.match, os.listdir(self.dirname))
        self.PathDict['Param'].sort()

        for key in self.PathDict.keys():
            is_okay &= len(self.PathDict[key]) > 0

        if is_okay:
            self.NewDirectory = True
            self.TimeStep.setMax(len(self.PathDict['Flds']))
            if self.Reload2End:
                self.TimeStep.value = len(self.PathDict['Flds'])
                self.playbackbar.slider.set(self.TimeStep.value)
            self.playbackbar.slider.config(to =(len(self.PathDict['Flds'])))
            self.shock_finder()

        return is_okay


    def OnOpen(self, e = None):
        """open a file"""


        tmpdir = tkFileDialog.askdirectory(title = 'Choose the directory of the output files', **self.dir_opt)
        if tmpdir == '':
            self.findDir()

        else:
            self.dirname = tmpdir
        if not self.pathOK():
#            p = MyDalog(self, 'Directory must contain either the output directory or all of the following: \n flds.tot.*, ptrl.tot.*, params.*, spect.*', title = 'Cannot find output files')
#            self.wait_window(p.top)
            self.findDir()

    def findDir(self, dlgstr = 'Choose the directory of the output files.'):
        """Look for /ouput folder, where the simulation results are
        stored. If output files are already in the path, they are
        automatically loaded"""
        # defining options for opening a directory
        self.dir_opt = {}
        self.dir_opt['initialdir'] = os.curdir
        self.dir_opt['mustexist'] = True
        self.dir_opt['parent'] = self

        if not self.pathOK():
            tmpdir = tkFileDialog.askdirectory(title = dlgstr, **self.dir_opt)
            if tmpdir != '':
                self.dirname = tmpdir
            if not self.pathOK():
#                p = MyDialog(self, 'Directory must contain either the output directory or all of the following: \n flds.tot.*, ptrl.tot.*, params.*, spect.*', title = 'Cannot find output files')
#                self.wait_window(p.top)
                self.findDir()


    def DrawCanvas(self):
        '''Initializes the figure, and then packs it into the main window.
        Should only be called once.'''

        # figsize (w,h tuple in inches) dpi (dots per inch)
        #f = Figure(figsize=(5,4), dpi=100)

        # Generate all of the subplot wrappers. They are stored in a 2D list
        # where the index [i][j] corresponds to the ith row, jth column

        # divy up the figure into a bunch of subplots using GridSpec.
        self.gs0 = gridspec.GridSpec(self.numOfRows.get(),self.numOfColumns.get())


        # Create the list of all of subplot wrappers
        self.SubPlotList = []
        for i in range(self.maxRows):
            tmplist = [SubPlotWrapper(self, figure = self.f, pos=(i,j)) for j in range(self.maxCols)]
            self.SubPlotList.append(tmplist)
        for i in range(self.maxRows):
            for j in range(self.maxCols):
                self.SubPlotList[i][j].SetGraph('PhasePlot')

        self.SubPlotList[0][1].PlotParamsDict['PhasePlot']['prtl_type'] = 1

        self.SubPlotList[1][1].SetGraph('FieldsPlot')
        self.SubPlotList[2][1].SetGraph('MagPlots')

        self.SubPlotList[1][0].SetGraph('DensityPlot')
        self.SubPlotList[2][0].SetGraph('SpectraPlot')

        # Make a list that will hold the previous ctype
        self.MakePrevCtypeList()
        self.canvas.show()
        self.canvas.get_tk_widget().pack(side=Tk.TOP, fill=Tk.BOTH, expand=1)
        self.ReDrawCanvas()


        self.f.canvas.mpl_connect('button_press_event', self.onclick)
#        self.canvas._tkcanvas.pack(side=Tk.TOP, fill=Tk.BOTH, expand=1)

        #self.label = Label(self.top, text = 'Text',bg='orange')
        #self.label.grid()
        # initialize (time index t)
    def MakeDefaultGraphs(self):
        # First get rid of any & all pop up windows:
        if self.settings_window is not None:
            self.settings_window.destroy()
        if self.measure_window is not None:
            self.measure_window.destroy()
        for i in range(self.numOfRows.get()):
            for j in range(self.numOfColumns.get()):
                try:
                    self.SubPlotList[i][j].graph.settings_window.destroy()
                except:
                    pass
        # set it to a 3x2 subplots
        if self.numOfRows.get() != 3:
            self.numOfRows.set(3)
        if self.numOfColumns.get() != 2:
            self.numOfColumns.set(2)

        # Now set the plots back to defaults
        #[0][0] is p_ix vs x phase plotChangeGraph(self, str_arg, redraw = True)
        self.SubPlotList[0][0].SetGraph('PhasePlot')
        self.SubPlotList[0][0].RestoreDefaultPlotParams()

        # electron phase diagram
        self.SubPlotList[0][1].SetGraph('PhasePlot')
        self.SubPlotList[0][1].RestoreDefaultPlotParams()
        self.SubPlotList[0][1].PlotParamsDict['PhasePlot']['prtl_type'] = 1

        # Density 1-D
        self.SubPlotList[1][0].SetGraph('DensityPlot')
        self.SubPlotList[1][0].RestoreDefaultPlotParams()

        # Mag Fields 1-D
        self.SubPlotList[1][1].SetGraph('FieldsPlot')
        self.SubPlotList[1][1].RestoreDefaultPlotParams()

        # Momentum spectrum distribution
        self.SubPlotList[2][0].SetGraph('SpectraPlot')
        self.SubPlotList[2][0].RestoreDefaultPlotParams()

        # delta B/B_0
        self.SubPlotList[2][1].SetGraph('MagPlots')
        self.SubPlotList[2][1].RestoreDefaultPlotParams()


        self.RenewCanvas(ForceRedraw = True, keep_view = False)

    def MakeAllPhase(self):
        # Make a 3x2 plot with the first column being pi-x v x, pi-y v x, pi-z v x
        # and the second column being the electrons.

        # First get rid of any & all pop up windows:
        if self.settings_window is not None:
            self.settings_window.destroy()
        if self.measure_window is not None:
            self.measure_window.destroy()
        for i in range(self.numOfRows.get()):
            for j in range(self.numOfColumns.get()):
                try:
                    self.SubPlotList[i][j].graph.settings_window.destroy()
                except:
                    pass
        # set it to a 3x2 subplots
        if self.numOfRows.get() != 3:
            self.numOfRows.set(3)
        if self.numOfColumns.get() != 2:
            self.numOfColumns.set(2)

        # Now set the plots back to defaults
        #[0][0] is p_ix vs x phase plotChangeGraph(self, str_arg, redraw = True)
        self.SubPlotList[0][0].SetGraph('PhasePlot')
        self.SubPlotList[0][0].RestoreDefaultPlotParams()

        self.SubPlotList[1][0].SetGraph('PhasePlot')
        self.SubPlotList[1][0].RestoreDefaultPlotParams()
        self.SubPlotList[1][0].PlotParamsDict['PhasePlot']['mom_dim'] = 1

        self.SubPlotList[2][0].SetGraph('PhasePlot')
        self.SubPlotList[2][0].RestoreDefaultPlotParams()
        self.SubPlotList[2][0].PlotParamsDict['PhasePlot']['mom_dim'] = 2

        # electron phase diagram
        self.SubPlotList[0][1].SetGraph('PhasePlot')
        self.SubPlotList[0][1].RestoreDefaultPlotParams()
        self.SubPlotList[0][1].PlotParamsDict['PhasePlot']['prtl_type'] = 1

        self.SubPlotList[1][1].SetGraph('PhasePlot')
        self.SubPlotList[1][1].RestoreDefaultPlotParams()
        self.SubPlotList[1][1].PlotParamsDict['PhasePlot']['prtl_type'] = 1
        self.SubPlotList[1][1].PlotParamsDict['PhasePlot']['mom_dim'] = 1

        self.SubPlotList[2][1].SetGraph('PhasePlot')
        self.SubPlotList[2][1].RestoreDefaultPlotParams()
        self.SubPlotList[2][1].PlotParamsDict['PhasePlot']['prtl_type'] = 1
        self.SubPlotList[2][1].PlotParamsDict['PhasePlot']['mom_dim'] = 2


        self.RenewCanvas(ForceRedraw = True, keep_view = False)

    def UpdateGridSpec(self, *args):
        '''A function that handles updates the gridspec that divides up of the
        plot into X x Y subplots'''
        # To prevent orphaned windows, we have to kill all of the windows of the
        # subplots that are no longer shown.

        for i in range(self.maxRows):
            for j in range(self.maxCols):
                if i < self.numOfRows.get() and j < self.numOfColumns.get():
                    pass
                elif self.SubPlotList[i][j].graph.settings_window is not None:
                    self.SubPlotList[i][j].graph.settings_window.destroy()

        self.gs0 = gridspec.GridSpec(self.numOfRows.get(),self.numOfColumns.get())
        self.RenewCanvas(keep_view = False, ForceRedraw = True)

    def LoadAllKeys(self):
        ''' A function that will find out will arrays need to be loaded for
        to draw the graphs. If the time hasn't changed, it will only load new keys.'''
        # Make a dictionary that stores all of the keys we will need to load
        # to draw the graphs.
        self.ToLoad = {'Flds': [], 'Prtl': [], 'Param': [], 'Spect': []}
        for i in range(self.numOfRows.get()):
            for j in range(self.numOfColumns.get()):
                # for each subplot, see what keys are needed
                tmpList = self.SubPlotList[i][j].GetKeys()
                # we always load time because it is needed to calculate the shock location
                self.ToLoad[self.H5KeyDict['time']].append('time')
                # We always load enough to calculate xmin, xmax, ymin, ymax:
                self.ToLoad[self.H5KeyDict['c_omp']].append('c_omp')
                self.ToLoad[self.H5KeyDict['istep']].append('istep')
                self.ToLoad[self.H5KeyDict['dens']].append('dens')


                for elm in tmpList:
                    # find out what type of file the key is stored in
                    ftype = self.H5KeyDict[elm]
                    # add the key to the list of that file type
                    self.ToLoad[ftype].append(elm)
        # See if we are in a new Directory
        if self.NewDirectory:
            # Make a list of timesteps we have already loaded.
            self.timestep_visited = []

            # Timestep queue that ensures that we delete the oldest viewed
            # timestep if memory gets too large
            self.timestep_queue = deque()

            # For each timestep we visit, we will load a dictionary and place it in a list
            self.ListOfDataDict = []

            self.NewDirectory = False


        if self.TimeStep.value in self.timestep_visited:
            cur_ind = self.timestep_visited.index(self.TimeStep.value)
            self.timestep_queue.remove(self.TimeStep.value)
            self.DataDict = self.ListOfDataDict[cur_ind]
            for pkey in self.ToLoad.keys():
                tmplist = list(set(self.ToLoad[pkey])) # get rid of duplicate keys
                tmplist2 = np.copy(tmplist)

                # get rid of keys that are already loaded
                for i in range(len(tmplist2)):
                    if tmplist2[i] in self.DataDict.keys():
                        tmplist.remove(tmplist2[i])
                # Now iterate over each path key and create a datadictionary
                if len(tmplist)> 0:
                    with h5py.File(os.path.join(self.dirname,self.PathDict[pkey][self.TimeStep.value-1]), 'r') as f:
                        for elm in tmplist:
                            try:
                                # Load all the keys
                                if elm == 'spect_dens':
                                    self.DataDict[elm] = np.copy(f['dens'][:])
                                else:
                                    self.DataDict[elm] = np.copy(f[elm][:])

                            except KeyError:
                                if elm == 'sizex':
                                    self.DataDict[elm] = 1
                                if elm == 'c':
                                    self.DataDict[elm]= 0.45
                                if elm == 'ppc0':
                                    self.DataDict[elm] = np.NaN
                                else:
                                    raise

            self.timestep_queue.append(self.TimeStep.value)

        else:
            # The time has not alread been visited so we have to reload everything
            self.DataDict = {}
            for pkey in self.ToLoad.keys():
                tmplist = list(set(self.ToLoad[pkey])) # get rid of duplicate keys
                # Load the file
                if len(tmplist) > 0: #check we actually have something to load
                    with h5py.File(os.path.join(self.dirname,self.PathDict[pkey][self.TimeStep.value-1]), 'r') as f:
                        for elm in tmplist:
                        # Load all the keys
                            try:
                                if elm == 'spect_dens':
                                    self.DataDict[elm] = np.copy(f['dens'][:])
                                else:
                                    self.DataDict[elm] = np.copy(f[elm][:])
                            except KeyError:
                                if elm == 'sizex':
                                    self.DataDict[elm] = 1
                                if elm == 'c':
                                    self.DataDict[elm] = 0.45
                                else:
                                    raise
            # don't keep more than 30 time steps in memory because of RAM issues
            if len(self.timestep_visited)>30:
                oldest_time = self.timestep_queue.popleft()
                oldest_ind = self.timestep_visited.index(oldest_time)
                self.timestep_visited.remove(oldest_time)
                self.ListOfDataDict.pop(oldest_ind)
            self.timestep_visited.append(self.TimeStep.value)
            self.ListOfDataDict.append(self.DataDict)
            self.timestep_queue.append(self.TimeStep.value)

        if np.isnan(self.prev_shock_loc):
            # If self.prev_shock_loc is NaN, that means this is the first time
            # the shock has been found, and the previous and current shock_loc
            # should be the same.

            # First calculate the new shock location
            self.shock_loc = self.DataDict['time'][0]*self.shock_speed
            # Set previous shock loc to current location
            self.prev_shock_loc = np.copy(self.shock_loc)
        else:
            # First save the previous shock location,
            self.prev_shock_loc = np.copy(self.shock_loc)
            # Now calculate the new shock location
            self.shock_loc = self.DataDict['time'][0]*self.shock_speed


        # Now that the DataDict is created, iterate over all the subplots and
        # load the data into them:
        for i in range(self.numOfRows.get()):
            for j in range(self.numOfColumns.get()):
                self.SubPlotList[i][j].LoadData()


    def MakePrevCtypeList(self):
        self.prev_ctype_list = []
        for i in range(self.numOfRows.get()):
            tmp_ctype_l = []
            for j in range(self.numOfColumns.get()):
                tmp_ctype_l.append(str(self.SubPlotList[i][j].chartType))
            self.prev_ctype_list.append(tmp_ctype_l)

    def FindCbars(self, prev = False):
        ''' A function that will find where all the cbars are in the current view '''
        self.IsCbarList = []
        for i in range(self.numOfRows.get()):
            for j in range(self.numOfColumns.get()):
                self.IsCbarList.append(False)
                if prev ==True:
                    if self.SubPlotList[i][j].GetPlotParam('twoD') == 1 and not self.SubPlotList[i][j].Changedto2D:
                    #Note the axes still show up in the view if they are set to zero so we have to do it this way.
#                    if self.SubPlotList[i][j].GetPlotParam('show_cbar') == 1:
                        self.IsCbarList.append(True)
                    elif self.SubPlotList[i][j].Changedto1D:
                        self.IsCbarList.append(True)
                elif self.SubPlotList[i][j].GetPlotParam('twoD') == 1:
                    self.IsCbarList.append(True)

    def SaveView(self):
        # A function that will make sure our view will stay the same as the
        # plot updates.
        cur_view =  list(self.toolbar._views.__call__())
        # Go to the home view
        self.toolbar._views.home()
        self.toolbar._positions.home()
        home_view =  list(self.toolbar._views.__call__())

        # Find cbars
        self.FindCbars(prev=True)
        # Filter out the colorbar axes
        for elm in np.where(self.IsCbarList)[0][::-1]:
            cur_view.pop(elm)
            home_view.pop(elm)

        self.is_changed_list = []
        self.old_views = []
        if cur_view is not None:
            for i in range(len(cur_view)):
                is_changed =[]
                for j in range(4):
                    is_changed.append(np.abs(home_view[i][j]-cur_view[i][j])>1E-5)
                self.is_changed_list.append(is_changed)
                self.old_views.append(cur_view[i])

    def LoadView(self):

        self.toolbar._views.clear()
        self.toolbar.push_current()
        cur_view = list(self.toolbar._views.__call__())

        # Find the cbars in the current plot
        self.FindCbars()

        # put the parts that have changed from the old view
        # into the proper place in the next view
        m = 0 # a counter that allows us to go from labeling the plots in [i][j] to 1d
        k = 0 # a counter that skips over the colorbars
        for i in range(self.numOfRows.get()):
            for j in range(self.numOfColumns.get()):
                tmp_old_view = list(self.old_views.pop(0))

                if self.IsCbarList[k]:
                    k += 1
                tmp_new_view = list(cur_view[k])
                if self.prev_ctype_list[i][j] == self.SubPlotList[i][j].chartType:
                    # see if the view has changed from the home view
                    is_changed = self.is_changed_list[m]
                    if self.SubPlotList[i][j].Changedto2D or self.SubPlotList[i][j].Changedto1D:
                        # only keep the x values if they have changed
                        for n in range(2):
                            if is_changed[n]:
                                tmp_new_view[n] = tmp_old_view[n]+self.xLimsRelative*(self.shock_loc-self.prev_shock_loc)
                    else:
                        # Keep any y or x that is changed
                        for n in range(4):
                            if is_changed[n]:
                                tmp_new_view[n] = tmp_old_view[n]
                                if n < 2:
                                    tmp_new_view[n]+=self.xLimsRelative*(self.shock_loc-self.prev_shock_loc)

                cur_view[k] = tmp_new_view
                # Handle the counting of the 'views' array in matplotlib
                #skip over colorbar axes
                m += 1
                k += 1
                self.SubPlotList[i][j].Changedto1D = False
                self.SubPlotList[i][j].Changedto2D = False

        self.toolbar._views.push(cur_view)
        self.toolbar.set_history_buttons()
        self.toolbar._update_view()


    def RenewCanvas(self, keep_view = True, ForceRedraw = False):

        '''We have two way of updated the graphs: one) by refreshing them using
        self.RefreshCanvas, we don't recreate all of the artists that matplotlib
        needs to make the plot work. self.RefreshCanvas should be fast. Two we
        can ReDraw the canvas using self.ReDrawCanvas. This recreates all the
        artists and will be slow. Sometimes the graph must be redrawn however,
        if the GridSpec changed, more plots are added, the chartype changed, if
        the plot went from 2d to 1D, etc.. If any change occurs that requires a
        redraw, renewcanvas must be called with ForceRedraw = True. '''

#        tic = time.time()
        if ForceRedraw:
            self.ReDrawCanvas(keep_view = keep_view)
        else:
            self.RefreshCanvas(keep_view = keep_view)
        # Record the current ctypes for later
        self.MakePrevCtypeList()


#        toc = time.time()
#        print toc-tic
    def ReDrawCanvas(self, keep_view = True):
        #  We need to see if the user has moved around the zoom level in python.
        # First we see if there are any views in the toolbar
        cur_view =  self.toolbar._views.__call__()

        if cur_view is None:
            keep_view = False
        if self.NewDirectory:
            keep_view = False
        if keep_view:
            self.SaveView()
        self.f.clf()
        #
        if self.clear_fig:
            self.canvas.show()

        self.LoadAllKeys()


        # Calculate the new xmin, and xmax

        # Find the first position with a physical x,y & k axis:
        self.first_x = None
        self.first_y = None
        self.first_k = None
        k = 0
        for i in range(self.numOfRows.get()):
            for j in range(self.numOfColumns.get()):

                # First handle the axes sharing
                if self.SubPlotList[i][j].chartType == 'FFTPlots':
                    # The plot type is a spectral plot, which has no spatial dim
                    if self.first_k is None:
                        self.first_k = (i,j)
                elif self.SubPlotList[i][j].chartType == 'SpectraPlot':
                    # The plot type is a spectral plot, which has no spatial dim
                    pass
                elif self.LinkSpatial != 1 and self.SubPlotList[i][j].chartType == 'PhasePlot':
                    # If this is the case we don't care about the phase plots
                    # as we don't want to share the axes
                    pass
                elif self.LinkSpatial == 3 and self.SubPlotList[i][j].GetPlotParam('twoD'):
                    # If the plot is twoD share the axes
                    if self.first_x is None and self.SubPlotList[i][j].GetPlotParam('spatial_x'):
                        self.first_x = (i,j)
                    if self.first_y is None and self.SubPlotList[i][j].GetPlotParam('spatial_y'):
                        self.first_y = (i,j)

                else:
                    # Just find the first spatial x and y direction.
                    if self.first_x is None and self.SubPlotList[i][j].GetPlotParam('spatial_x'):
                        self.first_x = (i,j)
                    if self.first_y is None and self.SubPlotList[i][j].GetPlotParam('spatial_y'):
                        self.first_y = (i,j)

                # Now... We can draw the graph.
                self.SubPlotList[i][j].DrawGraph()
        if self.show_title:
            tmpstr = self.PathDict['Prtl'][self.TimeStep.value-1].split('.')[-1]
            self.f.suptitle(os.path.abspath(self.dirname)+ '/*.'+tmpstr+' at time t = %d $\omega_{pe}^{-1}$'  % round(self.DataDict['time'][0]), size = 15)
        if keep_view:
            self.LoadView()


        self.canvas.show()
        self.canvas.get_tk_widget().update_idletasks()

        if self.recording:
            self.PrintFig()


    def RefreshCanvas(self, keep_view = True):
        #  We need to see if the user has moved around the zoom level in python.
        # First we see if there are any views in the toolbar
        cur_view =  self.toolbar._views.__call__()

        if cur_view is None:
            keep_view = False
        if self.NewDirectory:
            keep_view = False
        if keep_view:
            self.SaveView()

        self.toolbar._views.clear()

        self.LoadAllKeys()

        # Calculate the new shock location
#        self.shock_loc = self.DataDict['time'][0]*self.shock_speed


        # By design, the first_x and first_y cannot change if the graph is
        # being refreshed. Any call that would require this needs a redraw

        if Use_MultiProcess:
            jobs = []
            # Refresh graphs in parallel
            for i in range(self.numOfRows.get()):
                for j in range(self.numOfColumns.get()):
                    jobs.append(CallAThread(self, i, j))

            while len(jobs)>0:
                for process in jobs:
                    if not process.is_alive():
                        jobs.remove(process)
                time.sleep(.05)
            print 'refreshed'

        else:
            for i in range(self.numOfRows.get()):
                for j in range(self.numOfColumns.get()):
                    # Now we can refresh the graph.
                    self.SubPlotList[i][j].RefreshGraph()

        if self.show_title:
            tmpstr = self.PathDict['Prtl'][self.TimeStep.value-1].split('.')[-1]
            self.f.suptitle(os.path.abspath(self.dirname)+ '/*.'+tmpstr+' at time t = %d $\omega_{pe}^{-1}$'  % round(self.DataDict['time'][0]), size = 15)

        if keep_view:
            self.LoadView()

        self.canvas.draw()
        self.canvas.get_tk_widget().update_idletasks()
        if self.recording:
            self.PrintFig()

    def PrintFig(self):
        movie_dir = os.path.abspath(os.path.join(self.dirname, '..', 'Movie'))
        try:
            os.makedirs(movie_dir)
        except OSError:
            if not os.path.isdir(movie_dir):
                raise

        fname = 'iseult_img_'+ str(self.TimeStep.value).zfill(3)+'.png'
        self.f.savefig(os.path.join(movie_dir, fname))

    def onclick(self, event):
        '''After being clicked, we should use the x and y of the cursor to
        determine what subplot was clicked'''

        # Since the location of the cursor is returned in pixels and gs0 is
        # given as a relative value, we must first convert the value into a
        # relative x and y
        if not event.inaxes:
            pass
        if event.button == 1:
            pass
        else:
            fig_size = self.f.get_size_inches()*self.f.dpi # Fig size in px

            x_loc = event.x/fig_size[0] # The relative x position of the mouse in the figure
            y_loc = event.y/fig_size[1] # The relative y position of the mouse in the figure

            sub_plots = self.gs0.get_grid_positions(self.f)
            row_array = np.sort(np.append(sub_plots[0], sub_plots[1]))
            col_array = np.sort(np.append(sub_plots[2], sub_plots[3]))
            i = (len(row_array)-row_array.searchsorted(y_loc))/2
            j = col_array.searchsorted(x_loc)/2

            self.SubPlotList[i][j].OpenSubplotSettings()

    def shock_finder(self):
        '''The main idea of the shock finder, is we go to the last timestep
        in the simulation and find where the density is half it's max value.
        We then calculate the speed of the of the shock assuming it is
        traveling at constant velocity. We also calculate the initial B & E fields.'''

        # First load the first field file to find the initial size of the
        # box in the x direction, and find the initial field values
        with h5py.File(os.path.join(self.dirname,self.PathDict['Param'][0]), 'r') as f:
            # Find out what sigma is
            try:
                ''' Obviously the most correct way to do this to to calculate b0 from sigma.
                This is proving more difficult that I thought it would be, so I am calculating it
                as Jaehong did.

                sigma = f['sigma'][0]
                gamma0 = f['gamma0'][0]
                c = f['c'][0]
                btheta = f['btheta'][0]
                bphi = f['bphi'][0]

                ppc0 = f['ppc0'][0]
                mi = f['mi'][0]
                me = f['me'][0]
                print mi, c, ppc0
                if gamma0 <1:
                    beta0 = gamma0
                    gamma0 = 1/np.sqrt(1-gamma0**2)
                else:
                    beta0=np.sqrt(1-gamma0**(-2))


                if sigma <= 1E-10:
                    self.b0 = 1.0
                    self.e0 = 1.0
                else:
                    # b0 in the upstream frame
                    self.b0 = np.sqrt(gamma0*ppc0*.5*c**2*(mi+me)*sigma)
                    # Translate to the downstream frame
                    b_x = self.b0*np.cos(btheta)*np.cos(bphi)
                    b_y = self.b0*np.sin(btheta)*np.cos(bphi)
                    b_z = self.b0*np.sin(btheta)*np.cos(bphi)
                    print 'sigma b0', self.b0
                    '''
                    # Normalize by b0
                if np.abs(f['sigma'][0])<1E-8:
                    self.btheta = np.NaN
                else:
                    self.btheta = f['btheta'][0]
            except KeyError:
                self.btheta = np.NaN


        with h5py.File(os.path.join(self.dirname,self.PathDict['Flds'][0]), 'r') as f:
            by = f['by'][:]
            nxf0 = by.shape[1]
            if np.isnan(self.btheta):
                self.b0 = 1.0
                self.e0 = 1.0
            else:
                # Normalize by b0
                self.bx0 = f['bx'][0,-1,-10]
                self.by0 = by[0,-1,-10]
                self.bz0 = f['bz'][0,-1,-10]
                self.b0 = np.sqrt(self.bx0**2+self.by0**2+self.bz0**2)
                self.ex0 = f['ex'][0,-1,-10]
                self.ey0 = f['ey'][0,-1,-10]
                self.ez0 = f['ez'][0,-1,-10]
                self.e0 = np.sqrt(self.ex0**2+self.ey0**2+self.ez0**2)

        # Load the final time step to find the shock's location at the end.
        with h5py.File(os.path.join(self.dirname,self.PathDict['Flds'][-1]), 'r') as f:
            dens_arr =np.copy(f['dens'][0,:,:])

        with h5py.File(os.path.join(self.dirname,self.PathDict['Param'][-1]), 'r') as f:
            # I use this file to get the final time, the istep, interval, and c_omp
            final_time = f['time'][0]
            istep = f['istep'][0]
            interval = f['interval'][0]
            c_omp = f['c_omp'][0]

        # Find out where the shock is at the last time step.
        jstart = min(10*c_omp/istep, nxf0)
        # build the final x_axis of the plot

        xaxis_final = np.arange(dens_arr.shape[1])/c_omp*istep
        # Find the shock by seeing where the density is 1/2 of it's
        # max value.

        dens_half_max = max(dens_arr[dens_arr.shape[0]/2,jstart:])*.5

        # Find the farthest location where the average density is greater
        # than half max
        ishock_final = np.where(dens_arr[dens_arr.shape[0]/2,jstart:]>=dens_half_max)[0][-1]
        xshock_final = xaxis_final[ishock_final]
        self.shock_speed = xshock_final/final_time
        self.prev_shock_loc = np.NaN

    def setKnob(self, value):
        # If the time parameter changes update the plots
        self.RenewCanvas()

    def TxtEnter(self, e):
        self.playbackbar.TextCallback()

def CallAThread(iseult, i, j):
    '''Code that will hopefully allow multiprocessing on refreshing the graphs...
    Not working, doesn't update the plot DO NOT USE!'''
    p = multiprocessing.Process(target=worker, args=(iseult,i,j))
    p.start()
    p.join()
    return p



def worker(iseult,i,j):
    iseult.SubPlotList[i][j].RefreshGraph()
    return
if __name__ == "__main__":

    app = MainApp('Iseult')
    app.mainloop()
