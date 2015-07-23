"""
	Create a Processing sketch under the current directory that will
	simulate a Radial POV sweep of the passed in image file

 The number of LED Driver bits per chip = 
   the number of bits per output (12) * number of outputs (16) = 192
   and the number of bytes per chip = 24

 If we are using TLC5951s, they have 24 channels per chip, so, the number of bits per chip
   = 12 bits per channel * number of outputs (24) = 288
   and the number of bytes per chip = 36
   
 The number of TLC5940 bytes per raster line = 192 / 8 * number of cascaded TLC5940s = 24 * TLC5940_N
 
 The number of TLC5951 bytes per raster line = 288 / 8 * number of cascaded TLC5951s = 36 * TLC5951_N

 We discovered that it takes 17 SPI clock cycles to tranfer a byte of data between the Flash chip and the TLC5940(51)
   8 cycles to get the byte out of flash
   8 cycles to get the byte into the TLC5940(51)
   1 more data clock cycle to handle the looping and control logic (when using optimization level 3 in avg-gcc)

   There are an additional 20 data clock cycles required to service the TLC5940(51) at the end of each raster line:
      disable interrupts
      BLANK high
      Pulse XLAT
      BLANK low
      reset the GSCLK timer counter
      enable interrupts

   
 So, the actual number of data clock cycles per raster line is 17 * number of bytes per raster line + 20
   3 TLC5940 chips: 17 * 24 * 3 + 20 = 1244
   6 TLC5940 chips: 17 * 24 * 6 + 20 = 2468

   2 TLC5951 chips: 17 * 36 * 2 + 20 = 1244
   3 TLC5951 chips: 17 * 36 * 3 + 20 = 1856
   6 TLC5951 chips: 17 * 36 * 6 + 20 = 3692

 If we update the frames at a 30Hz rate, the actual data clock frequency is:
   clock cycles per raster line * 30 * number of raster lines

 There are 197 raster lines per revolution TLC5940 (32 leds radially, no overlapping pixels on outer circumference)
   numRasterLines = int(2 * pi * (32 - 0.5)) = 197
 There are 298 raster lines per revolution TLC5951 (48 leds radially, no overlapping pixels on outer circumference)
   numRasterLines = int(2 * pi * (48 - 0.5)) = 298

 You can control 16 RGB LEDs with 3 TLC5940 chips (16 outputs per chip)
 You can control 32 RGB LEDs with 6 TLC5940 chips (16 outputs per chip)
   That corresponds to an actual data clock signal frequency of:
   3 TLC5940 chips: 1244 * 30 Hz * 197 = 7352040 Hz
   6 TLC5940 chips: 2468 * 30 Hz * 197 = 14585880 Hz (> 10MHz, not workable)

 You can control 16 RGB LEDs with 2 TLC5951 chips (24 outputs per chip)
 You can control 24 RGB LEDs with 3 TLC5951 chips (24 outputs per chip)
 You can control 48 RGB LEDs with 6 TLC5951 chips (24 outputs per chip)
   That corresponds to an actual data clock signal frequency of:
   2 TLC5951 chips: 1244 * 30 Hz * 298 = 11121360 Hz (> 10MHz, not workable, but close)
   3 TLC5951 chips: 1856 * 30 Hz * 298 = 16592640 Hz (> 10MHz, not workable)
   6 TLC5951 chips: 3692 * 30 Hz * 298 = 33006480 Hz (> 10MHz, not workable, also Flash clock <= 30MHz)
   2, 3 and 6 TLC5951s are not workable because the highest data clock signal we can get form the ATMEGA328P
   is 10MHz or (1/2 main clock freq). So, if we reduce the frame refresh from 30 Hz to 27 Hz, it works:
   for 2 chips.  For 3 chips, 18 Hz works, but for 6 chips we have to use 9 Hz, which is much slower than desired.
   2 TLC5951 chips: 1244 * 27 Hz * 298 = 10009224 Hz
   3 TLC5951 chips: 1856 * 18 Hz * 298 = 9955584 Hz
   6 TLC5951 chips: 3692 * 9  Hz * 298 = 9901944 Hz
  
 We can only achieve a SPI clock of Fclk/2 in the ATMEGA328P, which has a maximum clock frequency of 20MHz.
 So, 32 non-overlapping TLC5940 RGB LEDS or 24 non-overlapping TLC5951 RGB LEDS is not possible.  For reasons
 detailed below, the GS clock frequency is similarly limited and will not allow even 6 TLC5940s at a 30Hz
 update frequency.
 This leaves four options:
  1) Elongate the 30 Hz RPOV pixels in the circumferential direction by setting the resolution scaling to < 1.
     6 TLC5940 chips at Fcpu=20MHz corrsponds to SCK = 10MHz, you need to set the resolution scaling to:
       10e6 / 14585880 = 0.686
	 2 TLC5951 chips at Fcpu=20MHz corrsponds to SCK = 10MHz, you need to set the resolution scaling to:
	   10e6 / 11121360 = 0.899
     3 TLC5951 chips at Fcpu=20MHz corrsponds to SCK = 10MHz, you need to set the resolution scaling to:
       10e6 / 16592640 = 0.603
     6 TLC5951 chips at Fcpu=20MHz corrsponds to SCK = 10MHz, you need to set the resolution scaling to:
       10e6 / 33006480 = 0.303 (this elongates the pixels too much at the outer circumference ~ 3X)
  2) Break up the radial LEDs into two sets, 3 TLC5940s per set, each set being driven by its own ATMEGA328P.
     Since we can then transmit each set of data simultaneously, we can cut the required data clock signal
     in half.  To accomodate this approach, we create three different Processing sketches whenever the number
     of TLC5940s is > 3 and is an even number.  One sketch that contains all N chips worth of data, and an inner 
     and outer sketch that each contain the respective half set of data.  You can choose different resolution
     scaling for the complete and half set sketches.
  3) Break up the radial LEDs into three sets, 3 TLC5951s per set, each set being driven by its own ATMEGA328P.
     Since we can then transmit each set of data simultaneously, we can cut the required data clock signal
     by a factor of 3.  To accomodate this approach, we create four different Processing sketches whenever the number
     of TLC5951s is > 3 and is an even multiple of 3.  One sketch that contains all N chips worth of data, and inner, 
     middle, and outer sketches that each contain the respective one third set of data.  You can choose different 
     resolution scaling for the complete and third set sketches.
  4) reduce the refresh rate (this is the least desirable solution):
     For 6 TLC5940s: 20 Hz yields a workable data clock signal requirement of:
       2468 * 20 Hz * 197 = 1008640 Hz
     For 3 TLC5951s: 18 Hz yields a workable data clock signal requirement of:
       1856 * 18 Hz * 298 = 9955584 Hz
     For 6 TLC5951s is simply too much of a load and would require too slow of an update frequency
       3692 * 9 Hz * 298 = 9901944

 Regardless of number of chips a grayscale clock of >= 
 122.88 kHz (4096 * 30 Hz), times the number of circumferential samples is required
 6 TLC5940 = 32 RGB LEDs - 197 circumferential samples (raster lines)
 6 TLC5951 = 48 RGB LEDs - 298 circumferential samples (raster lines)
 For 6 TLC5940: GS clock = 4096 * 30 * 197 = 24207360
 For 6 TLC5951: GS clock = 4096 * 30 * 298 = 36618240

 Once again this won't work, since the highest clock we can derive from the ATMEGA328P is 20MHz.
 To accomodate this, we allow the user to choose between using all 12 bits (4096 GS states) or 
 to only use the number of bits required to clock in the GS data.  After clocking in all the GS
 data, we reset the TLC5940(51) and start again.  This has the effect of making the GS state equal to
 number of bits clocked in to be the maximum brightness value available.
 Remember: the GS clock runs at twice the data clock frequency
 The numGSClockCycles = 2 * number of data clock cycles per raster line 
   3 TLC5940 chips: 2 * 1244 = 2488
   6 TLC5940 chips: 2 * 2468 = 4936 (> 4096, not workable)

   2 TLC5951 chips: 2 * 1244 = 2488
   3 TLC5951 chips: 2 * 1856 = 3712
   6 TLC5951 chips: 2 * 3692 = 7384 (>4096, not workable)

 This means that for a set of 3 chips, we would need a GS clock of:
 3 TLC5940s: GS clock = 2488 * 30 * 197 = 14704080
 3 TLC5951s: GS clock = 3712 * 25 * 197 = 18281600  (25 Hz because of the data clock limitation described earlier)
 For Two chips:
 2 TLC5951s: GS clock = 2488 * 30 * 288 = 21496320 (not workable > 20MHz)
  to make 2 TLC5951s work, we have to slightly reduce the frame refresh rate to 27 Hz:
 2 TLC5951s: GS clock = 2488 * 27 * 288 = 19346688 Hz
  
 We can do this with the AVR if we use a 20MHz clock and use CLKO as the GS clock

 Later in this program, we convert the 8 bit values retrieved from the image into 12 bt values with 
 a maximum brightness value defined by either the number of clock cycles required or 4096, whichever the user chose.
 So, we multiply the 8 bit values by numGSClockCycles/256, then rescale them back into 8 bit values
 before displaying them in Processing.  They get passed through as-is to the Flash and TLC5940(51)
 
"""

import sys
import os
import re
import warnings
import math
from PIL import Image

######################################################################################################
## BEGIN SUBROUTINES #################################################################################
######################################################################################################

def getPov(hash):
	"""return a POV.RPOV or POV.XYPOV instance"""
	povType = raw_input("Do you want (R)adial or (XY) POV? (default [R])\n")
	if povType != '' and povType.lower() != 'r':
		pov = XYPOV(hash)
	else:
		pov = RPOV(hash)
	pov.driver=getDriver()
	if pov.driver.numChannels != 16 and pov.driver.numChannels != 24:
		raise TypeError("The number of channels in the chosen LED driver chip (" + str(pov.driver.numChannels) + ") is not supported.  Only 16 and 24 supported\n")
	return pov

def getDriver():
	"""return a POV.LedDriver instance"""
	chipType = None
	while not chipType:
		chipType = raw_input("Do you want to use TLC5940 (1) or TLC5951 (2)?[2]\n")
		if chipType == '' or chipType == '2':
			chipType= '2'
		try:
				chipType = int(chipType)
		except ValueError:
			print "Invalid Number, must be either 1 (TLC5940) or 2 (TLC5951), try again\n"
			chipType=None
		if chipType and chipType < 1 or chipType > 2:
			print "Invalid Number, must be either 1 (TLC5940) or 2 (TLC5951), try again\n"
			chipType = None
	if chipType == 1:
		driver = LedDriver({'name':'TLC5940','numChannels':16})
	else:
		driver = LedDriver({'name':'TLC5951','numChannels':24})
	return driver
	
def getScreenSize(pov):
	"""set the POV screenSize aspect"""
	screenSize=None
	while not screenSize:
		screenSize=raw_input("Screen size for Processing sketch [500]\n")
		if screenSize == '':
			screenSize='500'
		try:
			screenSize = int(screenSize)
		except:
			print "Invalid number, try again\n"
			screenSize=None
	pov.screenSize=screenSize

def getSerialPort(pov):
	"""Set the COM port number to be used when communicating with the Driver board"""
	portNum = None
	while not portNum:
		portNum = raw_input("What COM port number do you want to use for Serial communications?[8]\n")
		if portNum == '':
			portNum ='8'
		try:
			portNum = int(portNum)
		except:
			print "Invalid number, try again\n"
			portNum=None
	pov.serialPort=portNum

def getModes(pov):
	""" convert the mode of the pictures (RGB or BW)"""
	# convert the image to RGB or L depending on whether or not the original
	# image contained color information
	modes = pov.modes()
	convert_all = raw_input("Do you want to step through the images and choose RGB or B/W conversion?[n]\n")
	if convert_all != '' and convert_all.lower() != 'n':
		for name,image in pov.images.iteritems():
			mode=pov.modes()[name]
			if mode == '1' or mode == 'L' or mode == 'I' or mode == 'F':
				convert = raw_input("Convert " + name + " from B/W to RGB (y/n)[n]\n")
				if convert != '' and convert.lower() != 'n':
					frameIndx=0
					for frame in pov.images[name]:
						pov.images[name][frameIndx] = frame.convert("RGB")
						frameIndx+=1
			else:
				convert = raw_input("Convert " + name + " from RGB to B/W (y/n)?[n]\n")
				if convert != '' and convert.lower() != 'n':
					frameIndx=0
					for frame in pov.images[name]:
						pov.images[name][frameIndx] = frame.convert("L")
						frameIndx+=1

def getFrameDelays(pov):
	""" get the frame delays for any animations"""
	# get the frame delays of any animations
	numAnimations=0
	get_all_framedelays=''
	for name,image in pov.images.iteritems():
		if len(pov.images[name]) > 1:
			numAnimations += 1
	if numAnimations > 0:
		get_all_framedelays = raw_input("Do you want to step through the animations and choose frame delays?  [n]\n")
	if get_all_framedelays != '' and get_all_framedelays != 'n':
		for name,image in pov.images.iteritems():
			if len(pov.images[name]) > 1:
				framedelays = None
				while framedelays == None:
					framedelays = raw_input("What frame delay do you want to use for " + name + " in ms? [" + str(pov.frameDelays[name]) + "]\n")
					if framedelays == '':
						framedelays = str(pov.frameDelays[name])
					try:
						framedelays = int(framedelays)
					except:
						print "Invalid number, try again\n"
						framedelays=None
				pov.frameDelays[name]=framedelays
			else:
				pov.frameDelays[name]=0

def getFrameRate(pov):
	""" set the POV frame rate"""
	frameRate = None
	while not frameRate:
		frameRate = raw_input("What is the frame rate in Hz?[30]\n")
		if frameRate == '':
			frameRate = '30'
		try:
			frameRate=int(frameRate)
		except ValueError:
			print "Invalid Number, try again\n"
		if frameRate and frameRate < 1:
			print "Invalid Number, must be greater than 0, try again\n"
			frameRate = None
	pov.frameRate=frameRate

def getNumChips(pov):
	"""set the number of driver chips to be used"""
	numChips = None
	while not numChips:
		numChips = raw_input("How many " + pov.driver.name + " driver chips do you have? [6]\n")
		if numChips == '':
			numChips = '6'
		try:
			numChips=int(numChips)
		except ValueError:
			print "Invalid Number, try again\n"
		if numChips and numChips < 1 or numChips > pov.driver.maxChips:
			print "Invalid Number, must be between 1 and " + pov.driver.maxChips + ", try again\n"
			numChips = None
		if numChips and not pov.gsFlag and ((numChips * pov.driver.numChannels % 3) != 0):
			print "Invalid Number, number of chips (" + str(numChips) + ") * number of channels per chip (" + str(pov.driver.numChannels) + ") must be a multiple of 3, try again\n"
			numChips = None
	pov.numChips=numChips
	getResolutionScaling(pov)
	# calculate the number of clock cycles required to transfer all the 12 bit values required
	# to fill out all the driver chips.
	# Always use 256 clock cycles or more so we don't scale things down below 256 bits
	# Each byte transferred between the Flash and the TLC5940 takes 17 SPI clock cycles
	# we have to multiply the actual number of bytes transferred by 17 and then add 20
	# clock cycles for resetting the driver to get the total number of clock cycles per transfer
	pov.numDataClockCycles = max(256,pov.numChips * pov.driver.numChannels * pov.driver.bitsPerChannel / 8 * 17 + 20)

	# the GS data clock is 2X the SPI data clock
	pov.numGSClockCycles = pov.numDataClockCycles * 2;

	# If you are sending all 12 bits worth of brightness value (0->4096), then numGSClockCycles
	# will be 4096, if not we set numGSClockCycles to the number of clock cycles required to
	# transfer all 12 bits per channel into all 16 channels of all attached TLC5940 chips.
	# In this case, we assume that the TLC5940 will be reset after that number of clock cycles.
	# This means that numGSClockCycles is a measure of the maximum brightness value achievable.
	# We use numGSClockCycles to scale the 8 bit brightness values read from the image before 
	# hex encoding them and transfering them to Processing and eventually to the TLC5940.
	bitsAns = raw_input("Use all 4096 driver GS states?\nThis yields the highest brightness resolution per pixel,\nbut requires the highest clock speed. (y,n)? [n]\n").lower()
	if bitsAns.lower() == 'y':
		#pov.numGSClockCycles = 4096
		# the TLC5951 auto resets, so we just scale to 8 bits
		pov.numGSClockCycles = 256
	pov.numGSClockCycles = 256
	print "numGSClockCycles = " + str(pov.numGSClockCycles) + "\n"


def getResolutionScaling(pov):
	""" set the pov resolution scaling to be used in the full Processing sketch.
	set the resolution of the outermost ring of the image.  1 means that each LED pixel
	at the outer ring will consist of one LED.  Numbers higher than 1 will will cause the
	the LED pixels to overlap at a resolution of less than 1 LED pixel.
	Numbers less than 1 will cause the LED pixels to be stretched circumferentially.
	Lower numbers will require lower frequency clocks on the Arduino, but will yield lower
	resolution pictures
	0.686 will allow for 197 circumferential samples per frame with 32 RGB LEDs at 20MHz CPU clock
	
	Given the limitations of the Data and GS clocks detailed above in the docstring, we assume that
	you are using half sets of TLC5940s (3 chips) or third sets of TLC5951s (2 chips) so we know it takes
	2488 GS clock cycles to push the data into the 3 TLC5940s or the 2 TLC5951s.  We also empirically determined
	that it takes 1000 GS clock cycles to address the Flash memory at the beginning of each frame.
	To achieve a frame rate of 30 Hz, we can calculate the maximum number of raster lines allowed
	using a 20MHz GS clock as:
	maxNumberRasterLines = 20 MHz / (2488 * 30 Hz + 1000) = 264.  
	We then use this to set the default resolution scaling as either the number required to get 264 raster
	lines or 1, if there are < 264 raster lines in the current configuration
	"""
	inputResolutionScaling = raw_input("Manually enter resolution scaling for each image?[n]")
	if inputResolutionScaling  == '' or inputResolutionScaling.lower() == 'n':
		inputResolutionScaling=False
	for name,image in pov.images.iteritems():
		defaultScaling = min(1.0,float(pov.maxFullSetRasterLines()) / pov.maxTouchingRasterLines()[name])
		resolutionScaling = None
		while not resolutionScaling:
			resolutionScaling=''
			if inputResolutionScaling:
				resolutionScaling = raw_input("Pixel resolution scaling ( > 1 means overlapping, < 1 means elongated)?[" + '{:0.3}'.format(defaultScaling)  + "]\n")
			if resolutionScaling == '':
				resolutionScaling = str(defaultScaling)
			try:
				resolutionScaling = float(resolutionScaling)
			except ValueError:
				print "Invalid Number, try again\n"
			if resolutionScaling <= 0:
				print "Valid values are greater than 0\n"
				resolutionScaling = None
		pov.resolutionScaling[name]=resolutionScaling

def createMainProcessingSketchFile(pov):
	"""return file handle to a .pde file of the same name as the image to put the Processing sketch"""
	# First create the sketch directory
	try:
		os.makedirs(pov.imageDir + os.sep + pov.driver.name + os.sep+pov.__class__.__name__+"_" + pov.name)
	except OSError:
		print "directory already exists\n"
	# then open the full sketch file
	sketch=open( pov.imageDir + os.sep + pov.driver.name + os.sep+pov.__class__.__name__+"_" + pov.name + os.sep + pov.__class__.__name__ + "_" + pov.name + ".pde" , "w")
	return sketch

def createMainProcessingSketchDataFiles(pov):
	"""return file handle to a .pde file of the same name as the image to put the Processing sketch"""
	# First create the sketch directory
	try:
		os.makedirs(pov.imageDir + os.sep + pov.driver.name + os.sep+pov.__class__.__name__+"_" + pov.name + "/data")
	except OSError:
		print "directory already exists\n"
# then open the full sketch data file
	dataFiles={}
	for name,image in pov.images.iteritems():
		dataFiles[name]=open( pov.imageDir + os.sep + pov.driver.name + os.sep+pov.__class__.__name__+"_" + pov.name + "/data/"+name+".txt", "w")
	return dataFiles

def saveImages(pov):
	"""save the processed picture in the full size sketch directory"""
	try:
		os.makedirs(pov.imageDir + os.sep + pov.driver.name + os.sep+pov.__class__.__name__+"_" + pov.name + "/tmp" )
	except:
		pass
	for name,image in pov.images.iteritems():
		for frame in image:
			frame.save(pov.imageDir + os.sep + pov.driver.name + os.sep+pov.__class__.__name__+"_" + pov.name + "/tmp/" + pov.__class__.__name__ + "_" + name + "_" + pov.aspectRatioStrings[name] + "_" + pov.modes()[name] + ".jpeg")

######################################################################################################
## END OF SUBROUTINES ################################################################################
######################################################################################################

######################################################################################################
## BEGIN LedDriver Class Definition ##################################################################
######################################################################################################

class LedDriver(object):
	"""LedDriver class"""
	numChannels = 16
	bitsPerChannel = 12
	name = 'TLC5940'
	maxChips = 21

	def __init__(self,data):
		if isinstance(data,dict):
			for key,value in data.iteritems():
				if key == 'numChannels':
					self.numChannels=value
				if key == 'bitsPerChannel':
					self.bitsPerChannel=value
				if key == 'name':
					self.name=value
				if key == 'maxChips':
					self.maxChips=value
		else:
			raise TypeError("Invalid data type passed to LedDriver __init__.  Should be a dictionary\n")

	def __str__(self):
		return "LedDriver instance named " + self.name;

	def numDataClockCyclesPerChip(self,dataClockCyclesPerByte):
		"""The number of Data clock cycles required to shift in all channels worth of data
		the dataClockCyclesPerByte is a value that reflects total overhead in getting the data
		from wherever it resides into the chip
		"""
		bytesPerChip = self.bitsPerChannel * self.numChannels / 8
		return bytesPerChip * dataClockCyclesPerByte

######################################################################################################
## END LedDriver Class Definition ####################################################################
######################################################################################################

######################################################################################################
## BEGIN POV Class Definition #######################################################################
######################################################################################################

class POV(object):
	"""POV class"""
	driver = LedDriver
	numChips=1
	images = {}
	imageDir = os.getcwd()
	sketchTemplatesDir = os.getcwd()
	fullSetDataFiles={}
	name = ''
	serialPort = 8
	gsFlag = {}
	hexCharsPerWord = {}
	resolutionScaling = {}
	partialResolutionScaling = {}
	createHalfSets = False
	createThirdSets = False
	xsize={}
	ysize={}
	origXSize = {}
	origYSize = {}
	edgeSize=1
	pixelSize={}
	screenSize=500
	controlHeight=200
	controlBorder=5
	aspectRatios = {}
	aspectRatioStrings = {}
	numGSClockCycles=1
	numDataClockCycles=1
	numDataClockCyclesPerByte=17
	dataClockOverheadPerLine=20
	dataClockOverheadPerFrame=500
	numFullSetPixelsMax=1
	numFullSetPixels={}
	frameDelays={}
	frameRate=1
	pixels={'full':{}}
	sketchString ={'full':""""""}

	def __init__(self,data={}):
		if isinstance(data,dict):
			for key,value in data.iteritems():
				if key == 'driver':
					self.driver=value
				if key == 'image':
					self.image=value
				if key == 'name':
					self.name=value
				if key == 'type':
					self.type=value
		else:
			raise TypeError("Invalid data type passed to RPOV __init__.  Should be a dictionary\n")
	def __str__(self):
		return "POV instance " + self.name;

	def modes(self):
		imageModes={}
		for name,image in self.images.iteritems():
			# we assume that all of the images in a sequence have the same mode, so just grab the first one
			imageModes[name]=image[0].mode
		return imageModes

	def standardize_formats(self):
		for name,mode in self.modes().iteritems():
			if mode == '1' or mode == 'L' or mode == 'I' or mode == 'F':
				frameIndx=0
				for frame in self.images[name]:
					self.images[name][frameIndx] = frame.convert("L")
					frameIndx+=1
				self.hexCharsPerWord[name] = 3
				self.gsFlag[name]=True
			else:
				frameIndx=0
				for frame in self.images[name]:
					self.images[name][frameIndx] = frame.convert("RGB")
					frameIndx+=1
				self.hexCharsPerWord[name] = 9
				self.gsFlag[name]=False

	def get_images(self,images):
		for name,image in images.iteritems():
			self.images[name]=[]
			for frame in image:
				try:
					self.images[name].append(Image.open(frame))
				except:
					print "Unable to open image file: " + image +"\n"
					raw_input("press enter\n");
					exit(-1)

	def setFrameDelays(self,frameDelays):
		"""set the default frame delays"""
		for name,image in self.images.iteritems():
			self.frameDelays[name]=frameDelays[name]

	def cropImages(self):
		"""return a cropped image for a POV"""
		for name,image in self.images.iteritems():
			# get image size
			frameIndx=0
			for frame in image:
				(self.xsize[name], self.ysize[name]) = frame.size
				self.origXSize[name]=self.xsize[name]
				self.origYSize[name]=self.ysize[name]
				imageAspect = float(self.xsize[name]) / float(self.ysize[name])

				# crop rectangle
				# (upper left coordinate,lower right coordinate)
				if imageAspect <= self.aspectRatios[name] :
					imageRectangle = (0,int(self.ysize[name] / 2 - 1.0 / self.aspectRatios[name] * self.xsize[name] / 2),self.xsize[name],int(self.ysize[name] / 2 + 1.0 / self.aspectRatios[name] * self.xsize[name] / 2))
				else:
					imageRectangle = (int(self.xsize[name] / 2 - self.aspectRatios[name] * self.ysize[name] / 2),0,int(self.xsize[name] / 2 + self.aspectRatios[name] * self.ysize[name] / 2),self.ysize[name])

				# crop the image to a rectangle centered vertically and horizontally within the image
				self.images[name][frameIndx]=frame.crop(imageRectangle)
				(self.xsize[name], self.ysize[name]) = self.images[name][frameIndx].size
				frameIndx+=1

	def maxFullSetRasterLines(self):
		""""return the maximum number of raster lines that can be supported for the given frame rate in Hz operation"""
		return int(10e6 / (self.numDataClockCyclesPerFullLine() * self.frameRate + self.dataClockOverheadPerFrame))

	def maxPartialSetRasterLines(self):
		""""return the maximum number of partial set raster lines that can be supported for the given frame rate in Hz operation"""
		if self.createHalfSets:
			return int(10e6 / (self.numDataClockCyclesPerHalfLine() * self.frameRate + self.dataClockOverheadPerFrame))
		else:
			return int(10e6 / (self.numDataClockCyclesPerThirdLine() * self.frameRate + self.dataClockOverheadPerFrame))

	def numDataClockCyclesPerFullLine(self):
		return self.driver.numDataClockCyclesPerChip(self.numDataClockCyclesPerByte)  * self.numChips + self.dataClockOverheadPerLine

	def numDataClockCyclesPerHalfLine(self):
		return self.driver.numDataClockCyclesPerChip(self.numDataClockCyclesPerByte)  * self.numChips / 2 + self.dataClockOverheadPerLine

	def numDataClockCyclesPerThirdLine(self):
		return self.driver.numDataClockCyclesPerChip(self.numDataClockCyclesPerByte) * self.numChips / 3 + self.dataClockOverheadPerLine

	def calculatePixels(self):
		"""calculate full and partial set pixel arrays"""
		self.calculateFullSetPixels()

	def getMemorySize(self):
		"""return the size of all images in memory, assuming that each LED uses 12 bits.
		Include the space required for the header CSV values"""
		memorySize=0
		if len(self.pixels['full']) == 0:
			return memorySize
		else:
			imageIndx=0
			numLeds=self.numLeds()
			for name,image in self.images.iteritems():
				frameIndx=0
				for frame in image:
					# number of bytes in the image = 
					# number of raster lines * number of LED pixels * number LEDs per LED pixel
					memorySize += len(self.pixels['full'][name][frameIndx])*len(self.pixels['full'][name][frameIndx][0])*len(self.pixels['full'][name][frameIndx][0][0])*3/2
					frameIndx += 1
				# calculate the amount of memory required for the header CSV values
				memorySize += len(self.getHeaderCsv()[name])
				imageIndx += 1
		return memorySize

	def getHeaderCsv(self):

		"""return the CSV header that will precede each image when sending to the board"""
		# header values
		# 0 - numImages (integer)
		# 1 - imageNum (integer)
		# 2 - frameDelay (integer)
		# 3 - lineLength (integer)
		# 4 - numLines (integer)
		# 5 - numBoards (integer)
		# 6 - numFrames (integer)
		# 7 - gsFlag (0 or 1)
		# 8 - reflect (0 or 1)
		headerString = {}
		imageIndx=0
		names=self.images.keys()
		names.sort()
		for name in names:
			# numImages,imageNum, frameDelay
			headerString[name]=""""""
			headerString[name] += str(len(self.images))+','+str(imageIndx)+','+str(self.frameDelays[name])+','
			# lineLength,numLines
			headerString[name] += str(self.numLeds()[name]*self.hexCharsPerWord[name]/3)+','+str(self.numFullSetPixels[name])+','
			# numBoards,numFrames
			headerString[name] += str(self.numChips / 2)+','+str(len(self.images[name]))+','
			# gsFlag,reflect
			if self.gsFlag[name]:
				gsFlag = 1
			else:
				gsFlag = 0
			if self.theta>=360:
				reflect=0
			else:
				reflect=1
			headerString[name] += str(gsFlag)+','+str(reflect)+','
			imageIndx += 1
		return headerString

	def createSketchStrings(self):
		"""create the desired sketch string(s) based on the POV object's current state"""
		self.createFullSetSketchString()
		self.sketchString['full'] += self.sketchSuffix()
		self.createFullSetDataFiles()

	def sketchPrefix(self,type):
		"""return the first part of full set the Processing sketches"""
		try:
			f=open(self.sketchTemplatesDir + 'sketchPrefix.txt');
		except:
			print "Unable to read sketchPrefix.txt: "  , sys.exc_info()[0]
			raw_input("press enter\n");
			exit(-1)
		prefix=f.read();
		imagesString="""{"""
		numPixelsString="""{"""
		hexCharsPerWordString="""{"""
		gsFlagString="""{"""
		numFramesString="""{"""
		frameDelayString="""{"""
		names = self.images.keys()
		names.sort()
		for name in names:
			numPixelsString += str(self.numFullSetPixels[name]) + ","
			imagesString += "\"" + name + ".txt\","
			hexCharsPerWordString += str(self.hexCharsPerWord[name]) + ","
			gsFlagString += str(self.gsFlag[name]).lower() + ","
			numFramesString += str(len(self.images[name])) + ","
			frameDelayString += str(self.frameDelays[name]) +","
		numPixelsString=numPixelsString[0:len(numPixelsString)-1]
		imagesString=imagesString[0:len(imagesString)-1]
		hexCharsPerWordString=hexCharsPerWordString[0:len(hexCharsPerWordString)-1]
		gsFlagString=gsFlagString[0:len(gsFlagString)-1]
		numFramesString=numFramesString[0:len(numFramesString)-1]
		frameDelayString=frameDelayString[0:len(frameDelayString)-1]
		imagesString += """}"""
		numPixelsString += """}"""
		hexCharsPerWordString += """}"""
		gsFlagString += """}"""
		numFramesString += """}"""
		frameDelayString += """}"""
		return prefix.format(
		SCREENSIZE=self.screenSize,
		CONTROLHEIGHT=self.controlHeight,
		CONTROLBORDER=self.controlBorder,
		SERIALPORT=self.serialPort,
		XSIZE=self.xsize,
		YSIZE=self.ysize,
		EDGESIZE=self.edgeSize,
		NUMPIXELSOUTER=numPixelsString,
		NUMBOARDS=self.numChips / 2,
		NUMFRAMES=numFramesString,
		FRAMEDELAY=frameDelayString,
		NUMIMAGES=str(len(self.images)),
		IMAGES=imagesString,
		GSFLAG=gsFlagString,
		THETA=self.theta,
		HEXCHARSPERWORD=hexCharsPerWordString)

	def sketchSuffix(self):
		"""return the last part of the Processing sketches"""
		try:
			f=open(self.sketchTemplatesDir + 'sketchSuffix.txt');
		except:
			print "Unable to read sketchSuffix.txt: "  , sys.exc_info()[0]
			raw_input("press enter\n");
			exit(-1)
		return f.read()

	def createFullSetDataFiles(self):
		"""create the fullset data file"""
		# scale up the 8 bit data to 12 bits to fit the TLC5940
		# make sure the full 8 bit range is extended to fill out either the full 12 bits (4096)
		# or numGSClockCycles depending on how you answered the question about using all 12 bits
		# for brightness asked earlier.
		hexFormatString='{:03x}'
		for name,image in self.images.iteritems():
			frameIndx=0
			string=""""""
			for frame in image:
				for x in range(self.numFullSetPixels[name]):
					line = """"""
					for y in range(self.numLeds()[name]):
						if self.hexCharsPerWord[name] == 3:
							line = line + hexFormatString.format(int(self.pixels['full'][name][frameIndx][x][y][0] * 1.0 * min(self.numGSClockCycles,4096) / 256))
						else:
							line = line + hexFormatString.format(int(self.pixels['full'][name][frameIndx][x][y][0] * 1.0 * min(self.numGSClockCycles,4096) / 256)) + hexFormatString.format(int(self.pixels['full'][name][frameIndx][x][y][1] * 1.0 * min(self.numGSClockCycles,4096) / 256)) + hexFormatString.format(int(self.pixels['full'][name][frameIndx][x][y][2] * 1.0 * min(self.numGSClockCycles,4096) / 256))
					line = line + "\n"
					string = string + line
				frameIndx+=1
			string=string[0:len(string)-1]
			self.fullSetDataFiles[name].write(string)
			self.fullSetDataFiles[name].close()

	def createFullSetSketchString(self):
		"""create the complete full set sketch string and store it in sketchString['full']"""
		string = self.sketchPrefix('full')
		string = string + """
int numGSClockCycles = {NUMCLOCKCYCLES};
String byteStringCurrent[] = {{}};
int partialSet = 1; // set to 2 if this is a partial set sketch, 1 otherwise
int nextPartialSet = 0; //  set to 1 if this is a partial set sketch and this is an outer half set
""".format(NUMCLOCKCYCLES=self.numGSClockCycles)
		self.sketchString['full']=string + self.sketchPovSpecific(1,'full')

######################################################################################################
## END POV Class Definition ##########################################################################
######################################################################################################

######################################################################################################
## BEGIN RPOV Class Definition #######################################################################
######################################################################################################

class RPOV(POV):
	"""RPOV class"""
	theta = 360
	modulation_value = 1.0
	mod_alpha = 0.5
	mod_threshold = 0.0

	def __str__(self):
		return "RPOV instance " + self.name;

	def getAspectRatios(self):
		"""set a new aspect ratio for an RPOV
		 set the aspect ratio of the final image.
		 Aspect ratio < 1 implies that the final image will be taller than it is wide.
		   This means that the frame rate will be faster than it would be for a 1:1 or greater aspect ratio
		   since we are assumed to be sweeping the LEDs at a constant velocity in the X-direction
		 Aspect ratio > 1 implies that the final image will be wider than it is tall.
		   This means that the frame rate will be slower than it would be for a 1:1 or lesser aspect ratio
		   since we are assumed to be sweeping the LEDs at a constant velocity in the X-direction
		"""
		# this is an RPOV, so set the aspect ratio from the angle through which we will rotate
		theta = None
		while not theta:
			thetaString = raw_input("Theta through which we will rotate.[360]\n")
			if thetaString == '':
				thetaString = '360'
			try:
				theta = float(thetaString)
			except ValueError:
				print "Invalid Number, try again\n"
				theta = None
			if theta <= 0 or theta> 360:
				print "Invalid Number, must be between 0 and 360 degrees, try again\n"
				theta = None
		self.theta = theta
		if self.theta <= 180.0:
			alpha = (math.pi - self.theta * 2.0 * math.pi / 360.0) / 2.0
			aspectRatio = 2.0 * math.cos(alpha)
		else:
			alpha = (self.theta * 2.0 * math.pi / 360.0- math.pi) / 2.0
			aspectRatio = 2.0 / (1.0 + math.sin(alpha))
		aspectRatioString="%1.3f" % (aspectRatio)
		for name,image in self.images.iteritems():
			self.aspectRatioStrings[name]=aspectRatioString.replace(".","_")
			self.aspectRatios[name]=aspectRatio
		

	def numLeds(self):
		"""return the number of LEDs to be used"""
		# Number of LEDs.  Assume we fill out all channels of the driver chip with LEDs
		# keep in mind that we forced # TLC5940 chips to be a multiple of 3 to ensure that all channels are used
		numLeds = {}
		for name,image in self.images.iteritems():
			if self.gsFlag[name]:
				numLeds[name] = self.numChips * self.driver.numChannels
			else:
				numLeds[name]= self.numChips * self.driver.numChannels / 3
			if self.theta <= 180:
				if int(self.ysize[name] / numLeds[name]) < 2:
					# increase the image resolution so there are sufficient pixels to sample
					frameIndx=0
					for frame in image:
						self.images[name][frameIndx]=frame.resize((int(self.aspectRatios[name]*numLeds[name]*2),numLeds[name]*2))
						frameIndx+=1
					(self.xsize[name], self.ysize[name]) = self.images[name][0].size
				self.pixelSize[name]=int(self.ysize[name] / numLeds[name])
			else:
				if int(self.xsize[name] / (numLeds[name] * 2)) < 2:
					# increase the image resolution so there are sufficient pixels to sample
					frameIndx=0
					for frame in image:
						self.images[name][frameIndx]=frame.resize((numLeds[name]*4,int(float(numLeds[name]*4)/self.aspectRatios[name])))
						frameIndx+=1
					(self.xsize[name], self.ysize[name]) = self.images[name][0].size
				self.pixelSize[name]=int(self.xsize[name] / (numLeds[name] * 2))
		return numLeds

	def maxTouchingRasterLines(self):
		"""calculate the maximum number of raster lines required in order to maintain the LEDs just touching
		at the outer circumference
		"""
		# the number of pixels that will fit in the outer diameter arc described by self.theta without overlapping.
		# alternatively you can just set this number to some value to define the resolution
		# of the RPOV image.  We move in by 1/2 pixelSize on the radius to get on the circumference
		# that runs through the center of the outer LED pixel
		maxTouchingRasterLines = {}
		for name,image in self.images.iteritems():
			maxTouchingRasterLines[name] = int(self.theta * 2.0 * math.pi / 360.0 * (self.numLeds()[name] - 0.5))
		return maxTouchingRasterLines

	def calculateFullSetPixels(self):
		"""calculate full set pixel lists"""
		#######################################
		for name,image in self.images.iteritems():
			frameIndx=0
			self.pixels['full'][name]=[]
			for frame in image:
				# actual diameter of the circle in image pixels being swept by the outermost LED.
				rpovDiam = self.numLeds()[name] * 2 * self.pixelSize[name]

				# origin of the sweep assuming that 0,0 is at the upper left with pos. x to the right
				# and pos. y down
				if self.theta <= 180:
					rpovOrigin = [int(self.xsize[name] / 2), int(self.ysize[name])]
				else:
					rpovOrigin = [int(self.xsize[name] / 2), int(self.xsize[name] / 2)]

				self.numFullSetPixels[name] = int(self.maxTouchingRasterLines()[name] * self.resolutionScaling[name])

				# number of degrees subtended by one RPOV LED pixel at the outer diameter
				thetaIncrLed = self.theta / self.numFullSetPixels[name]

				# set up list of radii for each swept LED pixel in image pixels
				# this is the radius of the inner arc of the swept RPOV pixel
				radii = [None] * self.numLeds()[name]
				for k in range(self.numLeds()[name]):
					radii[k] = self.pixelSize[name] * k

				# set up list of rotation degrees for each subsequent row of pixels in the sweep
				degrees = [None] * self.numFullSetPixels[name]
				for k in range(self.numFullSetPixels[name]):
					degrees[k] = 90.0 + self.theta / 2.0 - thetaIncrLed * k

				# set up a 3D list to hold the RPOV pixels [self.numLeds() x self.numFullSetPixels x pixel information]
				# self.pixels['full'][cx][rx][hexCharsPerWord]
				# cx = the location around the circumference
				# rx = the pixel location along the radius
				# hexCharsPerWord = list of the pixel information characters
				self.pixels['full'][name].append([None] * self.numFullSetPixels[name])
				for cx in range(self.numFullSetPixels[name]):
					self.pixels['full'][name][frameIndx][cx] = [None] * self.numLeds()[name]
					for rx in range(self.numLeds()[name]):
						self.pixels['full'][name][frameIndx][cx][rx] = [None] * (self.hexCharsPerWord[name] / 3)
				
				# this section fills out the self.pixels['full'][][][] array for the full set of LEDs 
				degIncr = 0
				for degree in degrees:
					radIncr = 0
					for radius in radii:
						gsvPixelAvg = 255
						redPixelAvg = 255
						bluPixelAvg = 255
						grnPixelAvg = 255
						# number of degrees subtended by one image pixel at this radius
						# we step through the arc at this resolution to grab the image pixels
						# check at the radius halfway into the image pixel
						thetaIncrImage = math.asin(1.0 / (radius + 0.5 * self.pixelSize[name])) * 360.0 / (2 * math.pi)

						# create a sequence of theta sampling points througout the LED pixel arc 
						# the sampling points are mid way through each thetaIncrImage sampling arc
						# make sure that we take at least one sample, this is important
						# in the innermost sampling interval, where we may potentially have an arc that
						# is smaller than an image pixel
						thetaIncrs=[None] * max(1,int(thetaIncrLed / thetaIncrImage))
						for theta in range(len(thetaIncrs)):
							thetaIncrs[theta] = theta * thetaIncrImage + degree + thetaIncrImage / 2
						
						# calculate the RPOV arc dimensions in which to sample the image
						innerRad = int(radius)
						outerRad = int(radius + self.pixelSize[name])
						
						# step through all image pixels in the RPOV LED pixel sampling arc and average them
						gsvPixelSum = 0
						redPixelSum = 0
						grnPixelSum = 0
						bluPixelSum = 0
						pixelsSampled = 0
						for arcRad in range(innerRad,outerRad+1):
							for arcTheta in thetaIncrs:
								xVal = int((rpovOrigin[0] + arcRad * math.cos(2 * math.pi / 360 * arcTheta)))
								yVal = int(rpovOrigin[1] - arcRad * math.sin(2 * math.pi / 360 * arcTheta))
								if xVal < self.xsize[name] and yVal < self.ysize[name] and xVal >= 0 and yVal >= 0:
									try:
										if self.gsFlag[name]:
											gsvPixel = frame.getpixel((xVal,yVal))
											gsvPixelSum += gsvPixel
										else:
											(redPixel,grnPixel,bluPixel) = frame.getpixel((xVal,yVal))
											redPixelSum += redPixel
											grnPixelSum += grnPixel
											bluPixelSum += bluPixel
									except IndexError:
										raise IndexError("Index Error in main pixel arc (" + str(xVal) + "," + str(yVal) + ").")
									pixelsSampled += 1
								if pixelsSampled > 0:
									if self.gsFlag[name]:
										gsvPixelAvg = gsvPixelSum / pixelsSampled
									else:
										redPixelAvg = redPixelSum / pixelsSampled
										grnPixelAvg = grnPixelSum / pixelsSampled
										bluPixelAvg = bluPixelSum / pixelsSampled
								else:
									gsvPixelAvg = 255
									redPixelAvg = 255
									grnPixelAvg = 255
									bluPixelAvg = 255
						#  stuff the resulting data into the pixels list
						if self.gsFlag[name]:
							self.pixels['full'][name][frameIndx][degIncr][radIncr][0] =  gsvPixelAvg
						else:
							self.pixels['full'][name][frameIndx][degIncr][radIncr][0] =  redPixelAvg
							self.pixels['full'][name][frameIndx][degIncr][radIncr][1] =  grnPixelAvg
							self.pixels['full'][name][frameIndx][degIncr][radIncr][2] =  bluPixelAvg
						radIncr += 1
					degIncr += 1
				frameIndx+=1

	def sketchPovSpecific(self,partialSet,type):
		"""return the POV-type specific code"""
		sweptLength=int(self.screenSize / 2)
		screenX=int(sweptLength * 2)
		screenY=int(sweptLength * 2) + 2 * self.controlBorder + self.controlHeight
		try:
			f=open(self.sketchTemplatesDir + 'sketchRpovSpecific.txt');
		except:
			print "Unable to read sketchRpovSpecific.txt: "  , sys.exc_info()[0]
			raw_input("press enter\n");
			exit(-1)
		string=f.read()
		return string.format(
		SCREENSIZE=self.screenSize,
		SCREENX=screenX,
		SCREENY=screenY,
		THETA=self.theta)

######################################################################################################
## END RPOV Class Definition #########################################################################
######################################################################################################

######################################################################################################
## BEGIN XYPOV Class Definition ######################################################################
######################################################################################################

class XYPOV(POV):
	"""XYPOV class"""
	origXSize = {}
	origYSize = {}

	def __str__(self):
		return "XYPOV instance"

	def getAspectRatio(self):
		"""set a new aspect ratio for an XYPOV
		 set the aspect ratio of the final image.
		 Aspect ratio < 1 implies that the final image will be taller than it is wide.
		   This means that the frame rate will be faster than it would be for a 1:1 or greater aspect ratio
		   since we are assumed to be sweeping the LEDs at a constant velocity in the X-direction
		 Aspect ratio > 1 implies that the final image will be wider than it is tall.
		   This means that the frame rate will be slower than it would be for a 1:1 or lesser aspect ratio
		   since we are assumed to be sweeping the LEDs at a constant velocity in the X-direction
		"""
		# this is an XYPOV, so ask the user for the aspect ratio directly
		try:
			aspectRatio = None
			while not aspectRatio:
				aspectRatioString = raw_input("Aspect ratio of the final image.\n(1:1,4:3,16:9,...)[1:1]?\n")
				if aspectRatioString == '':
					aspectRatioString = '1:1'
				aspectRatio=re.match(r"(\d+):(\d+)",aspectRatioString)
				if aspectRatio is None:
					print "Invalid Entry ["+aspectRatio+"], try again\n"
				else:
					try:
						aspectRatio = float(aspectRatio.groups()[0])/float(aspectRatio.groups()[1])
					except ValueError:
						aspectRatio = None
			self.aspectRatioString=aspectRatioString.replace(":","_")
		except:
			print "Unable to set aspect ratio: "  , sys.exc_info()[0]
			raw_input("press enter\n");
			exit(-1)
		self.aspectRatio=aspectRatio

	def numLeds(self):
		"""return the number of LEDs to be used"""
		# Number of LEDs.  Assume we fill out all channels of the driver chip with LEDs
		# keep in mind that we forced # TLC5940 chips to be a multiple of 3 to ensure that all channels are used
		if self.gsFlag:
			numLeds = self.numChips * self.driver.numChannels
		else:
			numLeds = self.numChips * self.driver.numChannels / 3
		for name,ysize in self.ysize.iteritems():
			self.pixelSize[name]=float(float(self.ysize[name]) / numLeds)
		return numLeds

	def maxTouchingRasterLines(self):
		"""calculate the number of raster lines given the aspect ratio"""
		return int(self.aspectRatio * self.numLeds())

	def calculateFullSetPixels(self):
		"""calculate the full set pixel lists"""
		self.numFullSetPixels = int(self.maxTouchingRasterLines() * self.resolutionScaling)
		# set up list of yValues for each swept LED pixel in image pixels
		# this is the yValue of the lower edge of the swept XYPOV pixel
		yValues = [None] * self.numLeds()
		for k in range(self.numLeds()):
			yValues[k] = int(self.pixelSize * (self.numLeds()-k-1))

		# set up list of xValues for each swept LED pixel in image pixels
		# this is the xValue of the left edge of the swept XYPOV pixel
		xValues = [None] * self.numFullSetPixels
		for k in range(self.numFullSetPixels):
			xValues[k] = int(self.pixelSize / self.resolutionScaling * k)

		# set up a 3D list to hold the XYPOV pixels [self.numLeds() x numFullSetPixels x pixel information]
		# pixels[x][y][hexCharsPerWord]
		# x = the pixel location in the x-dimension
		# y = the pixel location in the y-dimension
		# hexCharsPerWord = list of the pixel information characters
		self.pixels['full'] = [None] * self.numFullSetPixels
		for x in range(self.numFullSetPixels):
			self.pixels['full'][x] = [None] * self.numLeds()
			for y in range(self.numLeds()):
				self.pixels['full'][x][y] = [None] * (self.hexCharsPerWord / 3)

		# this section fills out the self.pixels['xxx'][][][] array for the LEDs 
		xIndex = 0
		for xVal in xValues:
			yIndex=0
			for yVal in yValues:
				gsvPixelAvg = 255
				redPixelAvg = 255
				bluPixelAvg = 255
				grnPixelAvg = 255
				# step through all image pixels in the XYPOV LED pixel sampling rectangle and average them
				gsvPixelSum = 0
				redPixelSum = 0
				grnPixelSum = 0
				bluPixelSum = 0
				pixelsSampled = 0
				for yIncr in range(yVal,int(yVal + self.pixelSize)):
					for xIncr in range(xVal,int(xVal + self.pixelSize)):
						if xIncr < self.xsize and yIncr < self.ysize and xIncr >= 0 and yIncr >= 0:
							try:
								if self.gsFlag:
									gsvPixel = self.image.getpixel((xIncr,yIncr))
									gsvPixelSum += gsvPixel
								else:
									(redPixel,grnPixel,bluPixel) = self.image.getpixel((xIncr,yIncr))
									redPixelSum += redPixel
									grnPixelSum += grnPixel
									bluPixelSum += bluPixel
							except IndexError:
								raise IndexError("Index Error in main pixel rectangle (" + str(xVal) + "," + str(yVal) + ").")
							pixelsSampled += 1
						if pixelsSampled > 0:
							if self.gsFlag:
								gsvPixelAvg = gsvPixelSum / pixelsSampled
							else:
								redPixelAvg = redPixelSum / pixelsSampled
								grnPixelAvg = grnPixelSum / pixelsSampled
								bluPixelAvg = bluPixelSum / pixelsSampled
						else:
							gsvPixelAvg = 255
							redPixelAvg = 255
							grnPixelAvg = 255
							bluPixelAvg = 255
				#  stuff the resulting data into the pixels list
				if self.gsFlag:
					self.pixels['full'][xIndex][yIndex][0] =  gsvPixelAvg
				else:
					self.pixels['full'][xIndex][yIndex][0] =  redPixelAvg
					self.pixels['full'][xIndex][yIndex][1] =  grnPixelAvg
					self.pixels['full'][xIndex][yIndex][2] =  bluPixelAvg
				yIndex += 1
			xIndex += 1

	def sketchPovSpecific(self,partialSet,type):
		"""return the POV-type specific code"""
		if type == 'full':
			numLines=self.numFullSetPixels
		else:
			numLines=self.numPartialSetPixels
		if self.aspectRatio <= 1:
			pixelXSize = (self.screenSize * self.aspectRatio)/numLines;
			pixelSize = float(self.screenSize)/self.numLeds();
		else:
			pixelXSize = float(self.screenSize)/numLines;
			pixelSize = float(self.screenSize)/self.aspectRatio/self.numLeds();
		sweptLength=partialSet * self.numLeds() * pixelSize;
		screenX=int(numLines * pixelXSize)
		screenY=int(self.numLeds() / partialSet * pixelSize + 2 * self.controlBorder + self.controlHeight)
		try:
			f=open(self.sketchTemplatesDir + 'sketchXYpovSpecific.txt');
		except:
			print "Unable to read sketchXYpovSpecific.txt: "  , sys.exc_info()[0]
			raw_input("press enter\n");
			exit(-1)
		string=f.read()
		return string.format(
		SCREENSIZE=self.screenSize,
		SCREENX=screenX,
		SCREENY=screenY,
		PIXELXSIZE=pixelXSize,
		PIXELSIZE=pixelSize)

######################################################################################################
## END XYPOV Class Definition ########################################################################
######################################################################################################