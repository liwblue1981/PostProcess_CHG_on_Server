import os, sys

BASE_PATH = os.path.dirname(os.path.dirname('__file__'))
# Full path (with name) to this file
absPath = os.path.abspath('__file__')

# Full directory specification
absDir = os.path.dirname(absPath)

# Full subdirectory specification
folder_list = ['core', 'conf', 'db', 'lib']
for folder in folder_list:
    subDir = os.path.join(absDir, folder)
    sys.path.append(subDir)


environment_key = {
    'VIEW_NAME': 'Viewport: 1',
    # create the new set to opened odb, need to wait second to make sure the new set is created successfully.
    'CACHE_TIME': 1,
    'GASKET_ALL_NODES': 'NGASKET_AUTO',
    # use input the bore node set for manually calculate the bore distortion, program will auto create a new set in case
    # several node sets are provided by user. This set is a combined set with all bore nodes.
    'BORE_DISTORTION_NODES': 'NBORE_AUTO',
    # Maximum Fourier order calculated by program, 12 should be enough already.
    'FOURIER_ORDER': 12,
    # using unique bore center for all layers in one cylinder, default is true, is set false, will calculate the center
    # and radius for each layer using least squire method
    'BORE_UNIQUE_CENTER': True,
    # maximum iteration times to find the correct interpolation for auto bore distortion calculation.
    'MAX_PATH_ITERATION': 10,
    # using path to interpolate displacement, if failed with current radius, program will automatically increase radius
    # with this value
    'BORE_RADIUS_SEARCH_AUTO_INCREMENT': 0.01,
    # the minimum space between two adjacent layers for bore distortion, will separate the layers based on Z coordinate
    'BORE_DISTORTION_SPACE': 0.1,
    # the bore distortion will be output using a standard format, every 5 degree will have one value
    'BORE_DISTORTION_ANGLE': 5,
    # Assumed the interpolation is succeed when path value length larger than 5.
    'BORE_DISTORTION_INTERPOLATION_DONE': 5,
    # Shift the start angle to avoid less interpolated value than expected, for automatically bore distortion only.
    'BORE_DISTORTION_SHIFT_ANGLE': 0.5,
    # Gasket behavior output, default format: 10.123, if (max_load / load_number) < 3, it will be 4, as 10.1234
    # e.g. max_load is 200, load_number is 20, line load output is 10.123, typically FB format
    # e.g. max_load is 10, load_number is 20, line load output is 10.1234, typically rubber LDs.
    'GASKET_DECIMAL_NUMBER': 3,
    'FATIGUE_CRITERIA_NAME': ['GOODMAN', 'GERBER', 'AVERAGE', 'DANGVON', 'SWT'],
    # max_s11 / min_s11, if greater than 100, means the element is not meshed fine enough.
    'STRESS_DIFFER_RATIO': 100,
    # Scale the current plot to make legend do not overlap with displayed object
    'TEMPERATURE_ZOOM': 0.9,
    # Translate the current plot to make legend do not overlap with displayed object
    'TEMPERATURE_XPAN': 0.1,
    # Rotate the current plot to make legend do not overlap with displayed object
    'TEMPERATURE_ROTATE': -180,
}


def relative_motion(slip1_x, slip1_y, slip2_x, slip2_y, shear1_x, shear1_y, shear2_x, shear2_y):
    """
    calculate the node relative motion data, unit um, MPa*um
    the shear stress is vector, using absolute value to get the average
    :param slip1_x: step_1 data, x direction - slip
    :param slip1_y: step_1 data, y direction - slip
    :param slip2_x: step_2 data, x direction - slip
    :param slip2_y: step_2 data, y direction - slip
    :param shear1_x: step_1 data, x direction - shear
    :param shear1_y: step_1 data, y direction - shear
    :param shear2_x: step_2 data, x direction - shear
    :param shear2_y: step_2 data, y direction - shear
    :return: RLM, FDP
    """
    slip1_data = abs(slip1_x - slip2_x) * 1000
    slip2_data = abs(slip1_y - slip2_y) * 1000
    shear1_data = (abs(shear1_x) + abs(shear2_x)) / 2
    shear2_data = (abs(shear1_y) + abs(shear2_y)) / 2
    res_rlm = (slip1_data ** 2 + slip2_data ** 2) ** 0.5
    res_fdp = (shear1_data * slip1_data) + (shear2_data * slip2_data)
    return res_rlm, res_fdp
