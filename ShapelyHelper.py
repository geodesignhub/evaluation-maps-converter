from shapely.geometry.base import BaseGeometry
from shapely.geometry import shape, mapping, shape, asShape
from shapely.geometry import MultiPolygon, MultiPoint, MultiLineString
from shapely.ops import unary_union
import json
import logging
from shapely import speedups

class ShapelyEncoder(json.JSONEncoder):

    ''' Encodes JSON strings into shapes processed by SHapely'''

    def default(self, obj):
        if isinstance(obj, BaseGeometry):
            return mapping(obj)
        return json.JSONEncoder.default(self, obj)


class ShapelyDecoder(json.JSONDecoder):
    ''' Decodes JSON strings into shapes processed by SHapely'''
    def decode(self, json_string):
        def shapely_object_hook(obj):
            if 'coordinates' in obj and 'type' in obj:
                return shape(obj)
            return obj
        return json.loads(json_string, object_hook=shapely_object_hook)


def export_to_JSON(data):
    ''' Export a shapely output to JSON'''
    return json.dumps(data, sort_keys=True, cls=ShapelyEncoder)


def load_from_JSON(json_string):
    '''Read JSON and a create a SHapely Object '''
    return json.loads(json_string, cls=ShapelyDecoder)

class GeomOperations():
    def __init__(self):
        self.logger = logging.getLogger("evals logger")

    def calculateBounds(self,allBounds):

        sw ={'lat':0,'lng':0}
        ne = {'lat':0,'lng':0}
        for curBounds in allBounds: 
            # mb = allBounds.split(',') # mb[0]  = sw_lng ,mb[1] = sw_lat, mb[2] = ne_lng, mb[3] = ne_lat
            sw['lat'] = float(curBounds[1]) if (sw['lat'] == 0) else min(float(curBounds[1]), sw['lat'])
            sw['lng'] = float(curBounds[0]) if (sw['lng'] == 0) else min(float(curBounds[0]), sw['lng'])
            ne['lat'] = float(curBounds[3]) if (ne['lat'] == 0) else max(float(curBounds[3]), ne['lat'])
            ne['lng'] = float(curBounds[2]) if (ne['lng'] == 0) else max(float(curBounds[2]), ne['lng'])   
            
        finalBounds = ["{:.8f}".format(sw['lng']) ,"{:.8f}".format(sw['lat']),"{:.8f}".format(ne['lng']),"{:.8f}".format(ne['lat'])]    
        finalBounds = ",".join(finalBounds) 
        return finalBounds

    def constructSingleFeatureDef(self, featureJSON,featureType):
        '''This function takes in the feature JSON and featuretype and outputs a GEOJSON object to be added
        in feature collection '''
        curFeature = {}
        curFeature['properties'] = {'areatype':featureType}
        curFeature['type']= 'Feature'
        curFeature['geometry']= json.loads(featureJSON)
        return curFeature

    def checkIntersection(self, planLayer, evalLayer,layerType):
        ''' This function intersects a evaluation feature with a test feature set and returns a feature collection '''
        outputJSON = {}
        outputJSON["type"] = "FeatureCollection"
        featureCollectionList = []
        success = 0
        try:
            x = planLayer.intersection(evalLayer)
            allJSON = export_to_JSON(x)
            featureCollectionList.append(self.constructSingleFeatureDef(allJSON,layerType))
            success = 1
        except Exception as e: 
            
            success = 0
            self.logger.error("Error in intersection {0} layer: {1}".format(layerType, e))

        outputJSON["features"]= featureCollectionList
        return outputJSON, success

    def genUnaryUnion(self, colorList ):
        try:
            colorUnion = unary_union([x for x in colorList if x.geom_type in ['Polygon' ,'MultiPolygon']])
        except Exception as e:
            self.logger.error("Union failed: %s" % e)
            colorUnion = unary_union([x for x in colorList if x.geom_type in ['Polygon','MultiPolygon'] and x.is_valid])

        return colorUnion

    def genFeature(self, geom, errorCounter):
        try:
            curShape = asShape(geom)
        except Exception as e:
            self.logger.error(explain_validity(curShape))
            errorCounter+=1
        return curShape, errorCounter



class ShapesFactory():
    '''
    A helper function to convert to a Shapely geometry
    '''
    def __init__(self):
        self.logger = logging.getLogger("evals logger")

    def genFeature(self, geom):
        try:
            curShape = asShape(geom)
        except Exception as e:
            self.logger.error(explain_validity(curShape))

        return curShape
        
    def multiPolytoFeature(self, mp):
        feats =[]
        for curCoords in mp['coordinates']:
            feats.append({'type':'Polygon','coordinates':curCoords})
        return feats

    def createUnaryUnion(self, allAreas):
        ''' Given a set of areas, this class constructs a unary union for them '''
        try:
            # Construct a unary_union assume that there are no errors in
            # geometry.
            allDsgnPlygons = unary_union(allAreas)
        except Exception as e1:
            # If there are errors while consutrcuting the union, examine the
            # geometries further to seperate
            s1All = []
            try:
                s1Polygons = MultiPolygon([x for x in allAreas if (
                    x.geom_type == 'Polygon' or x.geom_type == 'MultiPolygon') and x.is_valid])
                if s1Polygons:
                    s1All.append(s1Polygons)
            except Exception as e:
                logging.error(
                    'SpatialimpactCalculator.py Error in CreateUnaryUnion Polygon: %s' % e)
            if s1All:
                allDsgnPlygons = unary_union(s1All)
            else:
                allDsgnPlygons = ''

        return allDsgnPlygons




class GeoJSONHelper():
    def genRandom(self, featureType, numberVertices=3,
                        boundingBox=[-180.0, -90.0, 180.0, 90.0]):
        """
        Originally from : https://github.com/frewsxcv/python-geojson/blob/master/geojson/utils.py 
        Generates random geojson features depending on the parameters
        passed through.
        The bounding box defaults to the world - [-180.0, -90.0, 180.0, 90.0].
        The number of vertices defaults to 3.
        :param featureType: A geometry type
        :type featureType: Point, LineString, Polygon
        :param numberVertices: The number vertices that a linestring or polygon
        will have
        :type numberVertices: int
        :param boundingBox: A bounding box in which features will be restricted to
        :type boundingBox: list
        :return: The resulting random geojson object or geometry collection.
        :rtype: object
        :raises ValueError: if there is no featureType provided.
        """
        from geojson import Point, LineString, Polygon
        import random
        import math

        def coordInBBBOX(boundingBox):
            return [
                (random.random() * (boundingBox[2] - boundingBox[0])) + boundingBox[0],
                (random.random() * (boundingBox[3] - boundingBox[1])) + boundingBox[1]];
        
        def position(boundingBox):
            if (boundingBox): 
                return coordInBBBOX(boundingBox);
            else:
                return [randomLon(), randomLat()];
        

        lonMin = boundingBox[0]
        lonMax = boundingBox[2]

        def randomLon():
            return random.uniform(lonMin, lonMax)

        latMin = boundingBox[1]
        latMax = boundingBox[3]
        lldiff = [abs(latMax - latMin), abs(lonMin-lonMax)]
        def randomLat():
            return random.uniform(latMin, latMax)

        def createPoint():
            return Point((randomLon(), randomLat()))

        def createLine():
            coords = []
            for i in range(0, numberVertices):
                coords.append((randomLon(), randomLat()))
            return LineString(coords)

        def createPoly():
            aveRadius = float(sum(lldiff))/len(lldiff) if len(lldiff) > 0 else 0.1
            pt = position(boundingBox)
            # ctrX = 0.1
            # ctrY = 0.2
            ctrX = pt[0]
            ctrY = pt[1]

            irregularity = clip(0.1, 0, 1) * 2 * math.pi / numberVertices
            spikeyness = clip(0.5, 0, 1) * aveRadius


            angleSteps = []
            lower = (2 * math.pi / numberVertices) - irregularity
            upper = (2 * math.pi / numberVertices) + irregularity
            s = 0
            for i in range(numberVertices):
                tmp = random.uniform(lower, upper)
                angleSteps.append(tmp)
                s = s + tmp

            k = s / (2 * math.pi)
            for i in range(numberVertices):
                angleSteps[i] = angleSteps[i] / k

            points = []
            angle = random.uniform(0, 2 * math.pi)

            for i in range(numberVertices):
                r_i = clip(random.gauss(aveRadius, spikeyness), 0, 2 * aveRadius)

                x = ctrX + r_i * math.cos(angle)
                y = ctrY + r_i * math.sin(angle)
                points.append((float(x), float(y)))
                angle = angle + angleSteps[i]

            firstVal = points[0]
            points.append(firstVal)
            return Polygon([points])

        def clip(x, min, max):
            if(min > max):
                return x
            elif(x < min):
                return min
            elif(x > max):
                return max
            else:
                return x

        if featureType == 'Point':
            return createPoint()

        if featureType == 'LineString':
            return createLine()

        if featureType == 'Polygon':
            return createPoly()
