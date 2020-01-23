import math
import numpy as np
import time
from conf import setting


class RecordLog(object):
    """
    used to record the process status
    when add the new record, write to the log file will be executed.
    """

    def __init__(self):
        self.record = []

    def add_record(self, arr, log_file):
        arr.insert(0, time.strftime("%X", time.localtime()))
        self.record.append(arr)
        with open(log_file, 'at') as f:
            f.write(str(arr[0]).ljust(20) + str(arr[1]).ljust(80) + str(int(arr[2])).ljust(20) + '\n')

    def __str__(self):
        return str(self.record)


class ChgElements(object):
    """
    element object, include all the required data for element, stress, strain, coordinate, area, angle...
    """

    def __init__(self, number, connectivity, material):
        """
        initialize the elements object
        :param number: element number
        :param connectivity: the construction of element
        :param node_array: the node class object.
        """
        self.number = number
        self.connectivity = connectivity
        self.material = material
        self.node_array = []
        self.area = 0
        self.angle = 0
        self.width = 0
        self.bore_center = 0
        self.center_coord_list = []
        self.step_results = {}
        self.cycle_name = []
        for node in connectivity:
            self.step_results[node] = []
        # final results only include max, min, head lift, relative motion for operation and results for initial assembly
        self.final_results = {}
        self.fatigue_results = {}
        self.warning = []

    def _getlength(self, node1, node2):
        """
        calculate the element length for two nodes
        :param node1: node 1 coordinate
        :param node2: node 2 coordinate
        :return: the distance between node 1 and node 2
        """
        return math.sqrt((node1[0] - node2[0]) ** 2 + (node1[1] - node2[1]) ** 2)

    def _getarea(self, node1, node2, node3):
        """
        calculate the area of triangle combined with node 1, node 2, and node 3.
        :param node1: node array [x, y, z]
        :param node2:
        :param node3:
        :return: area of triangle
        """
        side_a = self._getlength(node1, node2)
        side_b = self._getlength(node2, node3)
        side_diagonal = self._getlength(node1, node3)
        half_circum = (side_a + side_b + side_diagonal) / 2
        area = math.sqrt(half_circum * (half_circum - side_a) * (half_circum - side_b) * (half_circum - side_diagonal))
        return area

    def set_node_coord(self, node_array):
        """
        node_array: node[node1, node2,...,node8],
        :param node_array: a list, 8 nodes for max, each node is a node class
        :return: None
        """
        self.node_array = node_array

    def set_bore_center(self, bore_max_x):
        """
        set the element belongs to which cylinder, and set its center x and y.
        can use the center of node1 and node3 to determine the element location
        :param cylinder_num: cylinder number of the element belongs to.
        :param center_x: cylinder center x coordinate
        :param center_y: cylinder center y coordinate
        :return:
        """
        node1 = self.node_array[0]
        node2 = self.node_array[2]
        node1_coord = node1.get_init_coord()
        node2_coord = node2.get_init_coord()
        element_x = (node1_coord[0] + node2_coord[0]) / 2
        for i, x_range in enumerate(bore_max_x):
            if element_x < x_range:
                self.bore_center = i
                break
        else:
            self.bore_center = i

    def set_fatigue(self, node_id, cycle_name, fatigue_result):
        self.cycle_name = cycle_name
        self.fatigue_results[node_id] = fatigue_result

    def get_bore_center(self):
        return self.bore_center

    def set_center_coord(self):
        """
        element centroid coordinate, will change according to different steps
        :return: the center_coord_list is [  [x1,x2,x3...], [y1,y2,y3...], [z1,z2,z3...]   ]
        """
        node = self.node_array
        real_location = []
        for current_node in node:
            init_coord = np.array(current_node.get_init_coord())
            displacement = current_node.get_displacement()
            real_location.append([])
            for item in displacement:
                real_location[-1].append(init_coord + np.array(item))
        if len(node) == 8:
            node_list = list(zip(real_location[0], real_location[1], real_location[2], real_location[3]))
        else:
            node_list = list(zip(real_location[0], real_location[1], real_location[2]))
        for current_step in node_list:
            node_x = np.array([x[0] for x in current_step])
            node_y = np.array([x[1] for x in current_step])
            node_z = np.array([x[2] for x in current_step])
            self.center_coord_list.append([node_x, node_y, node_z])

    def set_area_angle(self, center):
        """
        calculate element area, equivalent element width, element angle around the cylinder (only available for bead
        in excel format, for others, set as None for angle)
        1. using Helen's formula to calculate the area, the quadrangle will be split into two triangle and then sum together
        2. any type of quadrangle will be equivalent to a rectangle with same area and same diagonal length, the short length
           will be regarded as the element width.
           forumla: b=[sqrt(l*l+2*A)+sqrt(l*l-2*A)]/2,
           b means short length,
           l means diagonal length, and
           A is the area.
        3. if the element is triangle, the width is the third length.
        4. use the initial coordinate to calculate the angle and area
        :return:area, angle, width
        """
        node = self.node_array
        node1 = node[0].get_init_coord()
        node2 = node[1].get_init_coord()
        node3 = node[2].get_init_coord()
        area1 = self._getarea(node1, node2, node3)
        side_diagonal_1 = self._getlength(node1, node3)

        self.width = 2 * area1 / side_diagonal_1
        if len(node) == 8:
            node4 = node[3].get_init_coord()
            area2 = self._getarea(node1, node3, node4)
            area1 += area2
            side_diagonal_2 = self._getlength(node2, node4)
            side_diagonal = (side_diagonal_1 + side_diagonal_2) / 2
            self.width = math.sqrt(side_diagonal ** 2 + 2 * area1) - math.sqrt(side_diagonal ** 2 - 2 * area1)
            self.width /= 2
        self.area = area1
        element_x = (node1[0] + node3[0]) / 2
        element_y = (node1[1] + node3[1]) / 2
        radius = self._getlength([element_x, element_y], center)
        if element_y >= center[1]:
            self.angle = math.acos((element_x - center[0]) / radius) * 180 / math.pi
        else:
            self.angle = 360 - math.acos((element_x - center[0]) / radius) * 180 / math.pi

    def set_result(self, node_id, result):
        """
        set the element results, it is a dict type
        :param node_id: one element has 8 nodes, and each nodes in each step has its own value,
        :param result: a list, for each step, include stress, strain
        :return:
        """
        self.step_results[node_id].append(result)

    def _check_status(self):
        s11_list = []
        node_list = []
        info_list = []
        ratio_criteria = setting.environment_key['STRESS_DIFFER_RATIO']
        for node in self.connectivity:
            node_list.append(node)
            temp = [x[0] for x in self.step_results[node]]
            s11_list.append(temp)
        for i, item in enumerate(self.center_coord_list):
            temp = [x[i] for x in s11_list]
            min_value = min(temp)
            max_value = max(temp)
            if min_value < 0.001:
                ratio = max_value / 0.001
            else:
                ratio = max_value / min_value
            if ratio > ratio_criteria:
                node_max = node_list[temp.index(max_value)]
                node_min = node_list[temp.index(min_value)]
                info_list.append('STEP_' + str(i + 1) + ': MAX: ' + ' NODE: ' + '%20u' % node_max + ' VALUE:' +
                                 '%10.2f' % max_value + '--- MIN:' + ' NODE: ' + '%20u' % node_min + ' VALUE:' +
                                 '%10.2f' % min_value + '--- RATIO: ' + '%10.2f' % ratio)
        if info_list:
            self.warning = ['WARNING'] + info_list

    def set_final_results(self, node, init_assem, hot_assem, fixed_step, cylinder_num):
        s11 = [x[0] for x in self.step_results[node]]
        e11 = [x[1] for x in self.step_results[node]]
        line_load = []
        head_lift = []
        wear_list = []
        self._check_status()
        for oper_step in fixed_step:
            current_s11_list = s11[oper_step - 1:oper_step + cylinder_num]
            current_e11_list = e11[oper_step - 1:oper_step + cylinder_num]
            wear = map(lambda (a, b): a * b, zip(current_s11_list, current_e11_list))
            line_load.append([max(current_s11_list), min(current_s11_list)])
            head_lift.append((max(current_e11_list) - min(current_e11_list)) * 1000)
            wear_list.append(abs(sum(wear) - len(wear) * wear[0]))
        thermal_motion = []
        for i, oper_step in enumerate(fixed_step):
            e11_fixed = e11[oper_step - 1]
            for j in range(i + 1, len(fixed_step)):
                e11_another_fixed = e11[fixed_step[j] - 1]
                thermal_motion.append((e11_fixed - e11_another_fixed) * 1000)
        fatigue_data = []
        fatigue_all = self.fatigue_results[node]
        for i, oper_step in enumerate(fixed_step):
            fatigue_data.append([])
            fatigue_data[-1] = fatigue_all[i + 1][12]
        self.final_results[node] = [s11[init_assem - 1], s11[hot_assem - 1], line_load, head_lift,
                                    fatigue_data, thermal_motion, wear_list]

    def __str__(self):
        keys_1 = ['fix_load', 'firing_load', 'pre_load', 'unload_ratio', 'left_load', 'left_ratio',
                  'right_load', 'right_ratio']
        keys_2 = ['First Interpolation', 'Second Interpolation', 'Final Results', 'No Preload Interpolation',
                  'Safety Factor', 'Adjust Data']
        fatigue_criteria_name = setting.environment_key['FATIGUE_CRITERIA_NAME']
        data = '**' + '=' * 50 + '\n'
        data += '**' + 'ELEMENT NUMBER: '.rjust(25) + str(self.number) + '\n'
        data += '**' + 'CONNECTIVITY: '.rjust(25) + str(self.connectivity) + '\n'
        data += '**' + 'AREA: '.rjust(25) + str('%10.3f' % self.area) + '\n'
        data += '**' + 'ANGLE: '.rjust(25) + str('%10.1f' % self.angle) + '\n'
        data += '**' + 'WIDTH: '.rjust(25) + str('%10.3f' % self.width) + '\n'
        data += '**' + 'BORE ORDER: '.rjust(25) + str('%10u' % (self.bore_center + 1)) + '\n'
        data += '**' + 'MATERIAL: '.rjust(25) + str(self.material) + '\n'
        data += 'CENTER COORDINATE'.center(80, '*') + '\n'
        for i, item in enumerate(self.center_coord_list):
            data += ('STEP_' + str(i + 1)).rjust(20) * 3
        data += '\n'
        for i, item in enumerate(self.center_coord_list):
            data += 'X'.rjust(20) + 'Y'.rjust(20) + 'Z'.rjust(20)
        data += '\n'
        for i, item in enumerate(self.center_coord_list):
            center_coord = [value.mean() for value in item]
            for coord in center_coord:
                data += '%20.4f' % coord
        data += '\n'
        data += 'RESULTS'.center(80, '*') + '\n' + 'NODE'.rjust(20)
        for i, item in enumerate(self.center_coord_list):
            data += ('STEP_' + str(i + 1)).rjust(20) * 2
        data += '\n' + 'NUM'.rjust(20)
        for i, item in enumerate(self.center_coord_list):
            data += 'S11'.rjust(20) + 'E11'.rjust(20)
        data += '\n'
        for node in self.connectivity:
            data += '%20u' % node
            for i, item in enumerate(self.center_coord_list):
                current_result = self.step_results[node][i]
                data += '%20.2f' % current_result[0] + '%20.4f' % current_result[1]
            data += '\n'
        # print the fatigue data, create a if block to make code look nice
        if True:
            data += '**' + ('FATIGUE DATA FOR ELEMENT - ' + str(self.number)).rjust(50) + '\n'
            for cycle_num, cycle in enumerate(self.cycle_name):
                data += '=' * 50 + '\n'
                data += ('Cycle_' + cycle).center(50, '=') + '\n'
                # first line            NODE NUM            Status
                data += 'Node Num'.rjust(20) + 'Status'.rjust(10)
                data += cycle.center(len(keys_1) * 20 + len(keys_2) * 50)
                data += '\n'
                # second line                       FIX, FIRING, PRE...
                data += ''.rjust(30)
                for keys in keys_1:
                    data += keys.rjust(20)
                for keys in keys_2:
                    data += keys.center(50)
                data += '\n'
                # third line                                    GOODMAN, GERBER, AVEREAGE, DANGVON, SWT
                data += ''.rjust(30)
                for keys in keys_1:
                    data += ''.rjust(20)
                for keys in keys_2:
                    for name in fatigue_criteria_name:
                        data += name.rjust(10)
                data += '\n'
                for node in self.connectivity:
                    fatigue_has_data = self.fatigue_results[node][0]
                    # start the data print
                    data += '%20u' % node + fatigue_has_data.rjust(10)
                    fatigue_data = self.fatigue_results[node][1 + cycle_num]
                    for j, keys in enumerate(keys_1):
                        data += '%20.2f' % fatigue_data[j]
                    for k, keys in enumerate(keys_2):
                        unload_ratio = fatigue_data[j + k + 1]
                        for num in unload_ratio:
                            data += '%10.4f' % num
                    data += '\n'
        # print the final data
        # get the thermal motion name list
        thermal_motion_name = []
        for i in range(len(self.cycle_name)):
            for j in range(i + 1, len(self.cycle_name)):
                thermal_motion_name.append(self.cycle_name[i] + '-' + self.cycle_name[j])
        # first line
        data += 'Final Data'.center(50, '*') + '\n'
        # second line
        data += 'Node'.rjust(20) + 'Init_Assem'.rjust(20) + 'Hot_Assem'.rjust(20)
        # 3 means the cycle_max_line_load, cycle_min_line_load, cycle_max_head_lift
        for cycle_num, cycle in enumerate(self.cycle_name):
            data += (cycle.rjust(20)) * (3 + len(fatigue_criteria_name))
        data += ('THERMAL'.rjust(20)) * (len(thermal_motion_name))
        data += 'WEAR'.rjust(20)
        data += '\n'
        # third line
        data += 'Num'.rjust(20) + 'LINE_LOAD'.rjust(20) * 2
        for i in range(len(self.cycle_name)):
            data += 'LINE_LOAD'.rjust(20) * 2
            data += 'HEAD_LIFT'.rjust(20)
            for j in range(len(fatigue_criteria_name)):
                data += 'FATIGUE'.rjust(20)
        for i in range(len(thermal_motion_name)):
            data += 'MOTION'.rjust(20)
        data += 'WEAR'.rjust(20)
        data += '\n'
        # fourth line
        data += ''.rjust(60)
        for i in range(len(self.cycle_name)):
            data += 'MAX'.rjust(20) + 'MIN'.rjust(20) + 'MAX'.rjust(20)
            for j in range(len(fatigue_criteria_name)):
                data += fatigue_criteria_name[j].rjust(20)
        for j in range(len(thermal_motion_name)):
            data += thermal_motion_name[j].rjust(20)
        data += 'WEAR'.rjust(20)
        data += '\n'
        # now is the data line
        for node in self.connectivity:
            current_result = self.final_results[node]
            data += '%20u' % node
            data += '%20.2f' % current_result[0]
            data += '%20.2f' % current_result[1]
            for i in range(len(self.cycle_name)):
                data += '%20.2f' % current_result[2][i][0]
                data += '%20.2f' % current_result[2][i][1]
                data += '%20.2f' % current_result[3][i]
                safety_factor = current_result[4][i]
                for j in range(len(fatigue_criteria_name)):
                    data += '%20.4f' % safety_factor[j]
            for value in current_result[5]:
                data += '%20.2f' % value
            data += '%20.2f' % current_result[6][i]
            data += '\n'
        if self.warning:
            data += 'ELEMENT CHECK WARNING!!!'.center(30, '=') + '\n'
            for item in self.warning[1:]:
                data += item + '\n'
        data += 'ELEMENT PRINT FINISHED'.center(50, '=') + '\n'
        return data


class ChgNodes(object):
    def __init__(self, node_number):
        """
        node object initialize
        :param node_number: node number
        """
        self.node_number = node_number
        self.init_coord = []
        self.displacement = []
        self.relative = []
        self.relative_list = []
        self.final_relative = []
        self.cycle_name = ''
        self.cylinder_num = 1
        self.fixed_step = []

    def set_init_coord(self, coord):
        """
        set the noe initial coordinate
        :param coord: a list, [x, y, z]
        :return:
        """
        self.init_coord = coord

    def set_displacement(self, displacement):
        """
        set the node displacement
        :param displacement: a list, defines the displacement value for each step [ [u1, u2, u3], [u1, u2, u3]...]
        :return:
        """
        self.displacement.append(displacement)

    def set_relative(self, relative_value):
        """
        collect the relative value
        :param relative_value: a list [cshear1, cshear2, cslip1, cslip2]
        :return:
        """
        self.relative.append(relative_value)

    def cal_relative(self, fixed_step, cylinder_num, cycle_name):
        # do the calculation for RLM, FDP, but ignore MFFDP
        self.cycle_name = cycle_name
        self.cylinder_num = cylinder_num
        self.fixed_step = fixed_step
        cshear1 = [x[0] for x in self.relative]
        cshear2 = [x[1] for x in self.relative]
        cslip1 = [x[2] for x in self.relative]
        cslip2 = [x[3] for x in self.relative]
        relative_results = []
        final_results = []
        for oper_step in fixed_step:
            shear_list_1 = cshear1[oper_step - 1:oper_step + cylinder_num]
            shear_list_2 = cshear2[oper_step - 1:oper_step + cylinder_num]
            slip_list_1 = cslip1[oper_step - 1:oper_step + cylinder_num]
            slip_list_2 = cslip2[oper_step - 1:oper_step + cylinder_num]
            res_rlm = []
            res_fdp = []
            relative_results.append([])
            final_results.append([])
            for i in range(cylinder_num + 1):
                for j in range(i + 1, cylinder_num + 1):
                    rlm, fdp = setting.relative_motion(slip_list_1[i], slip_list_2[i], slip_list_1[j],
                                                       slip_list_2[j], shear_list_1[i],
                                                       shear_list_2[i], shear_list_1[j], shear_list_2[j])
                    res_rlm.append(rlm)
                    res_fdp.append(fdp)
                    relative_results[-1] = [res_rlm, res_fdp]
            final_results[-1] = [max(res_rlm), max(res_fdp), sum(res_rlm), sum(res_fdp)]
            self.relative_list = relative_results
            self.final_relative = final_results

    def get_init_coord(self):
        return self.init_coord

    def get_displacement(self):
        return self.displacement

    def __str__(self):
        title = ['FIXED']
        for i in range(self.cylinder_num):
            title.append('FIRING_' + str(i + 1))
        sub_title = ['SHEAR1', 'SHEAR2', 'SLIP1', 'SLIP2']
        data = 'NODE PRINT DATA'.center(80, '=') + '\n'

        data += 'BASE INFORMATION'.center(50, '=') + '\n'
        data += 'NODE'.rjust(20) + 'ORIGINAL'.center(30)
        for i in range(len(self.displacement)):
            data += ('STEP_' + str(i + 1)).center(30)
        data += '\n' + 'NUMBER'.rjust(20) + 'X'.rjust(10) + 'Y'.rjust(10) + 'Z'.rjust(10)
        for i in range(len(self.displacement)):
            data += 'U1'.rjust(10) + 'U2'.rjust(10) + 'U3'.rjust(10)
        data += '\n'
        data += str(self.node_number).rjust(20)
        for item in self.init_coord:
            data += '%10.4f' % item
        for i, item in enumerate(self.displacement):
            for value in item:
                data += '%10.4f' % value
        data += '\n'

        data += 'RELATIVE RAW DATA'.center(50, '=') + '\n'
        data += 'NODE'.rjust(20)
        for cycle in self.cycle_name:
            data += cycle.center(40 * (self.cylinder_num + 1))
        data += '\n' + 'NUMBER'.rjust(20)
        for cycle in self.cycle_name:
            for item in title:
                for i in sub_title:
                    data += item.rjust(10)
        data += '\n' + ''.rjust(20)
        for cycle in self.cycle_name:
            for item in title:
                for key in sub_title:
                    data += key.rjust(10)
        data += '\n' + str(self.node_number).rjust(20)
        for oper_step in self.fixed_step:
            for i in range(self.cylinder_num + 1):
                relative_data = self.relative[oper_step + i - 1]
                for item in relative_data:
                    data += '%10.4f' % item
        data += '\n'

        data += 'RELATIVE CALCULATED DATA'.center(50, '=') + '\n'
        data_size = 0
        for i in range(self.cylinder_num + 1):
            data_size += i
        data += 'NODE'.rjust(20)
        for cycle in self.cycle_name:
            for i in range(data_size):
                data += (cycle + '_RLM').rjust(20)
            for i in range(data_size):
                data += (cycle + '_FDP').rjust(20)
            data += (cycle + '_RLM').rjust(20) + (cycle + '_FDP').rjust(20)
            data += (cycle + '_RLM_SUM').rjust(20) + (cycle + '_FDP_SUM').rjust(20)
        data += '\n' + 'NUMBER'.rjust(20)
        temp_data = ''
        for i, item in enumerate(title):
            for j in range(i + 1, len(title)):
                temp_data += (item + '-' + title[j]).rjust(20)
        for cycle in self.cycle_name:
            data += temp_data * 2 + 'FINAL'.rjust(20) * 4
        data += '\n' + str(self.node_number).rjust(20)
        for i in range(len(self.fixed_step)):
            current_relative = self.relative_list[i]
            for item in current_relative:
                for value in item:
                    data += '%20.2f' % value
            current_relative = self.final_relative[i]
            for item in current_relative:
                data += '%20.2f' % item
        data += '\n'
        data += 'NODE PRINT DATA FINISHED'.center(80, '=') + '\n'
        return data


class ChgMaterial(object):
    def __init__(self, name, customer, fea_no, project_name):
        self.name = name
        self.customer = customer
        self.fea_no = fea_no
        self.project_name = project_name
        self.thermal_expansion = [(0.0, 20)]
        self.density = [(0.0, 20)]

    def set_density(self, density):
        # density type array [density, temperature]
        self.density = list(density)

    def set_thermal_expansion(self, expansion_data):
        # expansion_data type array [expansion, temperature]
        self.thermal_expansion = list(expansion_data)

    def print_material_head(self):
        data = ('**==CUSTOMER: ' + self.customer).ljust(50, '=') + '\n'
        data += ('**==PROJECT: ' + self.project_name).ljust(50, '=') + '\n'
        data += ('**==FEA_NO: ' + self.fea_no).ljust(50, '=') + '\n'
        return data

    def print_material_tail(self, data):
        data += '*EXPANSION, ZERO=20' + '\n'
        for item in self.thermal_expansion:
            data += ('%.3e' % item[0]) + ', ' + ('%.1f' % item[1]) + '\n'
        data += '**' + '=' * 50 + '\n'
        return data


class EngineMaterial(ChgMaterial):
    """
    density:
        {
            'dependencies': 0,
            'distributionType': UNIFORM,
            'fieldName': '',
            'table': ((7.83e-09, 20.0),),
            'temperatureDependency': ON
        }
    expansion:
        {
            'dependencies': 0,
            'table': ((1.15e-05, 20.0),),
            'temperatureDependency': ON,
            'type': ISOTROPIC,
            'userSubroutine': OFF,
            'zero': 20.0
        }
    elastic:
        {
            'dependencies': 0,
            'moduli': LONG_TERM,
            'noCompression': OFF,
            'noTension': OFF,
            'table': ((74000.0, 0.33, 20.0), ..., (62000.0, 0.33, 300.0)),
            'temperatureDependency': ON,
            'type': ISOTROPIC
        }
    plastic:
        {
            'dataType': HALF_CYCLE,
            'dependencies': 0,
            'hardening': ISOTROPIC,
            'numBackstresses': 0,
            'rate': OFF,
            'strainRangeDependency': OFF,
            'table': ((699.15, 0.0, 20.0), ..., (1100.0, 0.13475, 20.0)),
            'temperatureDependency': ON
        }
    """

    def __init__(self, name, customer, fea_no, project_name):
        super(EngineMaterial, self).__init__(name=name, customer=customer, fea_no=fea_no, project_name=project_name)
        self.density = []
        self.plastic = []
        self.elastic = []

    def set_elastic(self, elastic_data):
        # elastic_data type array [ modulus, Possion's ratio, temperature]
        self.elastic = list(elastic_data)

    def set_plastic(self, plastic_data):
        # plastic_data type array [ stress, strain, temperature]
        self.plastic = list(plastic_data)

    def get_property(self):
        property_dict = {'NAME': self.name, 'CUSTOMER': self.customer,
                         'FEA_NO': self.fea_no, 'PROJECT': self.project_name, 'ELASTIC': self.elastic,
                         'PLASTIC': self.plastic, 'EXPANSION': self.thermal_expansion, 'DENSITY': self.density}
        return property_dict

    def __str__(self):
        data = '**' + '=' * 50 + '\n'
        data += ('*MATERIAL, NAME= ' + self.name) + '\n'
        if self.density:
            data += '*DENSITY' + '\n'
            for item in self.density:
                data += ('%.3e' % item[0]) + ', ' + ('%.1f' % item[1]) + '\n'
        data += '*ELASTIC' + '\n'
        for item in self.elastic:
            data += ('%10.1f' % item[0]) + ', ' + ('%5.3f' % item[1]) + ', ' + ('%.1f' % item[2]) + '\n'
        if self.plastic:
            data += '*PLASTIC' + '\n'
            for item in self.plastic:
                data += ('%10.2f' % item[0]) + ', ' + ('%.5f' % item[1]) + ', ' + ('%.1f' % item[2]) + '\n'
        data = self.print_material_tail(data)
        return data


class GasketMaterial(ChgMaterial):
    """
    Example:
        gasketThicknessBehavior:
        {
            'dependencies': 0,
            'table':
                        dependencies = 0
                        ((0.0, 0.0), (0.68, 0.0516), ..., (140.0, 0.5094)),
                        dependencies = 1
                        ((0.0, 0.013, 1.0), (5.6, 0.0499, 1.0), (10.0, 0.0722, 1.0), ..., (200.0, 0.1555, 2.0))
            'temperatureDependency': OFF,
            'tensileStiffnessFactor': 0.001,
            'type': DAMAGE,
            'unloadingDependencies': 0,
            'unloadingTable': ((0.0, 0.0, 0.254), (2.28, 0.1824, 0.254), ..., (140.0, 0.5094, 0.5094)),
            'unloadingTemperatureDependency': OFF,
            'variableUnits': STRESS,
            'yieldOnset': 0.1,
            'yieldOnsetMethod': RELATIVE_SLOPE_DROP
        }
        expansion:
        {
            'dependencies': 0,
            'table': ((1.15e-05, 20.0), ..., (1.44e-05, 600.0)),
            'temperatureDependency': ON,
            'type': ISOTROPIC,
            'userSubroutine': OFF,
            'zero': 0.0
        }

        gasketMembraneElastic:
        {
            'dependencies': 0,
            'table': ((1000.0,),),
            'temperatureDependency': OFF
        }

        gasketTransverseShearElastic:
        {
            'dependencies': 0,
            'table':    ((600.0,),),
                        ((600.0, 1.0), (600.0, 2.0))
            'temperatureDependency': OFF,
            'variableUnits': STRESS
        }

        name:
            '0.7-THICK-MATERIAL-CUST'
    """

    def __init__(self, name, customer, fea_no, project_name):
        super(GasketMaterial, self).__init__(name=name, customer=customer, fea_no=fea_no, project_name=project_name)
        self.dependencies = 0
        self.loading = []
        self.unloading = []
        self.membrane = []
        self.transverse = []
        self.type = 'DAMAGE'

    def set_dependencies(self, dependencies, membrane, transverse):
        self.dependencies = dependencies
        self.membrane = membrane
        self.transverse = transverse

    def set_loading(self, loading_data):
        for i in range(self.dependencies + 1):
            self.loading.append([])
        for item in loading_data:
            dependencies = 0
            if len(item) == 3:
                dependencies = int(item[-1]) - 1
            self.loading[dependencies].append(item[:2])

    def set_unloading(self, unloading_data):
        for i in range(self.dependencies + 1):
            self.unloading.append([])
        for item in unloading_data:
            dependencies = 0
            if len(item) > 3:
                dependencies = item[-1]
            self.unloading[dependencies].append(item[:3])

    def set_type(self, loading_type):
        self.type = loading_type

    def get_material(self):
        material_dict = {
            'NAME': self.name,
            'TYPE': self.type,
            'DEPENDENCIES': self.dependencies,
            'EXPANSION': self.thermal_expansion,
            'MEMBRANE': self.membrane,
            'TRANSVERSE': self.transverse,
            'LOADING': self.loading,
            'UNLOADING': self.unloading
        }
        return material_dict

    def __str__(self):
        data = '**' + '=' * 50 + '\n'
        data += ('*GASKET BEHAVIOR, NAME= ' + self.name) + '\n'

        data += '*GASKET ELASTICITY, COMPONENT=TRANSVERSE SHEAR, VARIABLE = STRESS'
        if self.dependencies > 0:
            data += ', DEPENDENCIES=' + str(self.dependencies)
        data += '\n'
        for item in self.transverse:
            for current_item in item:
                data += '%5.1f' % current_item + ','.ljust(5)
            data = data.rstrip(',')
            data += '\n'

        data += '*GASKET ELASTICITY, COMPONENT=MEMBRANE'
        if self.dependencies > 0:
            data += ', DEPENDENCIES=' + str(self.dependencies)
        data += '\n'
        for item in self.membrane:
            for current_item in item:
                data += '%5.2f' % current_item + ','.ljust(5)
            data = data.rstrip(',')
            data += '\n'

        data += '*GASKET THICKNESS BEHAVIOR, DIRECTION=LOADING, TENSILE STIFFNESS FACTOR=0.001, VARIABLE = STRESS, TYPE = ' + self.type
        if self.dependencies > 0:
            data += ', DEPENDENCIES=' + str(self.dependencies)
        data += '\n'
        decimal_number = 1
        load_value_space = (self.loading[-1][0] * (self.dependencies + 1)) / len(self.loading)
        if load_value_space < setting.environment_key['GASKET_DECIMAL_NUMBER']:
            decimal_number = 4
        load_format = '%10.' + str(decimal_number) + 'f'
        for item in self.loading:
            for i, current_item in enumerate(item):
                if i == 0:
                    data += load_format % current_item + ','.ljust(5)
                elif i == 1:
                    data += '%10.4f' % current_item + ','.ljust(5)
                else:
                    data += ','.ljust(5) + '%5.1f' % current_item
            data = data.rstrip(',')
            data += '\n'

        data = self.print_material_tail(data)
        return data


class ChgSection(object):
    """
    section_type:   'GASKET', 'SOLID', 'BEAM'
    properties:     include all the parameters in section definition, dict type
    """

    def __init__(self, customer, fea_no, project_name):
        self.customer = customer
        self.fea_no = fea_no
        self.project_name = project_name
        self.section_type = ''
        self.properties = {}

    def set_type(self, section_type, key_input):
        # key_input is a list, [[key1, value1], [key2, value2]...]
        # example, for gasket section input, the key_input is
        # [['crossSection', 1.0], ['initialGap', 0.50237], ['initialThickness', 0.0], ['initialVoid', 0.0]
        # , ['material': 'BODY'], ['name': 'Section-BODY'], ['stabilizationStiffness': 0.0]]
        #
        # solid section,
        # [['material': 'GK-ALSI7MGCU0C5-T7_EIPITX_2187'], ['name': 'Section-V_HEAD'], ['thickness': 1.0]]
        self.section_type = section_type
        for item in key_input:
            if item[0] == 'name':
                item[1] = item[1][8:]
            self.properties[item[0]] = item[1]

    def get_material(self):
        return [self.properties['name'], self.properties['material'], self.section_type]

    def __str__(self):
        data = '**' + '=' * 50 + '\n'
        if self.section_type == 'GASKET':
            initial_gap = self.properties['initialGap']
            initial_thickness = self.properties['initialThickness']
            stabilize = self.properties['stabilizationStiffness']
            if stabilize > 0:
                data += '**!!!WARNING, STABILIZE IS NOT RECOMMENDED IN GASKET SECTION DEFINITION' + '\n'
            data += '*GASKET SECTION, ELSET=' + self.properties['name'] + ', BEHAVIOR=' + self.properties[
                'material']
            if stabilize > 0:
                data += ','.ljust(5) + 'STABILIZATION STIFFNESS=' + '%5.4f' % stabilize
            data += '\n'
            data += '%5.4f' % initial_thickness + ','.ljust(5) + '%5.4f' % initial_gap + ','.ljust(5)
        elif self.section_type == 'SOLID':
            data += '*SOLID SECTION, ELSET=' + self.properties['name'] + ', MATERIAL=' + self.properties[
                'material'] + '\n'
        elif self.section_type == 'BEAM':
            data += '*BEAM SECTION, ELSET=' + self.properties['name'] + ', MATERIAL=' + self.properties[
                'material'] + ', SECTION=' + self.properties['profile'] + '\n'
        return data


class FatigueData(object):
    def __init__(self, set_name, material_name, initial_gap, fatigue_id, fixload, preload, fatigue_name):
        self.set_name = set_name
        self.material = material_name
        self.inital_gap = initial_gap
        self.fatigue_id = fatigue_id
        self.fixload = fixload
        self.preload = preload
        self.fatigue_name = fatigue_name
        self.fatigue_data = {}

    def set_fatigue_data(self, fatigue_value):
        for i, fixload in enumerate(self.fixload):
            self.fatigue_data[fixload] = {}
            current_fatigue = fatigue_value[i]
            start_num = 0
            end_num = len(self.fatigue_name)
            for j, preload in enumerate(self.preload):
                self.fatigue_data[fixload][preload] = current_fatigue[start_num: end_num]
                start_num = end_num
                end_num += len(self.fatigue_name)
        return None

    def __str__(self):
        data = '**' + '=' * 50 + '\n'
        data += ('SET NAME: ' + str(self.set_name)).center(50, '*') + '\n'
        data += ('MATERIAL NAME: ' + str(self.material)).center(50, '*') + '\n'
        data += ('FATIGUE NAME: ' + str(self.fatigue_name)).center(50, '*') + '\n'
        data += ('FATIGUE ID: ' + str(self.fatigue_id)).center(50, '*') + '\n'
        data += ('FIX LOAD: ' + str(self.fixload)).center(50, '*') + '\n'
        data += ('PRE LOAD: ' + str(self.preload)).center(50, '*') + '\n'
        data += ('FATIGUE DATA: ' + str(self.fatigue_data)).center(50, '*') + '\n'
        data += '**' + '=' * 50 + '\n'
        return data


class BoreNodeLayer(object):
    """
        Calculate the Fourier Coefficient and Phase angle for all steps, results are for diameter, not radius
    """

    def __init__(self, cylinder_num, z_depth, bore_node_dict, bore_x, bore_y, radius, bore_unique_center,
                 fourier_order):
        """
        initialize the bore_distortion class, the object will refer to a certain layer
        :param cylinder_num:            the cylinder number, int type, used as a key for dict
        :param z_depth:                 the depth value, float type, used as a key for dict
        :param bore_node_dict:          node displacement dict, key: node number, value: original node coord and
                                        displacement list, as   {   node_num1: [[x,y,z], [u1, u2, u3]... ],
                                                                    node_num2: [[x,y,z], [u1, u2, u3]... ],
                                                                    ...
                                                                }
        :param bore_x:                  circle center coordinate x
        :param bore_y:                  circle center coordinate x
        :param radius:                  nominal bore radius
        :param bore_unique_center:      global setting, defined in setting file, Boolean type
                                        True:   all layers in one cylinder will use same bore center. Standard method
                                                for FEA, SIMALB also.
                                        False:  each layer has its own bore center, will be calculated using least
                                                square method. For the test value, see X13, BFCEC project, the bore
                                                distortion equipment used own center for each layer to get the Fourier
                                                value.
        :param fourier_order:           global setting, defined in setting file, int type, default value is 12. The value
                                        include 0 order value.
        """
        self.center = []
        self.bore_nodes = bore_node_dict
        self.cylinder_num = cylinder_num
        self.z_depth = z_depth
        self.fourier_result = []
        self.bore_x = bore_x
        self.bore_y = bore_y
        self.radius = radius
        self.bore_unique_center = bore_unique_center
        self.fourier_order = fourier_order
        self.angle_data = []
        self.angle_list = []

    def set_displacement(self, node_num, displacement_list):
        """
        set the displacement value for node in this object
        :param node_num:                node number, defined as a key
        :param displacement_list:       displacement list, [u1, u2, u3] for one step
        :return:                        None
        """
        self.bore_nodes[node_num].append(displacement_list)

    def _set_circle_center(self):
        """
        use the node list at each step, calculate the circle center for nodes in one layer of one cylinder,
        depending on the bore_unique_center setting.
        the center value is [
                                [center_x, center_y, radius]
                                [center_x, center_y, radius]
                                ...
                            ]
        :return:            None
        """
        node_count = len(self.bore_nodes)
        # bore_nodes.items()[0], get the first element of bore_nodes, bore_nodes.items()[0][1] is the value
        step_count = len(self.bore_nodes.items()[0][1]) - 1
        center_all_steps = []
        if self.bore_unique_center:  # using unique circle center for all layers in one cylinder.
            for step_num in range(step_count):
                center_all_steps.append([self.bore_x, self.bore_y, self.radius])
        else:  # using different circle center for each layer in one cylinder.
            for step_num in range(step_count):
                disp = []
                for key, value in self.bore_nodes.items():
                    x = value[0][0] + value[step_num + 1][0]
                    y = value[0][1] + value[step_num + 1][1]
                    z = value[0][2] + value[step_num + 1][2]
                    disp.append([x, y, z])
                sum_x1 = 0
                sum_y1 = 0
                sum_x2 = 0
                sum_y2 = 0
                sum_x3 = 0
                sum_y3 = 0
                sum_xy = 0
                sum_x1y2 = 0
                sum_x2y1 = 0
                for current_node in disp:
                    x, y = current_node[0:2]
                    sum_x1 = sum_x1 + x
                    sum_y1 = sum_y1 + y
                    sum_x2 = sum_x2 + x ** 2
                    sum_y2 = sum_y2 + y ** 2
                    sum_x3 = sum_x3 + x ** 3
                    sum_y3 = sum_y3 + y ** 3
                    sum_xy = sum_xy + x * y
                    sum_x1y2 = sum_x1y2 + x * y ** 2
                    sum_x2y1 = sum_x2y1 + x ** 2 * y
                c = node_count * sum_x2 - sum_x1 ** 2
                d = node_count * sum_xy - sum_x1 * sum_y1
                e = node_count * sum_x3 + node_count * sum_x1y2 - (sum_x2 + sum_y2) * sum_x1
                g = node_count * sum_y2 - sum_y1 ** 2
                h = node_count * sum_x2y1 + node_count * sum_y3 - (sum_x2 + sum_y2) * sum_y1
                value_a = (h * d - e * g) / (c * g - d * d)
                value_b = (h * c - e * d) / (d * d - g * c)
                value_c = -(value_a * sum_x1 + value_b * sum_y1 + sum_x2 + sum_y2) / node_count
                center_x = -value_a / 2
                center_y = -value_b / 2
                radius = (value_a ** 2 + value_b ** 2 - 4 * value_c) ** 0.5 / 2
                center_all_steps.append([center_x, center_y, radius])
        self.center = center_all_steps

    def cal_fourier(self):
        """
        calculate the fourier coefficient, for diameter, not for radius.
        fourier_result:         type: list
                                [
                                step1:[
                                        [coefficient_0, phase_0],
                                        [coefficient_1, phase_1],
                                        [coefficient_2, phase_2],
                                        ......
                                        [coefficient_12, phase_12]
                                      ]
                                step2:[
                                        [coefficient_0, phase_0],
                                        [coefficient_1, phase_1],
                                        [coefficient_2, phase_2],
                                        ......
                                        [coefficient_12, phase_12]
                                      ]
                                ...
                                ]

        :return: obtain the fourier and phase angle for all steps for this layer
        """
        fourier_order = self.fourier_order
        self._set_circle_center()  # get the layer center coordinate, and normal radius, it is a list.
        for i, center_coord in enumerate(self.center):
            center_x = center_coord[0]
            center_y = center_coord[1]
            radius = center_coord[2]
            current_step_result = []
            self.fourier_result.append([])
            for key, value in self.bore_nodes.items():
                x = value[0][0] + value[i + 1][0]  # current node X coordinate
                y = value[0][1] + value[i + 1][1]  # current node Y coordinate
                length = ((x - center_x) ** 2 + (y - center_y) ** 2) ** 0.5  # current length from node to center
                theta = math.acos((x - center_x) / length)  # current angle, unit: radian
                if y < center_y:  # using acos to get the angle, if Y < Center_Y, 2pi - theta
                    theta = 2 * math.pi - theta
                delta_r = length - radius
                current_step_result.append([key, x, y, length, theta, delta_r])
            sorted(current_step_result, key=lambda temp: temp[4])  # sort the list using theta
            temp = []
            delta_r_list = [item[-1] for item in current_step_result]
            for j in range(fourier_order):
                res1 = 0
                res2 = 0
                for item in current_step_result:
                    res1 += item[-1] * math.cos((j + 1) * item[-2])  # sum(delta_R * cos(order*theta)
                    res2 += item[-1] * math.sin((j + 1) * item[-2])  # sum(delta_R * sin(order*theta)
                temp_a = 2 * res1 / len(current_step_result)  # mean cos value
                temp_b = 2 * res2 / len(current_step_result)  # mean sin value
                coefficient = (temp_a ** 2 + temp_b ** 2) ** 0.5 * 2000  # Fourier coefficient
                phase = math.acos(temp_a * 2000 / coefficient)  # Phase angle
                if temp_b < 0:
                    phase = 2 * math.pi - phase
                temp.append([coefficient, phase])
            temp.insert(0, [sum(delta_r_list) / len(delta_r_list) * 2000, 0])
            self.fourier_result[-1] = temp

    def cal_angle_data(self):
        """
        create a standard format, based on angle from environment setting
        :return: list type,set the angle_data
        """
        angle_space = setting.environment_key['BORE_DISTORTION_ANGLE']
        angle_list = []
        angle = 0
        while True:
            if angle > 360:
                break
            angle_list.append(angle * math.pi / 180)
            angle += angle_space
        self.angle_list = angle_list
        for i in range(len(self.center)):
            temp = []
            for angle in angle_list:
                sum_delta_r = 0
                for j in range(self.fourier_order + 1):
                    sum_delta_r += self.fourier_result[i][j][0] * math.cos(j * angle - self.fourier_result[i][j][1])
                temp.append(sum_delta_r / 2000)
            self.angle_data.append(temp)

    def get_bore_nodes(self):
        return self.bore_nodes

    def get_z_depth(self):
        return self.z_depth

    def get_fourier(self):
        return self.fourier_result

    def __str__(self):
        data = 'BORE DISTORTION PRINT START' + '\n'
        data += 'Cylinder Num:'.rjust(30) + str(self.cylinder_num + 1).rjust(20) + '\n'
        data += 'Z Depth:'.rjust(30) + str(self.z_depth).rjust(20) + '\n'
        data += 'Fourier Order:'.rjust(30) + str(self.fourier_order).rjust(20) + '\n'
        data += 'Using Unique Bore Center?'.rjust(30) + str(self.bore_unique_center).rjust(20) + '\n'
        data += 'Normal Center X:'.rjust(30) + '%20.3f' % self.bore_x + '\n'
        data += 'Normal Center Y:'.rjust(30) + '%20.3f' % self.bore_y + '\n'
        data += 'Normal Bore Radius:'.rjust(30) + '%20.3f' % self.radius + '\n'

        data += 'LAYER NODE DISPLACEMENT PRINT START'.center(30, '=') + '\n'
        print_title = True
        for key, value in self.bore_nodes.items():
            if print_title:
                data += 'NODE NUM'.rjust(20)
                data += 'ORIGINAL_DISP_X'.rjust(20) + 'ORIGINAL_DISP_Y'.rjust(20) + 'ORIGINAL_DISP_Z'.rjust(20)
                for j in range(1, len(value)):
                    data += ('STEP_' + str(j) + '_U1').rjust(20) + ('STEP_' + str(j) + '_U2').rjust(20) + (
                            'STEP_' + str(j) + '_U3').rjust(20)
                data += '\n'
                print_title = False
            data += '%20u' % key
            for i, disp in enumerate(value):
                for disp_value in disp:
                    data += '%20.4f' % disp_value
            data += '\n'
        data += 'LAYER NODE DISPLACEMENT PRINT DONE'.center(30, '=') + '\n'

        data += 'LAYER CENTER COORDINATE PRINT START'.center(30, '=') + '\n'
        for i, value in enumerate(self.center):
            data += ('STEP_' + str(i + 1) + '_X').rjust(20) + ('STEP_' + str(i + 1) + '_Y').rjust(20) + (
                            'STEP_' + str(i + 1) + '_Z').rjust(20)
        data += '\n'
        for i, value in enumerate(self.center):
            for disp in value:
                data += '%20.3f' % disp
        data += '\n'
        data += 'LAYER CENTER COORDINATE PRINT DONE'.center(30, '=') + '\n'

        data += 'FOURIER RESULTS PRINT START'.center(30, '=') + '\n'
        data += 'ORDER'.rjust(20)
        for i in range(self.fourier_order + 1):
            data += str(i).rjust(20)*2
        data += '\n'
        data += ''.rjust(20)
        for i in range(self.fourier_order):
            data += 'COEFFICIENT'.rjust(20) + 'PHASE_ANGLE'.rjust(20)
        data += '\n'
        for i in range(len(self.center)):
            data += ('STEP' + str(i + 1)).rjust(20)
            current_result = self.fourier_result[i]
            for j, value in enumerate(current_result):
                data += '%20.2f' % value[0] + '%20.4f' % value[1]
            data += '\n'
        data += 'FOURIER RESULTS PRINT DONE'.center(30, '=') + '\n'

        data += 'STANDARD DISTORTION DATA PRINT START'.center(30, '=') + '\n'
        data += 'ANGLE'.rjust(20)
        for angle in self.angle_list:
            data += '%20.1f' % angle
        data += '\n'
        for i in range(len(self.center)):
            data += ('STEP' + str(i + 1)).rjust(20)
            delta_r_list = self.angle_data[i]
            for delta_r in delta_r_list:
                data += '%20.5f' % delta_r
            data += '\n'
        data += 'STANDARD DISTORTION DATA PRINT DONE'.center(30, '=') + '\n'
        return data


class CamNode(object):
    """
    store as dict type, key: node_num, value [[coord_x, coord_y, coord_z], [u1, u2, u3], [u1, u2, u3]...]
    """
    def __init__(self, cam_node_dict):
        self.cam_node_dict = cam_node_dict
        self.cam_distortion = {}
        self.sort_node = []
        self.total_step_num = 0

    def set_displacement(self, node_num, displacement_list):
        self.cam_node_dict[node_num].append(displacement_list)

    def get_displacement(self):
        return self.cam_node_dict

    def cal_cam_distortion(self):
        cam_node = []
        for key, value in self.cam_node_dict.items():
            cam_node.append([key, value[0][0]])
            self.cam_distortion[key] = []
        cam_node = sorted(cam_node, key=lambda temp: temp[1])  # sort the list using theta
        self.sort_node = [node[0] for node in cam_node]
        start_node = cam_node[0][0]
        end_node = cam_node[-1][0]
        x0 = cam_node[0][1]
        x1 = cam_node[-1][1]
        self.total_step_num = len(self.cam_node_dict[key])
        for step_num in range(1, self.total_step_num):
            z0 = self.cam_node_dict[start_node][step_num][2]
            z1 = self.cam_node_dict[end_node][step_num][2]
            slope = (z1-z0)/(x1-x0)
            intercept = z1 - slope * x1
            for key, value in self.cam_node_dict.items():
                x = value[0][0]
                z = value[step_num][2]
                distance = 1000 * (x * slope + intercept - z) / (slope**2 + 1)**0.5
                self.cam_distortion[key].append(distance)

    def get_cam_distortion(self):
        return self.cam_distortion

    def __str__(self):
        data = 'CAM DISTORTION PRINT START'.center(50, '*') + '\n'
        data += 'NODE'.rjust(20)
        for step_num in range(1, self.total_step_num):
            data += ('STEP_' + str(step_num)).rjust(20)
        data += '\n'
        for node in self.sort_node:
            data += '%20u' % node
            value = self.cam_distortion[node]
            for item in value:
                data += '%20.3f' % item
            data += '\n'
        data = 'CAM DISTORTION PRINT DONE'.center(50, '*') + '\n'
        return data






