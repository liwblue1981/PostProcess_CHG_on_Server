from abaqus import *
from abaqusConstants import *
from viewerModules import *
from odbAccess import *
from odbMaterial import *
from odbSection import *
import displayGroupOdbToolset as dgo
import json
import os
from db import model
from conf import setting


def read_from_odb(input_data, opened_odb, process_setting):
    """
    读取ODB,将每个单元,节点按照指定格式进行输出,鉴于打开一次会花费比较大,所以还是在打开的时候,将所有需要数据一次性读取
    :param input_data:      从前端获得的数据,该数据以Json格式存储
    :param opened_odb:      需要打开的ODB,之所以作为参数传入,是因为还有一些function会使用这个ODB,所以将其保存在主函数中
    :param process_setting: 局部关键变量字典.
    :return: process_setting, 新增了单元和节点结果.更新log数组
            element_result  单元结果,字典类型,单元号为key, value为单元类
            node_result     节点结果,字典类型,节点号为key, value为节点类
            log_array       日志数组,存储当前函数的操作日志记录
    """
    # 垫片单元集合
    report_set = input_data['report_set']
    excel_set = input_data['excel_set']
    fatigue_set = input_data['fatigue_set']
    add_elem_set = input_data['add_elem_set']
    add_elem_list = input_data['add_elem_list']

    # 其他读取信息
    process_setting['RELATIVE_MOTION'] = input_data['relative_motion']

    all_elem_sets = opened_odb.rootAssembly.instances['PART-1-1'].elementSets
    # 这两个字典分别记录了单元结果和节点结果,是返回值
    element_result = {}
    node_result = {}

    gasket_node_set = setting.enviroment_key['GASKET_ALL_NODES']
    gasket_elem_set = report_set + excel_set + fatigue_set + add_elem_set
    gasket_elem_set = list(set(gasket_elem_set))

    log_array = process_setting['LOG_ARRAY']
    log_object = process_setting['LOG_OBJECT']
    log_file = process_setting['LOG_FILE']
    process_setting['GASKET_ELEM_SETS'] = gasket_elem_set

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
            log_array.append(['Added Element Set' + set_name, 'Succeed'])
        except Exception as e:
            log_array.append(['Added Element Set' + set_name, 'Failed'])
            log_object.add_record(log_array)
            log_object.write_record(log_file)

    for elem_set in gasket_elem_set:
        elem_in_set = all_elem_sets[elem_set].elements
        for item in elem_in_set:
            element_nodes = item.connectivity
            element_number = item.label
            element_result[element_number] = model.ChgElements(element_number, list(element_nodes))
            for node in element_nodes:
                if node not in node_result:
                    node_result[node] = model.ChgNodes(node)

    log_array.append(['Gasket Element - Node Read', 'Succeed'])
    node_labels = tuple([keys for keys in node_result])
    process_setting['MAX_NODE_NUMBER'] = max(node_labels)
    element_labels = tuple([keys for keys in element_result])
    process_setting['MAX_ELEMENT_NUMBER'] = max(element_labels)
    _ = opened_odb.rootAssembly.instances['PART-1-1'].NodeSetFromNodeLabels(name=gasket_node_set,
                                                                            nodeLabels=node_labels)
    log_array.append(['Added Gasket Node Set', 'Succeed'])
    gasket_node_set_obj = opened_odb.rootAssembly.instances['PART-1-1'].nodeSets[gasket_node_set].nodes
    for node in gasket_node_set_obj:
        node_result[node].set_init_coord(node.coordinates)

    gasket_z_coord = [node_result[node].get_init_coord()[2] for node in node_result]
    process_setting['GASKET_MAX_Z'] = max(gasket_z_coord)
    process_setting['GASKET_MIN_Z'] = min(gasket_z_coord)

    log_array.append(['Node Coordinate Read', 'Succeed'])

    odb_steps = opened_odb.steps.keys()
    node_region = opened_odb.rootAssembly.instances['PART-1-1'].nodeSets[gasket_node_set]
    for current_step in odb_steps:
        # 先读取节点的结果,节点结果包括位移,SHEAR, SLIP
        current_result = opened_odb.steps[current_step].frames[-1].fieldOutputs['U'].getSubset(region=node_region)
        for item in current_result.values:
            node_result[item.nodeLabel].set_displacement(item.data)
        if process_setting['RELATIVE_MOTION'] == 'YES':
            cshear1 = opened_odb.steps[current_step].frames[-1].fieldOutputs['CSHEAR1']
            cshear2 = opened_odb.steps[current_step].frames[-1].fieldOutputs['CSHEAR2']
            cslip1 = opened_odb.steps[current_step].frames[-1].fieldOutputs['CSLIP1']
            cslip2 = opened_odb.steps[current_step].frames[-1].fieldOutputs['CSLIP2']
            temp_result = {}
            for item in cshear1.values:
                if item.nodeLabel in node_labels:
                    temp_result.setdefault(item.nodeLabel, [])
                    temp_result[item.nodeLabel].append(item.data)
            for item in cshear2.values:
                if item.nodeLabel in node_labels:
                    temp_result[item.nodeLabel].append(item.data)
            for item in cslip1.values:
                if item.nodeLabel in node_labels:
                    temp_result[item.nodeLabel].append(item.data)
            for item in cslip2.values:
                if item.nodeLabel in node_labels:
                    temp_result[item.nodeLabel].append(item.data)
            for keys in temp_result:
                node_result[keys].set_relative(temp_result[keys])
        log_array.append(['Node Result Read From ' + current_step, 'Succeed'])
        # 以下为单元计算,只需要读取S11, E11就好,因为中心计算,角度,面积与ODB本身无关
        current_result = opened_odb.steps[current_step].frames[-1].fieldOutputs['S']
        temp_result = {}
        for item in current_result.values:
            element_id = item.elementLabel
            if element_id in element_labels:
                temp_result[item.nodeLabel].append([item.data[0]])
        current_result = opened_odb.steps[current_step].frames[-1].fieldOutputs['E']
        for item in current_result.values:
            element_id = item.elementLabel
            if element_id in element_labels:
                temp_result[item.nodeLabel].append([item.data[0]])
        for item in element_result:
            for node in item.connectivity:
                element_result[item].set_result(node, temp_result[node])
        log_array.append(['Element Result Read From ' + current_step, 'Succeed'])

    for keys in element_result:
        connectivity = element_result[keys].connectivity
        node_array = []
        for node in connectivity:
            node_array.append(node_result[node].get_displacement())
        element_result[keys].set_node_coord(node_array)
        element_result[keys].set_area_angle()
        element_result[keys].set_center_coord()
    log_array.append(['Element Character Calculated ', 'Succeed'])

    process_setting['ELEM_RESULT'] = element_result
    process_setting['NODE_RESULT'] = node_result
    process_setting['LOG_ARRAY'] = log_array
    return process_setting


def print_to_file(current_session, print_name, position='Iso', zoom_value=1, x_pan=0, x_rotation=0):
    """
        打印图片到当前目录下
        position:   可以有Iso, Front...
        zoom_value: 是指缩放值,小于1,表示缩小.
        x_pan:      平移, 沿着X轴方向
        x_rotation: 转动,绕X轴转动
        对于出LINE LOAD, HEAD LIFT的图,需要进行缩放
        对于出温度场的图,需要进行旋转
    """
    current_session.view.setValues(session.views[position])
    current_session.view.rotate(xAngle=x_rotation)
    current_session.view.fitView()
    current_session.view.zoom(zoom_value)
    current_session.view.pan(xFraction=x_pan)
    session.printToFile(fileName=print_name, format=PNG, canvasObjects=(current_session,))


def plot_thermal_map(opened_odb, process_setting):
    """
    用于打印温度场图片
    :param opened_odb:      打开的ODB
    :param process_setting: 大字典,需要使用两个参数,temperature_step和temperature_name
    :return:
        process_setting
    """
    view_name = setting.enviroment_key['VIEW_NAME']
    current_session = session.Viewport[view_name]
    temperature_step = process_setting['TEMPERATURE_STEP']
    temperature_name = process_setting['TEMPERATURE_NAME']
    log_array = process_setting['LOG_ARRAY']
    zoom_value = process_setting['TEMPERATURE_ZOOM']
    xpan_value = process_setting['TEMPERATURE_XPAN']
    x_rotate = process_setting['TEMPERATURE_ROTATE']

    # 当前页面显示设置
    session.Viewport(name=view_name, origin=(0.0, 0.0), width=200, height=200)
    current_session.makeCurrent()
    current_session.maximize()
    current_session.setValues(displayedObject=opened_odb)
    current_session.viewportAnnotationOptions.setValues(triad=OFF, title=OFF, state=OFF, annotations=ON, compass=OFF)
    current_session.view.setProjection(projection=PARALLEL)
    current_session.odbDisplay.commonOptions.setValues(visibleEdges=NONE)

    current_session.enableMultipleColors()
    current_session.setColor(initialColor='#BDBDBD')
    cmap = current_session.colorMappings['Section']
    current_session.setColor(colorMapping=cmap)
    current_session.disableMultipleColors()

    print_to_file(current_session, print_name='Whole_Engine')
    log_array.append(['Create Engine Plot ', 'Succeed'])

    all_elem_sets = opened_odb.rootAssembly.instances['PART-1-1'].elementSets
    display_sets = []
    gasket_sets = []
    display_set_node = []
    for item in all_elem_sets:
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
    print_to_file(current_session, print_name='Gasket_Plan_View', position='Front')
    log_array.append(['Create Gasket Plot ', 'Succeed'])
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

    # 显示状态框,小数点一位,设置图例以及状态框字体
    current_session.view.setValues(state=ON)
    current_session.viewportAnnotationOptions.setValues(legendDecimalPlaces=1, legendNumberFormat=FIXED)
    current_session.viewportAnnotationOptions.setValues(
        legendFont='-*-arial-medium-r-normal-*-*-120-*-*-p-*-*-*')
    current_session.viewportAnnotationOptions.setValues(
        stateFont='-*-arial-medium-r-normal-*-*-100-*-*-p-*-*-*')
    current_session.odbDisplay.commonOptions.setValues(deformationScaling=UNIFORM, uniformScaleFactor=1)

    for i, step in enumerate(temperature_step):
        current_session.odbDisplay.setFrame(step=int(step)-1, frame=-1)
        if 'NT11' in opened_odb.steps.values()[0].frames[-1].fieldOutputs:
            current_session.odbDisplay.setPrimaryVariable(variableLabel='NT11', outputPosition=NODAL)
            for item in down_sets:
                print_title = temperature_name[i] + '_' + item + '_Temp'
                leaf = dgo.LeafFromElementSets(elementSets=('PART-1-1.' + item,))
                current_session.odbDisplay.displayGroup.replace(leaf=leaf)
                print_to_file(current_session, print_name=print_title, zoom_value=zoom_value, x_pan=xpan_value)
            for item in up_sets:
                print_title = temperature_name[i] + '_' + item + '_Temp'
                leaf = dgo.LeafFromElementSets(elementSets=('PART-1-1.' + item,))
                current_session.odbDisplay.displayGroup.replace(leaf=leaf)
                print_to_file(current_session, print_name=print_title, zoom_value=zoom_value, x_pan=xpan_value, x_rotation=x_rotate)
    log_array.append(['Create Thermal Map ', 'Succeed'])
    return process_setting


def get_section_force(opened_odb, process_setting):
    """
    生成截面总载荷,用于校准计算结果以及获得载荷分配, 读取了所有载荷步中不同SET的载荷值
    :param opened_odb:
    :param process_setting:
    :return:
    """
    view_name = setting.enviroment_key['VIEW_NAME']
    current_session = session.Viewport[view_name]
    odb_steps = opened_odb.steps.keys()
    gasket_sets = process_setting['GASKET_SET']
    section_force_file = process_setting['SECTION_FORCE_FILE']
    log_array = process_setting['LOG_ARRAY']

    with open(section_force_file, 'wt', encoding='utf-8') as f:
        f.write('SECTION FORCE START'.center(50, '#') + '\n')
    # 读取截面载荷
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
    section_force = {}
    gasket_sets.append('GASKET_ALL_ELEMENT_TEMP')
    for current_set in gasket_sets:
        section_force[current_set] = []
    with open(section_force_file, 'rt', encoding='utf-8') as f:
        lines = f.readlines()
        section_force_list = []
        for current_line in lines:
            item = current_line.split('=')
            if len(item) > 0:
                if item[0].strip() == 'Step':
                    step_num = item[1].strip()
                    section_force_list.append([])
                if item[0].strip() == 'Resultant force':
                    try:
                        force_value = item[1].split()[-1].strip()
                    except:
                        force_value = 0
                    section_force_list[-1].append(force_value)
    for i, current_set in enumerate(gasket_sets):
        for item in section_force_list:
            section_force[current_set].append(item[i])
            if not item[i]:
                log_array.append(['Section Force for ' + current_set + ' at Step ' + str(i+1), 'Failed'])
    log_array.append(['Read Section Force', 'Succeed'])
    process_setting['SECTION_FORCE'] = section_force
    return process_setting


def get_bolt_force(opened_odb, process_setting):
    """
    提取螺栓载荷
    :param opened_odb:
    :param process_setting:
    :return:
    """
    bolt_node_set = process_setting['BOLT_NODESET']
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
    return process_setting

