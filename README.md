# Evaluation Models Simplifer
A utility to simplify Evaluation files in Geodesign Hub.

Evaluation Maps produced by GIS tools as Shapefiles can be very large. This is a tool that will help in simplifying the maps. Please review the [data simplification](http://www.geodesignsupport.com/kb/map-simplification/) article to understand the file size and performance requirements for the tool.

###Features
Geodesign Hub uses [EPSG4326](http://espg.io/4326) projection and this tool will reproject your shapefiles before simplifying. In addition it will also create a GeoJSON that can be used in Geodesign Hub.  

###Before you start
You will need a set of Evaluation maps for your study area. Evaluation maps can be created using GIS tools. They are built in five or three colors using standard GIS modelling tools. There should be a ```areatype``` property in the attributes that has a value of one of the following strings: red2, red, yellow, green, green2, green3 or constraints. A detailed guide to building a evaluation file is [here](http://www.geodesignsupport.com/kb/step-by-step-guide-to-preparing-evaluation-maps/). This script will take the evaluation map produced by your model, do checks for the file type and the areatype attribute, reproject if necessary and convert it to GeoJSON. 

###Installing requirements
To make sure you have all the libraries installed on your system, please use the following command: 
```
pip install -r requirements.txt 
```
This will install [Shapely](http://toblerity.org/shapely/) among other libraries on your machine if you dont have it installed already.
#### Config.py
Firstly, update config.py with your input and output directories, file and also specify a simplification level.

####Inputs Directory
You should copy your evaluation Shapefile (unzipped) along with the other relevant "sidecar" files in the "inputs" directory. 

####Outputs Directory
The output directory contains simplified file in both Shapefile and GeoJSON format. 

####Understand Outputs
After converting to EPSG 4326, it uses the [Douglas-Peucker](https://en.wikipedia.org/wiki/Ramer%E2%80%93Douglas%E2%80%93Peucker_algorithm) simplification algorithm with a tolerance of 0.69 miles or 1.104 kms. It means that any lines will be simplifed within this band. For convenince, tolerance can be incereased or decreased. 

# Evaluation Models Validator
Utility to to test Evaluation map GeoJSON files in Geodesign Hub

This script that takes in a Evaluation Model GeoJSON and tests performance of it for geo spatial operations that are conducted on the Geodesign Hub Server. It can be useful to identify issues such as geometry errors and also test performance. 

###Before you start
You will need a set of GeoJSON files (evaluation maps) that are built in five or three colors using standard GIS modelling tools. There should be a ```areatype``` property in the attributes that has a value of one of the following strings: red, yellow, green, green2, green3. A detailed guide to building a evaluation file is [here](http://www.geodesignsupport.com/kb/step-by-step-guide-to-preparing-evaluation-maps/). In addition, using [www.geojson.io](www.geojson.io) create another file that has some example features to check the intersection performance. These features should overlap the evaluation files at the same study area.  

####Installing requirements
To make sure you have all the libraries installed on your system, please use the following command: 
```
pip install -r requirements.txt 
```
This will install [Shapely](http://toblerity.org/shapely/) on your machine if you dont have it installed already.
####Config.py
Firstly, update config.py with your directories and files for evaluations and features. 

####Evaluations Directory
Once code is synced, you can copy all your evaluation GeoJSON and the test feature geojson in the "evaluation" directory. 

####Features Directory
In this directory create a couple of "test" features in geojson to simulate what a user might draw. Go to [geojson.io](http://geojson.io), pan and zoom the map to the study area and draw some features. Then copy the JSON on the right hand side to create .geojson file and put it in this directory. 

####Output Directory
The output directory contains the result of a intersection of the features. 

####Understand Outputs
The script creates a union of the red, yellow and green features and intersects them against the drawn features. It will show if the evaluation has errors in its features and a also time it takes to perform a intersection. The lower the time the better it is for performance. If it takes more than 10 seconds, consider simplifying the evaluation file by reducing the features. 

###License
The MIT License (MIT)

Copyright (c) 2015 Geodesign Hub Pvt. Ltd.

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
