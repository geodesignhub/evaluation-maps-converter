from shapely.geometry.base import BaseGeometry
from shapely.geometry import shape, mapping, shape, asShape
from shapely.geometry import MultiPolygon, MultiPoint, MultiLineString
import os, sys
import json
import fiona 
from pyproj import Proj, transform
from fiona.crs import from_epsg
import config

import logging
import ShapelyHelper
from fiona import collection
import functools
import itertools

class ShapefileHelper():
	def __init__(self,opstatus):
		self.logger = logging.getLogger("evals logger")
		self.opstatus = opstatus
		

	def get_output_fname(self,fname, new_suffix, destdirectory= None):
		path = os.path.basename(fname)
		filepath , filename =  os.path.split(fname)
		fparts = filename.split('.')
		if len(fparts[-1]) == 3:
			fname = '.'.join(fparts[:-1]) + new_suffix + '.' + fparts[-1]
		if destdirectory:
			return os.path.join(destdirectory, fname)
		else:
			return os.path.join(path, fname)

	def convert_shp_to_geojson(self,shape_fname, destdirectory):
		"""Using the Fiona library convert shapefile to GeoJSON
		"""
		features = []
		crs = None
		if not os.path.isfile(shape_fname):
			self.logger.error('File not found: %s' % shape_fname)
		with fiona.open(shape_fname) as allfeats:
			# import pprint
			# pprint.pprint(c.schema)
			schema = allfeats.schema
			
			validated = self.validateSchema(schema)
			if validated:
			    for feat in allfeats:
			    	if 'areatype' in feat['properties'].keys():
			    		features.append(feat)
		my_layer = {
		    "type": "FeatureCollection",
		    "features": features }
		out_fname = os.path.join(destdirectory,os.path.basename(shape_fname).replace('.shp', '.geojson'))
		with open(out_fname, "w") as f:
			f.write(json.dumps(my_layer))
			f.close()

		self.logger.info('file written: %s' % out_fname)

		return out_fname
	def transform_coords(self,func, rec):
		# Transform record geometry coordinates using the provided function.
		# Returns a record or None.
		try:
		    assert rec['geometry']['type'] == "Polygon"
		    new_coords = []
		    for ring in rec['geometry']['coordinates']:
		        # Here is where we call func() to transform the coords.
		        x2, y2 = func(*zip(*ring))
		        new_coords.append(zip(x2, y2))
		    rec['geometry']['coordinates'] = new_coords
		    return rec
		except Exception, e:
		    # Writing untransformed features to a different shapefile
		    # is another option.
		    self.logger.error(
		        "Error transforming record %s:", rec)
		    return None

	def clean_geom(self,rec):
		# Ensure that record geometries are valid and "clean".
		# Returns a record or None.
		try:
		    geom = shape(rec['geometry'])
		    if not geom.is_valid:
		        clean = geom.buffer(0.0)
		        assert clean.is_valid
		        assert clean.geom_type == 'Polygon'
		        geom = clean
		    rec['geometry'] = mapping(geom)
		    return rec
		except Exception, e:
		    # Writing uncleanable features to a different shapefile
		    # is another option.
		    self.logger.error(
		        "Error cleaning record %s:", rec)
		    return None

	def reproject_to_4326(self, shape_fname, outputdirectory):
		output = self.get_output_fname(shape_fname, '_4326', outputdirectory)
		with fiona.open(shape_fname, "r") as source:
			with fiona.open(
					output,
					"w",
					driver=source.driver,
					schema=source.schema,
					crs = from_epsg(4326)
					) as sink:
				
				# Do the geoprocessing in a functional style. The transform_coords
				# function operates on and returns a single record. Its first argument
				# is a function that transforms a single coordinate pair between two
				# coordinate reference systems. We'll compose partial functions of 
				# these two into one function.
				origproj = Proj(source.crs, preserve_units=True)
				func = functools.partial(
					self.transform_coords,
					functools.partial(
						transform, 
						origproj, 
						Proj(sink.crs) ) 
					)
				# Transform the input records, using imap to loop/generate.
				results = itertools.imap(func, source)
				# The transformed record generator is used as input for a
				# "cleaning" generator.
				results = itertools.imap(self.clean_geom, results)
				# Remove null records from the results
				results = itertools.ifilter(bool, results)
				# Finally we write records from the last generator to the output
				# "sink" file.
				sink.writerecords(results)
		return output
				
	def validateSchema(self, schema):
		try: 
			assert schema['geometry'] == 'Polygon' 
			validated = True
		except AssertionError as e: 
			validated = False

		return validated
		
	def validateFeatures(self, allfeats, evalorimpact='eval'):
		validated = False
		checkDict = {'eval':['red', 'green', 'yellow', 'green2','green3']}
		toCheck = checkDict[evalorimpact]
		for f in allfeats:
			if 'areatype' in f['properties'].keys() and f['properties']['areatype'] in toCheck:
				validated = True
			else:
				validated = False
		return validated


class FileOperations():

    def __init__(self, SOURCE_FILE_SHARE, OUTPUT_SHARE, WORKING_SHARE, opstatus):
		self.SOURCE_FILE_SHARE = SOURCE_FILE_SHARE
		self.WORKING_SHARE = WORKING_SHARE
		self.OUTPUT_SHARE = OUTPUT_SHARE
		self.logger = logging.getLogger("evals logger")
		self.myShpFileHelper = ShapefileHelper()
		self.myShapeFactory = ShapelyHelper.ShapesFactory()
		self.opstatus = opstatus


    def reprojectFile(self, filepath):
        with fiona.open(filepath) as allfeats:
            # get the schema
            schema = allfeats.schema
            # get the crs
            crs = allfeats.crs
            # check if there is a areatype 
            self.logger.info("File read, validating schema and features..")
            schemavalidates = self.myShpFileHelper.validateSchema(schema)    
            featuresvalidate = self.myShpFileHelper.validateFeatures(allfeats)

            try: 
                assert schemavalidates
                self.logger.info("Schema OK..")
            except AssertionError as e:
                self.logger.error("Input Shapefile does not have a areatype attribute.")
                sys.exit(1)
            try: 
                assert featuresvalidate
                self.logger.info("Features OK..")
            except AssertionError as e: 
                self.logger.error("Features in a shapefile must have allowed areatype attributes")
                sys.exit(1)

            self.logger.info("Checking projection..")
            
            reprojected_fname = self.myShpFileHelper.reproject_to_4326(filepath, self.WORKING_SHARE)
            self.logger.info("File reprojected as %s .." % reprojected_fname)

        return reprojected_fname
        
    def simplifyReprojectedFile(self, reprojectedfilepath):    
        # simplify reprojected file
        with fiona.open(reprojectedfilepath) as allfeats:
            crs = allfeats.crs
            bounds = allfeats.bounds
            simplification = {'highest': 0.1,'high': 0.05, 'medium':0.01, 'low':0.0005, 'default':0.005,'none':0}
            # simplify the file
            allGeoms = []
            errorCounter = 0
            # Define a polygon feature geometry with one attribute
            polygonschema = {
                'geometry': 'Polygon',
                'properties': {'areatype':'str'}
            }
            simplificationlevel = simplification[config.simplificationlevel]
            self.logger.info("Simplifying with simplification level : %s " % config.simplificationlevel)
            
            for curFeat in allfeats:
                s = self.myShapeFactory.genFeature(curFeat['geometry'])
                if s:
                    allGeoms.append({'shp':s, 'areatype':curFeat['properties']['areatype']})

            simshp = []
            
            for curGeom in allGeoms:
                try:
                    assert simplificationlevel != 'none'
                    shp = curGeom['shp'].simplify(simplificationlevel, preserve_topology=True)
                except AssertionError as e: 
                    shp = curGeom['shp']
                s = {'shp': shp , 'areatype': curGeom['areatype']}
                simshp.append(s)
            
            sims = self.myShpFileHelper.get_output_fname(reprojectedfilepath,'_sim', self.WORKING_SHARE )
            self.logger.info("Writing simplified shapefile %s.." % sims)
            with collection(sims, 'w', driver='ESRI Shapefile',crs=crs, schema=polygonschema) as c:
                ## If there are multiple geometries, put the "for" loop here
                for curPoly in simshp:
                    c.write({
                        'geometry': mapping(curPoly['shp']), 
                        'properties': {'areatype':curPoly['areatype']}
                    })
        return sims, bounds