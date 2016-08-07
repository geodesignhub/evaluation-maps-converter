# Evaluation Maps Converter

A tool to convert Evaluation Map Shapefiles so that they can be uploaded on Geodesign Hub.

Geodesign Hub uses GeoJSON and [EPSG4326](http://espg.io/4326) projection and this tool will reproject your shapefiles before simplifying. In addition it will also create a GeoJSON that can be used in Geodesign Hub. Finally, this tool takes the GeoJSON and tests performance of it for geo spatial operations that are conducted on the Geodesign Hub Server. It can be useful to identify issues such as geometry errors and also test performance. 

It is Python Flask App that is deployed on Heroku.

![alt text][logo]

[logo]: http://i.imgur.com/fFXpocE.png "Evaluation Files Converter"


###Before you start
You will need a Evaluation map already prepared for your study area. Evaluation maps can be created using GIS tools. Please review evaluation map creation in the [step-by-step guide for data preparation](http://www.geodesignsupport.com/kb/step-by-step-guide-to-setting-up-data-for-your-project/) for a project on Geodesign Hub. They are built in five or three colors using standard GIS modelling tools. 

Your file must have a ```areatype``` property in the attributes table that has a value of one of the following strings: red, yellow, green, green2, green3 depending on the Evaluation model. A detailed guide to building a evaluation file is [here](http://www.geodesignsupport.com/kb/step-by-step-guide-to-preparing-evaluation-maps/). 

 
###Other notes
After converting to EPSG 4326, it uses the [Douglas-Peucker](https://en.wikipedia.org/wiki/Ramer%E2%80%93Douglas%E2%80%93Peucker_algorithm) simplification algorithm with a tolerance of 0.69 miles or 1.104 kms. It means that any lines will be simplifed within this band. For convenince, tolerance can be incereased or decreased. 

The script creates a union of the red, yellow and green features and intersects them against randomly drawn features. It will show if the evaluation has errors in its features and a also time it takes to perform a intersection. The lower the time the better it is for performance. If it takes more than 10 seconds, consider simplifying the evaluation file by reducing the features. 


###Background
Evaluation Maps produced by GIS tools as Shapefiles can be very large. In addition, Shapefiles cannot be directly uploaded to Geodesign Hub. This is a tool that will help in simplifying the maps, reprojecting them to EPSG 4326 and generate a GeoJSON for you. Then it can be directly uploaded to Geodesign Hub.

Please review the [data simplification](http://www.geodesignsupport.com/kb/map-simplification/) article to understand the file size and performance requirements for the tool.

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
