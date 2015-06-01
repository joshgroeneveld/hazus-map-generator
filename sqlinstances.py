# This script calls the Python wrapper for .NET available from: http://pythonnet.sourceforge.net/readme.html

import clr

clr.AddReference("Python.Runtime")
# from System.Data.Sql import *


def list_sql_servers(self):
        server_list = clr.System.Data.Sql.SqlDataSourceEnumerator.Instance.Instance.GetDataSources()
        self.hazus_server_choices = []
        for r in server_list.Rows:
            if str(r.ItemArray[1]) != '':
                self.hazus_server_choices.append(str(r.ItemArray[0]) + "\\" + str(r.ItemArray[1]))
            else:
                self.hazus_server_choices.append(str(r.ItemArray[0]))
        return self.hazus_server_choices