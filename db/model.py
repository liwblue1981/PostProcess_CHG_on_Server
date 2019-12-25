import math
import numpy as np
import time


class RecordLog:
    """
    used to record the process status
    """
    def __init__(self):
        self.record = []

    def add_record(self, arr):
        arr.insert(0, time.strftime("%X", time.localtime()))
        self.record.append(arr)
        print(str(arr))

    def write_record(self, log_file):
        with open(log_file, 'at', encoding='utf-8') as f:
            f.write('Reading from ODB Start'.center(50, '#'))
            for item in self.record:
                f.write(str(item[0]).ljust(30) + str(item[1]).ljust(50) + str(item[2]).ljust(30) + '\n')

    def __str__(self):
        return str(self.record)


class ChgElements:
    """
    element object, include all the required data for element, stress, strain, coordinate, area, angle...
    """
    def __init__(self, number, connectivity):
        """
        initialize the elements object
        :param number: element number
        :param connectivity: the construction of element
        """
        self.number = number
        self.connectivity = connectivity
        self.node_array = []
        self.section = 0
        self.area = 0
        self.angle = 0
        self.width = 0
        self.bore_center = []
        self.center_coord_list = []
        self.step_results = {}
        for node in connectivity:
            self.step_results[node] = []
        # final results only include max, min, head lift, relative motion for operation and results for initial assembly
        self.final_results = []

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
        :param node1: node array [x, y]
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
        :param node_array: a list, 8 nodes for max, each node is a list, include initial coord [x,y,z] and displacement
                           for each step, [u1, u2, u3], like [[x,y,z], [u1, u2, u3], [u1, u2, u3]...]
        :return: None
        """
        self.node_array = node_array

    def set_bore_center(self, cylinder_num, center_x, center_y):
        """
        set the element belongs to which cylinder, and set its center x and y.
        :param cylinder_num: cylinder number of the element belongs to.
        :param center_x: cylinder center x coordinate
        :param center_y: cylinder center y coordinate
        :return:
        """
        self.bore_center = [cylinder_num, center_x, center_y]

    def set_center_coord(self):
        """
        element centroid coordinate, will change according to different steps
        :return:
        """
        node = self.node_array
        node1 = node[0]
        node2 = node[1]
        node3 = node[2]
        if len(node) == 8:
            node4 = node[3]
            node_list = list(zip(node1, node2, node3, node4))
        else:
            node_list = list(zip(node1, node2, node3))
        for current_step in node_list:
            node_x = np.array([x[0] for x in current_step])
            node_y = np.array([x[1] for x in current_step])
            node_z = np.array([x[2] for x in current_step])
            self.center_coord_list.append([node_x, node_y, node_z])

    def set_area_angle(self):
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
        :return:area, angle, width
        """
        node = self.node_array
        center = self.bore_center
        node1 = node[0][0]
        node2 = node[1][0]
        node3 = node[2][0]
        area1 = self._getarea(node1, node2, node3)
        side_diagonal_1 = self._getlength(node1, node3)

        self.width = 2 * area1 / side_diagonal_1
        if len(node) == 8:
            node4 = node[3][0]
            area2 = self._getarea(node2, node3, node4)
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
            self.angle = math.acos((element_x - center[0]) * 180 / radius / math.pi)
        else:
            self.angle = 360 - math.acos((element_x - center[0]) * 180 / radius / math.pi)

    def set_result(self, node_id, result):
        """
        set the element results, it is a dict type
        :param node_id: one element has 8 nodes, and each nodes in each step has its own value,
        :param result: a list, for each step, include stress, strain, cslip, cstress
        :return:
        """
        self.step_results[node_id].append(result)


class ChgNodes:
    def __init__(self, node_number):
        """
        node object initialize
        :param node_number: node number
        """
        self.node_number = node_number
        self.init_coord = []
        self.displacement = []
        # list [[S11, E11], [S11, E11], ...]
        self.result = []
        self.relative = []

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

    def get_init_coord(self):
        return self.init_coord

    def get_displacement(self):
        return self.displacement

    def get_result(self):
        return self.result
