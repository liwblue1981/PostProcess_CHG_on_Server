#coding=utf-8
import sys, os
# myModule is located in subDir
sys.path.append(os.path.dirname(os.getcwd()))
from core import src

if __name__ == '__main__':
    src.abaqus_process('/data/Wei/FEA19-0840/FEA19-0840_userinput.json')
