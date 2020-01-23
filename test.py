from abaqus import *
from abaqusConstants import *
from viewerModules import *
from odbAccess import *
from odbMaterial import *
from odbSection import *
import math

import time
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
        data = 'CAM DISTORTION PRINT START' + '\n'
        data += 'NODE'.rjust(20)
        for step_num in range(self.total_step_num):
            data += ('STEP_' + str(step_num + 1)).rjust(20)
        data += '\n'
        for node in self.sort_node:
            data += '%20u' % node
            value = self.cam_distortion[node]
            for item in value:
                data += '%20.3f' % item
            data += '\n'
        return data

cam_check = False
cam_distortion_step = "2,3,5"
add_cam_node_list = ["32647535,  32647638,  32648808,  32649175,  32650436,  32650525,  32651690,  32652031", "32636220,  32636348,  32637814,  32638039,  32641304,  32641713,  32642907,  32643188,   32644151,  32644689"]
if add_cam_node_list and cam_distortion_step:
    cam_check = True
    cam_node_result = {}
    for i, item in enumerate(add_cam_node_list):
        temp_result = {}
        current_list = item.split(',')
        node_list = []
        node_set_name = 'AUTO_ADD_CAM' + str(i + 30)
        for node in current_list:
            node_list.append(int(node))
        _ = opened_odb.rootAssembly.instances['PART-1-1'].NodeSetFromNodeLabels(name=node_set_name,
                                                                                nodeLabels=tuple(node_list))
        # wait for 1 sec to make sure the new node set is created successfully
        time.sleep(1)
        # find the node in node set will be much faster than from all node
        # node_region = opened_odb.rootAssembly.instances['PART-1-1'].nodes can also find the right node
        node_region = opened_odb.rootAssembly.instances['PART-1-1'].nodeSets[node_set_name]
        for node in node_region.nodes:
            temp_result[node.label] = [node.coordinates]
        cam_node_result[node_set_name] = CamNode(temp_result)

for step_num, current_step in enumerate(odb_steps):
    if cam_check:
        for node_set in cam_node_result:
            node_region = opened_odb.rootAssembly.instances['PART-1-1'].nodeSets[node_set]
            current_result = opened_odb.steps[current_step].frames[-1].fieldOutputs['U'].getSubset(
                region=node_region)
            for item in current_result.values:
                cam_node_result[node_set].set_displacement(item.nodeLabel, item.data)

for node_set in cam_node_result:
    cam_node_result[node_set].cal_cam_distortion()


