import config
import ShapelyHelper, EvaluationFileOps
from shapely.ops import unary_union
from shapely.geometry.base import BaseGeometry
from shapely.geometry import shape, mapping, shape, asShape
from shapely.geometry import MultiPolygon, MultiPoint, MultiLineString
from shapely.validation import explain_validity
from shapely import speedups
if speedups.available:
        speedups.enable()   

import fiona 
import time
import shutil
from fiona.crs import to_string
import  json, geojson
from sqlitedict import SqliteDict
import os, sys
from os import listdir
from os.path import isfile, join
import logging
import Colorer
import zipfile

# LOG_FILENAME = "runlog.log"
loggers = {}
def configure_logging(name):
    global loggers
    if loggers.get(name):
        return loggers.get(name)
    else:    
        logger = logging.getLogger("evals logger")
        logger.setLevel(logging.DEBUG)
        # Format for our loglines
        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        # Setup console logging
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)
        ch.setFormatter(formatter)
        logger.addHandler(ch)
        # Setup file logging as well
        # fh = logging.FileHandler(LOG_FILENAME)
        # fh.setLevel(logging.DEBUG)
        # fh.setFormatter(formatter)
        # logger.addHandler(fh)
        logger.propagate = False
        return logger

curPath = os.path.dirname(os.path.realpath(__file__))

class OpStatus():
    
    def __init__(self):
        self.stages = {}
        for i in range(1,8):
            x = {'status':0, 'errors':[],'warnings':[], 'info':[], 'debug':[], 'success':[], 'statustext':""}
            self.stages[i] = x
        self.current_milli_time = lambda: int(round(time.time() * 1000))
    
    def add_warning(self, stage, msg):
        self.stages[stage]['warnings'].append({'msg':msg,'time':self.current_milli_time()})

    def add_success(self, stage, msg):
        self.stages[stage]['success'].append({'msg':msg,'time':self.current_milli_time()})
        
    def add_error(self, stage, msg):
        self.stages[stage]['errors'].append({'msg':msg,'time':self.current_milli_time()})
        
    def add_info(self, stage, msg):
        self.stages[stage]['info'].append({'msg':msg,'time':self.current_milli_time()})

    def add_debug(self, stage, msg):
        self.stages[stage]['debug'].append({'msg':msg,'time':self.current_milli_time()})

    def set_statustext(self, stage, msg):
        self.stages[stage]['statustext'] = msg

    def set_status(self, stage, status, statustext=None):
        self.stages[stage]['status']= status
        if statustext:
            self.stages[stage]['statustext']= statustext

    def get_allstatuses(self):
        return json.dumps(self.stages)


class ConvertEvaluation():
    '''
    There are seven stages to the process 
    1. Check if Zip file unzips properly
    2. Check if there is a Shapefile in the zip
    3. Check if the features and schema is correct
    4. Reproject the file
    5. Simplify the file
    6. Convert to geojson
    7. Check performance: 
        - Number of features
        - Errors in intersection
        - time required

    Status: 
    0 - Error / Failed
    1 - Success /OK
    2 - Warnings

    '''
    def __init__(self):
        self.SOURCE_FILE_SHARE = os.path.join(curPath, config.inputs['directory'])
        self.WORKING_SHARE = os.path.join(curPath, config.working['directory'])
        # final GEOJSON
        self.OUTPUT_SHARE = os.path.join(curPath, config.geojsonoutput['directory'])
        self.logger = configure_logging('evals logger')
        self.opstatus = OpStatus()

    def convert(self):
        self.logger.info("Geodesign Hub Evaluations Converter")    
        myShpFileHelper = EvaluationFileOps.ShapefileHelper(self.opstatus)
        self.logger.info("Reading source files.. ")
        curPath = os.path.dirname(os.path.realpath(__file__))
        allBounds = []
        if not os.path.exists(self.WORKING_SHARE):
            os.mkdir(self.WORKING_SHARE)
        if not os.path.exists(self.OUTPUT_SHARE):
            os.mkdir(self.OUTPUT_SHARE)
        try:
            assert os.path.exists(self.SOURCE_FILE_SHARE)
        except AssertionError as e:
            self.logger.error("Source file directory does not exist, please check config.py for correct filename and directory")

        zipfiles = [f1 for f1 in listdir(self.SOURCE_FILE_SHARE) if (os.path.splitext(f1)[1] == '.zip')]
        ferror = False
        for z in zipfiles:
            try:
                zip_ref = zipfile.ZipFile(os.path.join(self.SOURCE_FILE_SHARE,z), 'r')
                zip_ref.extractall(self.SOURCE_FILE_SHARE)
                zip_ref.close()
            except Exception as e:
                ferror = True
                self.opstatus.set_status(stage=1, status=0, statustext ="Problem with opening and reading Zip file contents.")
                self.opstatus.add_error(stage=1, msg = "Problems with your zip file, please make sure that it is not curropt.")

        if not ferror: 
            self.opstatus.set_status(stage=1, status=1, statustext ="Zip file read without problems")
            self.opstatus.add_success(stage=1, msg = "File contents unzipped successfully")
        
        inputfiles = [f for f in listdir(self.SOURCE_FILE_SHARE) if (isfile(os.path.join(self.SOURCE_FILE_SHARE, f)) and (os.path.splitext(f)[1] == '.shp'))]
        myFileOps = EvaluationFileOps.FileOperations(self.SOURCE_FILE_SHARE, self.OUTPUT_SHARE, self.WORKING_SHARE,self.opstatus)
        allGJ = {}
        if inputfiles:
            self.logger.warning("Incorrect zip file")
            self.opstatus.set_status(stage=2, status=1, statustext ="Shapefile was found in the archive")
            self.opstatus.add_success(stage=2, msg = "Shapefile extracted successfully and contents read")
            for f in inputfiles:
                filepath = os.path.join(self.SOURCE_FILE_SHARE, f)
                # validate features and schema
                with fiona.open(filepath) as curfile:
                    schema = curfile.schema
                    schemavalidates = myShpFileHelper.validateSchema(schema)    
                    featuresvalidate = myShpFileHelper.validateFeatures(curfile)
                    
                    try: 
                        assert schemavalidates
                        self.logger.info("Every feature is a polygon")
                        self.opstatus.add_info(stage=3, msg = "Every feature has a areatype attribute")
                    except AssertionError as e:
                        self.logger.error("Input Shapefile does not have a areatype attribute")
                        self.opstatus.add_error(stage=3, msg = "Input Shapefile does not have a areatype attribute")
                        
                        # sys.exit(1)
                    try: 
                        assert featuresvalidate
                        self.logger.info("Every feature as the correct areatype")
                        self.opstatus.add_info(stage=3, msg = "Every feature has the correct areatype value one of: red, yellow, green, green2, green3")
                    except AssertionError as e: 
                        self.logger.error("Features in a shapefile must have allowed areatype attributes")
                        self.opstatus.add_error(stage=3, msg = "Your Shapefile does not have the correct values for the areatype column, it has to be one of  red, yellow, green, green2, green3")
                        # sys.exit(1)

                if schemavalidates and featuresvalidate:
                        self.opstatus.set_status(stage=3, status=1, statustext ="Shapefile has the  areatype column and correct values in the attribtute table.")
                        self.opstatus.add_success(stage=3, msg = "Shapefile has the areatype column and correct values in the attribtute table")
                else:
                    self.opstatus.set_status(stage=3, status=0, statustext ="A areatype attribute is either not present or have the correct value. For further information please refer: http://www.geodesignsupport.com/kb/geojson-feature-attributes/")
                    self.opstatus.add_error(stage=3, msg = "Your shapefile attribute table must have a areatype column with the correct attribute.")
                # Reproject the file. 
                if schemavalidates and featuresvalidate:
                    reprojectedfile = myFileOps.reprojectFile(filepath)
                    simplifiedfile,bounds = myFileOps.simplifyReprojectedFile(reprojectedfile)
                    allBounds.append(bounds)
                    try:
                        gjFile = myShpFileHelper.convert_shp_to_geojson(simplifiedfile, self.WORKING_SHARE) 
                    except Exception as e: 
                        self.logger.error("Error in converting shapefile to Geojson %s" %e)
                        self.opstatus.set_status(stage=6, status=0, statustext ="Error in converting Shapefile to GeoJSON")
                        self.opstatus.add_error(stage=6, msg = "Error in converting Shapefile to GeoJSON %s" %e)

                    with open(gjFile,'r') as gj:
                        allGJ[f] = json.loads(gj.read())
                else: 
                    
                    self.opstatus.set_status(stage=4, status=0, statustext ="There are errors in file attribute table, reprojection not started")
                    self.opstatus.add_error(stage=4, msg = "Check the attribute table for areatype column and correct areatype value.")
                    self.opstatus.set_status(stage=5, status=0, statustext ="File attribute table does not validate, therefore will not simplify")
                    self.opstatus.add_error(stage=5, msg = "Check the attribute table for areatype column and correct areatype value")
                    
                    self.opstatus.set_status(stage=6, status=0, statustext ="Shapefile not converted to GeoJSON. ")
                    self.opstatus.add_error(stage=6, msg = "File will not be converted to GeoJSON, see earlier errors")
                    
                    self.opstatus.set_status(stage=7, status=0, statustext ="Performance testing not started, please upload the correct file")
                    self.opstatus.add_error(stage=7, msg = "File performance will not be checked, please review earlier errors")
                    # convert to geojson.
            try:
                assert schemavalidates and featuresvalidate
                self.logger.info("Starting perfomrance analysis")

                myGeomOps = ShapelyHelper.GeomOperations()
                allBounds = myGeomOps.calculateBounds(allBounds)
                allBounds = allBounds.split(',')
                allBounds = [float(i) for i in allBounds]

                evalulationColors = ['red2','red', 'yellow', 'green', 'green2','green3']
                evalPaths = [f for f in listdir(self.WORKING_SHARE) if (isfile(join(self.WORKING_SHARE, f)) and (os.path.splitext(f)[1] == '.geojson'))]
                # generate random features

                featData = {"type":"FeatureCollection", "features":[]}
                myGJHelper = ShapelyHelper.GeoJSONHelper()
                
                self.logger.info("Generating random features within the bounds")
                self.opstatus.add_info(stage=7, msg = "Generating random features within the evaluation feature bounds")
                for i in range(5):
                    x = myGJHelper.genRandom(featureType="Polygon", numberVertices=4, boundingBox= allBounds)
                    f = {"type": "Feature", "properties": {},"geometry":json.loads(geojson.dumps(x))}
                    featData['features'].append(f)

                # polygonize the features
                combinedPlanPolygons = []
                for feature in featData['features']:
                    combinedPlanPolygons.append(asShape(feature['geometry']))
                allPlanPolygons = MultiPolygon([x for x in combinedPlanPolygons if x.geom_type == 'Polygon' and x.is_valid])
                allPlanPolygons = unary_union(allPlanPolygons)
                # read the evaluations
                timetaken = []
                for fname in evalPaths:
                    self.logger.debug("Currently processsing: %s" % fname)
                    self.opstatus.add_info(stage=7, msg = "Currently processsing: %s" % fname)

                    evalFPath = os.path.join(self.WORKING_SHARE, fname)
                    cacheKey = os.path.basename(evalFPath)
                    
                    filepath = os.path.join(self.WORKING_SHARE, 'some.db')
                    s = SqliteDict(filepath, autocommit=False)
                    # read the evaluation file
                    with open(evalFPath, 'r') as gjFile:
                            data = gjFile.read()
                            evalData = json.loads(data)

                    colorDict =  {'red':[],'red2':[], 'yellow':[],'green':[],'green2':[], 'green3':[],'constraints':[]}
                    errorDict =  {'red':0,'red2':0, 'yellow':0,'green':0,'green2':0,'green3':0, 'constraints':0}

                    for curFeature in evalData['features']:
                        try:
                            assert curFeature['properties']['areatype']
                        except AssertionError as e:
                            self.logger.error("Every evaluation feature must have a areatype attribute")
                            self.opstatus.set_status(stage=7, status=0, statustext ="Areatype attribute not present")
                            self.opstatus.add_error(stage=7, msg = "Every evaluation feature must have a areatype attribute")
                            # sys.exit(1)

                        try:
                            assert curFeature['properties']['areatype'] in ['constraints','red2', 'red', 'yellow', 'green', 'green2','green3']
                        except AssertionError as e:
                            self.logger.error("Areatype must be one of valid, please review areatype property details at http://www.geodesignsupport.com/kb/geojson-feature-attributes/")
                            self.opstatus.set_status(stage=7, status=0, statustext ="Areatype attribute not present")
                            self.opstatus.add_error(stage=7, msg = "Areatype must be one of valid allowed values, please review areatype property details at http://www.geodesignsupport.com/kb/geojson-feature-attributes/")
                            # sys.exit(1)
                            
                        areatype = curFeature['properties']['areatype']
                        errorCounter = errorDict[areatype]

                        shp, errorCounter = myGeomOps.genFeature(curFeature['geometry'], errorCounter)
                        colorDict[areatype].append(shp) 
                        
                    self.logger.info("Geometry errors in %(A)s Red2, %(B)s Red, %(C)s Yellow, %(D)s Green, %(E)s Green2, %(F)s Green3 and %(G)s Constraints features." % {'A' : errorDict['red2'], 'B' : errorDict['red'], 'C':errorDict['yellow'], 'D':errorDict['green'], 'E':errorDict['green2'],'F':errorDict['green3'], 'G': errorDict['constraints']})
                    self.opstatus.add_info(stage=7, msg = "Geometry errors in %(A)s Red2, %(B)s Red, %(C)s Yellow, %(D)s Green, %(E)s Green2, %(F)s Green3 and %(G)s Constraints features." % {'A' : errorDict['red2'], 'B' : errorDict['red'], 'C':errorDict['yellow'], 'D':errorDict['green'], 'E':errorDict['green2'],'F':errorDict['green3'], 'G': errorDict['constraints']})
                
                    # self.logger.debug(len(colorDict['red2']), len(colorDict['red']), len(colorDict['yellow']), len(colorDict['green']),len(colorDict['green2']),len(colorDict['green3']),len(colorDict['constraints']))
                    x = "Processed " + str(len(colorDict['red2'])) + " Red2, "+  str(len(colorDict['red']))+ " Red, "+ str(len(colorDict['yellow']))+ " Yellow, "+ str(len(colorDict['green']))+ " Yellow, "+str(len(colorDict['green2']))+ " Yellow, "+str(len(colorDict['green3']))+ " Green3 features."
                    
                    self.opstatus.add_info(stage=7, msg = x)

                    import time
                    start_time = time.time()

                    # create a union and write to SqliteDict this is to test caching performance.   
                    for k in colorDict.iterkeys():
                        u = myGeomOps.genUnaryUnion(colorList=colorDict[k])
                        curCacheKey = cacheKey + '-' + k
                        if curCacheKey not in s.keys() and u:
                            s[curCacheKey] = u
                    s.commit()
                    self.logger.debug("--- %.4f seconds ---" % float(time.time() - start_time))
                    timetaken.append(float(time.time() - start_time))
                    self.opstatus.set_statustext(stage=7, msg = "Processing took %.4f seconds " % float(time.time() - start_time))
                    # -- write to union json file
                    for k in colorDict.iterkeys():
                        curCacheKey = cacheKey+ '-' + k
                        try:
                            u = s[curCacheKey]
                        except KeyError as e: 
                            u = []
                        if u:
                            featureCollectionList = []
                            allJSON = ShapelyHelper.export_to_JSON(u)
                            featureCollectionList.append(myGeomOps.constructSingleFeatureDef(allJSON,k))
                            outputJSON = {}
                            outputJSON["type"] = "FeatureCollection"
                            outputJSON["features"]= featureCollectionList
                            fname = k + '.json'
                            uf = os.path.join(self.OUTPUT_SHARE, fname)
                            with open(uf, 'w') as outFile:
                                json.dump(outputJSON , outFile)
                    # -- write to intersection json file
                    for k in colorDict.iterkeys():
                        curCacheKey = cacheKey+ '-' + k
                        self.logger.debug("%s intersection starts" % k)
                        # self.opstatus.add_debug(stage=7, msg = "%s intersection starts" % k)
                        fname = k + '-intersect.json'
                        o = os.path.join(self.OUTPUT_SHARE, fname)
                        try:
                            evalFeats = s[curCacheKey]
                        except KeyError as e: 
                            evalFeats = []

                        if evalFeats:
                            with open(o, 'w') as outFile:
                                json.dump( myGeomOps.checkIntersection(allPlanPolygons,evalFeats, k), outFile)
                        else: 
                            self.logger.info("No %s features in input evaluation." % k)
                            self.opstatus.add_info(stage=7, msg = "No %s features in evaluation file." % k)
                
                if max(timetaken) > 4.0:
                    self.opstatus.set_status(stage=7, status=2, statustext= "Your file is either too large or is taking too much time to process, it is recommended that you reduce the features or simplify them.")
                else:
                    self.opstatus.set_status(stage=7, status=1)
            except AssertionError as ae:
                   self.opstatus.set_status(stage=7, status=0)
        else:
            self.logger.warning("Incorrect zip file")
            self.opstatus.set_status(stage=2, status=0, statustext ="Could not find .shp in the root of the zip archive.")
            self.opstatus.add_error(stage=2, msg = "Please ensure that all Shapefiles are in the root directory, the current file does not have it in the root.")

        return allGJ , self.opstatus.get_allstatuses()

    def cleanDirectories(self):
        dirs = [self.WORKING_SHARE, self.SOURCE_FILE_SHARE, self.OUTPUT_SHARE]
        for folder in dirs:
            for the_file in os.listdir(folder):
                file_path = os.path.join(folder, the_file)
                try:
                    if (os.path.isfile(file_path) and (the_file != 'README')):
                        os.unlink(file_path)
                    elif os.path.isdir(file_path): shutil.rmtree(file_path)
                except Exception as e:
                    print e
                    self.logger.error("Error Clearing out share.")