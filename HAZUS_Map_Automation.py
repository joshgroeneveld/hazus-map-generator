# The purpose of this script is to create a set of maps from a HAZUS run
# based on user input.  The user selects one or more maps to create and
# the script takes maps from a template directory and copies them into
# a new project.  For each map, the script generates a PDF and JPEG output.

# Author: Josh Groeneveld
# Created On: 05.21.2015
# Updated On: 05.29.2015
# Copyright: 2015

"""NOTES: This script must be able to access the SQL Server instance that
HAZUS uses to store all of the analysis outputs.
"""

import sys
import traceback
import wx
import os
import logging
import shutil

# 1. Initialize wxpython window
class MainFrame(wx.Frame):
    logfile = None

    def __init__(self, parent):
        wx.Frame.__init__(self, parent, size=wx.Size(520, 710))

        if self.logfile is None:
            self.logfile = 'C:\\Temp\\HAZUS_Map_Generator_Log.txt'

        self.__initlogging()

        self.mainPanel = wx.Panel(self)

        self.SetTitle("HAZUS Map Generator version 0.1.0")

        self.sb = self.CreateStatusBar()
        self.sb.SetStatusText("Please select your output directory.")
        self.logger.info("Script initiated")

        # the welcome box
        self.welcome_sizerbox = wx.StaticBox(self.mainPanel, -1, "Welcome to the HAZUS Map Generator",
                                                pos=wx.Point(8, 6), size=wx.Size(476, 105))

        # the file picker box
        self.output_directory_staticbox = wx.StaticBox(self.mainPanel, -1, "Choose the output directory",
                                                pos=wx.Point(8, 120), size=wx.Size(476, 55))

        # the server info box
        self.serverinfo_staticbox = wx.StaticBox(self.mainPanel, -1, "Server Information",
                                                pos=wx.Point(8, 185), size=wx.Size(476, 340))

        # the create maps box
        self.create_maps_staticbox = wx.StaticBox(self.mainPanel, -1, "Create the selected maps",
                                                pos=wx.Point(8, 535), size=wx.Size(476, 100))

        # welcome text
        welcomemessage = "The HAZUS Map Generator creates a series of maps of your choice based on a HAZUS analysis." \
                         "  This tool assumes that you already have a HAZUS study region and that HAZUS has already" \
                         " finished analyzing the hazards in your study region.  Select your HAZUS Server and the" \
                         " study region from the list below to get started."

        self.welcome_label = wx.StaticText(self.mainPanel, -1, welcomemessage, pos=wx.Point(20, 30),
                                          size=wx.Size(460, 75))

        # Set up the menu to choose a directory from the system
        self.output_directory_dialog_button = wx.Button(self.mainPanel, label="Choose Output Directory",
                                                        pos=wx.Point(20, 140), size=wx.Size(200, -1))
        self.output_directory = ""
        self.output_directory_dialog_button.Bind(wx.EVT_BUTTON, self.select_output_directory)

        # Create an text box to input the name of the HAZUS Server
        self.hazus_server_label = wx.StaticText(self.mainPanel, -1, "HAZUS Server", pos=wx.Point(20, 210))
        self.hazus_server_name = str(os.environ['COMPUTERNAME']) + "\\HAZUSPLUSSRVR"

        self.hazus_server_textbox = wx.TextCtrl(self.mainPanel, -1, value=self.hazus_server_name,
                                                pos=wx.Point(175, 210), size=wx.Size(275, 25))

        # Create a text box to input the HAZUS Study Region Name
        self.hazus_db_list = wx.StaticText(self.mainPanel, -1, "Study Region", pos=wx.Point(20, 245))
        self.hazus_db = "Type Study Region Name Here"
        self.hazus_db_textbox = wx.TextCtrl(self.mainPanel, -1, value=self.hazus_db, pos=wx.Point(175, 245),
                                            size=wx.Size(250, 25))

        self.map_selection_label = wx.StaticText(self.mainPanel, -1, "Select the maps to create",
                                             pos=wx.Point(20, 280), size=wx.Size(300, 50))

        # Create a list box with all of the potential maps that the user can select
        self.map_choices = ["Map 1", "Map 2", "Map 3", "Map 4", "Map 5", "Map 6", "Map 7", "Map 8", "Map 9",
                            "Map 10", "Map 11", "Map 12"]
        self.map_list = wx.ListBox(self.mainPanel, -1, pos=wx.Point(20, 305), choices=self.map_choices,
                                   size=wx.Size(175, 200))

        # Create a list box to show the selected maps
        self.selected_map_label = wx.StaticText(self.mainPanel, -1, "Selected maps", pos=wx.Point(300, 280),
                                                size=wx.Size(300, 50))

        self.selected_map_choices = [""]
        self.selected_map_list = wx.ListBox(self.mainPanel, -1, pos=wx.Point(300, 305),
                                            choices=self.selected_map_choices, size=wx.Size(175, 200))

        # Create buttons to add maps to the selected list or remove them
        self.add_maps_to_selection = wx.Button(self.mainPanel, label="Add -->", pos=wx.Point(210, 350),
                                               size=wx.Size(80, 60))

        self.remove_maps_from_selection = wx.Button(self.mainPanel, label="Remove <--", pos=wx.Point(210, 420),
                                                    size=wx.Size(80, 60))

        # Create a button that runs the script
        self.create_maps = wx.Button(self.mainPanel, label="Go!", pos=wx.Point(20, 560),
                                        size=wx.Size(150, 60))
        # self.Bind(wx.EVT_BUTTON, self.oncreatemaps, self.createmaps)

        # Create a button that resets the form
        self.reset_button = wx.Button(self.mainPanel, label="Reset", pos=wx.Point(200, 560), size=wx.Size(150, 60))
        # self.Bind(wx.EVT_BUTTON, self.OnReset, self.resetButton)

        self.Show()
        
    # 2. Select output directory
    def select_output_directory(self, event):
        """This function allows the user to choose an output directory and then generates a list
        of available SQL Server instances for the user to select."""
        dlg = wx.DirDialog(self, "Choose a directory:", style=wx.DD_DEFAULT_STYLE)
        if dlg.ShowModal() == wx.ID_OK:
            self.output_directory = dlg.GetPath()
            self.sb.SetStatusText("You chose %s" % self.output_directory)
            self.logger.info("Output directory: " + self.output_directory)
        dlg.Destroy()

    # 3. Choose map or maps from list of templates and add to list of maps to create
    #  4. Run the script
    #  4a. Create the directory structure in output directory
    #  4.b Extract data from SQL Server
    #  4.c Create table queries to get only the data we need
    #  4.d Join data to census geography as needed
    #  4.e For each map, point .lyr templates in map to new data
    #  4.f Export maps as PDF and JPEG
    #  5. View log files if desired
    def __initlogging(self):
        """Initialize a log file to view all of the settings and error information each time
        the script runs."""
        self.logger = logging.getLogger("SitRepIncidentMapLog")
        self.logger.setLevel(logging.DEBUG)

        # Create a file handler
        ch = logging.FileHandler(self.logfile)
        ch.setLevel(logging.DEBUG)

        # Format the logfile entries
        formatter = logging.Formatter("[%(asctime)s][%(name)s:%(lineno)d][%(levelname)s] %(message)s")
        # add formatter to ch
        ch.setFormatter(formatter)
        # add ch to logger
        self.logger.addHandler(ch)

try:
    app = wx.App(False)
    MainFrame(None)
    app.MainLoop()

except:
    # Error handling code from ArcGIS Resource Center
    tb = sys.exc_info()[2]
    tbinfo = traceback.format_tb(tb)[0]
    pymsg = "PYTHON ERRORS:\nTraceback Info:\n" + tbinfo + "\nError Info:\n     " + str(sys.exc_type) + ": " + str(
        sys.exc_value) + "\n"

    print pymsg