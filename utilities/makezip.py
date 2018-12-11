import os
from os import listdir
from os.path import isfile, join
import zipfile

if __name__ == "__main__":
    cwd = os.getcwd()
    rawpath = os.path.join(cwd, 'reprojected')
    allfiles= [f for f in listdir(rawpath) if isfile(join(rawpath, f))]
    af = [f.split('.')[0] for f in listdir(rawpath) if isfile(join(rawpath, f))]
    onlyfiles =  (list(set(af)))

    opfolder = os.path.join(cwd, 'output')
    if not os.path.exists(opfolder):
        os.mkdir(opfolder)
    for file in onlyfiles: 
        zfilename = os.path.join(opfolder,file+'.zip' )
        with zipfile.ZipFile(zfilename, 'w') as myzip:
            lstFileNames = [f1 for f1 in allfiles if f1.split('.')[0] == file]
            for f in lstFileNames:   
                myzip.write(os.path.join(rawpath,f), f)