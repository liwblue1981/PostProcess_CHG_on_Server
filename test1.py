import test

a = [229.77, 0.1003, 4.74, 5.2972, 1.41, 4.5540, 0.12, 2.2232, 0.83, 1.5949, 0.39, 0.5893, 0.13, 3.1154, 0.19, 4.1836,
     0.22, 4.0103, 0.15, 3.9503, 0.05, 5.0122, 0.09, 5.4836]
b = a.split()

opened_odb = session.openOdb(name='D:/Programming/chg_readin/FEA19-0840.odb')
opened_odb = odbAccess.openOdb(name='D:/Programming/chg_readin/FEA19-0840.odb')

odb_steps = opened_odb.steps.keys()

add_cam_node_list = ["32647535,  32647638,  32648808,  32649175,  32650436,  32650525,  32651690,  32652031",
                     "32636220,  32636348,  32637814,  32638039,  32641304,  32641713,  32642907,  32643188,   32644151,  32644689"]
if add_cam_node_list:
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
            # wait for 1 sec to make sure the new node set is created successfully
            time.sleep(1)
            # find the node in node set will be much faster than from all node
            # node_region = opened_odb.rootAssembly.instances['PART-1-1'].nodes can also find the right node
            node_region = opened_odb.rootAssembly.instances['PART-1-1'].nodeSets[node_set_name]
            for node in node_region.nodes:
                temp_result[node.label] = [node.coordinates]
        except Exception as e:
            print (e)
        cam_node_result[node_set_name] = CamNode(temp_result)

with open('D:/Programming/chg_readin/FEA19-0840_userinput_auto.json', 'rt') as f:
    input_data = json.load(f)


