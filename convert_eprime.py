# -*- coding: utf-8 -*-
"""
Created on Mon May  5 12:32:17 2014
Three functions for converting data generated by E-Prime experiment to more
useable csv format.
1.  etext_to_rcsv: Converts exported "E-Prime text" file to reduced csv based
    on desired column headers. Make sure, when exporting the edat file as
    "E-Prime text", that Unicode is turned off.
2.  text_to_csv: Converts text file produced by successful completion of
    E-Prime experiment to csv. Output from text_to_csv can be used to deduce
    information necessary for text_to_rcsv (e.g. columns to merge, columns to
    rename, etc.). These variables would then be saved in the headers.pickle
    file.
3.  text_to_rcsv: Converts text file produced by successful completion of
    E-Prime experiment to reduced csv, using information from the variables
    contained in headers.pickle. Considerably more complex than text_to_csv,
    but if used properly the output should be indistinguishable from the output
    of etext_to_rcsv, only without the tedious step of exporting the
    "E-Prime text" file by hand.

command line usage: python convert_eprime.py [function_name] [inputs]
@author: tsalo
"""
import os
import pickle
import inspect
import csv
import numpy.core.fromnumeric as fn
import sys

# Read global variables from pickle file.
code_dir = os.path.dirname(os.path.abspath(inspect.stack()[0][1]))
with open(code_dir + "/headers.pickle") as file_:
    [headers, remnulls, replace_dict, fill_block, merge_cols, merge_col_names,
     null_cols] = pickle.load(file_)


def etext_to_rcsv(in_file, task):
    """
    Converts exported "E-Prime text" file to reduced csv.
    """
    header_list = headers.get(task)
    delimiter_, rem_lines = _det_file_type(in_file)
    try:
        with open(in_file, "rb") as fo:
            wholefile = list(csv.reader(fo, delimiter=delimiter_))
        header_index = []
    except IOError:
        print("Can't open input file- {0}".format(in_file))

    # Remove first three rows.
    for i_row in range(rem_lines):
        wholefile.pop(0)

    # Create list of columns with relevant headers.
    header_index = [_try_index(wholefile[0], hed) for hed in header_list if
                    _try_index(wholefile[0], hed) is not None]

    # Make empty (zeros) list of lists and fill with relevant data from
    # wholefile.
    out_arr = [[wholefile[i_row][col] for col in header_index]
               for i_row in range(fn.size(wholefile, 0))]

    # Either remove all instances of NULL or convert all instances of NULL to
    # NaN.
    if remnulls.get(task):
        null_index = [list(set([iRow for col in out_arr[iRow] if col == "NULL"]))
                      for iRow in range(fn.size(out_arr, 0))]
        null_index = sorted([val for sublist in null_index for val in sublist],
                             reverse=True)
        [out_arr.pop(i) for i in null_index]
    else:
        out_arr = [[word.replace("NULL", "NaN") for word in row]
                   for row in out_arr]

    # Write out and save csv file.
    out_file = in_file[:len(in_file)-3] + "csv"
    try:
        fo = open(out_file, "wb")
        file_ = csv.writer(fo)
        for row in out_arr:
            file_.writerow(row)

        print("Output file successfully created- {0}".format(out_file))
    except IOError:
        print("Can't open output file- {0}".format(out_file))
    finally:
        fo.close()


def text_to_csv(text_file, out_file):
    """
    Converts text file produced by successful completion of E-Prime experiment
    to csv. Output from text_to_csv can be used to deduce information necessary
    for text_to_rcsv (e.g. columns to merge, columns to rename, etc.)
    """
    
    # Load the text file as a list.
    with open(text_file, "r") as fo:
        text_data = list(fo)
    
    # Remove unicode characters.
    filtered_data = [_strip(row) for row in text_data]
    
    # Determine where rows begin and end.
    start_index = [i_row for i_row, row in enumerate(filtered_data)
                   if row == "*** LogFrame Start ***"]
    end_index = [i_row for i_row, row in enumerate(filtered_data)
                 if row == "*** LogFrame End ***"]
    if (len(start_index) != len(end_index) or start_index[0] >= end_index[0]):
        raise ValueError("LogFrame Starts and Ends do not match up.")
    
    # Find column headers and remove duplicates.
    all_headers = []
    data_by_rows = []
    
    for i_row in range(len(start_index)):
        one_row = filtered_data[start_index[i_row]+1:end_index[i_row]]
        data_by_rows.append(one_row)
        for j_col in range(len(one_row)):
            split_header_idx = one_row[j_col].index(": ")
            all_headers.append(one_row[j_col][:split_header_idx])
    
    unique_headers = list(set(all_headers))
    
    # Preallocate list of lists composed of NULLs.
    null_col = ["NULL"] * (len(start_index)+1)
    data_matrix = [null_col[:] for i_col in range(len(unique_headers))]
    
    # Fill list of lists with relevant data from data_by_rows and
    # unique_headers.
    for i_col in range(len(unique_headers)):
        data_matrix[i_col][0] = unique_headers[i_col]
    
    for i_row in range(len(start_index)):
        for j_col in range(len(data_by_rows[i_row])):
            split_header_idx = data_by_rows[i_row][j_col].index(": ")
            for k_header in range(len(unique_headers)):
                if (data_by_rows[i_row][j_col][:split_header_idx] ==
                        unique_headers[k_header]):
                    data_matrix[k_header][i_row + 1] = (data_by_rows[i_row]
                                                        [j_col]
                                                        [split_header_idx+2:])
    
    # If a column is all NULLs except for the header and one value at the
    # bottom, fill the column up with that bottom value.
    for i_col, col in enumerate(data_matrix):
        rows_w_vals = [j_cell for j_cell, cell in enumerate(col) if
                       cell != "NULL"]
        # If the column is full of NULLs (except for the last row and the header), len(row_w_vals) = 2
        if len(rows_w_vals) == 2 and (rows_w_vals[1] == len(col) - 1):
            data_matrix[i_col][1:len(col)] = ([col[rows_w_vals[1]]] * (len(col) - 1))
    
        data_matrix[i_col] = col[:len(col) - 2]
    
    # Transpose data_matrix.
    out_matrix = _transpose(data_matrix)
    
    try:
        fo = open(out_file, 'wb')
        file_ = csv.writer(fo)
        for row in out_matrix:
            file_.writerow(row)
    
        print("Output file successfully created- {0}".format(out_file))
    except IOError:
        print("Can't open output file- {0}".format(out_file))
    finally:
        fo.close()
    
    print("Saved " + out_file)


def text_to_rcsv(text_file, edat_file, out_file, task):
    """
    Converts text file produced by successful completion of E-Prime experiment
    to reduced csv. Considerably more complex than text_to_csv.
    """

    [_, edat_suffix] = os.path.splitext(edat_file)
    header_list = headers.get(task)
    replacements = replace_dict.get(task).get(edat_suffix)

    # Load the text file as a list.
    with open(text_file, "r") as fo:
        text_data = list(fo)

    # Remove unicode characters.
    filtered_data = [_strip(row) for row in text_data]

    # Determine where rows begin and end.
    start_index = [i_row for i_row, row in enumerate(filtered_data)
                   if row == "*** LogFrame Start ***"]
    end_index = [i_row for i_row, row in enumerate(filtered_data)
                 if row == "*** LogFrame End ***"]
    if (len(start_index) != len(end_index) or start_index[0] >= end_index[0]):
        raise ValueError("LogFrame Starts and Ends do not match up.")

    # Find column headers and remove duplicates.
    all_headers = []
    data_by_rows = []

    for i_row in range(len(start_index)):
        one_row = filtered_data[start_index[i_row]+1:end_index[i_row]]
        data_by_rows.append(one_row)
        for j_col in range(len(one_row)):
            split_header_idx = one_row[j_col].index(": ")
            all_headers.append(one_row[j_col][:split_header_idx])

    unique_headers = list(set(all_headers))

    # Preallocate list of lists composed of NULLs.
    null_col = ["NULL"] * (len(start_index)+1)
    data_matrix = [null_col[:] for i_col in range(len(unique_headers))]

    # Fill list of lists with relevant data from data_by_rows and
    # unique_headers.
    for i_col in range(len(unique_headers)):
        data_matrix[i_col][0] = unique_headers[i_col]

    for i_row in range(len(start_index)):
        for j_col in range(len(data_by_rows[i_row])):
            split_header_idx = data_by_rows[i_row][j_col].index(": ")
            for k_header in range(len(unique_headers)):
                if (data_by_rows[i_row][j_col][:split_header_idx] ==
                        unique_headers[k_header]):
                    data_matrix[k_header][i_row + 1] = (data_by_rows[i_row]
                                                        [j_col]
                                                        [split_header_idx+2:])

    # If a column is all NULLs except for the header and one value at the
    # bottom, fill the column up with that bottom value.
    # THIS SECTION NEEDS CLEANUP!
    for i_col, col in enumerate(data_matrix):
        rows_w_vals = [j_cell for j_cell, cell in enumerate(col) if
                       cell != "NULL"]
        if len(rows_w_vals) == 2 and (rows_w_vals[1] == len(col) - 1 or rows_w_vals[1] == len(col) - 2):
            data_matrix[i_col][1:len(col)] = ([col[rows_w_vals[1]]] * (len(col) - 1))
        elif any([header in col[0] for header in fill_block]):
            for null_row in range(1, len(rows_w_vals)):
                first = rows_w_vals[null_row - 1] + 1
                last = rows_w_vals[null_row]
                n_rows_to_fill = len(range(rows_w_vals[null_row - 1] + 1, rows_w_vals[null_row]))
                data_matrix[i_col][first:last] = (col[rows_w_vals[null_row]] * n_rows_to_fill)

        data_matrix[i_col] = col[:len(col) - 2]

    # Transpose data_matrix.
    t_data_matrix = _transpose(data_matrix)

    # Replace text headers with edat headers (replacement dict). Unnecessary if
    # your processing scripts are built around text files instead of edat
    # files.
    t_data_matrix[0] = [replacements.get(item, item) for item in
                        t_data_matrix[0]]

    # Pare data_matrix down based on desired headers
    # Create list of columns with relevant headers.
    header_index = [t_data_matrix[0].index(header) for header in header_list]

    # Merge any columns that need to be merged.
    columns_to_merge = merge_cols.get(task)
    merge_col_names_list = merge_col_names.get(task)
    merged_data = []
    for i_merge in range(len(merge_col_names_list)):
        merge_col_nums = [t_data_matrix[0].index(hed) for hed in
                          columns_to_merge[i_merge]]
        data_to_merge = [data_matrix[col] for col in merge_col_nums]
        merged_data.append(_merge_lists(data_to_merge, "all_else"))
        merged_data[i_merge][0] = merge_col_names_list[i_merge]

    out_matrix = [[t_data_matrix[i_row][col] for col in header_index]
                  for i_row in range(fn.size(t_data_matrix, 0))]

    # Transpose merged_data and append them to out_matrix.
    if len(merged_data) != 0:
        t_merged_data = _transpose(merged_data)
        for i_row in range(len(out_matrix)):
            out_matrix[i_row] = out_matrix[i_row] + t_merged_data[i_row]

    # Create column from which null index will be created.
    # Remove all instances of NULL by creating an index of NULL occurrences
    # and removing them from out_matrix.
    null_column_names = null_cols.get(task)
    null_column_index = [header_index[header_list.index(column)] for column in
                         null_column_names]
    nulls_to_merge = [data_matrix[col_num] for col_num in null_column_index]
    merged_nulls_list = _merge_lists(nulls_to_merge, "all_null")
    null_index = sorted([i_row for i_row in range(len(merged_nulls_list)) if
                         merged_nulls_list[i_row] == "NULL"], reverse=True)
    [out_matrix.pop(null_row) for null_row in null_index]

    try:
        fo = open(out_file, 'wb')
        file_ = csv.writer(fo)
        for row in out_matrix:
            file_.writerow(row)

        print("Output file successfully created- {0}".format(out_file))
    except IOError:
        print("Can't open output file- {0}".format(out_file))
    finally:
        fo.close()

    print("Saved " + out_file)


def _det_file_type(in_file):
    """
    Determines number of lines to remove and file delimiter from filetype.
    """
    [fn, sf] = os.path.splitext(in_file)
    if sf == ".csv":
        delimiter_ = ","
        rem_lines = 0
    elif sf == ".txt":
        delimiter_ = "\t"
        rem_lines = 3
    elif len(in_file) == 0:
        raise ValueError("Input file name is empty.")
    else:
        raise ValueError("Input file name is not .csv or .txt.")

    return delimiter_, rem_lines


def _merge_lists(lists, option):
    """
    Merges multiple lists into one list, with the default being the values of
    the first list. It either replaces values with NULL if NULL is in that
    position in another list or replaces NULL with values if values are in that
    position in another list.
    """
    if type(lists[0]) != list:
        return lists
    else:
        merged = lists[0]
        for i_col in range(len(lists)):
            if option == "all_null":
                merged = [lists[i_col][i_row] if lists[i_col][i_row] == "NULL"
                          else merged[i_row] for i_row in range(len(merged))]
            elif option == "all_else":
                merged = [lists[i_col][i_row] if lists[i_col][i_row] != "NULL"
                          else merged[i_row] for i_row in range(len(merged))]
        return merged


def _strip(string):
    """
    Removes unicode characters in string.
    """
    return "".join([val for val in string if 31 < ord(val) < 127])


def _transpose(list_):
    """
    Transposes a list of lists.
    """
    transposed_ = [[row[col] for row in list_] for col in range(len(list_[0]))]
    transposed = [col for col in transposed_ if col]
    return transposed


def _try_index(list_, val):
    """
    Indexes a list without throwing an error if the value isn't found.
    """
    try:
        return list_.index(val)
    except:
        print(val)
        pass


if __name__ == "__main__":
    """
    If called from the command line, the desired function should be the first
    argument.
    """
    function_name = sys.argv[1]
    module_functions = [name for name, obj in inspect.getmembers(sys.modules[__name__])
                        if (inspect.isfunction(obj) and not name.startswith('_'))]
    
    if function_name not in module_functions:
        raise IOError("Function {0} not in convert_eprime.".format(function_name))
    
    function = globals()[function_name]
    n_args = len(inspect.getargspec(function).args)
    
    if n_args != len(sys.argv) - 2:
        raise IOError("Function {0} takes {1} arguments, not {2}.".format(function_name, n_args, len(sys.argv)-2))

    function(*sys.argv[2:])  
