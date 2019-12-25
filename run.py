import os
import sys
# Full path (with name) to this file
absPath = os.path.abspath('__file__')

# Full directory specification
absDir = os.path.dirname(absPath)

# Full subdirectory specification
folder_list = ['core', 'conf', 'db', 'lib']
for folder in folder_list:
    subDir = os.path.join(absDir, folder)
    sys.path.append(subDir)

for files in sys.path:
    print('*'*10 + files)

# myModule is located in subDir
import src


# BASE_PATH = os.path.dirname(os.path.dirname(__file__))
# sys.path.append(BASE_PATH)
# sys.path.append('/scratch/postprocess_chg/')

# from core import src

print('111')

if __name__ == '__main__':
    print('222')
    src.abaqus_process('/data/Wei/FEA19-0840/FEA19-0840_backup.json')
