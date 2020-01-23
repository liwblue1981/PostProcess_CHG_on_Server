from abaqus import *
from abaqusConstants import *
from viewerModules import *
from odbAccess import *
from odbMaterial import *
from odbSection import *
import visualization
import displayGroupOdbToolset as dgo
from db import model
from conf import setting
import os
import time
import math


# current_session is the current displayed object in window, will be used for many functions, set as global
def read_distortion_step(distortion_step, read_info, start_value, log_array, log_object, log_file):
    if distortion_step:
        try:
            temp = distortion_step
            distortion_step = []
            for item in temp.split(','):
                distortion_step.append(int(item))
            log_array.append([read_info + ' Distortion Step Read Succeed', start_value])
        except Exception as e:
            log_array.append([read_info + ' Distortion Step Read Failed', start_value])
    else:
        distortion_step = []
    log_object.add_record(log_array[-1], log_file)
    return distortion_step


def bore_distortion_auto(process_setting, log_array, log_object, log_file, bore_distortion_results,
                         bore_distortion_radius, bore_center_x, bore_center_y, total_step_num, procedure_length):
    """

    :param process_setting:             big dict, contained all results, required input
    :param log_array:                   log data, record all the log information as a list
    :param log_object:                  log object, defined as a class
    :param log_file:                    log archived file, for each operation the file will be updated, and read by web,
                                        display as a processing bar.
    :param bore_distortion_results:     bore_distortion dict, stored the list of bore_distortion class, for auto or
                                        manually, both have same data structure
    :param bore_distortion_radius:      defined bore radius, should be exactly as the liner inner radius, but for poor
                                        mesh, it might not be as close to real value as possible. Program will
                                        automatically search the right radius for node interpolation, iteration limit
                                        can be set in setting file, MAX_PATH_ITERATION = 10. If exceed the limit, abaqus
                                        will be terminated. Possible solution is to increase value with 0.1
    :param bore_center_x:               bore center coordinate x, list [0.0, 93.0, 186.0, 279.0]
    :param bore_center_y:               bore center coordinate x, float 0.0
    :param procedure_length:            the whole procedure percentage, display in the processing bar
    :param total_step_num:              total step number
    :return:                            dict, bore_distortion_results
    """
    bore_distortion_auto_points = process_setting['BORE_DISTORTION_POINTS']
    bore_distortion_auto_layers = process_setting['BORE_DISTORTION_LAYERS']
    bore_distortion_auto_liner = process_setting['BORE_DISTORTION_LINER']
    bore_distortion_auto_starts = process_setting['BORE_DISTORTION_STARTS']
    bore_distortion_auto_ends = process_setting['BORE_DISTORTION_ENDS']
    total_cylinder_num = process_setting['TOTAL_CYLINDER_NAME']
    max_node = process_setting['MAX_NODE_NUMBER']
    fourier_order = setting.environment_key['FOURIER_ORDER']
    bore_radius_auto_increment = setting.environment_key['BORE_RADIUS_SEARCH_AUTO_INCREMENT']
    bore_interpolation_succeed = setting.environment_key['BORE_DISTORTION_INTERPOLATION_DONE']
    bore_interpolation_shift_angle = setting.environment_key['BORE_DISTORTION_SHIFT_ANGLE']
    start_record_value = process_setting['START_LOG_VALUE']
    number_interval = float(procedure_length) / total_step_num

    # new created node set, these nodes will be used to create a new surface element to show the bore distortion
    new_bore_set = []
    space = (bore_distortion_auto_ends - bore_distortion_auto_starts) / bore_distortion_auto_layers
    z_coord_list = [bore_distortion_auto_starts + space * i for i in range(bore_distortion_auto_layers + 1)]

    angle_space = 2 * math.pi / bore_distortion_auto_points
    # the node auto_incremental value for new created bore node
    node_step = 1
    for i in range(total_cylinder_num):
        bore_distortion_results[i] = {}
        for j in z_coord_list:
            temp = {}
            for k in range(bore_distortion_auto_points):
                node_num = max_node + node_step
                new_bore_set.append(node_num)
                node_step += 1
                temp[node_num] = [[bore_center_x[i] + bore_distortion_radius * math.cos(angle_space * k),
                                   bore_center_y + bore_distortion_radius * math.sin(angle_space * k), j]]
            bore_distortion_results[i][j] = model.BoreNodeLayer(i, j, temp, bore_center_x[i], bore_center_y,
                                                                bore_distortion_radius, True,
                                                                fourier_order)  # type: model.BoreNodeLayer

    leaf = dgo.LeafFromElementSets(elementSets=('PART-1-1.' + bore_distortion_auto_liner,))
    current_session.odbDisplay.displayGroup.replace(leaf=leaf)

    # search for right radius, all liner should have same radius, so only one cylinder is checked.
    k = 0
    max_path_iteration = setting.environment_key['MAX_PATH_ITERATION']
    current_radius = bore_distortion_radius
    while True:
        three_nodes = ((bore_center_x[0] + current_radius, bore_center_y, z_coord_list[0]),
                       (bore_center_x[0], bore_center_y + current_radius, z_coord_list[0]),
                       (bore_center_x[0] - current_radius, bore_center_y, z_coord_list[0]))
        path_name = 'test_path'
        session.Path(name=path_name, type=CIRCUMFERENTIAL, expression=three_nodes, circleDefinition=POINT_ARC,
                     numSegments=bore_distortion_auto_points, startAngle=0, endAngle=360, radius=CIRCLE_RADIUS)
        pth = session.paths[path_name]
        u1 = xyPlot.XYDataFromPath(path=pth, pathStyle=PATH_POINTS, shape=UNDEFORMED, labelType=SEQ_ID, step=0, frame=1,
                                   includeIntersections=False, variable=(('U', NODAL, ((COMPONENT, 'U1'),)),))
        # bore_interpolation_succeed is an artificial value, it is assumed the interpolation can be done if more than
        # bore_interpolation_succeed values are obtained
        if len(u1) > bore_interpolation_succeed:
            del session.paths[path_name]
            break
        else:
            print ('ITERATION ' + str(k + 1) + ': PATH LENGTH=' + str(len(u1)))
            current_radius += bore_radius_auto_increment
            del session.paths[path_name]
            k += 1
        if k > max_path_iteration:
            error_message = 'PATH CREATE FAILED WITH RADIUS = ' + str(current_radius)
            raise Exception(error_message)

    node_start = 0
    for i in range(total_cylinder_num):
        for j in z_coord_list:
            # search for right start_angle, if the interpolation done for the node is very close to the real node, there
            # will have no value for this location, which means the xy_data will less than expected. Specify a new start
            # angle can avoid the missed value.
            path_name = 'Path_' + str(i + 1) + '_' + str(j)
            three_nodes = ((bore_center_x[i] + current_radius, bore_center_y, j),
                           (bore_center_x[i], bore_center_y + current_radius, j),
                           (bore_center_x[i] - current_radius, bore_center_y, j))
            start_angle = 0
            end_angle = 360
            k = 0
            # different layers might have different mesh, so search the correct start angle for each layer
            while True:
                session.Path(name=path_name, type=CIRCUMFERENTIAL, expression=three_nodes, circleDefinition=POINT_ARC,
                             numSegments=bore_distortion_auto_points, startAngle=start_angle, endAngle=end_angle,
                             radius=CIRCLE_RADIUS)
                pth = session.paths[path_name]
                u1 = xyPlot.XYDataFromPath(path=pth, pathStyle=PATH_POINTS, shape=UNDEFORMED, labelType=SEQ_ID, step=0,
                                           frame=1, includeIntersections=False,
                                           variable=(('U', NODAL, ((COMPONENT, 'U1'),)),))
                if len(u1) < bore_distortion_auto_points:
                    start_angle += bore_interpolation_shift_angle
                    k += 1
                    del session.paths[path_name]
                elif k > max_path_iteration:
                    error_message = 'PATH CREATE FAILED WITH START ANGLE = ' + str(start_angle)
                    raise Exception(error_message)
                else:
                    break
            for step_num in range(total_step_num):
                u1 = xyPlot.XYDataFromPath(path=pth, pathStyle=PATH_POINTS, shape=UNDEFORMED, labelType=SEQ_ID,
                                           step=step_num, frame=1, includeIntersections=False,
                                           variable=(('U', NODAL, ((COMPONENT, 'U1'),)),))
                u2 = xyPlot.XYDataFromPath(path=pth, pathStyle=PATH_POINTS, shape=UNDEFORMED, labelType=SEQ_ID,
                                           step=step_num, frame=1, includeIntersections=False,
                                           variable=(('U', NODAL, ((COMPONENT, 'U2'),)),))
                node_count = 0
                for k in range(bore_distortion_auto_points):
                    node_num = new_bore_set[node_start + node_count]
                    bore_distortion_results[i][j].set_displacement(node_num, [u1[k][1], u2[k][1], 0])
                    node_count += 1
            node_start += node_count
            log_array.append(
                ['Auto Bore Distortion for Cylinder ' + str(i + 1) + ' DEPTH ' + str(j),
                 start_record_value + step_num * number_interval])
            log_object.add_record(log_array[-1], log_file)
    return bore_distortion_results, z_coord_list, new_bore_set


def get_material_data(opened_odb, process_setting, log_array, log_object, log_file, procedure_length, choice):
    """
    Get the material / section information from opened odb
    [Elastic, Plastic, Gasket Thickness behavior, Thermal Expansion, Density] are read --- material.
    ['GASKET', 'SOLID', 'BEAM']
    :param opened_odb:          opened current odb, all data will be read from the odb
    :param process_setting:     big dict, contained all results, required input
    :param log_array:           log data, record all the log information as a list
    :param log_object:          log object, defined as a class
    :param log_file:            log archived file, for each operation the file will be updated, and read by web,
                                display as a processing bar.
    :param procedure_length:    the whole procedure percentage, display in the processing bar.
    :param choice:              'MATERIAL' or 'SECTION', used to select the action.
    :return:                    dict type, new added key --- MATERIAL_DATA --- with material information
    """
    customer = process_setting['CUSTOMER']
    project_name = process_setting['PROJECT']
    fea_no = process_setting['REQUEST_NO']
    result_from_odb = {}
    start_record_value = process_setting['START_LOG_VALUE']
    i = 0
    if choice == 'MATERIAL':
        all_materials = opened_odb.materials
        number_interval = float(procedure_length) / len(all_materials)
        for k, v in all_materials.items():
            name = v.name
            result_from_odb[name] = []
            if hasattr(v, 'elastic'):
                elastic = v.elastic
                if elastic.type == 'ISOTROPIC':
                    result_from_odb[name].append('SOLID')
                    current_material = model.EngineMaterial(name, customer, fea_no, project_name)
                    current_material.set_elastic(elastic.table)
                    if hasattr(v, 'plastic'):
                        plastic = v.plastic
                        current_material.set_plastic(plastic.table)
            if hasattr(v, 'gasketThicknessBehavior'):
                membrane = v.gasketMembraneElastic
                transverse = v.gasketTransverseShearElastic
                behavior = v.gasketThicknessBehavior
                dependencies = behavior.dependencies
                behavior_type = behavior.type
                current_material = model.GasketMaterial(name, customer, fea_no, project_name)
                result_from_odb[name].append('GASKET')
                current_material.set_dependencies(dependencies, membrane, transverse)
                current_material.set_type(behavior_type)
                loading_curve = behavior.table
                current_material.set_loading(loading_curve)
                if hasattr(behavior, 'unloadingTable'):
                    loading_curve = behavior.unloadingTable
                    current_material.set_unloading(loading_curve)
            if hasattr(v, 'density'):
                density = v.density
                current_material.set_density(density.table)
            if hasattr(v, 'expansion'):
                expansion = v.expansion
                current_material.set_thermal_expansion(expansion.table)
            result_from_odb[name].append(current_material)
            log_array.append(['Read Material ' + name, start_record_value + i * number_interval])
            log_object.add_record(log_array[-1], log_file)
            i += 1
        process_setting['MATERIAL_DATA'] = result_from_odb
    elif choice == 'SECTION':
        all_sections = opened_odb.sections
        number_interval = float(procedure_length) / len(all_sections)
        for k, v in all_sections.items():
            name = v.name[8:]
            current_section = model.ChgSection(customer, fea_no, project_name)
            property_list = []
            for item in v.__members__:
                property_list.append([item, getattr(v, item)])
            if isinstance(v, GasketSectionType):
                current_type = 'GASKET'
            elif isinstance(v, HomogeneousSolidSectionType):
                current_type = 'SOLID'
            else:
                current_type = 'BEAM'
            current_section.set_type(current_type, property_list)
            result_from_odb[name] = current_section
            log_array.append(['Read Section ' + name, start_record_value + i * number_interval])
            log_object.add_record(log_array[-1], log_file)
            i += 1
        process_setting['SECTION_DATA'] = result_from_odb
    process_setting['START_LOG_VALUE'] = start_record_value + procedure_length
    return process_setting


def read_from_odb(opened_odb, process_setting, log_array, log_object, log_file, procedure_length):
    """
    read from ODB, output the element, node based on defined format, consider the cost for opening ODB, all the data
    will be obtained once the ODB is launched.
    :param opened_odb:          required opened odb, set as an input parameter dut to some other functions will use
                                this ODB later.
    :param process_setting:     big dict, contained all results, required input
    :param log_array:           log data, record all the log information as a list
    :param log_object:          log object, defined as a class
    :param log_file:            log archived file, for each operation the file will be updated, and read by web,
                                display as a processing bar.
    :param procedure_length:    the whole procedure percentage, display in the processing bar.
    :return:    process_setting,    new added elements or nodes results, will update the log list
                element_result      element result, dict type, key: element number, value: element class
                node_result         node result, dict type, key: node number, value: node class
                log_array           log array, store the operation record
    """
    # gasket element set
    report_set = process_setting['WEB_REPORT_SET']
    excel_set = process_setting['WEB_EXCEL_SET']
    fatigue_set = process_setting['WEB_FATIGUE_SET']
    add_elem_set = process_setting['WEB_ADDELEM_SET']
    add_elem_list = process_setting['WEB_ADDELEM_LIST']

    # other required read information
    bore_max_x = process_setting['BORE_CENTER_X_MAX']
    bore_center_x = process_setting['BORE_CENTER_X']
    bore_center_y = process_setting['BORE_CENTER_Y']

    cache_time = setting.environment_key['CACHE_TIME']

    # use dict type to record element and node result, will be used as returned value
    element_result = {}
    node_result = {}

    gasket_node_set = setting.environment_key['GASKET_ALL_NODES']
    report_set = [elem_set.strip().upper() for elem_set in report_set if elem_set != '']
    excel_set = [elem_set.strip().upper() for elem_set in excel_set if elem_set != '']
    fatigue_set = [elem_set.strip().upper() for elem_set in fatigue_set if elem_set != '']
    add_elem_set = [elem_set.strip().upper() for elem_set in add_elem_set if elem_set != '']
    gasket_elem_set = report_set + excel_set + fatigue_set + add_elem_set
    gasket_elem_set = list(set(gasket_elem_set))
    gasket_elem_set = [elem_set for elem_set in gasket_elem_set if elem_set != '']

    process_setting['GASKET_ELEM_SETS'] = gasket_elem_set
    start_record_value = process_setting['START_LOG_VALUE']

    total_cylinder_num = process_setting['TOTAL_CYLINDER_NAME']
    view_name = setting.environment_key['VIEW_NAME']
    global current_session
    current_session = session.Viewport(name=view_name)
    current_session.makeCurrent()
    current_session.maximize()
    current_session.setValues(displayedObject=opened_odb)
    current_session.viewportAnnotationOptions.setValues(triad=OFF, title=OFF, state=OFF, annotations=ON, compass=OFF)
    current_session.view.setProjection(projection=PARALLEL)
    current_session.odbDisplay.commonOptions.setValues(visibleEdges=NONE)

    # READ BORE DISTORITON INPUT
    bore_distortion_step = process_setting['BORE_DISTORTION_STEP']
    bore_distortion_radius = process_setting['BORE_DISTORTION_RADIUS']
    bore_distortion_manually = process_setting['BORE_DISTORTION_MANUALLY']
    bore_distortion_nodeset = process_setting['BORE_DISTORTION_NODESET']

    bore_unique_center = setting.environment_key['BORE_UNIQUE_CENTER']
    fourier_order = setting.environment_key['FOURIER_ORDER']

    cam_distortion_step = process_setting['CAM_DISTORTION_STEP']
    add_cam_node_list = process_setting['CAM_DISTORTION_NODE_LIST']

    bore_distortion_step = read_distortion_step(bore_distortion_step, 'Bore', start_record_value, log_array, log_object,
                                                log_file)
    cam_distortion_step = read_distortion_step(cam_distortion_step, 'Cam', start_record_value, log_array, log_object,
                                               log_file)

    # Create the new Added Element Set
    if add_elem_set:
        for i, set_name in enumerate(add_elem_set):
            current_list = add_elem_list[i].split(',')
            elem_list = []
            for item in current_list:
                elem_list.append(int(item))
            elem_list = tuple(elem_list)
            try:
                _ = opened_odb.rootAssembly.instances['PART-1-1'].ElementSetFromElementLabels(name=set_name.upper(),
                                                                                              elementLabels=elem_list)
                log_array.append(['Added Element Set ' + set_name + ' Succeed', start_record_value])
                time.sleep(cache_time)
            except Exception as e:
                log_array.append(['Added Element Set ' + set_name + ' Failed', start_record_value])
            log_object.add_record(log_array[-1], log_file)

    # Get the element property
    odb_sections = process_setting['SECTION_DATA']
    section_material = {}
    for item in odb_sections:
        result = odb_sections[item].get_material()
        if result[-1] == 'GASKET':
            section_material[item] = result[1]

    # Get the fatigue data
    fatigue_web_info = process_setting['WEB_FATIGUE_DATA']
    fatigue_criteria_name = process_setting['FATIGUE_CRITERIA_NAME']
    fatigue_data = {}
    for k, v in fatigue_web_info.items():
        material_name = v[0]
        initial_gap = v[1]
        fatigue_id = v[2]
        preload = v[3][0]
        fixload = v[3][1]
        fatigue_value = v[3][2]
        res = model.FatigueData(k, material_name, initial_gap, fatigue_id, fixload, preload, fatigue_criteria_name)
        res.set_fatigue_data(fatigue_value)
        fatigue_data[material_name] = res
    process_setting['FATIGUE_DATA'] = fatigue_data

    all_elem_sets = opened_odb.rootAssembly.instances['PART-1-1'].elementSets
    # Create Element and Node Class dict
    for elem_set in gasket_elem_set:
        elem_in_set = all_elem_sets[elem_set].elements
        if elem_set in section_material:
            material_name = section_material[elem_set]
        else:
            material_name = False
        for item in elem_in_set:
            element_nodes = item.connectivity
            element_number = item.label
            # if the element belongs to different set, it's material is unique
            if material_name:
                element_result[element_number] = model.ChgElements(element_number, list(element_nodes), material_name)
            for node in element_nodes:
                if node not in node_result:
                    node_result[node] = model.ChgNodes(node)

    node_labels = tuple([keys for keys in node_result])
    process_setting['MAX_NODE_NUMBER'] = max(node_labels)
    element_labels = tuple([keys for keys in element_result])
    process_setting['MAX_ELEMENT_NUMBER'] = max(element_labels)

    start_record_value += 1
    log_array.append(['Gasket Element - Node dict Succeed', start_record_value])
    log_object.add_record(log_array[-1], log_file)

    _ = opened_odb.rootAssembly.instances['PART-1-1'].NodeSetFromNodeLabels(name=gasket_node_set,
                                                                            nodeLabels=node_labels)
    start_record_value += 1
    log_array.append(['Added Gasket Node Set Succeed', start_record_value])
    log_object.add_record(log_array[-1], log_file)
    gasket_node_set_obj = opened_odb.rootAssembly.instances['PART-1-1'].nodeSets[gasket_node_set].nodes
    for node in gasket_node_set_obj:
        node_result[node.label].set_init_coord(node.coordinates)

    gasket_z_coord = [node_result[node].get_init_coord()[2] for node in node_result]
    process_setting['GASKET_MAX_Z'] = max(gasket_z_coord)
    process_setting['GASKET_MIN_Z'] = min(gasket_z_coord)
    start_record_value += 1
    log_array.append(['Node Coordinate Read Succeed', start_record_value])
    log_object.add_record(log_array[-1], log_file)

    odb_steps = opened_odb.steps.keys()

    bore_check = False

    if bore_distortion_step:
        # create the bore node set, determine the cylinder order, depth level
        bore_distortion_results = {}
        # used to record the node belongs to which cylinder, and which depth level.
        bore_distortion_node_key = {}
        if bore_distortion_manually:
            if bore_distortion_nodeset:
                bore_space_criteria = setting.environment_key['BORE_DISTORTION_SPACE']
                bore_check = True
                temp_result = {}
                z_coord_list = []
                temp = bore_distortion_nodeset.split(',')
                bore_distortion_nodeset = []
                # Read Bore Node based on user input bore node set
                for item in temp:
                    bore_distortion_nodeset.append(item.strip().upper())
                try:
                    for item in bore_distortion_nodeset:
                        # bore_node exist in model, can be read directly
                        node_region = opened_odb.rootAssembly.instances['PART-1-1'].nodeSets[item]
                        for node in node_region.nodes:
                            temp_result[node.label] = node.coordinates
                            z_coord_list.append(float('%10.1f' % node.coordinates[-1]))
                    log_array.append(['Bore Node Set Read Done', start_record_value])
                except Exception as e:
                    log_array.append(['Bore Node Set Read Failed', start_record_value])
                log_object.add_record(log_array[-1], log_file)
                # Remove duplicated Z depth, accuracy 0.1mm, assign bore node to BoreNodeLayer object according to
                # its cylinder number, Z depth
                z_coord_list = list(set(z_coord_list))
                z_coord_list.sort(reverse=True)
                bore_distortion_list = []
                for i in range(total_cylinder_num):
                    bore_distortion_list.append([])
                    for j in z_coord_list:
                        bore_distortion_list[-1].append([])
                for key, value in temp_result.items():
                    x_coord = value[0]
                    z_coord = value[-1]
                    for i, x_range in enumerate(bore_max_x):
                        if x_coord < x_range:
                            current_cylinder = i
                            break
                    for i, z_level in enumerate(z_coord_list):
                        if (z_coord > z_level - bore_space_criteria) and (z_coord < z_level + bore_space_criteria):
                            bore_distortion_list[current_cylinder][i].append(key)
                # Create BoreNodeLayer Object
                for i, bore_cylinder in enumerate(bore_distortion_list):
                    bore_distortion_results[i] = {}
                    for j, z_level in enumerate(z_coord_list):
                        temp = {}
                        node_list = bore_distortion_list[i][j]
                        for node in node_list:
                            temp[node] = [temp_result[node]]
                            bore_distortion_node_key[node] = [i, z_level]
                        bore_distortion_results[i][z_level] = model.BoreNodeLayer(i, z_level, temp, bore_center_x[i],
                                                                                  bore_center_y, bore_distortion_radius,
                                                                                  bore_unique_center,
                                                                                  fourier_order)  # type: model.BoreNodeLayer
                new_bore_set = []
                for keys in temp_result:
                    new_bore_set.append(keys)
                new_bore_set_name = setting.environment_key['BORE_DISTORTION_NODES']
                try:
                    _ = opened_odb.rootAssembly.instances['PART-1-1'].NodeSetFromNodeLabels(name=new_bore_set_name,
                                                                                            nodeLabels=new_bore_set)
                    time.sleep(cache_time)
                    log_array.append(['Added Bore Node Set ' + new_bore_set_name + ' Succeed', start_record_value])
                except Exception as e:
                    log_array.append(['Added Bore Node Set ' + new_bore_set_name + ' Failed', start_record_value])
                log_object.add_record(log_array[-1], log_file)
            else:
                raise Exception('**===NO BORE NODE SET IS SPECIFIED, CHECK YOUR INPUT PLEASE')
        else:
            bore_check = True
            # bore_distortion_results, z_coord_list, new_bore_set = bore_distortion_auto(process_setting, log_array,
            #                                                                            log_object, log_file,
            #                                                                            bore_distortion_results,
            #                                                                            bore_distortion_radius,
            #                                                                            bore_center_x, bore_center_y,
            #                                                                            len(odb_steps), 5)
            bore_distortion_results, z_coord_list, new_bore_set = bore_distortion_auto(process_setting, log_array,
                                                                                       log_object, log_file,
                                                                                       bore_distortion_results,
                                                                                       42, bore_center_x, bore_center_y,
                                                                                       len(odb_steps), 5)
        process_setting['NEW_BORE_NODE'] = new_bore_set
        process_setting['Z_LEVEL_LIST'] = z_coord_list
    # create the cam node set
    cam_check = False
    if add_cam_node_list and cam_distortion_step:
        cam_check = True
        cam_node_result = {}
        for i, item in enumerate(add_cam_node_list):
            temp_result = {}
            current_list = item.split(',')
            node_list = []
            node_set_name = 'AUTO_ADD_CAM' + str(i + 1)
            for node in current_list:
                node_list.append(int(node))
            try:
                _ = opened_odb.rootAssembly.instances['PART-1-1'].NodeSetFromNodeLabels(name=node_set_name,
                                                                                        nodeLabels=tuple(node_list))
                log_array.append(['Added Cam Node Set ' + node_set_name + ' Succeed', start_record_value])
                # wait for 1 sec to make sure the new node set is created successfully
                time.sleep(cache_time)
                # find the node in node set will be much faster than from all node
                # node_region = opened_odb.rootAssembly.instances['PART-1-1'].nodes can also find the right node
                node_region = opened_odb.rootAssembly.instances['PART-1-1'].nodeSets[node_set_name]
                for node in node_region.nodes:
                    temp_result[node.label] = [node.coordinates]
            except Exception as e:
                log_array.append(['Added Cam Node Set' + node_set_name + ' Failed', start_record_value])
            log_object.add_record(log_array[-1], log_file)
            cam_node_result[node_set_name] = model.CamNode(temp_result)

    start_record_value += 1
    number_interval = float(procedure_length) / len(odb_steps)
    # from num 15 to 60 is set the range for step reading

    for step_num, current_step in enumerate(odb_steps):
        # ================================================================================
        # if step_num > 3:
        #     break
        # ================================================================================
        # First read node result, including displacement, shear force and slip value
        # no matter relative is required or not, the value will be set to both cases.
        node_region = opened_odb.rootAssembly.instances['PART-1-1'].nodeSets[gasket_node_set]
        current_result = opened_odb.steps[current_step].frames[-1].fieldOutputs['U'].getSubset(region=node_region)
        temp_result = {}
        for item in current_result.values:
            node_result[item.nodeLabel].set_displacement(item.data)
            # set the default value here, since if cslip, cshear are required to output, but in fact the gasket face is
            # tied with head or block, then the tied node will have no value in cshear1...
            temp_result[item.nodeLabel] = [0, 0, 0, 0]
        if process_setting['RELATIVE_MOTION'] == 'YES':
            cshear1 = opened_odb.steps[current_step].frames[-1].fieldOutputs['CSHEAR1']
            cshear2 = opened_odb.steps[current_step].frames[-1].fieldOutputs['CSHEAR2']
            cslip1 = opened_odb.steps[current_step].frames[-1].fieldOutputs['CSLIP1']
            cslip2 = opened_odb.steps[current_step].frames[-1].fieldOutputs['CSLIP2']
            for item in cshear1.values:
                if item.nodeLabel in node_labels:
                    temp_result[item.nodeLabel][0] = item.data
            for item in cshear2.values:
                if item.nodeLabel in node_labels:
                    temp_result[item.nodeLabel][1] = item.data
            for item in cslip1.values:
                if item.nodeLabel in node_labels:
                    temp_result[item.nodeLabel][2] = item.data
            for item in cslip2.values:
                if item.nodeLabel in node_labels:
                    temp_result[item.nodeLabel][3] = item.data
        for keys in temp_result:
            node_result[keys].set_relative(temp_result[keys])
        log_array.append(['Node Result Read_' + current_step, start_record_value + step_num * number_interval])
        log_object.add_record(log_array[-1], log_file)
        # bore distortion node displacement read in
        if bore_check:
            if bore_distortion_manually:
                node_region = opened_odb.rootAssembly.instances['PART-1-1'].nodeSets[new_bore_set_name]
                current_result = opened_odb.steps[current_step].frames[-1].fieldOutputs['U'].getSubset(
                    region=node_region)
                for item in current_result.values:
                    current_cylinder = bore_distortion_node_key[item.nodeLabel][0]
                    z_level = bore_distortion_node_key[item.nodeLabel][1]
                    bore_distortion_results[current_cylinder][z_level].set_displacement(item.nodeLabel, item.data)
                log_array.append(['Bore Node Read_' + current_step, start_record_value + step_num * number_interval])
                log_object.add_record(log_array[-1], log_file)
        if cam_check:
            for node_set in cam_node_result:
                node_region = opened_odb.rootAssembly.instances['PART-1-1'].nodeSets[node_set]
                current_result = opened_odb.steps[current_step].frames[-1].fieldOutputs['U'].getSubset(
                    region=node_region)
                for item in current_result.values:
                    cam_node_result[node_set].set_displacement(item.nodeLabel, item.data)
        # followings are for element calculation, only S11, E11 are required, consider the centroid value is required,
        # angle, area are non of business of ODB itself.
        current_result = opened_odb.steps[current_step].frames[-1].fieldOutputs['S'].getSubset(position=ELEMENT_NODAL)
        temp_result = {}
        for item in current_result.values:
            element_id = item.elementLabel
            if element_id in element_labels:
                temp_result.setdefault(element_id, {})
                temp_result[element_id][item.nodeLabel] = [item.data[0]]
        current_result = opened_odb.steps[current_step].frames[-1].fieldOutputs['E'].getSubset(position=ELEMENT_NODAL)
        for item in current_result.values:
            element_id = item.elementLabel
            if element_id in element_labels:
                temp_result[element_id][item.nodeLabel].append(item.data[0])
        for item in element_result:
            for node in element_result[item].connectivity:
                element_result[item].set_result(node, temp_result[item][node])
        log_array.append(['Element Result Read_' + current_step, start_record_value + step_num * number_interval])
        log_object.add_record(log_array[-1], log_file)

    if bore_check:
        for current_cylinder in range(total_cylinder_num):
            for z_level in z_coord_list:
                print (bore_distortion_results[current_cylinder][z_level].get_bore_nodes())
                bore_distortion_results[current_cylinder][z_level].cal_fourier()
                bore_distortion_results[current_cylinder][z_level].cal_angle_data()
            log_array.append(
                ['Bore Distortion for Cylinder_' + str(current_cylinder + 1),
                 start_record_value + step_num * number_interval])
            log_object.add_record(log_array[-1], log_file)

        process_setting['BORE_DISTORTION_DATA'] = bore_distortion_results

    if cam_check:
        pass

    start_record_value += procedure_length

    for keys in element_result:
        connectivity = element_result[keys].connectivity
        node_array = []
        for node in connectivity:
            node_array.append(node_result[node])
        element_result[keys].set_node_coord(node_array)
        element_result[keys].set_bore_center(bore_max_x)
        cylinder_order = element_result[keys].get_bore_center()
        # center z coordinate is set to 0, will not be used in angle calculation
        center = [bore_center_x[cylinder_order], bore_center_y, 0]
        element_result[keys].set_center_coord()
        element_result[keys].set_area_angle(center)

    log_array.append(['Element Character Calculated Succeed', start_record_value])
    log_object.add_record(log_array[-1], log_file)

    process_setting['ELEM_RESULT'] = element_result
    process_setting['NODE_RESULT'] = node_result
    process_setting['LOG_ARRAY'] = log_array
    process_setting['START_LOG_VALUE'] = start_record_value
    return process_setting


def print_to_file(print_name, position='Iso', zoom_value=1, x_pan=0, x_rotation=0):
    """
        print the picture to current folder
        position:       choice, ISO, FRONT, ...
        zoom_value:     scale value, zoom -  when value less than 1.
        x_pan:          pan value along X axis
        x_rotation:     rotation angle along X axis
        the plot for line load, head lift will be scaled,
        while for thermal map, will be rotated.
    """
    current_session.view.setValues(session.views[position])
    current_session.view.rotate(xAngle=x_rotation)
    current_session.view.fitView()
    current_session.view.zoom(zoom_value)
    current_session.view.pan(xFraction=x_pan)
    session.printToFile(fileName=print_name, format=PNG, canvasObjects=(current_session,))


def plot_thermal_map(opened_odb, process_setting, log_array, log_object, log_file, procedure_length):
    """
    plot the temperature map.
    :param opened_odb:          opened current odb, all data will be read from the odb
    :param process_setting:     big dict, contained all results, required input
    :param log_array:           log data, record all the log information as a list
    :param log_object:          log object, defined as a class
    :param log_file:            log archived file, for each operation the file will be updated, and read by web,
                                display as a processing bar.
    :param procedure_length:    the whole procedure percentage, display in the processing bar.
    :return:
    """
    temperature_step = process_setting['TEMPERATURE_STEP']
    temperature_name = process_setting['TEMPERATURE_NAME']
    zoom_value = setting.environment_key['TEMPERATURE_ZOOM']
    xpan_value = setting.environment_key['TEMPERATURE_XPAN']
    x_rotate = setting.environment_key['TEMPERATURE_ROTATE']
    file_save_in = process_setting['FILE_SAVE_IN']
    start_record_value = process_setting['START_LOG_VALUE']

    # display set for current window
    # current_session.makeCurrent()
    # current_session.maximize()
    # current_session.setValues(displayedObject=opened_odb)
    current_session.viewportAnnotationOptions.setValues(triad=OFF, title=OFF, state=OFF, annotations=ON, compass=OFF)
    current_session.view.setProjection(projection=PARALLEL)
    current_session.odbDisplay.commonOptions.setValues(visibleEdges=NONE)

    current_session.enableMultipleColors()
    current_session.setColor(initialColor='#BDBDBD')
    cmap = current_session.colorMappings['Section']
    current_session.setColor(colorMapping=cmap)
    current_session.disableMultipleColors()

    print_to_file(print_name=os.path.join(file_save_in, 'Whole_Engine'))
    log_array.append(['Create Engine Plot Succeed', start_record_value + 1])
    log_object.add_record(log_array[-1], log_file)

    all_elem_sets = opened_odb.rootAssembly.instances['PART-1-1'].elementSets
    display_sets = []
    gasket_sets = []
    display_set_node = []

    # python version 2.x required keys
    for item in all_elem_sets.keys():
        select_elem = all_elem_sets[item].elements[0]
        elem_type = select_elem.type
        if 'GK3D' in elem_type:
            gasket_sets.append(item)
        else:
            display_sets.append(item)
            display_set_node.append(select_elem.connectivity[0])
    for i, item in enumerate(gasket_sets):
        leaf = dgo.LeafFromElementSets(elementSets=('PART-1-1.' + item))
        if i == 0:
            current_session.odbDisplay.displayGroup.replace(leaf=leaf)
        else:
            current_session.odbDisplay.displayGroup.add(leaf=leaf)
    print_to_file(print_name=os.path.join(file_save_in, 'Gasket_Plan_View'), position='Front')
    log_array.append(['Create Gasket Plot Succeed', start_record_value + 1])
    log_object.add_record(log_array[-1], log_file)
    process_setting['GASKET_SET'] = gasket_sets
    process_setting['ENGINE_SET'] = display_sets
    nodes_in_model = opened_odb.rootAssembly.instances['PART-1-1'].nodes
    up_sets = []
    down_sets = []
    critical_value = (process_setting['GASKET_MAX_Z'] + process_setting['GASKET_MIN_Z']) / 2
    for node in nodes_in_model:
        if node.label in display_set_node:
            if node.coordinates[2] > critical_value:
                up_sets.append(display_sets[display_set_node.index(node.label)])
            else:
                down_sets.append(display_sets[display_set_node.index(node.label)])

    log_array.append(['Engine Sets Separated Succeed', start_record_value + 1])
    log_object.add_record(log_array[-1], log_file)
    # state box, one number after decimal point, set the legend and font for state box
    current_session.viewportAnnotationOptions.setValues(state=ON)
    current_session.viewportAnnotationOptions.setValues(legendDecimalPlaces=1, legendNumberFormat=FIXED)
    current_session.viewportAnnotationOptions.setValues(
        legendFont='-*-arial-medium-r-normal-*-*-120-*-*-p-*-*-*')
    current_session.viewportAnnotationOptions.setValues(
        stateFont='-*-arial-medium-r-normal-*-*-100-*-*-p-*-*-*')
    current_session.odbDisplay.commonOptions.setValues(deformationScaling=UNIFORM, uniformScaleFactor=1)

    start_record_value += 1
    number_interval = float(procedure_length) / len(temperature_step)
    for i, step in enumerate(temperature_step):
        current_session.odbDisplay.setFrame(step=int(step) - 1, frame=-1)
        if 'NT11' in opened_odb.steps.values()[0].frames[-1].fieldOutputs:
            current_session.odbDisplay.setPrimaryVariable(variableLabel='NT11', outputPosition=NODAL)
            for item in down_sets:
                print_title = temperature_name[i] + '_' + item + '_Temp'
                leaf = dgo.LeafFromElementSets(elementSets=('PART-1-1.' + item,))
                current_session.odbDisplay.displayGroup.replace(leaf=leaf)
                print_to_file(print_name=os.path.join(file_save_in, print_title), zoom_value=zoom_value,
                              x_pan=xpan_value)
            for item in up_sets:
                print_title = temperature_name[i] + '_' + item + '_Temp'
                leaf = dgo.LeafFromElementSets(elementSets=('PART-1-1.' + item,))
                current_session.odbDisplay.displayGroup.replace(leaf=leaf)
                print_to_file(print_name=os.path.join(file_save_in, print_title), zoom_value=zoom_value,
                              x_pan=xpan_value, x_rotation=x_rotate)
        log_array.append(
            ['Thermal Map Plot for Step' + str(step) + ' Done.', start_record_value + i * number_interval])
        log_object.add_record(log_array[-1], log_file)
    process_setting['START_LOG_VALUE'] = start_record_value + procedure_length
    return process_setting


def get_section_force(opened_odb, process_setting, log_array, log_object, log_file, procedure_length):
    """
    generate the total force for section, will be used to calibrate the results and calculate the load distribution,
    will read in all force for different set in all steps.
    :param opened_odb:          opened current odb, all data will be read from the odb
    :param process_setting:     big dict, contained all results, required input
    :param log_array:           log data, record all the log information as a list
    :param log_object:          log object, defined as a class
    :param log_file:            log archived file, for each operation the file will be updated, and read by web,
                                display as a processing bar.
    :param procedure_length:    the whole procedure percentage, display in the processing bar.
    :return:                    dict type, new added key --- SECTION_FORCE_DATA ---
    """
    view_name = setting.environment_key['VIEW_NAME']
    current_session = session.viewports[view_name]
    odb_steps = opened_odb.steps.keys()
    gasket_sets = process_setting['GASKET_SET']
    section_force_file = process_setting['SECTION_FORCE_FILE']
    start_record_value = process_setting['START_LOG_VALUE']
    number_interval = float(procedure_length) / len(odb_steps)

    with open(section_force_file, 'wt') as f:
        f.write('SECTION FORCE START'.center(50, '#') + '\n')
    # read the section force
    # show all gasket set first
    for i, item in enumerate(gasket_sets):
        leaf = dgo.LeafFromElementSets(elementSets=('PART-1-1.' + item))
        if i == 0:
            current_session.odbDisplay.displayGroup.replace(leaf=leaf)
        else:
            current_session.odbDisplay.displayGroup.add(leaf=leaf)

    current_session.view.setValues(session.views['Front'])
    current_session.view.fitView()

    current_session.odbDisplay.setValues(viewCut=ON)
    current_session.odbDisplay.setValues(viewCutNames=('X-Plane',), viewCut=OFF)
    current_session.odbDisplay.setValues(viewCutNames=('Z-Plane',), viewCut=ON)
    current_session.odbDisplay.viewCuts['Z-Plane'].setValues(showModelOnCut=False)
    current_session.odbDisplay.viewCuts['Z-Plane'].setValues(showFreeBodyCut=True)

    for i, item in enumerate(odb_steps):
        current_session.odbDisplay.setFrame(step=i, frame=-1)
        for current_set in gasket_sets:
            leaf = dgo.LeafFromElementSets(elementSets=('PART-1-1.' + current_set))
            current_session.odbDisplay.displayGroup.replace(leaf=leaf)
            session.writeFreeBodyReport(fileName=section_force_file, append=ON)
        for j, current_set in enumerate(gasket_sets):
            leaf = dgo.LeafFromElementSets(elementSets=('PART-1-1.' + current_set))
            if j > 0:
                current_session.odbDisplay.displayGroup.add(leaf=leaf)
            else:
                current_session.odbDisplay.displayGroup.replace(leaf=leaf)
        session.writeFreeBodyReport(fileName=section_force_file, append=ON)
        log_array.append(['Read Section Force in Step ' + str(item), start_record_value + i * number_interval])
        log_object.add_record(log_array[-1], log_file)
    section_force = {}
    gasket_sets.append('GASKET_ALL_ELEMENT_TEMP')
    for current_set in gasket_sets:
        section_force[current_set] = []
    with open(section_force_file, 'rt') as f:
        lines = f.readlines()
        section_force_list = []
        step_mark = -1
        for current_line in lines:
            item = current_line.split('=')
            if len(item) > 0:
                if item[0].strip() == 'Step':
                    step_num = int(item[1].strip())
                    if not step_num == step_mark:
                        section_force_list.append([])
                        step_mark = step_num
                if item[0].strip() == 'Resultant force':
                    try:
                        force_value = item[1].split()[-1].strip()
                    except:
                        force_value = 0
                    section_force_list[-1].append(force_value)
    record_state = True
    start_record_value += procedure_length
    for i in range(len(odb_steps)):
        for j, current_set in enumerate(gasket_sets):
            try:
                force_value = float(section_force_list[i][j])
            except Exception as e:
                force_value = 0.0
                log_array.append(
                    ['Section Force for ' + current_set + ' at Step ' + str(i + 1) + 'Failed', start_record_value])
                log_object.add_record(log_array[-1], log_file)
                record_state = False
            section_force[current_set].append(force_value)
    if record_state:
        log_array.append(['Read Section Force Succeed', start_record_value])
        log_object.add_record(log_array[-1], log_file)
        process_setting['SECTION_FORCE'] = section_force
    process_setting['START_LOG_VALUE'] = start_record_value
    return process_setting


def get_bolt_force(opened_odb, process_setting, log_array, log_object, log_file, procedure_length):
    """
    Get the bolt force from current odb, the history output of bolt node is required.
    :param opened_odb:          opened current odb, all data will be read from the odb
    :param process_setting:     big dict, contained all results, required input
    :param log_array:           log data, record all the log information as a list
    :param log_object:          log object, defined as a class
    :param log_file:            log archived file, for each operation the file will be updated, and read by web,
                                display as a processing bar.
    :param procedure_length:    the whole procedure percentage, display in the processing bar.
    :return:                    dict type, new added key --- BOLT_FORCE --- with bolt force value
    """
    bolt_node_set = process_setting['BOLT_NODESET']
    start_record_value = process_setting['START_LOG_VALUE']
    bolt_node_list = opened_odb.rootAssembly.instances['PART-1-1'].nodeSets[bolt_node_set].nodes
    bolt_node_list = [node.label for node in bolt_node_list]
    odb_steps = opened_odb.steps.keys()
    bolt_force = []

    for step in odb_steps:
        bolt_force.append([])
        for node in bolt_node_list:
            node_num = 'Node PART-1-1.' + str(node)
            force_value = opened_odb.steps[step].historyRegions[node_num].historyOutputs['TF1'].data[-1][-1]
            bolt_force[-1].append(force_value)
    process_setting['BOLT_FORCE_VALUE'] = bolt_force
    start_record_value += procedure_length
    log_array.append(['Read Bolt Force Succeed', start_record_value])
    log_object.add_record(log_array[-1], log_file)
    process_setting['START_LOG_VALUE'] = start_record_value
    return process_setting


def find_fatigue_adjacent(current_value, value_list):
    """
    find the neighbour value of current value, used for the interpolation
    :param current_value:
    :param value_list:
    :return: the left, and right neighbour of current value.
    """
    if current_value <= value_list[0]:
        left_value = value_list[0]
        right_value = value_list[0]
    elif current_value >= value_list[-1]:
        left_value = value_list[-1]
        right_value = value_list[-1]
    else:
        for i, item in enumerate(value_list):
            if current_value < item:
                left_value = value_list[i - 1]
                right_value = value_list[i]
                break
    return left_value, right_value


def fatigue_interpolate(x, x0, x1, left_value_list, right_value_list, fatigue_criteria_name):
    """
    do the interpolation for fatigue calculation
    :param x:                               fixed load or preload value
    :param x0:                              the value in left_value_list, which is most close but less than x
    :param x1:                              the value in right_value_list, which is most close but greater than x
    :param left_value_list:                 first list used for interpolation
    :param right_value_list:                second list used for interpolation
    :param fatigue_criteria_name:           use to determine how many values should be interpolated
    :return:                                interpolated value, as a list, same size as fatigue_criteria_name
    """
    res = []
    for i, criteria in enumerate(fatigue_criteria_name):
        input1 = [x0, left_value_list[i]]
        input2 = [x1, right_value_list[i]]
        if input1[0] != input2[0]:
            y = input1[1] + (x - input1[0]) * (input2[1] - input1[1]) / (input2[0] - input1[0])
        else:
            y = input1[1]
        res.append(y)
    return res


def cal_relative(process_setting, log_array, log_object, log_file, procedure_length):
    """
    Calculate the relative motion for nodes, the procedure will be started even relative motion is not required.
    :param process_setting:     big dict, contained all results, required input
    :param log_array:           log data, record all the log information as a list
    :param log_object:          log object, defined as a class
    :param log_file:            log archived file, for each operation the file will be updated, and read by web,
                                display as a processing bar.
    :param procedure_length:    the whole procedure percentage, display in the processing bar.
    :return:                    update the node relative data
    """
    cylinder_name = process_setting['FIRING_CYLINDER_NAME']
    temperature_name = process_setting['TEMPERATURE_NAME']
    cylinder_num = len(cylinder_name)
    fixed_step = process_setting['TEMPERATURE_STEP']
    node_result = process_setting['NODE_RESULT']
    start_record_value = process_setting['START_LOG_VALUE']
    i = 0
    threshold = 0
    for key, value in node_result.items():  # type: model.ChgNodes
        value.cal_relative(fixed_step, cylinder_num, temperature_name)
        current_process = int(i * 100 / len(node_result))
        if current_process >= threshold:
            threshold += 10
            log_array.append(['Relative Motion Finished ' + str('%3.1f%%' % current_process),
                              start_record_value + current_process * float(procedure_length) / 100])
            log_object.add_record(log_array[-1], log_file)
    return process_setting


def cal_fatigue(process_setting, log_array, log_object, log_file, procedure_length):
    """
    For all elements will have the fatigue data, even they are not required.
    Three types,                1. not required to calculate fatigue, stauts = Abandon,
                                2. Required to calculate fatigue, and succeed, status = Succeed
                                3. Required to calculate fatigue, and failed, status = Failed
    :param process_setting:     big dict, contained all results, required input
    :param log_array:           log data, record all the log information as a list
    :param log_object:          log object, defined as a class
    :param log_file:            log archived file, for each operation the file will be updated, and read by web,
                                display as a processing bar.
    :param procedure_length:    the whole procedure percentage, display in the processing bar.
    ====================================================================================================================
    Fatigue data is a member of element data, the format is
    Element_Class[node][Status, [fix_load, fire_load, pre_load, unload_ratio, left_load, left_ratio, right_load,
                        right_ratio, interpolation_1, interpolation_2, interpolation_3, interpolation_4, safety_factor,
                        adjust_data]...]
    ====================================================================================================================
    0. Status:                     [Abandon, Succeed, Failed]
    1. data for cycle 1
    ...
    data for each cycle
    0. fix_load:                   max load during operation
    1. fire_load:                  min load during operation
    2. pre_load:                   max load from first step to the FIRST fixed step
    3. unload_ratio:               (fix_load - fire_load) / fix_load
    4. left_load:                  the load in fatigue_load list, which is most close but less than fix_load
    5. left_ratio:                 the ratio in fatigue_ratio list, which is most close but less than preload_ratio
    6. right_load:                 the load in fatigue_load list, which is most close but greater than fix_load
    7. right_ratio:                the ratio in fatigue_ratio list, which is most close but greater than preload_ratio
    8. interpolation_1:            first interpolation, using [left_load, left_ratio], [right_load, left_ratio],
                                return [left_interpolation_ratio], it is a list, include all interpolated data from
                                fatigue type: [Goodman, Gerber, Average, Dangvon, SWT]
    9. interpolation_2:            second interpolation, using [left_load, right_ratio], [right_load, right_ratio],
                                return [right_interpolation_ratio], it is a list, include all interpolated data from
                                fatigue type: [Goodman, Gerber, Average, Dangvon, SWT]
    10. interpolation_3:            third interpolation, using [left_interpolation_ratio, left_ratio],
                                [right_interpolation_ratio, right_ratio], return [final_allowed_ratio], it is a list,
                                include all interpolated data from fatigue type: [Goodman, Gerber, Average, Dangvon, SWT]
    11. interpolation_4:            fourth interpolation, using [left_load, 0], [right_load, 0], return [no_preload_ratio],
                                it is a list, include all interpolated data from fatigue type: [Goodman, Gerber, Average,
                                Dangvon, SWT]
    12. safety_factor:              final_allowed_ratio / unload_ratio, >1 means safe, <1 means risk, it is a list, include
                                all interpolated data from fatigue type: [Goodman, Gerber, Average, Dangvon, SWT]
    13. adjust_data:                no_preload_ratio - (final_allowed_ratio - unload_ratio)

    :return:                    None
    """
    element_result = process_setting['ELEM_RESULT']  # type: dict
    fatigue_value = process_setting['FATIGUE_DATA']  # type: dict
    fixed_step = process_setting['TEMPERATURE_STEP']
    initial_assembly_step = process_setting['INI_ASSEM']
    hot_assembly_step = process_setting['HOT_ASSEM']
    temperature_name = process_setting['TEMPERATURE_NAME']
    cylinder_name = process_setting['FIRING_CYLINDER_NAME']
    cylinder_num = len(cylinder_name)
    fatigue_criteria_name = process_setting['FATIGUE_CRITERIA_NAME']
    start_record_value = process_setting['START_LOG_VALUE']
    # number_interval = float(procedure_length) / len(element_result)
    # if not required, or failed, using 3 instead, means safe
    empty_list = [3 for value in fatigue_criteria_name]

    i = 0
    threshold = 0
    for element_id, element_value in element_result.items():  # type: model.ChgElements
        elem_material = element_value.material
        node_array = element_value.connectivity
        for node_id in node_array:
            res = element_value.step_results[node_id]
            s11_list = [x[0] for x in res]
            # s11_initial_assem = s11_list[initial_assembly_step - 1]
            # s11_hot_assem = s11_list[hot_assembly_step - 1]
            # obtain the max load before the first firing cycle
            s11_max_before_firing = max(s11_list[:fixed_step[0]])
            fatigue_result = []
            # fatigue_check, if required to calculate the fatigue, will be True, otherwise, False
            fatigue_check = False
            # fatigue_no_Error, if the calculation for fatigue failed, set False.
            fatigue_no_Error = True
            if elem_material in fatigue_value:
                fatigue_data_class = fatigue_value[elem_material]  # type: model.FatigueData
                line_load = fatigue_data_class.fixload
                preload_value = fatigue_data_class.preload
                fatigue_data = fatigue_data_class.fatigue_data
                fatigue_check = True
            for oper_num, oper_step in enumerate(fixed_step):
                fatigue_result.append([])
                current_s11_list = s11_list[oper_step - 1:oper_step + cylinder_num]
                fix_load = max(current_s11_list)
                firing_load = min(current_s11_list)
                preload = max(s11_max_before_firing, fix_load)
                if preload > 0:
                    preload_ratio = (preload - fix_load) / preload
                else:
                    preload_ratio = 0
                if fix_load > 0:
                    unload_ratio = (fix_load - firing_load) / fix_load
                else:
                    unload_ratio = 0
                fatigue_result[-1] = [fix_load, firing_load, preload, unload_ratio]
                if fatigue_check:
                    left_load, right_load = find_fatigue_adjacent(fix_load, line_load)
                    left_ratio, right_ratio = find_fatigue_adjacent(preload_ratio, preload_value)
                    fatigue_result[-1] += [left_load, left_ratio, right_load, right_ratio]
                    try:
                        # first using the load, left_ratio to interpolate
                        interpolation_1 = fatigue_interpolate(fix_load, left_load, right_load,
                                                              fatigue_data[left_load][left_ratio],
                                                              fatigue_data[right_load][left_ratio],
                                                              fatigue_criteria_name)
                        # second using the load, right_ratio to interpolate
                        interpolation_2 = fatigue_interpolate(fix_load, left_load, right_load,
                                                              fatigue_data[left_load][right_ratio],
                                                              fatigue_data[right_load][right_ratio],
                                                              fatigue_criteria_name)
                        # third get the final data
                        interpolation_3 = fatigue_interpolate(unload_ratio, left_ratio, right_ratio,
                                                              interpolation_1, interpolation_2, fatigue_criteria_name)
                        # get the no preload value
                        interpolation_4 = fatigue_interpolate(fix_load, left_load, right_load,
                                                              fatigue_data[left_load][0],
                                                              fatigue_data[right_load][0], fatigue_criteria_name)
                        # get the safety factor
                        if unload_ratio > 0:
                            safety_factor = [value / unload_ratio for value in interpolation_3]
                        else:
                            safety_factor = [3 for value in range(len(fatigue_criteria_name))]
                        # get the adjust data
                        adjust_data = [no_preload - with_preload + unload_ratio for no_preload, with_preload in
                                       zip(interpolation_4, interpolation_3)]
                        # final stored data
                        fatigue_result[-1] += [interpolation_1, interpolation_2, interpolation_3, interpolation_4,
                                               safety_factor, adjust_data]
                    except Exception as e:
                        fatigue_no_Error = False
                        for j in range(6):
                            fatigue_result[-1].append(empty_list)
                        log_array.append(
                            ['Fatigue Failed for Elem:' + str(element_id) + ' Node:' + str(node_id),
                             start_record_value])
                        log_object.add_record(log_array[-1], log_file)
                else:
                    fatigue_result[-1] += [0, 0, 0, 0]
                    for j in range(6):
                        fatigue_result[-1].append(empty_list)
            if fatigue_check:
                if fatigue_no_Error:
                    fatigue_result.insert(0, 'Succeed')
                else:
                    fatigue_result.insert(0, 'Failed')
            else:
                fatigue_result.insert(0, 'Abandon')
            element_value.set_fatigue(node_id, temperature_name, fatigue_result)
            element_value.set_final_results(node_id, initial_assembly_step, hot_assembly_step, fixed_step, cylinder_num)
            # here is the final results
        current_process = int(i * 100 / len(element_result))
        if current_process >= threshold:
            threshold += 10
            log_array.append(['Fatigue Calculate Finished ' + str('%3.1f%%' % current_process),
                              start_record_value + current_process * float(procedure_length) / 100])
            log_object.add_record(log_array[-1], log_file)
        i += 1
    process_setting['START_LOG_VALUE'] = start_record_value + procedure_length
    return process_setting
