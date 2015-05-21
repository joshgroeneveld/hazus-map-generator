# The purpose of this script is to create a set of maps from a HAZUS run
# based on user input.  The user selects one or more maps to create and
# the script takes maps from a template directory and copies them into
# a new project.  For each map, the script generates a PDF and JPEG output.

# Author: Josh Groeneveld
# Created On: 05.21.2015
# Updated On: 05.21.2015
# Copyright: 2015

"""NOTES: This script must be able to access the SQL Server instance that
HAZUS uses to store all of the analysis outputs.
"""

# pseudo-code

# 1. Initialize wxpython window

# 2. Select HAZUS SQL Server instance

# 3. Select HAZUS study region (SQL Server database)

# 4. Choose map or maps from list of templates and add to list of maps to create

# 5. Select output directory

# 6. Run the script
# 6a. Create the directory structure in output directory

# 6.b Extract data from SQL Server

# 6.c Create table queries to get only the data we need (can probably be combined with 6.b

# 6.d Join data to census geography as needed

# 6.e For each map, point .lyr templates in map to new data

# 6.f Export maps as PDF and JPEG

# 7. View log files if desired