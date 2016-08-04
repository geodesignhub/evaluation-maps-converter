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
from fiona.crs import to_string
import  json, geojson
from sqlitedict import SqliteDict
import os, sys
from os import listdir
from os.path import isfile, join
import logging
import Colorer
import zipfile

LOG_FILENAME = "runlog.log"

def configure_logging():

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
    fh = logging.FileHandler(LOG_FILENAME)
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(formatter)
    logger.addHandler(fh)
    logger.propagate = False
    return logger

curPath = os.path.dirname(os.path.realpath(__file__))

class ConvertEvaluation():
    
    
    def convert(self):
        logger = configure_logging()
        logger.info("Geodesign Hub Evaluations Converter")    
        myShpFileHelper = EvaluationFileOps.ShapefileHelper()
        logger.info("Reading source files.. ")
        curPath = os.path.dirname(os.path.realpath(__file__))
        allBounds = []
        SOURCE_FILE_SHARE = os.path.join(curPath, config.inputs['directory'])
        WORKING_SHARE = os.path.join(curPath, config.working['directory'])
        # final GEOJSON
        OUTPUT_SHARE = os.path.join(curPath, config.geojsonoutput['directory'])
        if not os.path.exists(WORKING_SHARE):
            os.mkdir(WORKING_SHARE)
        if not os.path.exists(OUTPUT_SHARE):
            os.mkdir(OUTPUT_SHARE)
        try:
            assert os.path.exists(SOURCE_FILE_SHARE)
        except AssertionError as e:
            logger.error("Source file directory does not exist, please check config.py for correct filename and directory")
            sys.exit(1)

        zipfiles = [f1 for f1 in listdir(SOURCE_FILE_SHARE) if (os.path.splitext(f1)[1] == '.zip')]
        for z in zipfiles:
            zip_ref = zipfile.ZipFile(os.path.join(SOURCE_FILE_SHARE,z), 'r')
            zip_ref.extractall(SOURCE_FILE_SHARE)
            zip_ref.close()

        inputfiles = [f for f in listdir(SOURCE_FILE_SHARE) if (isfile(os.path.join(SOURCE_FILE_SHARE, f)) and (os.path.splitext(f)[1] == '.shp'))]
        myFileOps = EvaluationFileOps.FileOperations(SOURCE_FILE_SHARE, OUTPUT_SHARE, WORKING_SHARE)
        for f in inputfiles:
            filepath = os.path.join(SOURCE_FILE_SHARE, f)
            # Reproject the file. 
            reprojectedfile = myFileOps.reprojectFile(filepath)
                
            simplifiedfile,bounds = myFileOps.simplifyReprojectedFile(reprojectedfile)
            allBounds.append(bounds)
            # convert to geojson.
            myShpFileHelper.convert_shp_to_geojson(simplifiedfile, WORKING_SHARE) 

        myGeomOps = ShapelyHelper.GeomOperations()
        allBounds = myGeomOps.calculateBounds(allBounds)
        allBounds = allBounds.split(',')
        allBounds = [float(i) for i in allBounds]

        evalulationColors = ['red2','red', 'yellow', 'green', 'green2','green3']
        evalPaths = [f for f in listdir(WORKING_SHARE) if (isfile(join(WORKING_SHARE, f)) and (os.path.splitext(f)[1] == '.geojson'))]
        # generate random features

        featData = {"type":"FeatureCollection", "features":[]}
        myGJHelper = ShapelyHelper.GeoJSONHelper()
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
        for fname in evalPaths:
            logger.debug("Currently processsing: %s" % fname)
            evalFPath = os.path.join(WORKING_SHARE, fname)
            cacheKey = os.path.basename(evalFPath)
            
            filepath = os.path.join(WORKING_SHARE, 'some.db')
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
                    logger.error("Every evaluation feature must have a areatype attribute")
                    sys.exit(1)

                try:
                    assert curFeature['properties']['areatype'] in ['constraints','red2', 'red', 'yellow', 'green', 'green2','green3']
                except AssertionError as e:
                    logger.error("Areatype must be one of valid, please review areatype property details at http://www.geodesignsupport.com/kb/geojson-feature-attributes/")
                    sys.exit(1)
                    
                areatype = curFeature['properties']['areatype']
                errorCounter = errorDict[areatype]

                shp, errorCounter = myGeomOps.genFeature(curFeature['geometry'], errorCounter)
                colorDict[areatype].append(shp) 
                
            logger.info("Exceptions in %(A)s Red2, %(B)s Red, %(C)s Yellow, %(D)s Green, %(E)s Green2, %(F)s Green3 and %(G)s Constraints features." % {'A' : errorDict['red2'], 'B' : errorDict['red'], 'C':errorDict['yellow'], 'D':errorDict['green'], 'E':errorDict['green2'],'F':errorDict['green3'], 'G': errorDict['constraints']})
           
            # logger.debug(len(colorDict['red2']), len(colorDict['red']), len(colorDict['yellow']), len(colorDict['green']),len(colorDict['green2']),len(colorDict['green3']),len(colorDict['constraints']))

            import time
            start_time = time.time()

            # create a union and write to SqliteDict this is to test caching performance.   
            for k in colorDict.iterkeys():
                u = myGeomOps.genUnaryUnion(colorList=colorDict[k])
                curCacheKey = cacheKey + '-' + k
                if curCacheKey not in s.keys() and u:
                    s[curCacheKey] = u
            s.commit()
            logger.debug("--- %.4f seconds ---" % float(time.time() - start_time))
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
                    uf = os.path.join(OUTPUT_SHARE, fname)
                    with open(uf, 'w') as outFile:
                        json.dump(outputJSON , outFile)
            # -- write to intersection json file
            for k in colorDict.iterkeys():
                curCacheKey = cacheKey+ '-' + k
                logger.debug("%s intersection starts" % k)
                fname = k + '-intersect.json'
                o = os.path.join(OUTPUT_SHARE, fname)
                try:
                    evalFeats = s[curCacheKey]
                except KeyError as e: 
                    evalFeats = []

                if evalFeats:
                    with open(o, 'w') as outFile:
                        json.dump( myGeomOps.checkIntersection(allPlanPolygons,evalFeats, k), outFile)
                else: 
                    logger.info("No %s features in input evaluation." % k)


            return "OK"