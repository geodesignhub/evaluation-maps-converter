from shapely.geometry import shape, mapping, shape, asShape
from shapely.geometry.base import BaseGeometry
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
try:
    from itertools import imap
except ImportError:
    # Python 3...
    imap=map
# import numpy as np

class GeopackageHelper():
	def __init__(self,opstatus):
		self.logger = logging.getLogger("evals logger")
		self.opstatus = opstatus
		self.reprojectErrors = False
		
	def get_output_fname(self,fname, new_suffix, destdirectory= None):
		path = os.path.basename(fname)
		filepath , filename =  os.path.split(fname)

		fparts = filename.split('.')
		if len(fparts[-1]) == 4:
			fname = '.'.join(fparts[:-1]) + new_suffix + '.' + fparts[-1]

		if destdirectory:
			return os.path.join(destdirectory, fname)
		else:
			return os.path.join(path, fname)

	def convert_gpkg_to_geojson(self,shape_fname, destdirectory):
		"""Using the Fiona library convert GeopackageHelper to GeoJSON
		"""
		features = []
		crs = None
		if not os.path.isfile(shape_fname):
			self.logger.error('File not found: %s' % shape_fname)
		self.opstatus.add_info(stage=6, msg = "Rounding coordinates to six decimal precision")


		out_fname = os.path.join(destdirectory,os.path.basename(shape_fname).replace('.gpkg', '.geojson'))
		with fiona.open(shape_fname, driver='GPKG') as source:
			with fiona.open(out_fname, "w",driver='GeoJSON',crs = fiona.crs.from_epsg(4326),schema=source.schema) as sink:
				for rec in source:
					sink.write(rec)

		self.logger.info('file written: %s' % out_fname)
		self.opstatus.set_status(stage=6, status=1, statustext ="File successfully converted to GeoJSON with six decimal precision")
		self.opstatus.add_success(stage=6, msg = "GeoJSON file successfully written")
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
		except Exception as e:
		    # Writing untransformed features to a different shapefile
		    # is another option.

			self.reprojectErrors = True
			self.logger.error(
			    "Error transforming record.")
			return None

	def clean_geom(self,rec):
		# Ensure that record geometries are valid and "clean".
		# Returns a record or None.

		try:
		    geom = shape(rec['geometry'])
		    print(rec)
		    if not geom.is_valid:
		        clean = geom.buffer(0.0)
		        assert clean.is_valid
		        assert clean.geom_type in ['Polygon','MultiPolygon']
		        geom = clean
		    rec['geometry'] = mapping(geom)
		    return rec
		except Exception as e:
			print(e)
		    # Writing uncleanable features to a different shapefile
		    # is another option.
			self.reprojectErrors = True
			self.opstatus.add_warning(stage=4, msg = "Error in reprojecting record in the file, please check for geometry errors and reproject to EPSG:4326 in GIS and try again.")
			# self.logger.error(
		        # "Error cleaning record %s:", e)
			
			return None

	def reproject_to_4326(self, shape_fname, outputdirectory):
		
		output = self.get_output_fname(shape_fname, '_4326', outputdirectory)
		with fiona.open(shape_fname, "r") as source:
			with fiona.open(
					output,
					"w",
					driver='GPKG',
					schema=source.schema,
					crs = from_epsg(4326)
					) as sink:
				
				origproj = Proj(source.crs, preserve_units=True)
				
				func = functools.partial(
					self.transform_coords,
					functools.partial(
						transform, 
						origproj, 
						Proj(sink.crs) ) 
					)
				# Transform the input records, using imap to loop/generate.
				results = map(func, source)
				# The transformed record generator is used as input for a
				# "cleaning" generator.

				# results = map(self.clean_geom, results)
				# Remove null records from the results
				results = filter(bool, results)
				# Finally we write records from the last generator to the output
				# "sink" file.

	
				sink.writerecords(results)
				
				
		return output, self.reprojectErrors
				
	def validateSchema(self, schema):

		try: 
			assert schema['geometry'] in ['Polygon' , 'MultiPolygon']
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
		self.opstatus = opstatus
		self.myShpFileHelper = GeopackageHelper(self.opstatus)
		self.myShapeFactory = ShapelyHelper.ShapesFactory()

	def multipart_to_singlepart(self, filepath):
		allGeoms =[]
		with fiona.open(filepath, driver='GPKG') as allfeats:
			crs = allfeats.crs
			for curFeat in allfeats:
				s = self.myShapeFactory.genFeature(curFeat['geometry'])
				if s:
					allGeoms.append({'shp':s, 'areatype':curFeat['properties']['areatype']})
		fg = []
		for curGeom in allGeoms:	
			shp = curGeom['shp']
			if shp.geom_type == 'MultiPolygon':
				polys = list(shp)
				for shp1 in polys: 							
					s = {'shp': shp1 , 'areatype': curGeom['areatype']}							
					fg.append(s)
			elif shp.geom_type == 'Polygon':
				s = {'shp': shp1 , 'areatype': curGeom['areatype']}		
				fg.append(s)


		sp = self.myShpFileHelper.get_output_fname(filepath,'_sp', self.WORKING_SHARE)
		
		# Define a polygon feature geometry with one attribute
		polygonschema = {
		    'geometry': 'Polygon',
		    'properties': {'areatype':'str'}
		}

		with collection(sp, 'w', driver='GPKG',crs=crs, schema=polygonschema) as c:
			## If there are multiple geometries, put the "for" loop here
			for curPoly in fg:				
				c.write({
					'geometry': mapping(curPoly['shp']), 
					'properties': {'areatype':curPoly['areatype']}
				})
		return sp

	def reprojectFile(self, filepath):
		reprojectionErrors = False
		with fiona.open(filepath, driver='GPKG') as allfeats:
			# get the schema
			schema = allfeats.schema
			# get the crs
			crs = allfeats.crs
			if (('init' in crs) and (crs['init'] == 'epsg:4326')):
				reprojected_fname= filepath
			else:
					self.logger.info("Reprojecting file")
					self.opstatus.add_info(stage=4, msg = "Checking projection..")
					self.opstatus.add_info(stage=4, msg = "Reprojecting file to EPSG 4326 projection")
					
					reprojected_fname, reprojectionErrors  = self.myShpFileHelper.reproject_to_4326(filepath, self.WORKING_SHARE)

		return reprojected_fname, reprojectionErrors

	def simplifyReprojectedFile(self, reprojectedfilepath):    
        # simplify reprojected file

		with fiona.open(reprojectedfilepath,driver='GPKG') as allfeats:
			crs = allfeats.crs
			bounds = allfeats.bounds
			simplification = {'highest': 0.01,'high': 0.005, 'medium':0.001, 'low':0.0005, 'default':0.00001,'none':0}
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
			self.opstatus.add_info(stage=5, msg = "Simplifying with simplification level : %s " % config.simplificationlevel)
			for curFeat in allfeats:
				s = self.myShapeFactory.genFeature(curFeat['geometry'])
				if s:
					area = s.area
					allGeoms.append({'area': area, 'shp':s, 'areatype':curFeat['properties']['areatype']})
		simshp = []
		# # filter out small areas
		
		maxareadict =  max(allGeoms, key=lambda x:x['area'])
		maxarea =  maxareadict['area']
		areathreshold = (maxarea * 0.005)

		allGeoms = [i for i in allGeoms if i['area'] > areathreshold]
		
		for curGeom in allGeoms:				
			try:
				assert simplificationlevel != 'none'
				shp = curGeom['shp'].simplify(simplificationlevel, preserve_topology=True)
			except AssertionError as e: 					
			    shp = curGeom['shp']
			else:
				if shp.geom_type == 'MultiPolygon':
					polys = list(shp)
					for shp1 in polys: 							
						s = {'shp': shp1 , 'areatype': curGeom['areatype']}							
						simshp.append(s)

				else:
					s = {'shp': shp , 'areatype': curGeom['areatype']}
					simshp.append(s)


		sims = self.myShpFileHelper.get_output_fname(reprojectedfilepath,'_sim', self.WORKING_SHARE )
		
		self.logger.info("Writing simplified Geopackage %s.." % sims) 
		self.opstatus.add_info(stage=5, msg = "Writing simplified Geopackage")
		
		try:
			with collection(sims, 'w', driver='GPKG',crs=crs, schema=polygonschema) as c:
				## If there are multiple geometries, put the "for" loop here
				for curPoly in simshp:				

					c.write({
						'geometry': mapping(curPoly['shp']), 
						'properties': {'areatype':curPoly['areatype']}
					})
			
			self.opstatus.set_status(stage=5, status=1, statustext ="Simplifed Geopackage written successfully")
			self.opstatus.add_success(stage=5, msg = "Simplifed file written successfully")
		except Exception as e: 
			self.opstatus.set_status(stage=5, status=0, statustext ="Error in writing simplified Geopackage")
			self.opstatus.add_error(stage=5, msg = "Error in writing simplified Geopackage" %e)

		return sims, bounds