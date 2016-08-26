# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
# Name:        Find Topology Errors                                           #
# Purpose:     Generates a table of stream network topology errors.           #
#                                                                             #
# Author:      Jesse Langdon (jesse@southforkresearch.org)                    #
#              South Fork Research, Inc.                                      #
#              Seattle, Washington                                            #
#                                                                             #
# Created:     2016-Aug-19                                                    #
# Version:     0.1                                                            #
# Modified:                                                                   #
#                                                                             #
# Copyright:   (c) Jesse Langdon 2016                                         #
#                                                                             #
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
#!/usr/bin/env python

# Import arcpy module
import itertools
from itertools import *
import arcpy
import gis_tools

# Set environmental variables
arcpy.env.overwriteOutput = True

#Error Codes
# 0 - no errors
# 1 - dangle
# 2 - potential braid
# 3 - duplicate
# 4 - overlap
# 5 - crossed
# 6 - disconnected
# 7 - flipped flow direction


# Find dangle errors
def dangles(in_network_fc, tmp_network_tbl, max_len):
    arcpy.AddMessage("...dangles")
    in_network_fc_lyr = "in_network_fc_lyr"
    arcpy.MakeFeatureLayer_management(in_network_fc, in_network_fc_lyr)

    # Set global variables
    ERROR_CODE = 1

    # Plot dangles
    dangle_pnt = gis_tools.newGISDataset("in_memory", "dangle_pnt")
    arcpy.FeatureVerticesToPoints_management(in_network_fc_lyr, dangle_pnt, "DANGLE")

    # Select reaches that intersect dangles, also < 30 meter in length
    arcpy.SelectLayerByLocation_management(in_network_fc_lyr, "INTERSECT", dangle_pnt)
    length_field = arcpy.Describe(in_network_fc_lyr).LengthFieldName
    expr = """"{0}"<{1}""".format(length_field, 30)
    arcpy.SelectLayerByAttribute_management(in_network_fc_lyr, "SUBSET_SELECTION", expr)
    arcpy.FeatureClassToFeatureClass_conversion(in_network_fc_lyr, "in_memory", "dangles")
    arcpy.MakeFeatureLayer_management(r"in_memory\dangles", "dangles_lyr")
    arcpy.SelectLayerByAttribute_management(in_network_fc_lyr, "REMOVE_FROM_SELECTION")

    # Add error values to network table
    arcpy.AddJoin_management(tmp_network_tbl, "ReachID", "dangles_lyr", "ReachID", "KEEP_COMMON")
    arcpy.CalculateField_management(tmp_network_tbl, "ERROR_CODE", ERROR_CODE, "PYTHON_9.3")
    arcpy.RemoveJoin_management(tmp_network_tbl)

    # Clean up
    arcpy.Delete_management("dangles_lyr")
    arcpy.Delete_management(in_network_fc_lyr)
    del dangle_pnt

    return


# Find braided reach errors
def braids(in_network_fc, tmp_network_tbl):
    arcpy.AddMessage("...braids")
    in_network_fc_lyr = "in_network_fc_lyr"
    arcpy.MakeFeatureLayer_management(in_network_fc, in_network_fc_lyr)

    # Set global variables
    ERROR_CODE = 2

    # Create temporary in_memory version of input stream network
    tmp_network_fc = r"in_memory\tmp_network_fc"
    arcpy.FeatureClassToFeatureClass_conversion(in_network_fc_lyr, "in_memory", "tmp_network_fc")
    #arcpy.FeatureClassToFeatureClass_conversion("in_network_fc_lyr", "C:\JL\Testing\GNAT\BuildNetworkTopology\YF.gdb", "tmp_network_fc")

    # Clear temp data
    if arcpy.Exists("in_memory//DonutPolygons"):
        arcpy.Delete_management("in_memory//DonutPolygons")
    if arcpy.Exists("lyrDonuts"):
        arcpy.Delete_management("lyrDonuts")
    if arcpy.Exists("lyrBraidedReaches"):
        arcpy.Delete_management("lyrBraidedReaches")

    # Find donut reaches
    arcpy.FeatureToPolygon_management(tmp_network_fc, "in_memory/DonutPolygons")
    arcpy.MakeFeatureLayer_management(tmp_network_fc, "lyrBraidedReaches")
    arcpy.MakeFeatureLayer_management("in_memory/DonutPolygons", "lyrDonuts")
    arcpy.SelectLayerByLocation_management("lyrBraidedReaches", "SHARE_A_LINE_SEGMENT_WITH", "lyrDonuts", '',
                                           "NEW_SELECTION")
    arcpy.FeatureClassToFeatureClass_conversion("lyrBraidedReaches", "in_memory", "braids")
    arcpy.MakeFeatureLayer_management(r"in_memory\braids", "braids_lyr")

    # Add error values to network table
    arcpy.AddJoin_management(tmp_network_tbl, "ReachID", "braids_lyr", "ReachID", "KEEP_COMMON")
    arcpy.CalculateField_management(tmp_network_tbl, "ERROR_CODE", ERROR_CODE, "PYTHON_9.3")
    arcpy.RemoveJoin_management(tmp_network_tbl)

    # Clean up
    arcpy.Delete_management("braids_lyr")
    arcpy.Delete_management(tmp_network_fc)

    return


# Find duplicate reaches
def duplicates(in_network_fc, tmp_network_tbl):
    arcpy.AddMessage("...duplicate reaches")
    in_network_fc_lyr = "in_network_fc_lyr"
    arcpy.MakeFeatureLayer_management(in_network_fc, in_network_fc_lyr)

    # Set global variables
    ERROR_CODE = 3

    # Create temporary in_memory version of in_network_fc
    tmp_network_fc = r"in_memory\tmp_network_fc"
    arcpy.FeatureClassToFeatureClass_conversion(in_network_fc_lyr, "in_memory", "tmp_network_fc")
    arcpy.AddField_management(tmp_network_fc, "IsDuplicate", "SHORT")
    arcpy.AddField_management(tmp_network_fc, "Reach_Length", "DOUBLE")
    arcpy.MakeFeatureLayer_management(tmp_network_fc, "tmp_network_fc_lyr")
    arcpy.CalculateField_management("tmp_network_fc_lyr", "Reach_Length", "!shape.length@meters!", "PYTHON_9.3" )

    # Find identical reaches based on length field
    with arcpy.da.SearchCursor("tmp_network_fc_lyr", ["Reach_Length"]) as length_cursor:
        lengths = [r[0] for r in length_cursor]
    with arcpy.da.UpdateCursor("tmp_network_fc_lyr", ["Reach_Length", "IsDuplicate"]) as cursor:
        for row in cursor:
            if lengths.count(row[0]) > 1:
                row[1] = 1
            else:                row[1] = 0
            cursor.updateRow(row)

    # Select duplicate records
    expr = """"{0}" = {1}""".format("IsDuplicate", 1)
    arcpy.SelectLayerByAttribute_management("tmp_network_fc_lyr","NEW_SELECTION", expr)
    arcpy.FeatureClassToFeatureClass_conversion("tmp_network_fc_lyr", "in_memory", "duplicates_only")
    arcpy.MakeFeatureLayer_management("in_memory\\duplicates_only", "duplicates_only_lyr")

    # Add error values to network table
    arcpy.AddJoin_management(tmp_network_tbl, "ReachID", "duplicates_only_lyr", "ReachID", "KEEP_COMMON")
    arcpy.CalculateField_management(tmp_network_tbl, "ERROR_CODE", ERROR_CODE, "PYTHON_9.3")
    arcpy.RemoveJoin_management(tmp_network_tbl)

    # Clean up
    arcpy.Delete_management(tmp_network_fc)
    arcpy.Delete_management("tmp_network_fc_lyr")
    arcpy.Delete_management("in_memory\\duplicates_only")
    arcpy.Delete_management("duplicates_only_lyr")

    return


## Find overlapped or crossed segments
def reach_pair_errors(in_network_fc, tmp_network_tbl, reach_id):
    arcpy.AddMessage("...overlap/crossing errors")
    in_network_fc_lyr = "in_network_fc_lyr"
    arcpy.MakeFeatureLayer_management(in_network_fc, in_network_fc_lyr)

    # Create a list with reach ID and associated upstream ID
    field_name_list = ['ReachID', 'UpstreamID', 'ERROR_CODE']
    with arcpy.da.SearchCursor(tmp_network_tbl, field_name_list) as scursor:
        for srow in scursor:
            reach_pair = [srow[0], srow[1]]

            # Select reach and its upstream buddy
            expr = """"{0}" = {1} or "{0}" = {2}""".format("ReachID", reach_pair[0], reach_pair[1])
            arcpy.SelectLayerByAttribute_management(in_network_fc_lyr, "NEW_SELECTION", expr)
            arcpy.CopyFeatures_management(in_network_fc_lyr, r"in_memory\sel_rch")
            arcpy.MakeFeatureLayer_management(r"in_memory\sel_rch", "sel_rch_lyr")
            #arcpy.FeatureClassToFeatureClass_conversion("sel_rch_lyr", r"C:\JL\Testing\GNAT\BuildNetworkTopology\YF.gdb", "sel_rch")

            # Send temporary reach feature class to error functions
            result_cross = cross("sel_rch_lyr")
            result_overlap = overlap("sel_rch_lyr")
            result_connect = connected("sel_rch_lyr")

            # Update record in network table
            if result_overlap != 0:
                with arcpy.da.UpdateCursor(tmp_network_tbl, ["ReachID", "ERROR_CODE"], expr) as ucursor:
                    for urow in ucursor:
                        if urow[1] == 0:
                            urow[1] = result_overlap
                            ucursor.updateRow(urow)
            elif result_cross != 0:
                with arcpy.da.UpdateCursor(tmp_network_tbl, ["ReachID", "ERROR_CODE"], expr) as ucursor:
                    for urow in ucursor:
                        if urow[1] == 0:
                            urow[1] = result_cross
                            ucursor.updateRow(urow)
            elif result_connect != 0:
                with arcpy.da.UpdateCursor(tmp_network_tbl, ["ReachID", "ERROR_CODE"], expr) as ucursor:
                    for urow in ucursor:
                        if urow[1] == 0:
                            urow[1] = result_connect
                            ucursor.updateRow(urow)
            else:
                with arcpy.da.UpdateCursor(tmp_network_tbl, ["ReachID", "ERROR_CODE"], expr) as ucursor:
                    for urow in ucursor:
                        if urow[1] != 0:
                            pass
                        else:
                            urow[1] = 0
                            ucursor.updateRow(urow)

            # Clean up
            del urow, ucursor
            arcpy.Delete_management("sel_rch_lyr")
            arcpy.Delete_management("in_memory\sel_rch")

    return


def overlap(tmp_network_fc):
    # Set global constant
    ERROR_CODE = 4

    with arcpy.da.SearchCursor(tmp_network_fc, ['ReachID', 'SHAPE@']) as cursor:
        for r1,r2 in itertools.combinations(cursor, 2):
            if r1[1].overlaps(r2[1]):
                return ERROR_CODE
            else:
                return 0


def cross(tmp_network_fc):
    # Set global constant
    ERROR_CODE = 5

    with arcpy.da.SearchCursor(tmp_network_fc, ['ReachID', 'SHAPE@']) as cursor:
        for r1,r2 in itertools.combinations(cursor, 2):
            if r1[1].crosses(r2[1]):
                return ERROR_CODE
            else:
                return 0

def connected(tmp_network_fc):
    #Set global constant
    ERROR_CODE = 6

    with arcpy.da.SearchCursor(tmp_network_fc, ['ReachID', 'SHAPE@']) as cursor:
        for r1,r2 in itertools.combinations(cursor, 2):
            if r1[1].disjoint(r2[1]):
                return ERROR_CODE
            else:
                return 0

## Find flow direction errors
def flow_direction(tmp_network_tbl):
    arcpy.AddMessage("... flow direction")

    ERROR_CODE = 7

    upstream_field_list = ["UpstreamID", "FROM_NODE", "TO_NODE"]
    val_dict = {r[0]:(r[1:]) for r in arcpy.da.SearchCursor(tmp_network_tbl, upstream_field_list)}
    reach_field_list = ["ReachID", "FROM_NODE", "TO_NODE", "ERROR_CODE"]

    with arcpy.da.UpdateCursor(tmp_network_tbl, reach_field_list) as ucursor:
        for urow in ucursor:
            key_val = urow[0]
            if key_val in val_dict:
                if urow[0] != val_dict[key_val][0]:
                    if (urow[1] == val_dict[key_val][0]):
                        urow[3] = ERROR_CODE
                        ucursor.updateRow(urow)
                    # elif (urow[2] == val_dict[key_val][1]):
                    #     urow[3] = 6
                    #     ucursor.updateRow(urow)
    del val_dict

    return


def main(in_network_fc, in_network_table, outflow_id, max_len):
    arcpy.AddMessage("Searching for errors: ")

    # Get file geodatabase from input stream network feature class
    file_gdb_path = arcpy.Describe(in_network_fc).path

    # Create temporary, in_memory version of stream network table
    if arcpy.Exists("in_network_fc"):
        arcpy.Delete_management("in_network_fc")
    if arcpy.Exists("in_network_table"):
        arcpy.Delete_management("in_network_table")
    if arcpy.Exists("tmp_memory_table"):
        arcpy.Delete_management("tmp_memory_table")
    arcpy.MakeTableView_management(in_network_table, "in_network_table_lyr")
    arcpy.CopyRows_management("in_network_table_lyr", r"in_memory\tmp_network_table")
    arcpy.MakeTableView_management(r"in_memory\tmp_network_table", "tmp_network_table_lyr")
    # add required fields
    list_fields = arcpy.ListFields("tmp_network_table_lyr", "ERROR_CODE")
    if len(list_fields) != 1:
        arcpy.AddField_management("tmp_network_table_lyr", "ERROR_CODE", "LONG")
        arcpy.CalculateField_management("tmp_network_table_lyr", "ERROR_CODE", "0", "PYTHON_9.3")

    # Find errors
    dangles(in_network_fc, "tmp_network_table_lyr", max_len)
    braids(in_network_fc, "tmp_network_table_lyr")
    duplicates(in_network_fc, "tmp_network_table_lyr")
    reach_pair_errors(in_network_fc, "tmp_network_table_lyr", outflow_id)
    flow_direction("tmp_network_table_lyr")

    # Clean up and write final error table
    oid_field = arcpy.Describe("tmp_network_table_lyr").OIDFieldName
    keep_fields = [oid_field, "ReachID", "ERROR_CODE"]
    list_obj = arcpy.ListFields("tmp_network_table_lyr")
    tmp_field_names = [f.name for f in list_obj]
    for field_name in tmp_field_names:
        if field_name not in keep_fields:
            arcpy.DeleteField_management("tmp_network_table_lyr", field_name)
    expr = """"{0}" > {1}""".format("ERROR_CODE", "0")
    arcpy.SelectLayerByAttribute_management("tmp_network_table_lyr", "NEW_SELECTION", expr)
    arcpy.CopyRows_management("tmp_network_table_lyr", file_gdb_path + "\NetworkErrors")

# FOR TESTING
# if __name__ == "__main__":
#     in_network_fc= r"C:\JL\Testing\GNAT\BuildNetworkTopology\YF.gdb\StreamNetwork"
#     in_network_tbl = r"C:\JL\Testing\GNAT\BuildNetworkTopology\YF.gdb\StreamNetworkTable"
#     outflow_id = 1135
#     max_len = 30
#
#     main(in_network_fc, in_network_tbl, outflow_id, max_len)