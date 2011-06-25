#!/usr/bin/env python

import re
import os
import sys
import glob
import socket
import getpass
import urllib2
import xml.sax
import zipfile
import cStringIO
import xml.dom.minidom

kThisScriptName= os.path.split(__file__)[1]
kThisScriptNoDots= kThisScriptName.replace('.', '_')

kExportsFile= "exports.txt"
kHTTPPrefix= "http://"
kBootStrapServers= [
	kHTTPPrefix+"markiv/~marcp/"+kThisScriptNoDots+"/"+kExportsFile,
	kHTTPPrefix+"itscommunity.com/"+kThisScriptNoDots+"/"+kExportsFile
]
kPOSIXOSName= 'posix'
kDarwinOSUName= 'Darwin'
kLibraryPathName= "Library"
kCachesPathName= "Caches"
kDirectoryType= "[directory]"
kDirectoryTag= "directory"
kFileTag= "file"
kHashTag= "hash"
kDependenciesTag= "dependencies"
kHomeEnvName= 'HOME'
kOSSupportMessage= "This OS needs some values supported"
kRealBuildScriptName= "buildExt.py"
kPackageFileName= "package.xml"
kManifestFileNameInExport= "manifest.xml"
kThisDomain= "com_itscommunity"
kThisName= "build"
kDefaultPreferences= """<build>
	<exports>%(export)s</exports>
	<dependencies>%(dependencies)s</dependencies>
	<base_url>%(url)s</base_url>
	<scratch>%(scratch)s</scratch>
	<domain>com_yourdomain</domain>
	<author>Your Name</author>
	<email>your@email.address</email>
	<company>Your Company Name</company>
	<untitled>Untitled</untitled>
</build>"""
kThisFullName= kThisDomain+"_"+kThisName
kThisScriptPath= os.path.split(os.path.realpath(__file__))[0]
kEndOfLineWhenWeDontKnowWhatToUse= "\r\n"
kReadBlockSize= 4096
kBuildPhaseOrder= "dabf"
kEndOfLinePattern= re.compile(r"(\r\n|\r|\n)")
kExportNamePattern= re.compile(r"^(.*[/\\])?(.*)_([0-9]+_[0-9]+_[0-9]+[%(phases)s][0-9]+)_([a-zA-Z0-9]+)\.zip$"%{'phases': kBuildPhaseOrder})
kVersionPattern= re.compile(r"^([0-9]+)[._]([0-9]+)[._]([0-9]+)([%(phases)s])([0-9]+)$"%{'phases': kBuildPhaseOrder})
kManifestLinePattern= re.compile(r"^\s*([0-9a-fA-F]+),([0-9a-fA-F]+)\s+(.*)$", re.MULTILINE)
kManifestDirPattern= re.compile(r"^\s*\[directory\]\s+(.*)$", re.MULTILINE)

# ****************** General Purpose Utilities ******************


try:
	import hashlib # introduced in python 2.5
	kUseHashlib= True
except:
	import md5 # deprecated in python 2.5
	kUseHashlib= False

# Abstraction to generate an MD5 hasher.
#	So we don't have to know if hashlib is available on this system
def newMD5Hasher():
	if kUseHashlib:
		return hashlib.md5()
	return md5.new()

# Attempts to do rm -r path
#	does not handle read-only files
def fullyDeleteDirectoryHierarchy(path):
	for (root, dirs, files) in os.walk(path, topdown= False):
		for file in files:
			os.remove(os.path.join(root, file))
		for dir in dirs:
			os.rmdir(os.path.join(root, dir))

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


# ****************** XML Utilities ******************


# returns a tag who is the first element of each path element (separated by slash (/))
#	For instance:
#	<document>
#		<file>
#			<name>test</name>
#		</file>
#	</document>
#	findTagByPath(xml, "file/name")
#	would return a tag that contains the text "test"
#	note: document, the top level tag, is considered the documentElement, and ignored
#	Returns None if there is nothing in the XML of that path
def findTagByPath(xml, path):
	#print "findTaxByPath(",xml,",",path,")"
	element= xml.documentElement
	parts= path.split('/')
	for part in parts:
		#print "\t","part",part
		elementList= element.getElementsByTagName(part)
		if len(elementList) == 0:
			return None
		element= elementList[0]
	return element

# given an XML tag element, extract all text elements from it,
#	appending them into one string
def extractTextFromTagContents(tagElement):
	child= tagElement.firstChild
	text= ""
	while child:
		if isinstance(child, xml.dom.minidom.Text):
			text+= child.data
		else:
			pass #sys.stderr.write("WARNING: non-Text in tag "+str(child)+"\n")
		if child == tagElement.lastChild:
			break
		child= child.nextSibling
	return text

# See: findTagByPath for path explanation
#	gets the containing text from a tag
#	return None if path does not exist in the XML
def extractTagTextByPath(xml, path):
	tag= findTagByPath(xml, path)
	if not tag:
		return None
	return extractTextFromTagContents(tag)


# ****************** build.py Specific Utilities ******************


# compares two versions
#		returns > 0 if v1 > v2
#		returns < 0 if v1 < v2
#		returns 0 if v1 == v2
#print "v1="+str(v1)
#print "v2="+str(v2)
def compareVersions(v1, v2):
	m1= kVersionPattern.match(v1)
	m2= kVersionPattern.match(v2)
	if int(m1.group(1)) != int(m2.group(1)):
		return int(m1.group(1)) - int(m2.group(1))
	if int(m1.group(2)) != int(m2.group(2)):
		return int(m1.group(2)) - int(m2.group(2))
	if int(m1.group(3)) != int(m2.group(3)):
		return int(m1.group(3)) - int(m2.group(3))
	if kBuildPhaseOrder.find(m1.group(4)) != kBuildPhaseOrder.find(m2.group(4)):
		return kBuildPhaseOrder.find(m1.group(4)) - kBuildPhaseOrder.find(m2.group(4))
	return int(m1.group(5)) - int(m2.group(5))

# Gets the OS specific path to the preferences file
def getPreferenceFilePath():
	if os.name == kPOSIXOSName and os.uname()[0] == kDarwinOSUName:
		return os.path.join(os.environ[kHomeEnvName], kLibraryPathName, "Preferences", kThisScriptNoDots+".xml")
	raise AssertionError(kOSSupportMessage)

# Gets the OS specific default path for exports
def getDefaultExportPath():
	if os.name == kPOSIXOSName and os.uname()[0] == kDarwinOSUName:
		return os.path.join(os.environ[kHomeEnvName], "Sites", kThisScriptNoDots)
	raise AssertionError(kOSSupportMessage)

# Gets the OS specific default URL for exports (externally visible), should match getDefaultExportPath()
def getDefaultURL():
	if os.name == kPOSIXOSName and os.uname()[0] == kDarwinOSUName:
		return kHTTPPrefix+socket.gethostname()+"/~"+getpass.getuser()+"/"+kThisScriptNoDots
	raise AssertionError(kOSSupportMessage)

# Gets the OS specific path to the scratch directory
def getDefaultScratchPath():
	if os.name == kPOSIXOSName and os.uname()[0] == kDarwinOSUName:
		return os.path.join(os.environ[kHomeEnvName], kLibraryPathName, kCachesPathName, kThisScriptNoDots+"_scratch")
	raise AssertionError(kOSSupportMessage)

# Gets the OS specific path to the dependencies directory
def getDefaultDependenciesPath():
	if os.name == kPOSIXOSName and os.uname()[0] == kDarwinOSUName:
		return os.path.join(os.environ[kHomeEnvName], kLibraryPathName, kCachesPathName, kThisScriptNoDots)
	raise AssertionError(kOSSupportMessage)

# Gets a list of all the preference override files by the given name in the given path
def findPreferenceOverrideFiles(currentPath, overrideName):
	found= []
	while True:
		here= os.path.join(currentPath, overrideName)
		if os.path.isfile(here):
			found.append(here)
		(currentPath, dirname)= os.path.split(currentPath)
		if len(dirname) == 0:
			break
	return found

# inputs:
#	http://server.com/~user/path/domain_name_1.0.0d0_hash.zip
#	c:\server\www\domain_name_1.0.0d0_hash.zip
#	domain_name_1.0.0d0_hash.zip
# returns full name, version, hash, filename, url (maybe empty), path (maybe empty)
def splitIdIntoParts(item):
	#print "splitIdIntoParts(",item,")"
	path= ""
	url= ""
	if os.path.isfile(item):
		(path, name)= os.path.split(item)
	elif item.find(kHTTPPrefix) == 0:
		(url, name)= item.rsplit('/', 1)
	else:
		name= item
	match= kExportNamePattern.match(name)
	if not match:
		return (None, None, None, None, None, None)
	return (match.group(2), match.group(3), match.group(4), name, url, path)

def compareBuildVersions(b1, b2):
	#print "compareBuildVersions(",b1,",",b2,")"
	v1= splitIdIntoParts(b1)[1]
	v2= splitIdIntoParts(b2)[1]
	#print "\t",v1,v2
	return compareVersions(v1, v2)

# Hashes a file and returns the hash(es)
#	Uses MD5 for hashing
#	If writeable is specified, all input will be written to this writeable
#	2 hashes are returned, which are:
#		0: hash of original data
#		1: hash of contents with line endings  (\r and \n) removed
#	returns a comma separated list of MD5 hashes
def fileHash(readable, writeable= None):
	binaryHash= newMD5Hasher()
	textHash= newMD5Hasher()
	while True:
		block= readable.read(kReadBlockSize)
		if not block:
			break
		binaryHash.update(block)
		if writeable:
			writeable.write(block)
		textHash.update(block.replace("\r", "").replace("\n", ""))
	return (binaryHash.hexdigest(), textHash.hexdigest())

def download(url, exportDir):
	filename= url.split('/')[-1]
	destination= os.path.join(exportDirs[0], filename)
	destinationFile= open(destination, "wb")
	connection= urllib2.urlopen(url)
	hash= fileHash(connection, writeable= destinationFile)
	destinationFile.close()
	connection.close()
	if splitIdIntoParts(url)[3].lower() != hash[0].hexdigest().lower():
		raise AssertionError(url+" is corrupt")
	return destination

def findARemoteBuild(exportDir):
	exportsList= os.path.join(exportDir, kExportsFile)
	if os.path.isfile(exportsList):
		exportFile= open(exportsList, "r")
		exportFileContents= exportFile.read()
		exportFile.close()
		lines= kEndOfLinePattern.split(exportFileContents)
		for line in lines:
			server= line.rsplit('/', 1)[0].strip()+"/"+kExportsFile
			if server.find(kHTTPPrefix) == 0 and server not in kBootStrapServers:
				kBootStrapServers.insert(0, server) # we don't want to burden the original bootstrap servers
	serverIndex= 0
	while serverIndex < len(kBootStrapServers):
		try:
			connection= urllib2.urlopen(kBootStrapServers[serverIndex])
			listing= connection.read()
			connection.close()
			buildFiles= []
			for export in kEndOfLinePattern.split(listing):
				try:
					(fullName, version, hash, filename, url, path)= splitIdIntoParts(export.strip())
					if len(server) > 0:
						server= url+"/"+kExportsFile
						if server not in kBootStrapServers:
							kBootStrapServers.insert(serverIndex + 1, server)
					if fullName == kThisFullName:
						buildFiles.append(filename)
				except:
					pass # skipp listing items that don't look right
			buildFiles.sort(lambda x,y: compareBuildVersions(x,y))
			buildFiles.reverse()
			for buildFile in buildFiles:
				try:
					return download(kBootStrapServers[serverIndex].rsplit('/', 1)[0]+"/"+buildFile, exportsDir[0])
				except:
					pass # ignore exports that don't download
		except:
			pass # ignore problems and go on to the next one
		serverIndex+= 1
	return None

def findABuild(exportDir):
	#print "findABuild(",exportDir,")"
	potentialBuilds= []
	for file in glob.glob(os.path.join(exportDir, kThisFullName+"_*.zip")):
		if splitIdIntoParts(file)[0]:
			potentialBuilds.append(file)
	if len(potentialBuilds) == 0:
		return findARemoteBuild(exportDir)
	potentialBuilds.sort(lambda x,y: compareBuildVersions(x,y))
	return potentialBuilds[-1] # should this be 0?

def findBuildId(exportDir, buildId):
	#print "findBuildId(",exportDir,",",buildId,")"
	filename= splitIdIntoParts(buildId)[3]
	fullPath= os.path.join(exportDir, filename)
	if os.path.isfile(fullPath):
		return fullPath
	return None

def getPrefInfo(preferenceFile):
	preferenceXML= xml.dom.minidom.parse(preferenceFile)
	exportsPath= extractTagTextByPath(preferenceXML, "exports")
	dependenciesPath= extractTagTextByPath(preferenceXML, kDependenciesTag)
	preferenceXML.unlink()
	return (exportsPath, dependenciesPath)

def generateManifestOfDirectory(directory):
	manifest= {}
	for path, dirs, files in os.walk(directory):
		for file in files:
			filePath= os.path.join(path, file)
			theFile= open(filePath, "r")
			manifest[getSubPathRelative(directory, filePath)]= fileHash(theFile)
			theFile.close()
		for dir in dirs:
			dirPath= os.path.join(path, dir)
			manifest[getSubPathRelative(directory, dirPath)]= kDirectoryType
	return manifest

class ManifestSAXHandler(xml.sax.handler.ContentHandler):
	kFileTypeItems= [kFileTag, kDirectoryTag] # , "link"
	def __init__(self):
		self.__manifest= {}
		self.__currentFile= None
		self.__binaryMD5= None
		self.__textMD5= None
		self.__hashIsText= None
		self.__hashText= None
	def startElement(self, name, attrs):
		if name in self.kFileTypeItems:
			path= attrs.getValue('path')
			if name == kFileTag:
				self.__currentFile= path
			elif name == kDirectoryTag:
				self.__manifest[path]= kDirectoryType
		elif name == kHashTag and attrs.getValue('algorithm') == "md5":
			self.__hashIsText= 'text' in attrs.getNames() and attrs.getValue('text')[0].lower() == 't'
			self.__hashText= ""
	def endElement(self, name):
		if name == kFileTag:
			self.__manifest[self.__currentFile]= (self.__binaryMD5, self.__textMD5)
			self.__currentFile= None
			self.__binaryMD5= None
			self.__textMD5= None
		elif name == kHashTag:
			if None != self.__hashIsText and None != self.__hashText:
				hash= self.__hashText.rstrip()
				if self.__hashIsText:
					self.__textMD5= hash
					if None == self.__binaryMD5:
						self.__binaryMD5= hash
				else:
					self.__binaryMD5= hash
					if None == self.__textMD5:
						self.__textMD5= hash
		self.__hashText= None
	def characters(self, text):
		if None != self.__hashText:
			if len(self.__hashText) == 0:
				lstripped= text
				if len(lstripped) > 0:
					self.__hashText= lstripped
			else:
				self.__hashText+= text
	def manifest(self):
		return self.__manifest

def openFileInZip(zipFileObject, path):
	try:
		return zipFileObject.open(path)
	except:
		return cStringIO.StringIO(zipFileObject.read(path))

def ensureExport(depDir, exportFile):
	#print "ensureExport(",depDir,", ",exportFile,")"
	exportZip= zipfile.ZipFile(exportFile, "r")
	manifest= openFileInZip(exportZip, kManifestFileNameInExport)
	worker= ManifestSAXHandler()
	parser= xml.sax.make_parser()
	parser.setContentHandler(worker)
	parser.parse(manifest)
	manifest.close()
	manifestFromExport= worker.manifest()
	#print "manifestFromExport", [manifestFromExport]
	idParts= splitIdIntoParts(exportFile)
	fullName= idParts[0]
	version= idParts[1].replace('.', '_')
	dependencyDir= os.path.join(depDir, fullName, version)
	if not os.path.isdir(dependencyDir):
		#print "ensureExport(",depDir,",",exportFile,") making dir 1 ",dependencyDir
		os.makedirs(dependencyDir)
	manifestFromDirectory= generateManifestOfDirectory(dependencyDir)
	toRemove= []
	for possiblyRemove in manifestFromDirectory:
		#print "possiblyRemove",possiblyRemove
		doesExist= manifestFromExport.has_key(possiblyRemove)
		binaryMatch= doesExist and manifestFromDirectory[possiblyRemove][0].lower() == manifestFromExport[possiblyRemove][0].lower()
		textMatch= doesExist and manifestFromDirectory[possiblyRemove][1].lower() == manifestFromExport[possiblyRemove][1].lower()
		doesNotMatch= not binaryMatch and not textMatch
		if doesNotMatch:
			fullPath= os.path.join(dependencyDir, possiblyRemove)
			#print "Removing ",fullPath,doesNotMatch,binaryMatch,textMatch,doesExist
			if os.path.isdir(fullPath):
				fullyDeleteDirectoryHierarchy(fullPath)
			else:
				os.remove(fullPath)
			toRemove.append(possiblyRemove)
	for item in toRemove:
		del manifestFromDirectory[item]
	for possiblyAdd in manifestFromExport:
		#print "possiblyAdd",possiblyAdd
		if not manifestFromDirectory.has_key(possiblyAdd):
			if manifestFromExport[possiblyAdd] == kDirectoryType:
				#print "ensureExport(",depDir,",",exportFile,") making dir 2 ",os.path.join(dependencyDir, possiblyAdd)
				directoryPath= os.path.join(dependencyDir, possiblyAdd)
				if not os.path.isdir(directoryPath):
					os.makedirs(directoryPath)
			else:
				parts= possiblyAdd.split("\\")
				if len(parts) > 0:
					zipPath= "/".join(parts) # patch up DOS paths
				else:
					zipPath= possiblyAdd
				source= openFileInZip(exportZip, zipPath)
				destinationPath= os.path.join(dependencyDir, possiblyAdd)
				if not os.path.isdir(os.path.split(destinationPath)[0]):
					#print "ensureExport(",depDir,",",exportFile,") making dir 3 ",os.path.split(destinationPath)[0]
					os.makedirs(os.path.split(destinationPath)[0])
				#print "\t","adding: ",destinationPath,zipPath
				destinationFile= open(destinationPath, "w")
				hash= fileHash(source, writeable= destinationFile)
				destinationFile.close()
				source.close()
				if hash[0].lower() != manifestFromExport[possiblyAdd][0].lower():
					if hash[1].lower() != manifestFromExport[possiblyAdd][1].lower():
						raise AssertionError("Corrupt file: "+destinationPath+" from "+exportFile)
	exportZip.close()
	return dependencyDir


# ****************** main ******************


if __name__ == "__main__":
	preferencesPath= getPreferenceFilePath()
	if not os.path.isfile(preferencesPath):
		prefFile= open(preferencesPath, "w")
		prefFile.write(kDefaultPreferences%({
			'export': getDefaultExportPath(),
			'dependencies': getDefaultDependenciesPath(),
			'scratch': getDefaultScratchPath(),
			'url': getDefaultURL(),
		}))
		prefFile.close()
		print "Please re-run %s after updating %s"%(kThisScriptName, preferencesPath)
		sys.exit(1)
	(exportDir, depDir)= getPrefInfo(preferencesPath)
	if not os.path.isdir(exportDir):
		#print "main making dir 1 ",exportDir
		os.makedirs(exportDir)
	if not os.path.isdir(depDir):
		#print "main making dir 2 ",depDir
		os.makedirs(depDir)
	packageFilePath= os.path.join(kThisScriptPath, kPackageFileName)
	buildBasePath= None
	buildExportPath= None
	#print "packageFilePath",packageFilePath
	if os.path.isfile(packageFilePath):
		packageXML= xml.dom.minidom.parse(packageFilePath)
		packageName= extractTagTextByPath(packageXML, "name")
		packageDomain= extractTagTextByPath(packageXML, "domain")
		if kThisDomain == packageDomain and kThisName == packageName: # we *are* the build
			buildBasePath= kThisScriptPath
		else:
			itemXMLList= findTagByPath(packageXML, kDependenciesTag)
			if itemXMLList:
				for export in itemXMLList.getElementsByTagName("dependency"):
					location= extractTextFromTagContents(export)
					isExportName= kExportNamePattern.match(location.split("/")[-1].strip())
					if isExportName and isExportName.group(2) == kThisFullName:
						buildExportPath= findBuildId(exportDir, location.strip())
						break
		packageXML.unlink()
	if not buildBasePath and not buildExportPath: # could not find a build
		buildExportPath= findABuild(exportDir)
	if not buildBasePath and not buildExportPath: # could not find a build
		print "Unable to find any build export. Please download one and copy it to: "+exportDir
		sys.exit(1)
	#print "buildBasePath",buildBasePath
	#print "buildExportPath",buildExportPath
	if not buildBasePath and buildExportPath:
		buildExportFile= open(buildExportPath, "r")
		exportHash= fileHash(buildExportFile)
		buildExportFile.close()
		if exportHash[0].lower() != splitIdIntoParts(buildExportPath)[2].lower():
			print "Build export is corrupt, please delete and try again: "+buildExportPath
			sys.exit(1)
		buildBasePath= ensureExport(depDir, buildExportPath)
		#print "ensureExport buildBasePath",buildBasePath
	if not buildBasePath:
		print "Unable to get a path for the build export dependency."
		sys.exit(1)
	buildExtPath= os.path.join(buildBasePath, kRealBuildScriptName)
	#print "buildExtPath",buildExtPath
	if not os.path.isfile(buildExtPath):
		print "Missing file: "+buildExtPath
		sys.exit(1)
	context= {
		'__file__': os.path.normpath(os.path.join(os.getcwd(), __file__)),
		'__build__': kThisScriptPath,
		'__script_name_no_dots__': kThisScriptNoDots,
		'preferencesPath': preferencesPath,
		'exportDir': exportDir,
		'depDir': depDir,
		'packageFilePath': packageFilePath,
		'buildBasePath': buildBasePath,
		'buildExportPath': buildExportPath,
	}
	sys.path.insert(0, buildBasePath) # search in build directory first for imports
	execfile(buildExtPath, context)
