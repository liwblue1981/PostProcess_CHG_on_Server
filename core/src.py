# coding=utf-8
from abaqus import *
from abaqusConstants import *
from viewerModules import *
from odbAccess import *
from odbMaterial import *
from odbSection import *
import visualization
import displayGroupOdbToolset as dgo

import json
import os
from db import model
from conf import setting
from lib import common


def unicode_convert(input_data):
    if isinstance(input_data, dict):
        return {unicode_convert(key): unicode_convert(value) for key, value in input_data.iteritems()}
    elif isinstance(input_data, list):
        return [unicode_convert(element) for element in input_data]
    elif isinstance(input_data, unicode):
        return input_data.encode('utf-8')
    else:
        return input_data


def abaqus_process(json_file):
    setting.environment_key['VIEW_NAME'] = 'Viewport: 1'

    with open(json_file, 'rt') as f:
        input_data = json.load(f)

    input_data = unicode_convert(input_data)
    # ODB path read in
    odb_path = input_data['server_path']                                            # "/data/Wei/FEA19-0840/"
    odb_name = input_data['main_input_file']                                        # "FEA19-0840.inp"
    if odb_name.endswith('.inp'):
        odb_name = odb_name[:-4]
    odb_file = os.path.join(odb_path, odb_name) + '.odb'
    temperature_step = input_data['fixed_step']                                     # [15, 20, ..., 55]
    temperature_name = input_data['firing_name_list']                               # ["Cycle_1", ..., "Cycle_9"]
    bolt_node = input_data['bolt_node'].upper()                                     # "PRELOAD_NODES"

    write_to_log = model.RecordLog()
    log_file = os.path.join(odb_path, odb_name + '_postprocess.log')
    with open(log_file, 'wt') as f:
        f.write('')

    section_force_file = log_file.split('.')[0] + '.sforce'

    process_setting = {
        'WEB_REPORT_SET': input_data['report_set'],                                 # ["HB", "FB", ..., "stopper"]
        'WEB_EXCEL_SET': input_data['excel_set'],                                   # ["fb", "flex", "stopper"]
        'WEB_FATIGUE_SET': input_data['fatigue_set'],                               # ["FB", ..., "FLEX"]
        'WEB_ADDELEM_SET': input_data['add_elem_set_name'],                         # ["aa", "bb", "cc"]
        # ["90005376,...,  90005834", "90005456,  ...,  90005790"]                  #
        'WEB_ADDELEM_LIST': input_data['add_elem_set_list'],                        #
        # dict {
        #       "FB":
        #           ["FB-2500W...-2FL", 0.048, 12,
        #               [
        #                   [0.0, 0.1, 0.2, 0.3, 0.4],
        #                   [75.0, 100.0, 125.0, 150.0, 175.0, 200.0, 250.0, 350.0],
        #                   [
        #                       [0.322299987, ..., , 1.0],
        #                       [0.248600006, ..., 0.771099985],
        #                       [0.259600013, ..., 0.686699986],
        #                       [0.3116, ..., 0.41170001],
        #                       [0.300999999,..., 0.414600015],
        #                   ]
        #               ]
        #           ]
        #       }
        'WEB_FATIGUE_DATA': input_data['gasket_section'],                           #
        'FATIGUE_CRITERIA_NAME': setting.environment_key['FATIGUE_CRITERIA_NAME'],   # ['GOODMAN', ... 'SWT']
        'MAX_NODE_NUMBER': 0,
        'MAX_ELEMENT_NUMBER': 0,
        'GASKET_MAX_Z': 0,
        'GASKET_MIN_Z': 0,
        'GASKET_SET': 0,
        'ENGINE_SET': 0,
        'LOG_FILE': log_file,
        'LOG_ARRAY': [],
        'LOG_OBJECT': write_to_log,
        'ODB_FILE': odb_file,
        'INI_ASSEM': input_data['ini_assem'],                                       # 2
        'HOT_ASSEM': input_data['hot_assem'],                                       # 3
        'RELATIVE_MOTION': input_data['relative_motion'],                           # YES
        'TEMPERATURE_STEP': temperature_step,
        'TEMPERATURE_NAME': temperature_name,
        'SECTION_FORCE_FILE': section_force_file,
        'BOLT_NODESET': bolt_node,                                                  # "PRELOAD_NODES"
        'BOLT_FORCE_VALUE': 0,
        'TOTAL_CYLINDER_NAME': input_data['total_cylinder_num'],                    # 4
        'FIRING_CYLINDER_NAME': input_data['firing_cylinder_name'],                 # ["A", "B", "C", "D"]
        'BORE_CENTER_X': input_data['firing_cylinder_x_center'],                    # [0.0, 93.0, 186.0, 279.0]
        'BORE_CENTER_Y': input_data['bore_center_y'],                               # 0.0
        'BORE_CENTER_X_MIN': input_data['firing_cylinder_x_min'],                   # [-93.0, 46.5, 139.5, 232.5]
        'BORE_CENTER_X_MAX': input_data['firing_cylinder_x_max'],                   # [46.5, 139.5, 232.5, 372.0]
        'FILE_SAVE_IN': odb_path,
        'CUSTOMER': input_data['customer'],
        'PROJECT': input_data['project_name'],
        'REQUEST_NO': input_data['request_number'],
        'START_LOG_VALUE': 9,
        'BORE_DISTORTION_STEP': input_data['bore_distortion_step'],                 # "2,4,6"
        'BORE_DISTORTION_RADIUS': input_data['bore_distortion_radius'],             # 50.0
        'BORE_DISTORTION_MANUALLY': input_data['boredistortion_manually'],          # False
        'BORE_DISTORTION_NODESET': input_data['boredistortion_manually_nodeset'],   # None or 'nbore'
        'BORE_DISTORTION_POINTS': input_data['boredistortion_auto_points'],         # 72
        'BORE_DISTORTION_LAYERS': input_data['boredistortion_auto_layers'],         # 20
        'BORE_DISTORTION_ORDER': input_data['bore_distortion_order'],               # 4
        'BORE_DISTORTION_LINER': input_data['boredistortion_auto_linername'],       # None or "v_liner"
        'BORE_DISTORTION_STARTS': input_data['boredistortion_auto_starts'],         # -5.0
        'BORE_DISTORTION_ENDS': input_data['boredistortion_auto_ends'],             # -100.0
        'CAM_DISTORTION_STEP': input_data['cam_distortion_step'],                   # "2,3,5"
        #   ["32647535,  ...,  32652031", "32636220,  ...,  32644689"]              #
        'CAM_DISTORTION_NODE_LIST': input_data['add_cam_node_list'],                #
    }

    try:
        process_setting['BORE_DISTORTION_LINER'] = input_data['boredistortion_auto_linername'].strip().upper()
    except:
        process_setting['BORE_DISTORTION_LINER'] = None

    log_array = process_setting['LOG_ARRAY']
    log_object = process_setting['LOG_OBJECT']

    opened_odb = session.openOdb(name=odb_file)
    log_array.append(['Launch ODB Succeed', 8])
    log_object.add_record(log_array[-1], log_file)
    # 1. Read material, procedure_length = 1, start = 9
    process_setting = common.get_material_data(opened_odb, process_setting, log_array, log_object, log_file, 1,
                                               'MATERIAL')
    # 2. Read Section, procedure_length = 1, start = 10
    process_setting = common.get_material_data(opened_odb, process_setting, log_array, log_object, log_file, 1,
                                               'SECTION')
    # 3. Read element and node data, procedure_length = 45, start = 11
    process_setting = common.read_from_odb(opened_odb, process_setting, log_array, log_object, log_file, 45)
    # 4. Calculate the relative motion, procedure_length = 2, start = 56
    process_setting = common.cal_relative(process_setting, log_array, log_object, log_file, 2)
    # 5. Calculate the fatigue, procedure_length = 4, start = 58
    process_setting = common.cal_fatigue(process_setting, log_array, log_object, log_file, 4)
    # Print pictures, Status record percentage 60 ~ 65
    process_setting = common.plot_thermal_map(opened_odb, process_setting, log_array, log_object, log_file, 5)
    # Read Total force of section. Status record percentage 66~70
    process_setting = common.get_section_force(opened_odb, process_setting, log_array, log_object, log_file, 5)
    # read bolt force, Status record percentage 71
    process_setting = common.get_bolt_force(opened_odb, process_setting, log_array, log_object, log_file, 1)

    opened_odb.close()

    # test use
    elem = process_setting['ELEM_RESULT']
    node = process_setting['NODE_RESULT']
    bore_distortion = process_setting['BORE_DISTORTION_DATA']
    elem_list = [90006423, 90007297, 90005512, 90022176]
    node_list = [90000931, 90001675, 90000720, 90015414, 90010920, 90007031, 90015652]
    try:
        for item in elem_list:
            print (elem[item])
        for item in node_list:
            print (node[item])
        bore_node = process_setting['NEW_BORE_NODE'][0]
        bore_z_level = process_setting['Z_LEVEL_LIST'][0]
        print (bore_distortion[1][bore_z_level])
    except:
        pass

    print (process_setting)
    #insert the bore distortion value for a double check
