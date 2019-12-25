import os, sys

file = r'D:\New_Work\aa\EV01 FEA input20191224\Temperature_hot_Max.inp'

with open(file,'rb') as f:
    line = f.readline()
    i = 0
    while i < 100:
        line = line.decode('gbk')
        print(line)
        i += 1