from abaqus import *
from abaqusConstants import *
from viewerModules import *
from odbAccess import *
from odbMaterial import *
from odbSection import *
import displayGroupOdbToolset as dgo
import json
import os
import model
import setting


def abaqus_process(json_file):
    setting.enviroment_key['VIEW_NAME'] = 'Viewport: 1'

    with open(json_file, 'rt') as f:
        input_data = json.load(f)

    write_to_log = model.RecordLog()
    print('*'*100)
    print(input_data)
    log_file = os.path.join(input_data['server_path'], input_data['main_input_file'] + '_postprocess.log')
    section_force_file = log_file.split('.')[0] + '.sforce'

    # ODB path read in
    odb_path = input_data['server_path']
    odb_name = input_data['main_input_file']
    odb_file = os.path.join(odb_path, odb_name) + '.odb'
    temperature_step = input_data['fixed_step']
    # temperature_name = input_data['firing_name_list']
    temperature_name = []
    bolt_node = input_data['bolt_node'].upper()

    process_setting = {
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
        'TEMPERATURE_STEP': temperature_step,
        'TEMPERATURE_NAME': temperature_name,
        'TEMPERATURE_ZOOM': 0.9,
        'TEMPERATURE_XPAN': 0.1,
        'TEMPERATURE_ROTATE': -180,
        'SECTION_FORCE_FILE': section_force_file,
        'BOLT_NODESET': bolt_node,
        'BOLT_FORCE_VALUE': 0,
    }

    print(process_setting)

    opened_odb = session.openOdb(name=odb_file)
    # Read element and node data
    process_setting = read_from_odb(input_data, opened_odb, process_setting)
    # Print pictures
    process_setting = plot_thermal_map(opened_odb, process_setting)
    # Read Total force of section
    process_setting = get_section_force(opened_odb, process_setting)
    # read bolt force


    opened_odb.close()

    # bore distortion read in
    bore_distortion_step = input_data['bore_distortion_step']
    bore_distortion_radius = input_data['bore_distortion_radius']
    bore_distortion_manually = input_data['boredistortion_manually']
    bore_distortion_manually_nodeset = input_data['boredistortion_manually_nodeset']
    bore_distortion_auto_points = input_data['boredistortion_auto_points']
    boredistortion_auto_layers = input_data['boredistortion_auto_layers']
    boredistortion_auto_linername = input_data['boredistortion_auto_linername']
    boredistortion_auto_starts = input_data['boredistortion_auto_starts']
    boredistortion_auto_ends = input_data['boredistortion_auto_ends']

    # cam journal distortion read in
    cam_distortion_step = input_data['cam_distortion_step']
    add_cam_node_list = input_data['add_cam_node_list']

    ini_assem = input_data['ini_assem']
    hot_assem = input_data['hot_assem']

    print (process_setting)
