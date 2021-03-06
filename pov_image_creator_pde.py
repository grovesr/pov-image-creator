#!/usr/bin/python
# -*- coding: utf-8 -*-
"""Create one or more Processing sketches that can be used to visualize Persistence of Vision (POV)
effects in both Radial (RPOV) mode (i.e. propellor clock) and Linear (XYPOV) mode.  The created Processing
sketches can be used to program an Atmel POV board though the Serial port.

 Eventually we might just establish the Serial connection here and program the POV board from Python.  
 Then the Processing sketch(es) would be used for POV visualization only."""

import sys
import os
#import shutil
import subprocess
#import win32process
from PIL import Image
import POV

if len(sys.argv) < 2:
	raw_input("Please specify an image directory. Hit [enter] then try again.\n")
	sys.exit(-1)
if not os.path.isdir(sys.argv[1]):
	raw_input("First argument to this script should be the name of a directory containing image files. Hit [enter] then try again.\n")
	sys.exit(-1)
if len(sys.argv) == 3:
	try:
		compileProcessing = int(sys.argv[2])
	except:
		print "Second argument to this script should be numeric [" + sys.argv[2] + "]\n"
		raw_input("press enter\n")
		exit(-1)
else:
	compileAns=raw_input("Do you want to compile the processing sketches?[n]\n")
	if compileAns == '' or compileAns.lower() == 'n':
		compileProcessing = 0
	else:
		compileProcessing = 1
# determine image directory name
imageDirFullPathName = sys.argv[1]
imageDirName = imageDirFullPathName.rsplit(".",1)
imageDirName=imageDirName[0].rsplit(os.sep,1)
imageDirName=imageDirName[1]
dirContents = os.listdir(imageDirFullPathName)
dirContents.sort()
# hash of image names each of whichb points to a list of the image frames (>=1) in each image
imageFiles = {}
frameDelays={}
for file in dirContents:
	try:
		tmp=Image.open(imageDirFullPathName + os.sep + file)
	except IOError:
		continue
	try:
		# query image file to see if it is an animated gif with multiple frames
		numFrames = subprocess.check_output(['identify','-format','"%n"', imageDirFullPathName + os.sep + file])
	except:
		print "unable to query image file " + file + " : ", sys.exc_info()[0] 
		raw_input("press enter\n");
		exit(-1)
	imageName = file.split(".",1)[0]
	numFrames=int(numFrames.lstrip('"').split('"',1)[0])
	if numFrames > 1:
		# this is an animated GIF and we need to extract each frame and save it as a file
		# then take the saved frames and import them
		try:
			# query image file to see what the frame delay is (only check the first frame and assume
			# all frame delays are the same for now
			frameDelay = subprocess.check_output(['identify','-format','"%T"', imageDirFullPathName + os.sep + file])
		except:
			print "unable to query image file " + file + " : ", sys.exc_info()[0] 
			raw_input("press enter\n");
			exit(-1)
		frameDelay=int(frameDelay.lstrip('"').split('"',1)[0])
		# convert frame delay from centi-seconds to milli-seconds
		frameDelays[imageName]=frameDelay*10
		try:
			os.makedirs(imageDirFullPathName + "/tmp" )
		except:
			pass
		try:
			subprocess.check_call(['convert','-coalesce', imageDirFullPathName + os.sep + file, imageDirFullPathName + "/tmp/" + file.rsplit('.',1)[0] + '%03d.gif'])
		except:
			# use imagemagick to split out the individual frames and put them in new files with a frame index
			print "unable to extract frames from image file " + file + " : ", sys.exc_info()[0] 
			raw_input("press enter\n");
			exit(-1)
		animationList=[]
		# if this is an animation, put a list of the frame images here
		for indx in range(numFrames):
			animationList.append(imageDirFullPathName + "/tmp/" + file.rsplit('.',1)[0] + '{:03d}'.format(indx) + ".gif")
		imageFiles[imageName]=animationList
	else:
		# if this isn't an animation put a list with the single frame image here
		imageFiles[imageName]=[imageDirFullPathName + os.sep + file]
		frameDelays[imageName]=0

sourcefilename=sys.argv[0]
sketchTemplatesDir = sourcefilename.split(".")[0]
sketchTemplatesDir = sketchTemplatesDir.rsplit(os.sep,1)
sketchTemplatesDir = sketchTemplatesDir[0] + "/sketchTemplates/"

try:
	pov=POV.getPov({'name' : imageDirName})
except:
	print "Unable to create POV object: ", sys.exc_info()[0] 
	raw_input("press enter\n");
	exit(-1)
POV.getScreenSize(pov)
pov.imageDir=imageDirFullPathName;
pov.sketchTemplatesDir=sketchTemplatesDir
pov.get_images(imageFiles)
POV.getModes(pov)
POV.getFrameRate(pov)
pov.setFrameDelays(frameDelays)
POV.getFrameDelays(pov)
pov.getAspectRatios()

try:
	fullSetSketch=POV.createMainProcessingSketchFile(pov)
except:
	print "Unable to create Sketch files: "  , sys.exc_info()[0]
	raw_input("press enter\n");
	exit(-1)
try:
	pov.fullSetDataFiles=POV.createMainProcessingSketchDataFiles(pov)
except:
	print "Unable to create full set data files: "  , sys.exc_info()[0]
	raw_input("press enter\n");
	exit(-1)
pov.standardize_formats()
pov.cropImages()
#try:
POV.getNumChips(pov)
#except:
#	print "Unable to determine the number of chips: "  , sys.exc_info()[0]
#	raw_input("press enter\n");
#	exit(-1)
pov.numLeds()

if pov.pixelSize <= 1:
	print("\nNumber of image pixels per LED is < 2.\nCurrent density is "+str(pov.edgeSize)+"x"+str(pov.edgeSize)+".\nTry increasing the pixel density to > "+str(2*(pov.numLeds() * 2))+"x"+str(2*(pov.numLeds() * 2))+" in GIMP.\nHit [enter] and try again.\n")
	raw_input("press enter\n");
	sys.exit(-1)

try:
	POV.saveImages(pov)
except:
	print "Unable to save the updated image file: "  , sys.exc_info()[0]
	raw_input("press enter\n");
	exit(-1)
try:
	pov.calculatePixels()
except:
	print "Unable to create the pixel arrays: "  , sys.exc_info()[0]
	raw_input("press enter\n");
	exit(-1)
try:
	pov.createSketchStrings()
except:
	print "Unable to create the strings used to create the Sketch files: "  , sys.exc_info()[0]
	raw_input("press enter\n");
	exit(-1)


try:
	fullSetSketch.write( pov.sketchString['full'] )
except:
	print "Unable to create the final FullSet Sketch file: "  , sys.exc_info()[0]
	fullSetSketch.close()
	raw_input("press enter\n");
	exit(-1)
fullSetSketch.close()
print "Done creating " + pov.imageDir + os.sep + pov.driver.name + os.sep+pov.__class__.__name__+"_" + pov.name + os.sep + pov.__class__.__name__ + "_" + pov.name + ".pde\n"
print "Your " + str(len(pov.images.keys())) + " image(s) will consume " + str(pov.getMemorySize()) + " bytes in the flash memory\n"
raw_input("press enter\n");

if compileProcessing:
	try:
		subprocess.call("processing-java --export --force --sketch=\"" + pov.imageDir + os.sep + pov.driver.name + os.sep+pov.__class__.__name__+"_" + pov.name + "\" --output=\"" + pov.imageDir + os.sep + pov.driver.name + os.sep+pov.__class__.__name__+"_" + pov.name + "/application.windows32\"")
	except:
		print "Unable to compile the full set processing sketch: ", sys.exc_info()[0]
		raw_input("press enter\n")
		exit(-1)
	print "Done creating compiled sketch\n"
	raw_input("press enter\n");
