# The purpose of this script is to create a set of maps from a HAZUS run
# based on user input.  The user selects one or more maps to create and
# the script takes maps from a template directory and copies them into
# a new project.  For each map, the script generates a PDF and JPEG output.

# Author: Josh Groeneveld
# Created On: 05.21.2015
# Updated On: 12.09.2015
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
import sqlinstances
import pyodbc
import inspect
import arcpy

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
        self.scenario_dir = ""
        self.scenario_data_dir = ""
        self.study_region_data = ""
        self.output_directory_dialog_button.Bind(wx.EVT_BUTTON, self.select_output_directory)

        # Create an drop down menu to select the name of the HAZUS Server
        self.hazus_server_label = wx.StaticText(self.mainPanel, -1, "Select your HAZUS Server", pos=wx.Point(20, 210))
        self.hazus_server_choices = ["Server 1", "Server 2"]

        self.hazus_server_list = wx.ComboBox(self.mainPanel, -1, "", choices=self.hazus_server_choices,
                                             pos=wx.Point(175, 210), size=wx.Size(250, 25))
        self.hazus_server = ""

        self.hazus_server_list.Bind(wx.EVT_COMBOBOX, self.select_hazus_server)

        # Create a drop down menu to select the HAZUS Study Region
        self.hazus_db_list = wx.StaticText(self.mainPanel, -1, "Select your Study Region", pos=wx.Point(20, 245))
        self.db_choices = ["Study Region 1", "Study Region 2"]
        self.db_list = wx.ComboBox(self.mainPanel, -1, "", choices=self.db_choices,
                                          pos=wx.Point(175, 245), size=wx.Size(250, 25))
        self.hazus_db = ""

        self.map_selection_label = wx.StaticText(self.mainPanel, -1, "Select the maps to create",
                                             pos=wx.Point(20, 280), size=wx.Size(300, 25))
        self.db_list.Bind(wx.EVT_COMBOBOX, self.select_hazus_db)

        # Create a list box with all of the potential maps that the user can select
        self.map_choices = ["Direct Economic Loss", "Shelter Needs", "Elderly Populations", "Utility Damage",
                            "Building Inspection Needs", "Estimated Debris", "Demographic Distribution",
                            "Highway Infrastructure Damage", "Impaired Hospitals", "Water Infrastructure Damage",
                            "Search and Rescue Needs", "Special Needs Populations"]

        self.map_list = wx.ListBox(self.mainPanel, -1, pos=wx.Point(20, 305), choices=self.map_choices,
                                   size=wx.Size(175, 200), style=wx.LB_EXTENDED | wx.LB_SORT)

        # Create a list box to show the selected maps
        self.selected_map_label = wx.StaticText(self.mainPanel, -1, "Selected maps", pos=wx.Point(300, 280),
                                                size=wx.Size(300, 25))

        self.selected_map_choices = []
        self.selected_maps = []
        self.selected_map_list = wx.ListBox(self.mainPanel, -1, pos=wx.Point(300, 305),
                                            style=wx.LB_EXTENDED | wx.LB_SORT, choices=self.selected_map_choices,
                                            size=wx.Size(175, 200))
        self.deselect_map_choices = []
        self.map_extent = {}

        # Disable the map selection lists until the user selects a server and a database
        self.map_list.Disable()
        self.selected_map_list.Disable()

        # Create buttons to add maps to the selected list or remove them
        self.add_maps_to_selection = wx.Button(self.mainPanel, label="Add -->", pos=wx.Point(210, 350),
                                               size=wx.Size(80, 60))
        self.add_maps_to_selection.Bind(wx.EVT_BUTTON, self.select_maps)

        self.remove_maps_from_selection = wx.Button(self.mainPanel, label="Remove <--", pos=wx.Point(210, 420),
                                                    size=wx.Size(80, 60))
        self.remove_maps_from_selection.Bind(wx.EVT_BUTTON, self.deselect_maps)

        # Create a button that runs the script
        self.create_maps = wx.Button(self.mainPanel, label="Go!", pos=wx.Point(20, 560),
                                        size=wx.Size(150, 60))
        self.Bind(wx.EVT_BUTTON, self.copy_template, self.create_maps)

        # Create a button that resets the form
        self.reset_button = wx.Button(self.mainPanel, label="Reset", pos=wx.Point(200, 560), size=wx.Size(150, 60))
        # self.Bind(wx.EVT_BUTTON, self.OnReset, self.resetButton)

        self.Show()

    # 2. Select output directory
    def select_output_directory(self, event):
        """This function allows the user to choose an output directory and then generates a list
        of available SQL Server instances for the user to select."""
        dlg = wx.DirDialog(self, "Choose a directory:", style=wx.DD_DEFAULT_STYLE)
        dlg.Show()
        if dlg.ShowModal() == wx.ID_OK:
            self.output_directory = dlg.GetPath()
            self.sb.SetStatusText("You chose %s" % self.output_directory)
            self.logger.info("Output directory: " + self.output_directory)
        dlg.Destroy()
        self.hazus_server_choices = sqlinstances.list_sql_servers(self)
        self.hazus_server_list.Clear()
        for server in self.hazus_server_choices:
            self.hazus_server_list.Append(server)
        self.sb.SetStatusText("Please select your HAZUS Server")

    # 3. Select HAZUS SQL Server instance
    def select_hazus_server(self, event):
        """This function allows the user to select a HAZUS server (SQL Server instance) from a
        drop down list, and then populates a drop down list of HAZUS study regions (databases)
        for the user to select."""
        self.hazus_server = self.hazus_server_list.GetValue()
        self.sb.SetStatusText("You chose %s" % self.hazus_server)
        self.logger.info("HAZUS Server: " + str(self.hazus_server))

        # Populate the drop down menu of databases in the server
        cxn = pyodbc.connect('DRIVER={SQL Server};SERVER=%s;DATABASE=master;UID="hazuspuser";'
                             'PASSWORD="gohazusplus_01";Trusted_Connection=yes' % str(self.hazus_server))
        cursor = cxn.cursor()
        cursor.execute("select name from sys.databases")
        rows = cursor.fetchall()
        self.db_list.Clear()
        for row in rows:
            self.db_list.Append(row[0])
        self.sb.SetStatusText("Please select your HAZUS Study Region")
        cxn.close()

    # 4. Select HAZUS study region (SQL Server database)
    def select_hazus_db(self, event):
        """This function allows the user to select a HAZUS Study Region (SQL Server Database) from
        a drop down list, then enables the user to select the set of maps to generate."""
        self.hazus_db = self.db_list.GetValue()
        self.sb.SetStatusText("You chose %s" % self.hazus_db)
        self.logger.info("HAZUS Database: " + str(self.hazus_db))

        # Enable the map selection lists
        self.map_list.Enable()
        self.selected_map_list.Enable()
        self.sb.SetStatusText("Please choose the maps you want to create")

    # 5. Choose map or maps from list of templates and add to list of maps to create
    def select_maps(self, event):
        """This function allows the user to select some or all of the available maps and add them
        to the list of maps to create."""
        self.selected_map_choices = list(self.map_list.GetSelections())

        # Add the selected maps to the selected list, and remove these selections from the
        # original list so that each map can only be selected once
        for s in self.selected_map_choices:
            selected_map = self.map_list.GetString(s)
            self.selected_maps.append(selected_map)
            self.map_choices.remove(selected_map)
            self.logger.info("Added " + str(selected_map) + " to selection")
        self.selected_map_list.Set(self.selected_maps)
        self.map_list.Set(self.map_choices)
        self.sb.SetStatusText("Click Go! to create maps or adjust your selections")

    def deselect_maps(self, event):
        """This function allows the user to revise the current map selection before creating the maps."""
        self.deselect_map_choices = list(self.selected_map_list.GetSelections())

        for d in self.deselect_map_choices:
            map_to_deselect = self.selected_map_list.GetString(d)
            self.map_choices.append(map_to_deselect)
            self.selected_maps.remove(map_to_deselect)
            self.logger.info("Removed " + str(map_to_deselect) + " from selection")
        self.selected_map_list.Set(self.selected_maps)
        self.map_list.Set(self.map_choices)
        self.sb.SetStatusText("Click Go! if you are happy with your selections")

    # 6. Run the script
    # 6a. Create the directory structure in output directory
    # Copy the template shakemap geodatabase to a Data folder in the
    # same directory as the earthquake name
    def copy_template(self, event):
        """This function copies a template study region geodatabase and the
        layer files into the selected output directory."""
        temp = inspect.stack()[0][1]
        script_dir = temp.replace('HAZUS_Map_Automation.py', "Template")
        self.scenario_dir = self.output_directory + "\\" + self.hazus_db
        self.scenario_data_dir = self.scenario_dir + "\\Scenario_Data"
        self.study_region_data = self.scenario_data_dir + "\\Data\\StudyRegionData.mdb"
        shutil.copytree(script_dir, self.scenario_data_dir)
        self.sb.SetStatusText("Copied template data and maps to " + self.scenario_data_dir)
        self.logger.info("Copied template data and maps to " + self.scenario_data_dir)
        output_dirs = ["Summary_Reports", "JPEG", "PDF"]
        os.chdir(self.scenario_dir)
        for new_dir in output_dirs:
            os.mkdir(new_dir)
        self.sb.SetStatusText("Created output dirs in: " + self.scenario_dir)
        self.connect_to_db()

    # 6.b Extract data from SQL Server
    # Use pyodbc to connect to SQL Server
    def connect_to_db(self):
        """This function establishes a connection to the selected HAZUS database
        to extract data for the selected maps."""
        connection_str = """
        DRIVER={SQL Server};
        SERVER=%s;
        DATABASE=%s;
        UID=hazuspuser;
        PWD=gohazusplus_01""" % (self.hazus_server, self.hazus_db)

        conn = pyodbc.connect(connection_str)
        self.sb.SetStatusText("Established connection to: " + self.hazus_db)
        self.logger.info("Established connection to: " + self.hazus_db)
        cursor = conn.cursor()
        maps_to_create = []
        for selected_map in self.selected_maps:
            self.logger.info("Selected map list includes: " + selected_map)
            lower_case = selected_map.lower()
            no_spaces = lower_case.replace(" ", "_")
            maps_to_create.append(str(no_spaces))

        self.determine_map_extent(cursor)
        # Call a function to extract the data needed for each map
        # For example, if building inspection needs is one of the selected maps,
        # the getattr() statement below generates the following:
        # getattr(self, building_inspection_needs)(), which is equivalent to:
        # self.building_inspection_needs()
        for m in maps_to_create:
            getattr(self, m)(cursor)
        cursor.close()
        conn.close()
        self.sb.SetStatusText("Closed connection to the HAZUS database")

    def determine_map_extent(self, cursor):
        """This function accepts a cursor from pyodbc to call the SQL Server
        database and queries the database for all tracts in the current study
        region.  These tracts are then passed to arcpy to calculate the extent
        of these tracts.  This extent is returned out of the function and passed
        to each of the maps selected."""
        study_region_tracts_sql = """
        SELECT Tract FROM hzTract
        """
        cursor.execute(study_region_tracts_sql)
        study_region_tracts = cursor.fetchall()
        tracts_to_select = []
        for sr_tract in study_region_tracts:
            tracts_to_select.append(sr_tract[0])

        # Convert list of tracts into a string to add to a selection query
        str_tracts = str(tracts_to_select)
        str_tracts = str_tracts.replace("[", "")
        str_tracts = str_tracts.replace("]", "")

        tract_fc = arcpy.mapping.Layer(self.scenario_data_dir + "\\Data\\TotalEconLoss.lyr")
        out_fl = self.scenario_data_dir + "\\Data\\Selected_Tracts.lyr"

        arcpy.management.MakeFeatureLayer(tract_fc, "temp_lyr")
        lyr = arcpy.mapping.Layer("temp_lyr")
        lyr.definitionQuery = "[Tract] in (" + str_tracts + ")"
        lyr.saveACopy(out_fl)
        selection_layer = arcpy.mapping.Layer(out_fl)
        # Get extent of feature layer
        tract_extent = selection_layer.getExtent()
        # Return extent out of function as dictionary
        self.map_extent["XMin"] = tract_extent.XMin
        self.map_extent["XMax"] = tract_extent.XMax
        self.map_extent["YMin"] = tract_extent.YMin
        self.map_extent["YMax"] = tract_extent.YMax

        self.sb.SetStatusText("Determined map extent")

    # 6.c Create table queries to get only the data we need
    # For each possible map, create a function to call the specific data needed

    def building_inspection_needs(self, cursor):
        """This function creates the building inspection needs map by querying
        the eqTractDmg table in the SQL Server database."""
        self.logger.info("You want to make a building inspection needs map!")

        # Get the data from SQL Server
        building_inspection_sql = """
        SELECT Tract, Sum(PDsSlightBC) as PDsSlightBC, Sum(PDsModerateBC) as PDsModerateBC,
        Sum(PDsExtensiveBC) as PDsExtensiveBC, Sum(PDsCompleteBC) as PDsCompleteBC
        FROM eqTractDmg WHERE DmgMechType='STR'
        GROUP BY Tract
        """
        cursor.execute(building_inspection_sql)
        inspection_tracts = cursor.fetchall()

        # Update the corresponding fields in the StudyRegionData.mdb\eqTract table
        fc = self.study_region_data + "\\eqTract"
        for ins_tract in inspection_tracts:
            tract = ins_tract.Tract
            slight = ins_tract.PDsSlightBC
            moderate = ins_tract.PDsModerateBC
            extensive = ins_tract.PDsExtensiveBC
            complete = ins_tract.PDsCompleteBC

            query = '[Tract] = ' + '\'' + tract + '\''
            fields = ['PDsSlightBC', 'PDsModerateBC', 'PDsExtensiveBC', 'PDsCompleteBC', 'SL_MO_TOT']
            with arcpy.da.UpdateCursor(fc, fields, query) as urows:
                for urow in urows:
                    urow[0] = slight
                    urow[1] = moderate
                    urow[2] = extensive
                    urow[3] = complete
                    urow[4] = slight + moderate
                    urows.updateRow(urow)

        self.update_fc(fc, 'PDsSlightBC')

    def demographic_distribution(self, cursor):
        """This function creates a demographic distribution map by showing the
        distribution of people who may not speak English as a first language."""
        self.logger.info("You want to make a demographic distribution map!")

    def direct_economic_loss(self, cursor):
        """This function creates a direct economic loss map by querying the
        eqTractEconLoss table in the SQL Server database."""
        self.logger.info("You want to make a direct economic loss map!")

        # Get the data from SQL Server
        economic_loss_sql = """
        SELECT Tract, Sum(TotalLoss) as TotalLoss
        FROM eqTractEconLoss
        GROUP BY Tract
        """
        cursor.execute(economic_loss_sql)
        del_tracts = cursor.fetchall()

        # Update the corresponding fields in the StudyRegionData.mdb\eqTract table
        fc = self.study_region_data + "\\eqTract"
        for del_tract in del_tracts:
            tract = del_tract.Tract
            total_econ_loss = del_tract.TotalLoss

            query = '[Tract] = ' + '\'' + tract + '\''
            fields = ['TotalEconLoss']
            with arcpy.da.UpdateCursor(fc, fields, query) as urows:
                for urow in urows:
                    urow[0] = total_econ_loss
                    urows.updateRow(urow)

        self.update_fc(fc, 'TotalEconLoss')

    def elderly_populations(self, cursor):
        """This function creates an elderly populations map by showing the
        distribution of people over the age of 65."""
        self.logger.info("You want to make an elderly populations map!")

    def estimated_debris(self, cursor):
        """This function creates an estimated debris map by querying the
        eqTract table in the SQL Server database."""
        self.logger.info("You want to make an estimated debris map!")

        # Get the data from SQL Server
        debris_sql = """
        SELECT Tract, DebrisS, DebrisC, DebrisTotal
        FROM eqTract
        """
        cursor.execute(debris_sql)
        debris_tracts = cursor.fetchall()

        # Update the corresponding fields in the StudyRegionData.mdb\eqTract table
        fc = self.study_region_data + "\\eqTract"
        for debris_tract in debris_tracts:
            tract = debris_tract.Tract
            debriss = debris_tract.DebrisS
            debrisc = debris_tract.DebrisC
            debris_total = debris_tract.DebrisTotal

            query = '[Tract] = ' + '\'' + tract + '\''
            fields = ['DebrisS', 'DebrisC', 'DebrisTotal']
            with arcpy.da.UpdateCursor(fc, fields, query) as urows:
                for urow in urows:
                    urow[0] = debriss
                    urow[1] = debrisc
                    urow[2] = debris_total
                    urows.updateRow(urow)

        self.update_fc(fc, 'DebrisTotal')

    def highway_infrastructure_damage(self, cursor):
        """This function creates a highway Infrastructure damage map by querying
        the eqHighwayBridge and eqHighwaySegement tables in the SQL Server database."""
        self.logger.info("You want to make a highway Infrastructure damage map!")

        # Get the data from SQL Server
        highways_sql = """
        SELECT HighwaySegID, PDsExceedModerate, FunctDay1, EconLoss
        FROM eqHighwaySegment
        """
        cursor.execute(highways_sql)
        highways = cursor.fetchall()

        # Update the corresponding fields in the StudyRegionData.mdb\eqHighwaySegment table
        highway_fc = self.study_region_data + "\\eqHighwaySegment"
        for highway in highways:
            highway_id = highway.HighwaySegID
            highway_moderate = highway.PDsExceedModerate
            highway_functday1 = highway.FunctDay1
            highway_econ_loss = highway.EconLoss

            query = '[HighwaySegID] = ' + '\'' + highway_id + '\''
            fields = ['PDsExceedModerate', 'FunctDay1', 'EconLoss']
            with arcpy.da.UpdateCursor(highway_fc, fields, query) as urows:
                for urow in urows:
                    urow[0] = highway_moderate
                    urow[1] = highway_functday1
                    urow[2] = highway_econ_loss
                    urows.updateRow(urow)

        self.update_fc(highway_fc, 'PDsExceedModerate')

        # Get the data from SQL Server
        bridges_sql = """
        SELECT HighwayBridgeID, PDsExceedModerate, FunctDay1, EconLoss
        FROM eqHighwayBridge
        """
        cursor.execute(bridges_sql)
        bridges = cursor.fetchall()

        # Update the corresponding fields in the StudyRegionData.mdb\eqHighwayBridge table
        bridge_fc = self.study_region_data + "\\eqHighwayBridge"
        for bridge in bridges:
            bridge_id = bridge.HighwayBridgeID
            bridge_moderate = bridge.PDsExceedModerate
            bridge_functday1 = bridge.FunctDay1
            bridge_econ_loss = bridge.EconLoss

            query = '[HighwayBridgeId] = ' + '\'' + bridge_id + '\''
            fields = ['PDsExceedModerate', 'FunctDay1', 'EconLoss']
            with arcpy.da.UpdateCursor(bridge_fc, fields, query) as urows:
                for urow in urows:
                    urow[0] = bridge_moderate
                    urow[1] = bridge_functday1
                    urow[2] = bridge_econ_loss
                    urows.updateRow(urow)

        self.update_fc(bridge_fc, 'PDsExceedModerate')

    def impaired_hospitals(self, cursor):
        """This function creates an impaired hospitals map by querying the
        eqCareFlty table for hospital performance data and the eqTractCasOccup
        table for life threatening injury data."""
        self.logger.info("You want to make an impaired hospitals map!")

        # Get the data from SQL Server
        hospital_sql = """
        SELECT CareFltyID, PDsExceedModerate, FunctDay1, EconLoss
        FROM eqCareFlty
        """
        injury_sql = """
        SELECT Tract, Sum(Level1Injury) as Level1Injury, Sum(Level2Injury) as Level2Injury,
        Sum(Level3Injury) as Level3Injury, Sum(Level4Injury) as Level4Injury
        FROM eqTractCasOccup
        WHERE CasTime = 'D' AND InOutTot = 'TOT'
        GROUP BY Tract
        """
        cursor.execute(hospital_sql)
        hospitals = cursor.fetchall()

        # Update the corresponding fields in the StudyRegionData.mdb\eqCareFlty table
        hospital_fc = self.study_region_data + "\\eqCareFlty"
        for hospital in hospitals:
            hospital_id = hospital.CareFltyID
            hospital_moderate = hospital.PDsExceedModerate
            hospital_functday1 = hospital.FunctDay1
            hospital_econ_loss = hospital.EconLoss

            query = '[CareFltyId] = ' + '\'' + hospital_id + '\''
            fields = ['PDsExceedModerate', 'FunctDay1', 'EconLoss']
            with arcpy.da.UpdateCursor(hospital_fc, fields, query) as urows:
                for urow in urows:
                    urow[0] = hospital_moderate
                    urow[1] = hospital_functday1
                    urow[2] = hospital_econ_loss
                    urows.updateRow(urow)

        self.update_fc(hospital_fc, 'PDsExceedModerate')

        # Update the corresponding fields in the StudyRegionData.mdb\eqTract table
        cursor.execute(injury_sql)
        injury_tracts = cursor.fetchall()
        fc = self.study_region_data + "\\eqTract"
        for injury_tract in injury_tracts:
            tract = injury_tract.Tract
            level1 = injury_tract.Level1Injury
            level2 = injury_tract.Level2Injury
            level3 = injury_tract.Level3Injury
            level4 = injury_tract.Level4Injury

            query = '[Tract] = ' + '\'' + tract + '\''
            fields = ['Level1Injury', 'Level2Injury', 'Level3Injury', 'Level4Injury', 'SUM_2_3']
            with arcpy.da.UpdateCursor(fc, fields, query) as urows:
                for urow in urows:
                    urow[0] = level1
                    urow[1] = level2
                    urow[2] = level3
                    urow[3] = level4
                    urow[4] = level2 + level3
                    urows.updateRow(urow)

        self.update_fc(fc, 'Level1Injury')

    def search_and_rescue_needs(self, cursor):
        """This function creates a search and rescue needs map by querying the
        eqTractDmg table in the SQL Server database.  Search and rescue needs are
        represented by red tag (complete) damage buildings.  Only a portion of these
        buildings would be expected to collapse (e.g., 15 percent of URMs)."""
        self.logger.info("You want to make a search and rescue needs map!")

        # Get the data from SQL Server
        sar_sql = """
        SELECT Tract, Sum(PDsCompleteBC) as PDsCompleteBC
        FROM eqTractDmg WHERE DmgMechType='STR'
        GROUP BY Tract
        """
        cursor.execute(sar_sql)
        sar_tracts = cursor.fetchall()

        # Update the corresponding fields in the StudyRegionData.mdb\eqTract table
        fc = self.study_region_data + "\\eqTract"
        for sar_tract in sar_tracts:
            tract = sar_tract.Tract
            complete = sar_tract.PDsCompleteBC

            query = '[Tract] = ' + '\'' + tract + '\''
            fields = ['PDsCompleteBC']
            with arcpy.da.UpdateCursor(fc, fields, query) as urows:
                for urow in urows:
                    urow[0] = complete
                    urows.updateRow(urow)

        self.update_fc(fc, 'PDsCompleteBC')

    def shelter_needs(self, cursor):
        """This function creates a shelter needs map by querying the
        eqTract table in the SQL Server database."""
        self.logger.info("You want to make a shelter needs map!")

        # Get the data from SQL Server
        shelter_sql = """
        SELECT Tract, ShortTermShelter, DisplacedHouseholds, ExposedPeople, ExposedValue
        FROM eqTract
        """
        cursor.execute(shelter_sql)
        shelter_tracts = cursor.fetchall()

        # Update the corresponding fields in the StudyRegionData.mdb\eqTract table
        fc = self.study_region_data + "\\eqTract"
        for shelter_tract in shelter_tracts:
            tract = shelter_tract.Tract
            displaced = shelter_tract.DisplacedHouseholds
            shelter = shelter_tract.ShortTermShelter
            exposed_people = shelter_tract.ExposedPeople
            exposed_value = shelter_tract.ExposedValue

            query = '[Tract] = ' + '\'' + tract + '\''
            fields = ['DisplacedHouseholds', 'ShortTermShelter', 'ExposedPeople', 'ExposedValue']
            with arcpy.da.UpdateCursor(fc, fields, query) as urows:
                for urow in urows:
                    urow[0] = displaced
                    urow[1] = shelter
                    urow[2] = exposed_people
                    urow[3] = exposed_value
                    urows.updateRow(urow)

        self.update_fc(fc, 'DisplacedHouseholds')


    def special_needs_populations(self, cursor):
        self.logger.info("You want to make a special needs populations map!")

    def utility_damage(self, cursor):
        """THis function creates a utility damage map by querying the
        eqElectricPowerFlty, eqOilFlty and eqNaturalGasFlty tables in the
        SQL Server database."""
        self.logger.info("You want to make a utility damage map!")

        # Get the datat from SQL Server
        electric_flty_sql = """
        SELECT ElectricPowerFltyID, PDsExceedModerate, FunctDay1, EconLoss
        FROM eqElectricPowerFlty
        """
        cursor.execute(electric_flty_sql)
        electric_facilities = cursor.fetchall()

        # Update the corresponding fields in the StudyRegionData.mdb\eqElectricPowerFlty table
        electric_fc = self.study_region_data + "\\eqElectricPowerFlty"
        for electric_facility in electric_facilities:
            electric_flty_id = electric_facility.ElectricPowerFltyID
            electric_flty_moderate = electric_facility.PDsExceedModerate
            electric_flty_funct_day1 = electric_facility.FunctDay1
            electric_flty_econ_loss = electric_facility.EconLoss

            query = '[ElectricPowerFltyID] = ' + '\'' + electric_flty_id + '\''
            fields = ['PDsExceedModerate', 'FunctDay1', 'EconLoss']
            with arcpy.da.UpdateCursor(electric_fc, fields, query) as urows:
                for urow in urows:
                    urow[0] = electric_flty_moderate
                    urow[1] = electric_flty_moderate
                    urow[2] = electric_flty_econ_loss
                    urows.updateRow(urow)

        self.update_fc(electric_fc, 'PDsExceedModerate')

        # Get the datat from SQL Server
        natural_gas_flty_sql = """
        SELECT NaturalGasFltyID, PDsExceedModerate, FunctDay1, EconLoss
        FROM eqNaturalGasFlty
        """
        cursor.execute(natural_gas_flty_sql)
        natural_gas_facilities = cursor.fetchall()

        # Update the corresponding fields in the StudyRegionData.mdb\eqNaturalGasFlty table
        ng_fc = self.study_region_data + "\\eqNaturalGasFlty"
        for natural_gas_facility in natural_gas_facilities:
            natural_gas_flty_id = natural_gas_facility.ElectricPowerFltyID
            natural_gas_flty_moderate = natural_gas_facility.PDsExceedModerate
            natural_gas_flty_funct_day1 = natural_gas_facility.FunctDay1
            natural_gas_flty_econ_loss = natural_gas_facility.EconLoss

            query = '[NaturalGasFltyID] = ' + '\'' + natural_gas_flty_id + '\''
            fields = ['PDsExceedModerate', 'FunctDay1', 'EconLoss']
            with arcpy.da.UpdateCursor(ng_fc, fields, query) as urows:
                for urow in urows:
                    urow[0] = natural_gas_flty_moderate
                    urow[1] = natural_gas_flty_moderate
                    urow[2] = natural_gas_flty_econ_loss
                    urows.updateRow(urow)

        self.update_fc(ng_fc, 'PDsExceedModerate')

        # Get the datat from SQL Server
        oil_flty_sql = """
        SELECT OilFltyID, PDsExceedModerate, FunctDay1, EconLoss
        FROM eqOilFlty
        """
        cursor.execute(oil_flty_sql)
        oil_facilities = cursor.fetchall()

        # Update the corresponding fields in the StudyRegionData.mdb\eqOilFlty table
        oil_fc = self.study_region_data + "\\eqOilFlty"
        for oil_facility in oil_facilities:
            oil_flty_id = oil_facility.ElectricPowerFltyID
            oil_flty_moderate = oil_facility.PDsExceedModerate
            oil_flty_funct_day1 = oil_facility.FunctDay1
            oil_flty_econ_loss = oil_facility.EconLoss

            query = '[OilFltyID] = ' + '\'' + oil_flty_id + '\''
            fields = ['PDsExceedModerate', 'FunctDay1', 'EconLoss']
            with arcpy.da.UpdateCursor(oil_fc, fields, query) as urows:
                for urow in urows:
                    urow[0] = oil_flty_moderate
                    urow[1] = oil_flty_moderate
                    urow[2] = oil_flty_econ_loss
                    urows.updateRow(urow)

        self.update_fc(oil_fc, 'PDsExceedModerate')

    def water_infrastructure_damage(self, cursor):
        """This function creates a potable water infrastructure damage map by
        querying the eqPotableWaterDL table in the SQL Server database."""
        self.logger.info("You want to make a water Infrastructure damage map!")

        # Get the data from SQL Server
        water_sql = """
        SELECT Tract, TotalPipe, TotalNumRepairs, TotalDysRepairs, EconLoss, Cost
        FROM eqPotableWaterDL
        """
        cursor.execute(water_sql)
        water_tracts = cursor.fetchall()

        # Update the corresponding fields in the StudyRegionData.mdb\eqPotableWaterDL table
        fc = self.study_region_data + "\\eqPotableWaterDL"
        for water_tract in water_tracts:
            tract = water_tract.Tract
            total_pipe = water_tract.TotalPipe
            total_repairs = water_tract.TotalNumRepairs
            total_days = water_tract.TotalDysRepairs
            econ_loss = water_tract.EconLoss
            cost = water_tract.Cost

            query = '[Tract] = ' + '\'' + tract + '\''
            fields = ['TotalPipe', 'TotalNumRepairs', 'TotalDysRepairs', 'EconLoss', 'Cost']
            with arcpy.da.UpdateCursor(fc, fields, query) as urows:
                for urow in urows:
                    urow[0] = total_pipe
                    urow[1] = total_repairs
                    urow[2] = total_days
                    urow[3] = econ_loss
                    urow[4] = cost
                    urows.updateRow(urow)

        self.update_fc(fc, 'TotalDysRepairs')

    def update_fc(self, fc, field):
        """This function updates a feature class that removes all of the records
        from the geodatabase that are not part of the study region.  The fc
        parameter is the feature class to update and the field parameter is the
        field in the feature class that was updated with data from the HAZUS
        database.  Records not part of the study region will have a field value
        of NULL."""
        query = '[' + field + '] IS NULL'
        with arcpy.da.UpdateCursor(fc, '*', query) as urows:
            for urow in urows:
                urows.deleteRow()

# 6.d Join data to census geography as needed

# 6.e For each map, point .lyr templates in map to new data

# 6.f Export maps as PDF and JPEG

# 7. View log files if desired
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
