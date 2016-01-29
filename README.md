# hazus-map-generator

The HAZUS Map Generator creates a series of up to nine maps to show results from
a HAZUS earthquake analysis.  [HAZUS](https://www.fema.gov/hazus-software) is a
GIS-based disaster loss estimation software from the [Federal Emergency Management
Agency](http://www.fema.gov).  HAZUS can estimate losses from earthquakes, floods
and hurricanes.

This tool is a simple app made with [wxPython](http://www.wxpython.org/) to automate the creation of a standard
set of maps based on [this](https://data.femadata.com/MOTF/SOPs/Standard%20Operating%20Procedure%20for%20the%20Creation%20of%20Earthquake%20Scenario%20Priority%20Maps.pdf) SOP.  The SOP lists twelve different
maps, but the HAZUS Map Generator only creates those maps based on data from the
HAZUS output.

![HAZUS Map Generator](/images/main_window.png)

### Status

This tool has only been tested against HAZUS 2.2 SP1, ArcGIS 10.2.2
and Windows 7.  One of the goals in the near future is to update this tool to work
with the newly released HAZUS 3.0.

### Dependencies
You will need the following Python modules for this tool to run properly:
* [wx](http://www.wxpython.org/) (3.0.3)
* arcpy (Distributed with each [ArcGIS](http://www.esri.com/software/arcgis/arcgis-for-desktop) installation)
* [pyodbc](http://mkleehammer.github.io/pyodbc/) (3.0.7)
* [pythonnet](https://github.com/pythonnet/pythonnet) (2.0.0)
* os
* sys
* inspect
* shutil
* traceback
* logging

### Getting Started
This tool assumes that you already have a HAZUS study region and that you've already
completed the HAZUS analysis.  This tool is only designed to automate the creation of
maps following the analysis -- it can't run the analysis automatically.

Once you have all of the dependencies loaded, download a copy of the repo to your machine.
The repo includes a set of template maps and layer files that you can use or modify to fit your needs.

The script uses pyodbc to establish a connection to the HAZUS database -- a SQL Server
instance that usually ends in ..//HAZUSPLUSSRVR.  The HAZUS database can be on your local
machine, or another machine on your network as long as the computer running the script can
access the remote machine.

The script goes through each of the selected maps and executes a SQL query against the HAZUS database to return the information needed for the map.  It then uses an arcpy UpdateCursor to populate the relevant data layers with the information from the SQL query.

Using the arcpy.mapping module, the script zooms to the extent of the study region and then exports the map as both a JPEG and PDF.

#### To Do

* Update to work with HAZUS 3.0
* Make the logger information more useful
* Connect the Reset button with a function that resets the selections and drop-downs before running the script
