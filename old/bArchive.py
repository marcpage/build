#!/usr/bin/env python

__all__ = [ # exported symbols from this module
	"validate", 		# function to validate/repair/restore and archive with/to a directory
	"generate",			# generate an archive from a directory
	"ZipArchive",		# A wrapper for ZipArchive files
	"kStandardCodecs",	# Standard codecs defined by this module
	"kAllKnownHashes",	# Hash algorithms found by this module
	"kMD5Hash",			# Just the MD5 hash algorithm
	"platformEOL",		# The platform's end of line character
	"platformTempDir",	# The platform's temporary directory
	"XMLCodec",			# xml encoding &#xXX;
	"DollarHexCodec",	# codec to convert undesirables to $XX
	"Base64Codec",		# standard base64 encoding
	"ManifestCompare",	# xml.sax handler
	"VerifyHandler",	# For ManifestCompare to handle each file/dir/link as we encounter them
	"transferAndHash",	# Transfer data from one stream and hash the contents and convert eols
	"hashListsMatch",	# compares results of transferAndHash from two transfers
	"reportException",	# handles reporting exceptions when you catch them
]

""" Mac OS X 10.4 (Tiger)			Python 2.3.5
	Mac OS X 10.5 (Leopard/ppc)		Python 2.5.1
	Mac OS X 10.6 (Snow Leopard)	Python 2.6.1

	Test Dataset: LabVIEW 8.6 Mac Directory
			544 MB
			27,879 Files (9,291 Text Files)
			1,319 Directories
			90 Symlinks
		12 minutes to generate archive
		38 minutes to restore archive to empty directory
		5 minutes to quickly validate
		7 minutes to fully validate
"""
import os
import re
import sys
import bDOM
import stat
import time
import base64
import random
import string
import xml.sax
import zipfile
import calendar
import datetime
import cStringIO
import traceback
try:
	import hashlib
	kHashLibAvailable= True
except:
	import md5
	kHashLibAvailable= False
try:
	import xattr
	kXattrAvailable= True
except:
	kXattrAvailable= False

class StreamHasher:
	def __init__(self, stream, hashers):
		""" hashers is a list of (str(name), hasher(update), isText)
		"""
		self.__stream= stream
		self.__hashers= hashers
		self.__lastEndedWithCarriageReturn= False
		self.__readMode= None
	def write(self, block):
		self.__validate(reading= False)
		self.__updateHashers(block)
		self.__stream.write(block)
	def read(self, size):
		self.__validate(reading= True)
		block= self.__stream.read(size)
		self.__updateHashers(block)
		return block
	def readline(self):
		self.__validate(reading= True)
		block= self.__stream.readline()
		self.__updateHashers(block)
		return block
	def __validate(self, reading):
		if reading != self.__readMode and None != self.__readMode:
			raise AssertionError("Cannot use StreamHasher for read and write simultaneously")
		self.__readMode= reading
	def __updateHashers(self, block):
		textBlock= self.__getTextBlock(block)
		for hasher in self.__hashers:
			if hasher[2]: # isText
				hasher[1].update(textBlock)
			else:
				hasher[1].update(block)
	def __getTextBlock(self, block):
		textBlock= block
		if self.__lastEndedWithCarriageReturn:
			if block[0] == "\n":
				textBlock= block[1:]
		self.__lastEndedWithCarriageReturn= len(block) > 0 and block[-1] == "\r"
		return textBlock.replace("\r\n", "\n").replace("\r", "\n")

class XMLCodec:
	kCharactersToEscapePattern= re.compile(r"([^a-zA-Z0-9_; /@=:.-])")
	kEscapePattern= re.compile(r"\&#x([0-9A-Fa-f]);")
	def __init__(self):
		pass
	def encode(self, text):
		return self.kCharactersToEscapePattern.sub(lambda m: "&#x%x;"%(ord(m.group(1))), text)
	def decode(self, encoded):
		return self.kEscapePattern.sub(lambda m: char(int(m.group(1), 16)), encoded)
	def name(self):
		return "xml"

class DollarHexCodec:
	kCharactersToEscapePattern= re.compile(r"([^a-zA-Z0-9_;-])")
	kEscapePattern= re.compile(r"\$([0-9A-Fa-f][0-9A-Fa-f])")
	def __init__(self):
		pass
	def encode(self, text):
		return self.kCharactersToEscapePattern.sub(lambda m: "$%02x"%(ord(m.group(1))), text)
	def decode(self, encoded):
		return self.kEscapePattern.sub(lambda m: char(int(m.group(1), 16)), encoded)
	def name(self):
		return "dollarhex"

class Base64Codec:
	def __init__(self):
		pass
	def encode(self, text):
		return base64.standard_b64encode(text)
	def decode(self, encoded):
		return base64.standard_b64decode(encoded)
	def name(self):
		return "base64"

kStandardCodecs= (
	( DollarHexCodec().name(), DollarHexCodec() ),
	( XMLCodec().name(), XMLCodec() ),
	( Base64Codec().name(), Base64Codec() ),
)

def platformTempDir():
	if os.name == 'posix':
		return "/tmp"
	# can also check os.uname()[0] == 'Darwin' on Mac
	raise SyntaxError("Add your OS here")

def platformEOL():
	if os.name == 'posix':
		return "\n"
	# can also check os.uname()[0] == 'Darwin' on Mac
	raise SyntaxError("Add your OS here")

def reportException(file= sys.stderr, depth= 5):
	exc_type, exc_value, exc_stack = sys.exc_info()
	traceback.print_exception(exc_type, exc_value, exc_stack, limit=depth, file=file)

def hashListsMatch(hashes1, hashes2, isText= False, valueIfNotFound= None):
	match= None
	for hash1 in hashes1:
		for hash2 in hashes2:
			#print "hashListsMatch",hash1,hash2
			if hash1[0] != hash2[0]: # algorithm
				continue # not the same type of hash
			if hash1[2] != hash2[2]: # is hash of unix eol text
				continue # not the same type of content
			if hash1[1] == hash2[1]: # hash value
				match= True # we're good
				continue
			if isText and not hash1[2]:
				continue # it's text, this is a binary hash
			return False # same algorithm and type and hashes mismatch, fail
	if None == match: # we didn't find hashes we could compare
		match= valueIfNotFound
	return match

def pathToList(path):
	elements= []
	while True:
		(path, name)= os.path.split(path)
		elements.insert(0, name)
		if not name:
			break
	return elements

def statWrapper(path):
	stats= os.lstat(path)
	isdir= stat.S_ISDIR(stats.st_mode)
	isfile= stat.S_ISREG(stats.st_mode)
	mods= stat.S_IMODE(stats.st_mode)
	readonly= mods & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH) == 0
	executable= mods & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH) != 0
	if isdir:
		executable= False # executable for directories means readable
	return (stats, isdir, isfile, mods, readonly, executable)

def fullyDeleteDirectoryHierarchy(path):
	""" Attempts to do rm -r path
		does not handle read-only files
	"""
	for (root, dirs, files) in os.walk(path, topdown= False):
		for file in files:
			os.remove(os.path.join(root, file))
		for dir in dirs:
			os.rmdir(os.path.join(root, dir))
	if os.path.isdir(path):
		os.rmdir(path)
	elif os.path.isfile(path):
		os.remove(path)

def skip(relativePath, skipPaths, skipExtensions, skipNames):
	#print "skip(",relativePath,", ",skipPaths,", ",skipExtensions,", ",skipNames,")"
	relativePathParts= pathToList(relativePath)
	#print "relativePathParts",relativePathParts,"relativePath",relativePath
	for part in relativePathParts:
		#print "part",part
		if part in skipNames:
			return True # something in the path is in the skip list
		for extension in skipExtensions:
			#print "\t","extension",extension
			if part.endswith(extension):
				#print "\t","skipping",relativePath
				return True # something in the path has this extension
	for item in skipPaths:
		itemParts= pathToList(item)
		#print "item",item,"itemParts",itemParts
		if len(itemParts) > len(relativePathParts):
			continue # skipPath has more elements, we can't be in it
		relativeSubPath= os.path.join(*relativePathParts[:len(itemParts)])
		#print "relativeSubPath",relativeSubPath
		if relativeSubPath == item:
			return True # the first n items match, skip it
	return False

#kBetterDateFormat= "%Y/%m/%d@%H:%M:%S.%f" # not supported in 2.5.1 (Mac OS X 10.5/ppc)
kReliableDateFormat= "%Y/%m/%d@%H:%M:%S"
def formatDate(timestamp):
	dt= datetime.datetime.utcfromtimestamp(timestamp)
	return dt.strftime(kReliableDateFormat)

def parseDate(timestampString):
	dt= datetime.datetime.strptime(timestampString, kReliableDateFormat)
	return calendar.timegm(dt.timetuple())

# Assumption: path is a sub-path of base
#	return relative path from base to path
#	os.path.join(base, result) == path
def getSubPathRelative(base, path):
	#print ">getSubPathRelative(",base,",",path,")"
	if path.find(base) < 0:
		raise SyntaxError(path+" is not in "+base)
	relative= ""
	while not os.path.samefile(base, path):
		#print ">",relative,base,path
		(path, name)= os.path.split(path)
		if len(relative) == 0:
			relative= name
		else:
			relative= os.path.join(name, relative)
		#print "<",relative,base,path,name
	#print "<getSubPathRelative(",base,",",path,")"
	return relative

class ManifestCompare(xml.sax.handler.ContentHandler):
	kFileTypeItems= ["file", "directory", "link"]
	def __init__(self, notifier, decoders):
		"""
			decoders is array of (name, decoder) ( .decode(block) )
			notifier ( .notify( (file|link|directory, properties) ) called for each item

			properties
				path - relative
				hash - list of (name, hexhash)
				xattr - dict of name -> value
		"""
		self.__skipPaths= []
		self.__skipExtensions= []
		self.__skipNames= []
		self.__stack= []
		self.__notifier= notifier
		self.__decoders= decoders
	def skipPaths(self):
		return self.__skipPaths
	def skipExtensions(self):
		return self.__skipExtensions
	def skipNames(self):
		return self.__skipNames
	def startElement(self, name, attrs):
		#print ">",self.__stack
		attributes= {}
		for attribute in attrs.getNames(): # get attributes and put them in the stack
			attributes[attribute]= attrs.getValue(attribute)
		self.__stack.append( (name, attributes) )
		if len(self.__stack) == 1 and name != "manifest":
			raise SyntaxError("Not a manifest: "+name)
		elif len(self.__stack) == 2:
			if name == "filter":
				stackTop= self.__stack[-1]
				if stackTop[1].has_key('path'):
					self.__skipPaths.append(stackTop[1]['path'])
				if stackTop[1].has_key('name'):
					self.__skipNames.append(stackTop[1]['name'])
				if stackTop[1].has_key('extension'):
					self.__skipExtensions.append(stackTop[1]['extension'])
	def endElement(self, name):
		#print "<",self.__stack
		text= None
		stackTop= self.__stack[-1]
		if stackTop[1].has_key('__text__'):
			text= stackTop[1]['__text__'].rstrip()
		inFileItem= len(self.__stack) == 3 and self.__stack[-2][0] in self.kFileTypeItems
		if inFileItem:
			if name == "xattr":
				if not self.__stack[-2][1].has_key('xattr'):
					self.__stack[-2][1]['xattr']= {}
				decoderNeeded= stackTop[1].has_key('encoding')
				if decoderNeeded and self.__decoders:
					for decoder in self.__decoders:
						if stackTop[1]['encoding'] == decoder[0]:
							text= decoder[1].decode(text)
							decoderNeeded= False
							break
				if decoderNeeded:
					raise SyntaxError("Unknown encoding: "+stackTop[1]['encoding'])
				self.__stack[-2][1]['xattr'][stackTop[1]['name']]= text
			elif name == "hash":
				if not self.__stack[-2][1].has_key('hash'):
					self.__stack[-2][1]['hash']= []
				self.__stack[-2][1]['hash'].append( (
					stackTop[1]['algorithm'],
					text,
					stackTop[1].has_key('text') and stackTop[1]['text'][0].lower() == 't'
					) )
		elif len(self.__stack) == 2 and stackTop[0] in self.kFileTypeItems:
			self.__notifier.notify(stackTop)
		self.__stack= self.__stack[:-1] # pop element off stack
	def characters(self, text):
		stackTop= self.__stack[-1]
		if not stackTop[1].has_key('__text__'):
			if len(text.strip()) > 0:
				stackTop[1]['__text__']= text.lstrip()
		else:
			stackTop[1]['__text__']+= text

def transferAndHash(input, hashers, output, detectText, changeLineEndingsTo, blockTransferSize):
	""" changeLineEndingsTo if None, no line ending change
			otherwise if detectText then lineEndings will only be changed if it looks like text
			otherwise if not detectText and changeLineEndingsTo then all eols will be changed
	"""
	if not hashers:
		hashers= []
	fileHashers= []
	textHashers= []
	for hasher in hashers:
		fileHashers.append( (hasher[0], hasher[1].copy()) )
		if detectText:
			textHashers.append( (hasher[0], hasher[1].copy()) )
	isProbablyText= True
	unixTextSize= 0.0
	unixTextNoEOLSize= 0.0
	unixTextNoPrintableSize= 0.0
	while True:
		block= input.read(blockTransferSize)
		if not block:
			break
		if block[-1] == "\r": # handle chunk split in the middle of eol
			nextByte= input.read(1)
			if len(nextByte) == 1:
				block+= nextByte
		if isProbablyText and block.find("\0") >= 0:
			isProbablyText= False
		for hasher in fileHashers:
			hasher[1].update(block)
		if textHashers:
			unixText= block.replace("\r\n", "\n").replace("\r", "\n")
			for hasher in textHashers:
				hasher[1].update(unixText)
			unixTextSize+= len(unixText)
			unixTextNoEOLSize+= len(unixText.replace("\n", ""))
			unixTextNoPrintableSize+= len(filter(lambda x: x in string.printable, unixText))
		if output:
			convertEOLOnDetectionOfText= changeLineEndingsTo and detectText and isProbablyText
			askedToConvertEOLRegardless= changeLineEndingsTo and not detectText
			if convertEOLOnDetectionOfText or askedToConvertEOLRegardless:
				block= block.replace("\n", changeLineEndingsTo)
			output.write(block)
	numberOfLines= unixTextSize - unixTextNoEOLSize
	if unixTextSize > 0.0:
		percentNonPrintable= (unixTextSize - unixTextNoPrintableSize) / unixTextSize
	else:
		percentNonPrintable= 1.0
	if numberOfLines > 0.0:
		averageLineLength= unixTextSize / numberOfLines
	else:
		averageLineLength= 0.0
	isProbablyText= isProbablyText and averageLineLength > 0.0001 and averageLineLength < 20000.0
	isProbablyText= isProbablyText and percentNonPrintable < 0.10
	hashes= []
	for hasher in fileHashers:
		hashes.append( (hasher[0], hasher[1].hexdigest(), False ))
	for hasher in textHashers:
		hashes.append( (hasher[0], hasher[1].hexdigest(), True) )
	if not isProbablyText:
		numberOfLines= -1
	return (numberOfLines, hashes)

class VerifyHandler:
	kExecutableFlags= stat.S_IEXEC | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
	kWriteFlags= stat.S_IWRITE | stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH
	def __init__(self, base, fixLevel, archive, hashers, convertEOL, blockTransferSize):
		"""
			archive ( .open(relpath, 'r') ->  .close() .read(size) -> str )
			fixLevel
				-1 = do not fix, just throw exception
				 0 = do not fix, just keep list of problems
				 1 = fix, but don't hash unless timestamp or size is off
				 2 = fully validate all contents
		"""
		self.__base= base
		self.__exist= []
		if hashers:
			self.__hashers= hashers
		else:
			self.__hashers= []
		self.__size= blockTransferSize
		self.__links= []
		self.__fix= fixLevel
		self.__archive= archive
		self.__eol= convertEOL
		self.__problems= []
		self.__directoryModDates= []
		self.__readOnlyDirectories= []
	def found(self):
		return self.__exist
	def finish(self, skipPaths, skipExtensions, skipNames):
		""" patches up all the stuff that has to be done at the end, like:
				* remove items that don't belong
				* create symlinks (target must exist to create it)
				* set directory modification times (make sure all mods are done first)
		"""
		for link in self.__links:
			try:
				if not os.path.isdir(os.path.split(link[0])[0]):
					os.makedirs(os.path.split(link[0])[0])
				os.symlink(link[1]['target'], link[0])
				self.__applyxattr(link[0], link, reportProblems= False)
				os.utime(link[0], (time.time(), parseDate(link[1]['modified'])) )
			except:
				#print "link",link
				reportException()
				self.__addProblem(
					(None, {'path': link[0]}),
					"Could not create symlink to "+link[1]['target']
				)
		toDelete= []
		#print skipPaths, skipExtensions, skipNames
		for (directory, dirs, files) in os.walk(self.__base):
			baseRelativePath= getSubPathRelative(self.__base, directory)
			items= list(dirs)
			items.extend(files)
			for item in items:
				relativePath= os.path.join(baseRelativePath, item)
				doSkip= skip(relativePath, skipPaths, skipExtensions, skipNames)
				#print relativePath, doSkip
				if not doSkip and relativePath not in self.__exist:
					toDelete.append(os.path.join(directory, item))
		for item in toDelete:
			self.__addProblem((None, {'path': item}),"Should not exist: "+item)
			if self.__fix > 0:
				#print "4 fullyDeleteDirectoryHierarchy ",item
				fullyDeleteDirectoryHierarchy(item)
		for directory in self.__directoryModDates:
			os.utime(directory[0], directory[1])
		for directory in self.__readOnlyDirectories:
			#print "3",directory[0],"%o"%(directory[1])
			os.chmod(directory[0], directory[1])
		return self.__problems
	def problems(self):
		return self.__problems
	def __create(self, fullPath, info, report= True):
		if report:
			self.__addProblem(info, info[0]+" does not exist: "+fullPath)
		if info[0] == 'link':
			if self.__fix > 0:
				if not os.path.isdir(os.path.split(fullPath)[0]):
					os.makedirs(os.path.split(fullPath)[0])
				try:
					os.symlink(info[1]['target'], fullPath)
				except:
					#print "1st link", (fullPath, info[1])
					reportException()
					self.__links.append( (fullPath, info[1]) )
		elif info[0] == 'directory':
			if self.__fix > 0:
				os.makedirs(fullPath)
		else:
			if self.__archive and self.__fix > 0:
				archiveFile= self.__archive.open(info[1]['path'], 'r')
				isText= info[1].has_key('lines')
				if isText:
					useEOL= self.__eol
				else:
					useEOL= None
				if not os.path.isdir(os.path.split(fullPath)[0]):
					os.makedirs(os.path.split(fullPath)[0])
				localFile= open(os.path.join(fullPath), 'w')
				(numberOfLines, hashes)= transferAndHash(
											archiveFile,
											self.__hashers,
											localFile,
											False,
											useEOL,
											self.__size
										)
				localFile.close()
				archiveFile.close()
				return (numberOfLines >= 0, hashes)
		return (None, None)
	def __addProblem(self, info, description):
		if info[1]['path'] not in self.__problems:
			self.__problems.append( (info[1]['path'], description) )
		if self.__fix < 0:
			raise SyntaxError(description)
	def __stat(self, fullPath, info, isText, hashes):
		try:
			(stats, isdir, isfile, mods, readonly, executable)= statWrapper(fullPath)
			wasCreated= False
		except KeyboardInterrupt,e:
			raise e
		except: # doesn't exist, fix it
			(isText, hashes)= self.__create(fullPath, info, report= True)
			try:
				(stats, isdir, isfile, mods, readonly, executable)= statWrapper(fullPath)
				wasCreated= True
			except KeyboardInterrupt,e:
				raise e
			except:
				#reportException()
				return (None, None, None, None, None, None, None, None, None)
		return (stats, isdir, isfile, mods, readonly, executable, isText, hashes, wasCreated)
	def __commonHashers(self, info):
		hashersUsed= []
		#print "Looking in file hashes"
		for hasher in info[1]['hash']:
			#print "\t",hasher
			if hasher[0] not in hashersUsed:
				#print "\t","Adding"
				hashersUsed.append(hasher[0])
		hashersToUse= []
		#print "Looking at what hashers we know"
		for hasher in self.__hashers:
			#print "\t",hasher
			if hasher[0] in hashersUsed:
				#print "\t","Using"
				hashersToUse.append(hasher)
		return hashersToUse
	def __hashOfFileMatches(self, info, fullPath):
		#print "__hashOfFileMatches(",info,",",fullPath,")"
		hashersToUse= self.__commonHashers(info)
		#print "\t",hashersToUse
		existingFile= open(fullPath, 'r')
		(numberOfLines, hashes)= transferAndHash(
									existingFile,
									hashersToUse,
									None,
									info[1].has_key('lines'), # is text
									None, # no eol to replace, we're not writing
									self.__size
								)
		isText= (numberOfLines >= 0) and info[1].has_key('lines')
		#print "\t",isText,numberOfLines,hashes
		return hashListsMatch(hashes, info[1]['hash'], isText, valueIfNotFound= True)
	def __applyxattr(self, fullPath, info, reportProblems= True):
		if kXattrAvailable and info[1].has_key('xattr'):
			try:
				existingAttributes= xattr.listxattr(fullPath)
			except KeyboardInterrupt,e:
				raise e
			except: # Can't list existing attributes on the file
				reportException()
				existingAttributes= []
			for attribute in info[1]['xattr']:
				action= None
				if attribute in existingAttributes:
					try:
						value= xattr.getxattr(fullPath, attribute, True)
						if value == info[1]['xattr'][attribute]:
							continue # no need to change it
					except KeyboardInterrupt,e:
						raise e
					except:
						reportException()
						pass # we need to set it
					action= xattr.XATTR_REPLACE
					self.__addProblem(info, "Attribute "+attribute+" value is wrong")
				else:
					action= xattr.XATTR_CREATE
					self.__addProblem(info, "Attribute "+attribute+" is missing")
				if None != action:
					try:
						value= info[1]['xattr'][attribute]
						xattr.setxattr(fullPath, attribute, value, action, True)
					except KeyboardInterrupt,e:
						raise e
					except: # can't read this attribute
						reportException()
						pass
	def notify(self, info):
		#print "info",info
		looksLikeText= None
		hashes= None
		self.__exist.append(info[1]['path']) # keep track of all paths
		fullPath= os.path.join(self.__base, info[1]['path'])
		#print "1",fullPath,os.path.exists(fullPath),os.path.isfile(fullPath),os.path.isdir(fullPath),os.path.islink(fullPath)
		#print "fullPath",fullPath
		(stats, isdir, isfile, mods, readonly, executable, looksLikeText,
			hashes, wasCreated)= self.__stat(fullPath, info, looksLikeText, hashes)
		#print "2",fullPath,os.path.exists(fullPath),os.path.isfile(fullPath),os.path.isdir(fullPath),os.path.islink(fullPath)
		if None == stats:
			if self.__fix > 0 and (self.__archive or info[0] != "file"):
				(looksLikeText, hashes)= self.__create(fullPath, info, report= True)
				#print "3",fullPath,os.path.exists(fullPath),os.path.isfile(fullPath),os.path.isdir(fullPath),os.path.islink(fullPath)
				(stats, isdir, isfile, mods, readonly, executable, looksLikeText,
					hashes, wasCreated)= self.__stat(fullPath, info, looksLikeText, hashes)
				#print "4",fullPath,os.path.exists(fullPath),os.path.isfile(fullPath),os.path.isdir(fullPath),os.path.islink(fullPath)
				wasCreated= True
				if None == stats:
					self.__addProblem(info, "Unable to create "+info[0]+" "+fullPath)
			elif None == stats:
				return
		directoryMismatch= isdir and info[0] != "directory"
		fileMismatch= isfile and info[0] != "file"
		linkMismatch= not isfile and not isdir and info[0] != "link"
		expectedExecutable= info[1].has_key('executable') and info[1]['executable'][0].lower() == 't'
		expectedReadonly= info[1].has_key('readonly') and info[1]['readonly'][0].lower() == 't'
		#print "expectedExecutable",expectedExecutable,"expectedReadonly",expectedReadonly
		#print "isdir",isdir,"isfile",isfile,"mods %o"%(mods)
		#print "executable",executable,"looksLikeText",looksLikeText,"hashes",hashes
		if directoryMismatch or fileMismatch or linkMismatch:
			self.__addProblem(info, fullPath+" was expected to be a "+info[0]+" but it isn't")
			if self.__fix > 0 and (self.__archive or info[0] != "file"):
				#print "1 fullyDeleteDirectoryHierarchy ",fullPath
				fullyDeleteDirectoryHierarchy(fullPath) # remove it and create correct type
				#print "5",fullPath,os.path.exists(fullPath),os.path.isfile(fullPath),os.path.isdir(fullPath),os.path.islink(fullPath)
				(looksLikeText, hashes)= self.__create(fullPath, info, report= False)
				(stats, isdir, isfile, mods, readonly, executable, looksLikeText,
					hashes, wasCreated)= self.__stat(fullPath, info, looksLikeText, hashes)
				#print "6",fullPath,os.path.exists(fullPath),os.path.isfile(fullPath),os.path.isdir(fullPath),os.path.islink(fullPath)
				#print "just created",(fullPath, info, stats)
				wasCreated= True
		if None == stats:
			if info[0] != "link":
				self.__addProblem(info, "Unable to create %s at %s"%(info[0], fullPath))
			return
		mtimeMatches= True
		if info[1].has_key('modified'):
			expectedmtime= parseDate(info[1]['modified'])
			#print info
			mtimeMatches= abs(stats.st_mtime - expectedmtime) < 0.1
		sizeMatches= True
		if info[1].has_key('size'):
			delta= 0
			if info[1].has_key('lines'):
				delta= long(info[1]['lines'])
			size= long(info[1]['size'])
			sizeMatches= size == stats.st_size or abs(size - stats.st_size) == delta
			#print "size",size,"delta",delta,"stats.st_size",stats.st_size
		if isfile and not wasCreated:
			if not sizeMatches:
				self.__addProblem(info,
					"File size varies on "+fullPath
					+" expected %d, %d or %d"%(size, size + delta, size - delta)
					+" but found %d"%(stats.st_size)
				)
				if self.__fix > 0 and self.__archive:
					#print "5 fullyDeleteDirectoryHierarchy ",fullPath
					fullyDeleteDirectoryHierarchy(fullPath)
					#print "7",fullPath,os.path.exists(fullPath),os.path.isfile(fullPath),os.path.isdir(fullPath),os.path.islink(fullPath)
					(looksLikeText, hashes)= self.__create(fullPath, info, report= False)
					#print "8",fullPath,os.path.exists(fullPath),os.path.isfile(fullPath),os.path.isdir(fullPath),os.path.islink(fullPath)
					wasCreated= True
			elif not mtimeMatches or self.__fix > 1: # timestamps mismatch or full validation
				#print "mtimeMatches",mtimeMatches,"self.__fix > 1",self.__fix > 1,fullPath
				#print "\t",info,self.__hashers
				if info[1].has_key('hash') and self.__hashers:
					if not self.__hashOfFileMatches(info, fullPath):
						#print "\t","Contents Changed",fullPath
						self.__addProblem(info, "Contents changed "+fullPath)
						if self.__fix > 0 and self.__archive:
							#print "\t","Fixing",fullPath
							#print "6 fullyDeleteDirectoryHierarchy ",fullPath
							fullyDeleteDirectoryHierarchy(fullPath)
							#print "9",fullPath,os.path.exists(fullPath),os.path.isfile(fullPath),os.path.isdir(fullPath),os.path.islink(fullPath)
							(looksLikeText, hashes)= self.__create(fullPath, info, report= False)
							#print "a",fullPath,os.path.exists(fullPath),os.path.isfile(fullPath),os.path.isdir(fullPath),os.path.islink(fullPath)
							wasCreated= True
		# full validation validates files just created
		if isfile and wasCreated and self.__fix > 1:
			if not self.__hashOfFileMatches(info, fullPath):
				self.__addProblem(info, "File corrupted from archive: "+fullPath)
		if expectedExecutable != executable and not isdir or expectedReadonly != readonly:
			if not isdir and expectedExecutable != executable and not wasCreated:
				#print "exec",fullPath, "\t", expectedExecutable, executable, wasCreated, "%o"%(mods)
				self.__addProblem(info, "Executability was not correct: "+fullPath)
			if expectedReadonly != readonly and not wasCreated:
				#print "read",fullPath, "\t", expectedReadonly, readonly, wasCreated, "%o"%(mods)
				self.__addProblem(info, "Write flag was not correct: "+fullPath)
			if expectedExecutable and not executable:
				mods|= self.kExecutableFlags
			elif not isdir and not expectedExecutable and executable:
				mods&= ~self.kExecutableFlags # executable on a directory means it's readable
			if expectedReadonly and not readonly:
				mods&= ~self.kWriteFlags
			elif not expectedReadonly and readonly:
				mods|= self.kWriteFlags
			if not isdir:
				#print "1",fullPath, "expectedReadonly",expectedReadonly,"readonly",readonly,"expectedExecutable",expectedExecutable,"executable",executable,"%o"%(mods)
				os.chmod(fullPath, mods)
				#print "b",fullPath,os.path.exists(fullPath),os.path.isfile(fullPath),os.path.isdir(fullPath),os.path.islink(fullPath)
		if isdir and expectedReadonly:
			if readonly:
				#print "2",fullPath, "expectedReadonly",expectedReadonly,"readonly",readonly,"expectedExecutable",expectedExecutable,"executable",executable,"%o"%(mods)
				os.chmod(fullPath, mods | self.kWriteFlags)
				#print "c",fullPath,os.path.exists(fullPath),os.path.isfile(fullPath),os.path.isdir(fullPath),os.path.islink(fullPath)
			self.__readOnlyDirectories.append( (fullPath, mods) )
		if info[0] == "link" and info[1]['target'] != os.readlink(fullPath):
			self.__addProblem(info,
				"Link contents for "+fullPath+" expected to be "
				+info[1]['target']+" but is "+os.readlink(fullPath)
			)
			if self.__fix > 0:
				#print "3 fullyDeleteDirectoryHierarchy ",fullPath
				fullyDeleteDirectoryHierarchy(fullPath) # remove it and recreate
				#print "d",fullPath,os.path.exists(fullPath),os.path.isfile(fullPath),os.path.isdir(fullPath),os.path.islink(fullPath)
				self.__create(fullPath, info, report= False)
				#print "e",fullPath,os.path.exists(fullPath),os.path.isfile(fullPath),os.path.isdir(fullPath),os.path.islink(fullPath)
		self.__applyxattr(fullPath, info, reportProblems= not wasCreated)
		if not mtimeMatches and (isdir or isfile): # os.utime does not modify link mtime
			if not wasCreated and not isdir: # if we created the file, don't report it as a problem
				self.__addProblem(info,
					"Modification date for "+fullPath+" should have been "+info[1]['modified']
					+" but was "+formatDate(stats.st_mtime)
				)
			if self.__fix > 0:
				if isdir:
					self.__directoryModDates.append( (
						fullPath,
						(stats.st_atime, parseDate(info[1]['modified']))
					) )
				elif info[0] != "link":
					#print "utime", (fullPath, info)
					#print (stats, isdir, isfile, mods, readonly, executable, looksLikeText, hashes, wasCreated)
					os.utime(fullPath, (stats.st_atime, parseDate(info[1]['modified'])) )

def __copyHashers(hashers):
	copy= []
	for hasher in hashers:
		copy.append( (hasher[0], hasher[1].copy(), False) )
		copy.append( (hasher[0], hasher[1].copy(), True) )
	return copy

def validate(manifest, path, fixLevel, hashers, decoders, key, signatures, platformEOL, archive, blockTransferSize):
	""" signatures is a list of tuples of (algorithm, signature, isText)
	"""
	if key and archive and hashers and signatures:
		manifestHashers= __copyHashers(hashers)
	else:
		manifestHashers= []
	manifestStream= StreamHasher(manifest, manifestHashers)
	verifier= VerifyHandler(path, fixLevel, archive, hashers, platformEOL, blockTransferSize)
	comparitor= ManifestCompare(verifier, decoders)
	parser= xml.sax.make_parser()
	parser.setContentHandler(comparitor)
	parser.parse(manifestStream)
	for hash in manifestHashers:
		for signature in signatures:
			if hash[0] == signature[0] and hash[2] == signature[2]:
				expected= long(hash[1].hexdigest(), 16)
				if not key.validate(long(signature[1], 16), expected):
					raise AssertionError("Invalid Signature: "+hash[0])
	return verifier.finish(
		comparitor.skipPaths(),
		comparitor.skipExtensions(),
		comparitor.skipNames()
	)

def generate(path, out, hashers, encoders, key, signature, archive, detectText,
				skipPaths, skipExtensions, skipNames, blockTransferSize):
	""" generates an XML manifest from a location
		path is location to start generating
		out the stream to write the xml manfifest to ( .write(block) )
		hashers is array of (name, hasher) ( .update(block) .hexdigest(block) )
		encoders is array of (name, encoder) ( .encode(block) )
		detectText if True then file will be parsed to determine if it can be text
			also will generate text hashes (if hashers passed in)
		archive a place to stream files as we check them
			( .open(relpath, 'w') -> .write(block) .close()  )
			or ( .open(relpath, 'w') -> store(filePath, archivePath) .close() )
		skipPaths, skipNames, skipExtensions lists of things to not add to the manifest
	"""
	if isinstance(out, basestring): # if out was a path instead of a stream
		out= open(out, 'w')
	if not hashers:
		hashers= []
	if not encoders:
		encoders= []
	if not skipPaths:
		skipPaths= []
	if not skipNames:
		skipNames= []
	if not skipExtensions:
		skipExtensions= []
	if key and not key.isPrivate():
		raise AssertionError("key must be a private key to sign")
	if key and archive and hashers and signature:
		manifestHashers= __copyHashers(hashers)
	else:
		manifestHashers= []
	hashedOut= StreamHasher(out, manifestHashers)
	hashedOut.write("<manifest>\n")
	xmlencoder= XMLCodec()
	for item in skipPaths:
		hashedOut.write("\t<filter path='%s'/>\n"%(xmlencoder.encode(item)))
	for item in skipNames:
		hashedOut.write("\t<filter name='%s'/>\n"%(xmlencoder.encode(item)))
	for item in skipExtensions:
		hashedOut.write("\t<filter extension='%s'/>\n"%(xmlencoder.encode(item)))
	for (directory, dirs, files) in os.walk(path, topdown= True):
		baseRelativePath= getSubPathRelative(path, directory)
		if skip(baseRelativePath, skipPaths, skipExtensions, skipNames):
			continue # don't bother walking all items if this path is skipped
		#print "working in",path,baseRelativePath
		items= list(dirs)
		items.extend(files)
		for item in items:
			fullPath= os.path.join(directory, item)
			relativePath= os.path.join(baseRelativePath, item)
			#print "looking at",fullPath,relativePath
			if skip(relativePath, skipPaths, skipExtensions, skipNames):
				continue
			(stats, isdir, isfile, mods, readonly, executable)= statWrapper(fullPath)
			tagType= None
			if isdir:
				tagType= "directory"
				hashedOut.write("\t<%s"%(tagType))
			elif stat.S_ISLNK(stats.st_mode):
				tagType= "link"
				hashedOut.write("\t<%s target='%s'"%(tagType, xmlencoder.encode(os.readlink(fullPath))))
			elif isfile:
				tagType= "file"
				hashedOut.write("\t<%s size='%d'"%(tagType, stats.st_size))
			else:
				continue # not a file/link/directory, skip it
			if readonly:
				hashedOut.write(" readonly='true'")
			if executable:
				hashedOut.write(" executable='true'")
			hashedOut.write(" path='%s' modified='%s'"%(
				xmlencoder.encode(relativePath),
				formatDate(stats.st_mtime),
			))
			if (archive or hashers or detectText) and isfile:
				archiveFile= None
				if archive:
					try: # if the archive doesn't support streaming, just store the file
						archive.store(fullPath, relativePath)
					except KeyboardInterrupt,e:
						raise e
					except: # does support streaming, store the file while calculating the hashes
						reportException()
						archiveFile= archive.open(relativePath, 'w')
				sourceFile= open(fullPath, 'r')
				(numberOfLines, hashes)= transferAndHash(
											sourceFile,
											hashers,
											archiveFile,
											detectText,
											None, # no line ending change when archiving
											blockTransferSize
										)
				sourceFile.close()
				if archiveFile:
					archiveFile.close()
				if numberOfLines >= 0 and detectText:
					hashedOut.write(" lines='%d'"%(numberOfLines))
				hashedOut.write(">\n") # close on file tag
				for hash in hashes:
					if hash[2]:
						isText= " text='true'"
					else:
						isText= ""
					hashedOut.write("\t\t<hash algorithm='%s'%s>%s</hash>\n"%(hash[0], isText, hash[1]))
			else:
				hashedOut.write(">\n") # close on directory, link and file tags (files we didn't open)
			if kXattrAvailable:
				try:
					attrs= xattr.listxattr(fullPath)
					for attr in attrs:
						try:
							value= xattr.getxattr(fullPath, attr, True)
							bestEncoding= None
							bestEncodingName= None
							for encoder in encoders:
								encoded= encoder[1].encode(value)
								if not bestEncoding or len(encoded) < len(bestEncoding):
									bestEncoding= encoded
									bestEncodingName= encoder[0]
							if bestEncodingName:
								encoding= " encoding='%s'"%(bestEncodingName)
								value= bestEncoding
							else:
								encoding= ""
							hashedOut.write("\t\t<xattr name='%s'%s>%s</xattr>\n"%(attr, encoding, value))
						except KeyboardInterrupt,e:
							raise e
						except: # can't read this attribute
							reportException()
							pass
				except KeyboardInterrupt,e:
					raise e
				except: # something went wrong
					reportException()
					pass
			hashedOut.write("\t</%s>\n"%(tagType))
	hashedOut.write("</manifest>\n")
	if manifestHashers:
		signature.write("<signature key='%s'>\n"%(key.public()))
		for hash in manifestHashers:
			if hash[2]: # isText
				isText= " text='true'"
			else:
				isText= ""
			signature.write("\t<signed algorithm='%s' hash='%s'%s>%x</signed>\n"%(
				hash[0], hash[1].hexdigest(), isText,
				key.sign(long(hash[1].hexdigest(), 16))
			))
		signature.write("</signature>\n")

if kHashLibAvailable:
	kAllKnownHashes= []
	try:
		__knownAlgorithms= hashlib.algorithms
	except:
		__knownAlgorithms= ("md5", "sha1", "sha224", "sha256", "sha384", "sha512")
	for algorithm in __knownAlgorithms:
		kAllKnownHashes.append( (algorithm, hashlib.new(algorithm)) )
	kMD5Hash= ( ("md5", hashlib.new("md5")), )
else:
	kMD5Hash= ( ('md5', md5.new()), )
	kAllKnownHashes= kMD5Hash

class ZipArchiveWriteFile:
	def __init__(self, path, archive):
		likelyUniquePrefix= "ZIP_ARCHIVE_FILE_%x-%x-%x_"%(
			time.time(),
			random.randrange(0,100000),
			os.getpid()
		)
		self.__path= path
		self.__archive= archive
		self.__tmpPath= os.path.join(platformTempDir(), likelyUniquePrefix+os.path.split(path)[1])
		self.__file= open(self.__tmpPath, 'w')
	def write(self, block):
		self.__file.write(block)
	def close(self):
		self.__file.close()
		self.__archive.store(self.__tmpPath, self.__path)
		os.remove(self.__tmpPath)

class ZipArchive:
	def __init__(self, path, mode):
		self.__path= path
		self.__mode= mode
		if 'r' == mode:
			self.__file= zipfile.ZipFile(path, mode)
		elif 'w' == mode or 'a' == mode:
			self.__file= zipfile.ZipFile(path, mode, zipfile.ZIP_DEFLATED)
			mode= 'w'
	def store(self, filePath, archivePath):
		self.__file.write(filePath, archivePath, zipfile.ZIP_DEFLATED)
	def open(self, path, mode):
		if self.__mode != mode:
			raise SyntaxError("Archive opened with mode "+self.__mode+" but now using "+mode)
		if mode == 'w':
			return ZipArchiveWriteFile(path, self)
		elif mode == 'r':
			try:
				return self.__file.open(path, mode)
			except:
				#reportException() ZipFile.open not in this version
				return cStringIO.StringIO(self.__file.read(path))
	def close(self):
		self.__file.close()

def getSignatures(signatureFile):
	dom= bDOM.link(signatureFile)
	key= dom.documentElement.getAttribute('key')
	signatures= []
	for signature in dom.documentElement.getElementsByTagName('signed'):
		algorithm= signature.getAttribute('algorithm')
		value= bDOM.extractTextFromTagContents(signature)
		isText= signature.hasAttribute('text') and signature.getAttribute('text')[0].lower() == 't'
		signatures.append( (algorithm, value, isText) )
	dom.unlink()
	return (key, signatures)

if __name__ == "__main__":
	archivePath= sys.argv[1]
	directoryForManifest= sys.argv[2]
	if len(sys.argv) > 3:
		fixLevel= int(sys.argv[3])
	else:
		fixLevel= -1
	if os.path.exists(archivePath):
		archiveMode= 'r'
	else:
		archiveMode= 'w'
	archive= ZipArchive(archivePath, archiveMode)
	manifestStream= archive.open("manifest.xml", archiveMode)
	signatureFile= archive.open("signature.xml", archiveMode)
	import bRSA
	if archiveMode == 'r':
		signatures= getSignatures(signatureFile)
		key= bRSA.Key(signatures[0])
		print validate(
			manifestStream,
			directoryForManifest,
			fixLevel,
			kAllKnownHashes, kStandardCodecs,
			key, signatures[1],
			platformEOL(), #"\r\n", #platformEOL(), # eol to convert text files to
			archive,
			4096 # size of transfer blocks
		)
	else:
		key= bRSA.Key(-512) # large enough to handle a sha512
		print "Key Generated",key
		generate(
			directoryForManifest, manifestStream,
			kAllKnownHashes, kStandardCodecs,
			key, signatureFile, archive,
			True, # detect text
			['old'], ['.pyc'], ['.DS_Store'], # skip paths, extensions and names
			4096 # size of transfer blocks
		)
	signatureFile.close()
	manifestStream.close()
	archive.close()

