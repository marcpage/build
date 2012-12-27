#!/usr/bin/env python

import os
import re
import sys
import bXML
import stat
import datetime
import cStringIO
import traceback
try:
	import xattr
	kXattrAvailable= True
except:
	kXattrAvailable= False

def pathToList(path):
	elements= []
	while True:
		(path, name)= os.path.split(path)
		elements.insert(0, name)
		if not name:
			break
	return elements

""" TODO
	Have a validate/fix method
	have a way to validate/fix from a sax stream
"""

kCharactersToEscapePattern= re.compile(r"([^a-zA-Z0-9_])")
def escape(string):
	return kCharactersToEscapePattern.sub(lambda m: "$%02x"%(ord(m.group(1))), string)

kEscapePattern= re.compile(r"\$([0-9A-Fa-f][0-9A-Fa-f])")
def unescape(string):
	return kEscapePattern.sub(lambda m: char(int(m.group(1), 16)), string)

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
	if path.find(base) < 0:
		raise SyntaxError(path+" is not in "+base)
	relative= ""
	while not os.path.samefile(base, path):
		(path, name)= os.path.split(path)
		if len(relative) == 0:
			relative= name
		else:
			relative= os.path.join(name, relative)
	return relative

class Manifest:
	def __init__(self, dirOrPathOrText, skipPaths= None, skipExtensions= None, skipNames= None, doHash= True, skipAttributes= None):
		self.__path= None
		self.__contents= None
		if os.path.isdir(dirOrPathOrText):
			self.__path= dirOrPathOrText
			self.__parseDirectory(skipPaths, skipExtensions, skipNames, doHash, skipAttributes)
		else:
			self.__contents= bXML.link(dirOrPathOrText)
	def unlink(self):
		self.__contents.unlink()
	def save(self, pathOrFile= None):
		if not pathOrFile:
			pathOrFile= self.__path
		if not pathOrFile:
			raise SyntaxError("No Path Specified")
		if isinstance(pathOrFile, basestring):
			file= open(pathOrFile, 'w')
			self.__contents.writexml(file)
			file.close()
		else:
			self.__contents.writexml(pathOrFile)
	def __skipped(self, relativePath, skipPaths, skipExtensions, skipNames):
		if skipPaths:
			for item in skipPaths:
				if relativePath.startswith(item):
					return True
		if skipNames or skipExtensions:
			pathNames= pathToList(relativePath)
			for name in pathNames:
				if skipNames and name in skipNames:
					return True
				if skipExtensions:
					for ext in skipExtensions:
						if name.endswith(ext):
							return True
		return False
	def __addElement(self, relativePath, doHash, skipAttributes):
		try:
			fullPath= os.path.join(self.__path, relativePath)
			stats= os.lstat(fullPath)
			properties= {'path': relativePath}
			if stat.S_ISLNK(stats.st_mode):
				kind= "link"
				properties['target']= os.readlink(fullPath)
			elif stat.S_ISDIR(stats.st_mode):
				kind= "directory"
			elif stat.S_ISREG(stats.st_mode):
				kind= "file"
				properties['size']= str(stats.st_size)
			else:
				return None # unknown file type, skip it
			properties['modified']= formatDate(stats.st_mtime)
			mods= stat.S_IMODE(stats.st_mode)
			if mods & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH) == 0:
				properties['readonly']= "true"
			if mods & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH) != 0:
				properties['executable']= "true"
			bXML.appendText(self.__contents.documentElement, "\n\t")
			element= bXML.appendElement(self.__contents.documentElement, kind, properties)
			if kXattrAvailable:
				try:
					attrs= xattr.listxattr(fullPath)
					for attr in attrs:
						try:
							value= xattr.getxattr(fullPath, attr, True)
							bXML.appendText(element, "\n\t\t")
							tag= bXML.appendElement(element, "xattr", {'name': attr})
							bXML.appendText(tag, escape(value))
						except: # can't read this attribute
							exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()
							traceback.print_exception(exceptionType, exceptionValue, exceptionTraceback, limit=5, file=sys.stderr)
							pass
				except: # something went wrong
					exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()
					traceback.print_exception(exceptionType, exceptionValue, exceptionTraceback, limit=5, file=sys.stderr)
					pass
			if element.firstChild:
				bXML.appendText(element, "\n\t")
		except: # skip files we can't look at
			exceptionType, exceptionValue, exceptionTraceback = sys.exc_info()
			traceback.print_exception(exceptionType, exceptionValue, exceptionTraceback, limit=5, file=sys.stderr)
			pass
	def __parseDirectory(self, skipPaths, skipExtensions, skipNames, doHash, skipAttributes):
		if self.__contents != None:
			raise SyntaxError("Already Created")
		self.__contents= bXML.create("manifest")
		if skipExtensions:
			for item in skipExtensions:
				bXML.appendText(self.__contents.documentElement, "\n\t")
				bXML.appendElement(self.__contents.documentElement, "filter", {'extension': item})
		if skipPaths:
			for item in skipPaths:
				bXML.appendText(self.__contents.documentElement, "\n\t")
				bXML.appendElement(self.__contents.documentElement, "filter", {'path': item})
		if skipNames:
			for item in skipNames:
				bXML.appendText(self.__contents.documentElement, "\n\t")
				bXML.appendElement(self.__contents.documentElement, "filter", {'name': item})
		for path, dirs, files in os.walk(self.__path):
			relativePath= getSubPathRelative(self.__path, path)
			if self.__skipped(relativePath, skipPaths, skipExtensions, skipNames):
				continue
			files.extend(dirs)
			for item in files:
				if self.__skipped(item, None, skipExtensions, skipNames):
					continue
				itemFullPath= os.path.join(path, item)
				itemRelativePath= os.path.join(relativePath, item)
				if self.__skipped(itemRelativePath, skipPaths, None, None):
					continue
				self.__addElement(itemRelativePath, doHash, skipAttributes)
		if self.__contents.documentElement.firstChild:
			bXML.appendText(self.__contents.documentElement, "\n")
				
if __name__ == "__main__":
	for arg in sys.argv[1:]:
		manifest= Manifest(arg)
		buffer= cStringIO.StringIO()
		manifest.save(buffer)
		manifest2= Manifest(buffer.getvalue())
		manifestPath= os.path.join("/tmp", os.path.split(arg)[1]+".xml")
		manifest2.save(manifestPath)
		manifest3= Manifest(manifestPath)
		manifest3.save(sys.stdout)
