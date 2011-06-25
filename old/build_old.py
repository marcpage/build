#!/usr/bin/env python

# We support back to at least python 2.3.5

import sys
import random
import math
import zipfile
import xml.dom.minidom
import os
import zipfile
import re
import urllib2
import stat
try:
	import hashlib	# introduced in python 2.5
	kUseHashlib= True
except:
	import md5		# deprecated in python 2.5
	kUseHashlib= False

""" The list of allowed command line arguments """
arguments= {
	'--name': None,		# Used to name a new project (ignored if there is already a kPackageFileName)
	'--upgrade': 0,
		'--yes': 0,
	'--merge': None,
	'--branch': None,
	'--revert': None,
	'--export': 0,
		'--phase': 0,	# change the build phase before exporting
	'--pref': None,
	'--verbose': 0,
}

""" key for package """
kDepByNameKey= 'dependencies_by_name'

""" Only one of these arguments may be passed at a time """
kOnlyOneOfTheseArgs= ['--upgrade', '--merge', '--branch', '--revert', '--export']

""" Do not export these files """
kExportIgnoreFileList= [".DS_Store"]

""" Files with these extensions in the export are allowed """
kDoNotRemoveExtensionsFromExport= ['.pyc']

""" Search these servers if there is not build on the local machine """
kBootStrapServers= ["http://markiv/~marcp/build.py/exports.txt", "http://myberrygoodhealth.com/build.py/exports.txt"]

""" Name of the package XML file """
kPackageFileName= "package.xml"

""" Name of the rules python file to execute for building """
kRulesFileName= "rules.py"

""" Name of the exports list file in the export directory """
kExportsFile= "exports.txt"

""" Name of the manifest file inside the export zip """
kManifestFileNameInExport= "manifest.txt"

""" The build domain """
kThisDomain= "com_myberrygoodhealth"

""" The build name """
kThisName= "build"

""" The full build name """
kThisFullName= kThisDomain+"_"+kThisName

""" The name of this script """
kThisScriptName= os.path.split(__file__)[1]

""" The name of this script, with all dots (.) changed to underscores (_) """
kThisScriptNoDots= kThisScriptName.replace('.', '_')

""" The end of line string to use when you don't know what to use """
kEndOfLineWhenWeDontKnowWhatToUse= "\r\n"

""" The size of block to read when doing block copies """
kReadBlockSize= 4096

""" The order in which the build phases progress, from lowest to highest value """
kBuildPhaseOrder= "dabf"

""" Pattern to split on to get lines """
kEndOfLinePattern= re.compile(r"(\r\n|\r|\n)")

""" Used to break up the zip file name, 1 = full name (domain and name), 2= version, 3= hash """
kExportNamePattern= re.compile(r"^(.*)_([0-9]+_[0-9]+_[0-9]+[%(phases)s][0-9]+)_([a-zA-Z0-9]+)\.zip$"%{'phases': kBuildPhaseOrder})

""" The parts of a version, used to compare versions """
kVersionPattern= re.compile(r"^([0-9]+)[._]([0-9]+)[._]([0-9]+)([%(phases)s])([0-9]+)$"%{'phases': kBuildPhaseOrder})

""" The pattern to search for for files to copy to the new project folder, if they do not exist """
kTemplateFilenameString= "_template."

""" The string in the changes.html file to place new changes under """
kChangeInsertPattern= re.compile(r"<!-- Insert New Version Here -->")

""" The text to put after kChangeInsertPattern in changes.html """
kNewChangeText= """
			<br><b>Version %(version)s</b>
				<ol>
					<li>Put Changes Here
				</ol>"""

""" The default preferences file contents """
kDefaultPreferences= """<build>
	<exports>%(export)s</exports>
	<dependencies>%(dependencies)s</dependencies>
	<scratch>%(scratch)s</scratch>
	<domain>com_yourdomain</domain>
	<author>Your Name</author>
	<email>your@email.address</email>
	<company>Your Company Name</company>
	<untitled>Untitled</untitled>
</build>"""


""" ****************** General Purpose Utilities ****************** """


def fullyDeleteDirectoryHierarchy(path):
	""" Attempts to do rm -r path
		does not handle read-only files
	"""
	for (root, dirs, files) in os.walk(path, topdown= False):
		for file in files:
			os.remove(os.path.join(root, file))
		for dir in dirs:
			os.rmdir(os.path.join(root, dir))

def newMD5Hasher():
	""" Abstraction to generate an MD5 hasher.
		So we don't have to know if hashlib is available on this system
	"""
	if kUseHashlib:
		return hashlib.md5()
	return md5.new()

def getSubPathRelative(base, path):
	""" Assumption: path is a sub-path of base
		return relative path from base to path
		os.path.join(base, result) == path
	"""
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

def osname():
	""" Gets the name of the OS
		Possible values:
			Mac OS X
			Windows
			Linux
		for other posix environments, returns uname[0]
		otherwise returns os.name
	"""
	if os.name == 'posix':
		if os.uname()[0] == 'Darwin':
			return 'Mac'
		return os.uname()[0]
	elif os.name == 'nt':
		return 'Windows'
	return os.name

def parseArgs(validArgs):
	""" Parse the command line arguments and return them.
		validArgs is a dictionary with key being the switches for the command line
		if the value for a given key is an integer, the integer will be incremented each time the switch is encountered
			integer value switches cannot have a field after it
		if the value for a given key is a list, the argument after the given key on the command line will be appended to the list
		otherwise, the value will be assigned the argument after the given key
		if one of the keys is empty string, it's value should be a list
			empty string key will get all arguments that are not part of a switch, usually used for file paths
		if there is no emptry string key, and a switch is encountered that is not a key, a SyntexError is raised
	"""
	nextIs= None
	for arg in sys.argv[1:]:
		if None == nextIs and not arg in validArgs.keys() and '' in validArgs.keys():
			nextIs= ''
		if None != nextIs:
			if isinstance(validArgs[nextIs], list):
				validArgs[nextIs].append(arg)
			else:
				validArgs[nextIs]= arg
			nextIs= None
		elif arg in validArgs.keys():
			if isinstance(validArgs[arg], int):
				validArgs[arg]+= 1
			else:
				nextIs= arg
		else:
			raise SyntaxError(
				"ERROR: Unknown parameter: "+arg+"\nValid Args: "+", ".join(validArgs.keys())+"\n"
			)

def fileHash(path, isText= False):
	""" Hashes a file and returns the hash(es)
		Uses MD5 for hashing
		if isText is True, then 4 hashes are returned, which are:
			0: hash of original data
			1: hash of contents with line ending converted to UNIX (\n)
			2: hash of contents with line ending converted to Mac (\r)
			3: hash of contents with line ending converted to DOS (\r\n)
		returns a comma separated list of MD5 hashes if isTest is true, otherwise returns just one MD5 hash
	"""
	if isText:
		hashers= (newMD5Hasher(), newMD5Hasher(), newMD5Hasher(), newMD5Hasher())
	else:
		hashers= (newMD5Hasher(),)
	file= open(path, "rb")
	while True:
		block= file.read(kReadBlockSize)
		if not block:
			break
		while isText and (block[-1] == "\r" or block[-1] == "\n"):
			character= file.read(1)
			if len(character) == 0:
				break
			block+= character
		hashers[0].update(block)
		if isText:
			unixBlock= block.replace("\r\n", '\n').replace('\r', '\n')
			hashers[1].update(unixBlock)
			macBlock= block.replace("\r\n", '\r').replace('\n', '\r')
			hashers[2].update(macBlock)
			dosBlock= unixBlock.replace('\n', "\r\n")
			hashers[3].update(dosBlock)
	file.close()
	if isText:
		return hashers[0].hexdigest()+","+hashers[1].hexdigest()+","+hashers[2].hexdigest()+","+hashers[3].hexdigest()
	return hashers[0].hexdigest()


""" ****************** XML Utilities ****************** """


def findTagByPath(xml, path):
	""" returns a tag who is the first element of each path element (separated by slash (/))
		For instance:
		<document>
			<file>
				<name>test</name>
			</file>
		</document>
		findTagByPath(xml, "file/name")
		would return a tag that contains the text "test"
		note: document, the top level tag, is considered the documentElement, and ignored
		Returns None if there is nothing in the XML of that path
	"""
	element= xml.documentElement
	parts= path.split('/')
	for part in parts:
		elementList= element.getElementsByTagName(part)
		if len(elementList) == 0:
			return None
		element= elementList[0]
	return element

def extractTextFromTagContents(tagElement):
	""" given an XML tag element, extract all text elements from it,
		appending them into one string
		TODO: Does this handle text [CDATA] text?
	"""
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

def extractTagTextByPath(xml, path):
	""" See: findTagByPath for path explanation
		gets the containing text from a tag
		return None if path does not exist in the XML
	"""
	tag= findTagByPath(xml, path)
	if not tag:
		return None
	return extractTextFromTagContents(tag)

def setTagContentsByPath(xml, path, newContents):
	""" See: findTagByPath for path explanation
		changes the contents of a tag
		NOTE: if it has sub-tags, they will be deleted also
	"""
	element= findTagByPath(xml, path)
	while element.hasChildNodes():
		element.removeChild(element.firstChild)
	textNode= xml.createTextNode(newContents)
	element.appendChild(textNode)

def addTagToList(xml, path, tag, contents):
	""" See: findTagByPath for path explanation
		a tag with the given name and text contents is inserted into
			the tag with the given path
	"""
	element= findTagByPath(xml, path)
	newTag= xml.createElement(tag)
	tagContents= xml.createTextNode(contents)
	newTag.appendChild(tagContents)
	element.appendChild(newTag)


""" ****************** build.py Specific Utilities ****************** """


def compareVersions(v1, v2):
	""" compares two versions
			returns > 0 if v1 > v2
			returns < 0 if v1 < v2
			returns 0 if v1 == v2
	"""
	#print "v1="+str(v1)
	#print "v2="+str(v2)
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
	
def parseExport(exportString):
	""" Takes a line from a kExportsFile file and returns of tuple of:
		0: full name (domain_shortName)
		1: url (entire line, if it is not local, otherwise None)
		2: server (the path to the kExportsFile on the server if it is not local, otherwise None)
	"""
	exportString= exportString.strip()
	name= None
	server= None
	url= None
	if len(exportString) > 0:
		slashPos= exportString.rfind('/')
		if slashPos > 0:
			server= exportString[:slashPos + 1]+kExportsFile
			url= exportString
			name= exportString[slashPos + 1:]
		else:
			name= exportString
	return (name, url, server)

def getIDURLOnServer(server, export):
	""" TODO: Document
	"""
	slashPos= server.rfind('/')
	(identifier, exportURL, exportServer)= parseExport(export)
	return server[:slashPos + 1]+identifier

def exportsMatch(e1, e2):
	""" TODO: Document
		Are these export identifiers a match
		each may be full name, identifier or even url
		if all the data from the smaller matches it's
			counterpart in the other, return True
	"""
	if e1 == e2:
		return True
	(i1, u1, s1)= parseExport(e1)
	(i2, u2, s2)= parseExport(e2)
	if i1 == i2:
		return True
	m1= kExportNamePattern.match(i1)
	m2= kExportNamePattern.match(i2)
	if not m1: # full name, not identifier
		return i1 == m2.group(1)
	if not m2: # full name, not identifier
		return m1.group(1) == i2
	# if hashes (group(3)) don't match, we got a duplicate export, but ignore that, they're the same
	return m1.group(1) == m2.group(1) and m1.group(2) == m2.group(2)

def compareExports(e1, e2):
	""" TODO: Document
	"""
	if e1 == e2: # literally identical
		return 0
	(i1, u1, s1)= parseExport(e1)
	(i2, u2, s2)= parseExport(e2)
	if i1 == i2: # logically identical (full ID matches)
		if s1 == s2: # now sort by server
			return 0
		if not s1:
			return -1
		if not s2:
			return 1
		if s1 > s2:
			return 1
		if s1 < s2:
			return -1
		return 0
	m1= kExportNamePattern.match(i1)
	m2= kExportNamePattern.match(i2)
	if not m1 and not m2: # neither one is a valid export name
		if e1 < e2:
			return -1
		if e1 > e2:
			return 1
		return 0
	if not m1: # just e1 is not a valid export name
		return -1
	if not m2: # just e2 is not a valid export name
		return 1
	if m1.group(1) < m2.group(1): # compare full names
		return -1
	if m1.group(1) > m2.group(1):
		return 1
	versionComparison= compareVersions(m1.group(2), m2.group(2))
	if versionComparison != 0:
		return versionComparison
	if m1.group(3) == m2.group(3):
		return 0
	# we should never get here, a full name / version should be unique to a hash
	if m1.group(3) > m2.group(3):
		return 1
	return -1
		
def parseExportsContents(exportsContents):
	""" Given the contents of a kExportsFile, return a tuple of:
		0: identifiers (names of the zip files) listed, without any URLs
		1: All items specified as URLs (not local)
		2: All servers (with path to kExportsFile on that server) mentioned in the exportsContents
	"""
	servers= []
	urls= []
	names= []
	for line in kEndOfLinePattern.split(exportsContents):
		(name, url, server)= parseExport(line)
		if name and name not in names:
			names.append(name)
		if url and url not in urls:
			urls.append(url)
		if server and server not in servers:
			servers.append(server)
	return (names, urls, servers)

def parseLocalExports(exportsDir):
	""" See parseExportsContents for a description of return values
		gets all the information from the local kExportsFile
	"""
	localExportsFile= os.path.join(exportsDir, kExportsFile)
	if os.path.isfile(localExportsFile):
		localExportsFile= open(localExportsFile, "r")
		localExportsContents= localExportsFile.read()
		localExportsFile.close()
		return parseExportsContents(localExportsContents)
	return ([], [], [])

def parseServerExports(server):
	""" See parseExportsContents for a description of return values
		get all the information from a URL for a kExportsFile (server)
	"""
	try:
		connection= urllib2.urlopen(server)
		contents= connection.read()
		connection.close()
		return parseExportsContents(contents)
	except:
		return ([], [], [])

def handleArguments(args, runAsSubScript):
	""" TODO Document
	"""
	if osname() == 'Mac':
		preferencesPath= os.path.join(os.environ['HOME'], 'Library', 'Preferences', kThisScriptNoDots+'.xml')
		defaultExportPath= os.path.join(os.environ['HOME'], 'Sites', kThisScriptName)
		defaultDependenciesPath= os.path.join(os.environ['HOME'], 'Library', 'Caches', kThisScriptName)
		defaultScratchPath= os.path.join(os.environ['HOME'], 'Library', 'Caches', kThisName+'_scratch')
	else:
		raise SyntaxError("Figure out what to use for paths for platform '%s'"%(osname()));
	parseArgs(args)
	if runAsSubScript:
		args['--export']= 0 # do not export just because the calling script is exporting
		useCwd= os.path.split(__file__)[0]
	else:
		useCwd= os.getcwd()
	onlyOneCount= 0
	for arg in args:
		if args[arg] and arg in kOnlyOneOfTheseArgs:
			if args['--verbose']:
				print "Found an 'onlyOne': "+arg
			onlyOneCount+= 1
	if onlyOneCount > 1:
		if args['--verbose']:
			print "onlyOneCount= %d"%(onlyOneCount)
		raise SyntaxError("These arguments cannot be used together: "+", ".join(kOnlyOneOfTheseArgs))
	if not args['--pref']:
		args['--pref']= preferencesPath
	if args['--verbose']:
		print "Arguments"
		for arg in args:
			print "\t%s=%s"%(arg, args[arg])
	try:
		prefsDOM= xml.dom.minidom.parse(args['--pref'])
	except:
		prefsDOM= xml.dom.minidom.parseString(kDefaultPreferences%{
			'export': defaultExportPath,
			'dependencies': defaultDependenciesPath,
			'scratch': defaultScratchPath,
		})
		prefFile= open(args['--pref'], 'w')
		prefsDOM.writexml(prefFile)
		prefsDOM.unlink()
		prefFile.close()
		return "Please update: '%s', no further action taken"%(args['--pref'])
	prefs= {
		'directories': {
			'exports': extractTagTextByPath(prefsDOM, "exports"),
			'dependencies': extractTagTextByPath(prefsDOM, "dependencies"),
			'scratch': extractTagTextByPath(prefsDOM, "scratch"),
		},
		'domain': extractTagTextByPath(prefsDOM, "domain"),
		'author': extractTagTextByPath(prefsDOM, "author"),
		'email': extractTagTextByPath(prefsDOM, "email"),
		'company': extractTagTextByPath(prefsDOM, "company"),
		'untitled': extractTagTextByPath(prefsDOM, "untitled"),
		'cwd': useCwd, # kind of a hack, but let's us get the cwd when run as a sub-script
	}
	prefsDOM.unlink()
	if prefs['untitled'] and not args['--name']:
		args['--name']= prefs['untitled']
	if not args['--name']:
		args['--name']= "Untitled"
	if args['--verbose']:
		print "Preferences"
		for pref in prefs:
			if isinstance(prefs[pref], dict):
				print "\t"+pref
				for item in prefs[pref]:
					print "\t\t%s=%s"%(item, prefs[pref][item])
			else:
				print "\t%s=%s"%(pref, prefs[pref])
	return prefs

def parseXMLListOfExports(xml, pathToList, itemName, itemList, warningList):
	""" TODO: Document
	"""
	itemXMLList= findTagByPath(xml, pathToList)
	if itemXMLList:
		for export in itemXMLList.getElementsByTagName(itemName):
			location= extractTextFromTagContents(export)
			(identifier, url, server)= parseExport(location)
			correctlyNamedIdentifier= kExportNamePattern.match(identifier)
			if not correctlyNamedIdentifier:
				warningList.append(
					"%s '%s' has a mis-named file '%s', must match '%s'"%(
						pathToList,
						export,
						identifier,
						kExportNamePattern.pattern,
					)
				)
			else:
				info= {
					'id': identifier,
					'full_name': correctlyNamedIdentifier.group(1),
					'version': correctlyNamedIdentifier.group(2),
					'hash': correctlyNamedIdentifier.group(3),
					'url': url,
					'server': server,
				}
				itemList.append(info)

def printPackage(package):
	""" TODO: Document
	"""
	for item in package:
		if isinstance(package[item], list):
			if len(package[item]) == 0:
				print "\t"+item+" [Empty]"
			else:
				print "\t"+item
			for index in range(0, len(package[item])):
				element= package[item][index]
				if isinstance(element, dict):
					print "\t\t#%d"%(index + 1)
					for key in element:
						print "\t\t%s=%s"%(key, element[key])
				else:
					print "\t\t#%d '%s'"%(index + 1, element)
		else:
			print "\t%s=%s"%(item, package[item])

def parsePackageXML(packageXML):
	""" TODO: Document
	"""
	contents= {
		'name': extractTagTextByPath(packageXML, "name"),
		'domain': extractTagTextByPath(packageXML, "domain"),
		'author': extractTagTextByPath(packageXML, "author"),
		'email': extractTagTextByPath(packageXML, "email"),
		'version': extractTagTextByPath(packageXML, "version"),
		'company': extractTagTextByPath(packageXML, "company"),
		'errors': [],
		'warnings': [],
		'dependencies': [],
		'previous': [],
	}
	parseXMLListOfExports(packageXML, "dependencies", "dependency", contents['dependencies'], contents['warnings'])
	parseXMLListOfExports(packageXML, "previous", "version", contents['previous'], contents['warnings'])
	if contents['domain'] and contents['name']:
		contents['full_name']= contents['domain']+"_"+contents['name']
	else:
		contents['full_name']= None
	return contents

def getPackageSubdirectory(path, name, package):
	""" TODO: Document
	"""
	if not package.has_key('directories'):
		package['directories']= {}
	package['directories'][name]= os.path.join(path, package['domain'], package['name'], package['version'])
	return package['directories'][name]

def parsePackage(preferences):
	""" TODO: Document
	"""
	path= os.path.join(preferences['cwd'], kPackageFileName)
	package= xml.dom.minidom.parse(path)
	contents= parsePackageXML(package)
	package.unlink()
	contents['path']= path
	getPackageSubdirectory(preferences['directories']['scratch'], 'out', contents)
	contents['directories']['in']= os.path.split(contents['path'])[0]
	return contents

def findIDInURLList(ids, urls):
	""" TODO: Document
	"""
	if not isinstance(ids, list):
		ids= [ids]
	foundURLs= list(ids)
	for url in urls:
		for identifier in ids:
			position= url.rfind(identifier)
			if position == len(url) - len(identifier) and url not in foundURLs:
				foundURLs.insert(0, url)
	return foundURLs

def downloadExportURL(verbose, exportsDir, url):
	""" Given the URL to a zipfile, download it and append it to the local kExportsFile
		NOTE: Does not extract it, just downloads it
	"""
	(name, url, server)= parseExport(url)
	exportName= kExportNamePattern.match(name)
	if not exportName:
		return False # Trying to download non-export
	if not os.path.isdir(exportsDir):
		os.makedirs(exportsDir)
	localPath= os.path.join(exportsDir, name)
	localFile= open(localPath, "wb")
	remoteConnection= urllib2.urlopen(url)
	hasher= newMD5Hasher()
	while True:
		block= remoteConnection.read(kReadBlockSize)
		if not block:
			break
		hasher.update(block)
		localFile.write(block)
	localFile.close()
	remoteConnection.close()
	hashIsGood= hasher.hexdigest().lower() == exportName.group(3).lower()
	if not hashIsGood or not validateExportFile(verbose, localPath):
		os.remove(localPath)
		return False # Corrupt export
	localExports= parseLocalExports(exportsDir)
	if url not in localExports:
		localExportsFile= open(os.path.join(exportsDir, kExportsFile), "a")
		localExportsFile.write(url+kEndOfLineWhenWeDontKnowWhatToUse)
		localExportsFile.close()
	return True

def validateExportFileAgainstHash(hashes, fileContents):
	""" given a list of comma separated MD5 hashes, checks that the contents match one of them
	"""
	hashes= hashes.lower().split(',')
	hasher= newMD5Hasher()
	hasher.update(fileContents)
	calculatedHash= hasher.hexdigest().lower()
	return calculatedHash in hashes
	
def findExports(ids, name):
	""" TODO: Finnish documenting
		name can be either  the full name or the identifier (zip file name)
		1. find exact export
		2. find exports with given name
			if all == True, then return a list of all with that fullName
	"""
	found= []
	for foundID in ids:
		if foundID == name:
			return [foundID] # found exactly what they were looking for
		foundIDMatchesExportPattern= kExportNamePattern.match(foundID)
		if foundIDMatchesExportPattern:
			if name == foundIDMatchesExportPattern.group(1):
				foundVersion= foundIDMatchesExportPattern.group(2)
				if foundID not in found:
					found.append(foundID)
	return found

def findExportURLsOnServer(verbose, name, server):
	""" TODO: Document
	"""
	if verbose:
		print "findExportURLsOnServer(name= %s, server=%s)"%(name, server)
	(ids, urls, servers)= parseServerExports(server)
	foundURLs= []
	for identifier in findExports(ids, name):
		if exportsMatch(name, identifier):
			url= getIDURLOnServer(server, identifier)
			if url not in foundURLs:
				foundURLs.append(url)
			otherURLs= findIDInURLList(identifier, urls)
			for url in otherURLs:
				if url not in foundURLs:
					foundURLs.append(url)
	return (foundURLs, servers)

def findRemoteExportURLs(verbose, name, serverList):
	""" TODO: Document
	"""
	foundURLs= []
	newServers= []
	for server in serverList:
		(foundURLs, foundServers)= findExportURLsOnServer(verbose, name, server)
		for url in foundURLs:
			if url not in foundURLs:
				foundURLs.append(url)
		for foundServer in foundServers:
			if foundServer not in newServers and foundServer not in serverList:
				newServers.append(foundServer)
	return (foundURLs, newServers)

def validateExportFile(verbose, path, wantDetails= False):
	""" Checks that an export file meets the following requirements:
			1. filname matches kExportNamePattern
			2. hash in filename matches MD5 hash of contents of the file
			3. must have a kPackageFileName file in the zip
			4. package must have name, domain and version tags
			5. name, domain and version of the filename must match the ones in the package file
		if wantDetails, on success returns a tuple of:
			0: zipfile.ZipFile of the export
			1: package dict
		if not wantDetails (the default), then just return True
		NOTE: If wantDetails and successfully validated (False not returned, but the tuple)
			you *must* call results[0].close() when you are done
	"""
	if verbose:
		print "validateExportFile(path= %s, wantDetails= %s)"%(path, str(wantDetails))
	if not os.path.isfile(path):
		if verbose:
			print "not a file"
		return False
	(directory, filename)= os.path.split(path)
	matchesExportPattern= kExportNamePattern.match(filename)
	if not matchesExportPattern:
		if verbose:
			print "Export name was not of the expected format"
		return False
	fullName= matchesExportPattern.group(1)
	version= matchesExportPattern.group(2)
	hash= matchesExportPattern.group(3).lower()
	actualHash= fileHash(path, isText= False).lower()
	if hash != actualHash:
		if verbose:
			print "Export is corrupt, hash does not match contents"
		return False
	try:
		exportFile= zipfile.ZipFile(path, "r")
	except:
		if verbose:
			print "unable to read export zip file"
		return False
	try:
		packageXML= exportFile.read(kPackageFileName)
	except:
		exportFile.close()
		if verbose:
			print "no package file in the export zip file"
		return False
	try:
		packageDOM= xml.dom.minidom.parseString(packageXML)
	except:
		exportFile.close()
		if verbose:
			print "package file is corrupt in export"
		return False
	package= parsePackageXML(packageDOM)
	packageDOM.unlink()
	if not package['full_name']:
		exportFile.close()
		if verbose:
			print "either no name or no domain tag in package"
		return False
	if not package['version']:
		exportFile.close()
		if verbose:
			print "no version tag in package"
		return False
	if fullName != package['full_name']:
		if verbose:
			print "Export name does not match package"
		return False
	if compareVersions(version, package['version']) != 0:
		if verbose:
			print "Version in export name does not match package name: %s vs package: %s"%(version, package['version'])
		return False
	if wantDetails:
		return (exportFile, package)
	exportFile.close()
	return True

def findValidLocalExport(verbose, exportsDir, name, wantURLs= False):
	""" TODO: Document
	"""
	if verbose:
		print "findValidLocalExport(exportsDir= %s, name= %s, wantURLs= %s"%(
			exportsDir,
			name,
			str(wantURLs),
		)
	(ids, urls, servers)= parseLocalExports(exportsDir)
	found= findExports(ids, name)
	found.sort(lambda x,y: compareExports(y, x)) # version high to low
	if verbose:
		print "found %s: %s"%(name, str(found))
	for localExport in found:
		if verbose:
			print "evaluating export: "+localExport
		if validateExportFile(verbose, os.path.join(exportsDir, localExport)):
			if verbose:
				print localExport+" validated"
			if wantURLs:
				return findIDInURLList(localExport, urls) # found it locally
			return localExport
	if wantURLs:
		return []
	return None

def ensureLocalExport(verbose, preferences, export= None, name= None, serverList= None, wantURLs= False):
	""" TODO: Document
		TODO: Add all new found URLs to the kExportsFile
		if export is not given, and name is a full name (not an id) then the latest version found
			will be returned
	"""
	
	if export:
		(name, url, server)= parseExport(export)
	else:
		server= None
	if verbose:
		print "ensureLocalExport(export= %s, name= %s, serverList= %s, wantURLs=%s)"%(
			str(export),
			str(name),
			str(serverList),
			str(wantURLs),
		)

	# search locally
	validLocalExport= findValidLocalExport(verbose, preferences['directories']['exports'], name, wantURLs)
	if validLocalExport:
		return validLocalExport
	
	# if not local, prepare list of servers to search
	if serverList: # if a seed list of servers was passed in, use them
		servers= list(serverList)
	else:
		servers= []
	
	# if there was a server listed in the export id, add it to the top of the list
	if server and server not in servers:
		servers.insert(0, server)
	
	# get the localURLs so we don't append duplicates
	(localIDs, localURLs, localServers)= parseLocalExports(preferences['directories']['exports'])

	# walk servers (and servers they reference) until we find what we are looking for
	alreadySearched= []
	while len(servers) > 0:
		(urls, newServers)= findRemoteExportURLs(verbose, name, servers)
		newURLs= []
		for url in urls: # look for new URLs for this name
			if url not in newURLs and url not in localURLs:
				newURLs.append(url)
		if newURLs: # if we found new URLs, add them to the exports.txt file
			exportsFile= open(os.path.join(preferences['directories']['exports'], kExportsFile), "a")
			exportsFile.write(kEndOfLineWhenWeDontKnowWhatToUse.join(newURLs))
			exportsFile.close()
			localURLs.extend(newURLs)
		for url in urls:
			if downloadExportURL(verbose, preferences['directories']['exports'], url):
				validLocalExport= findValidLocalExport(verbose, preferences['directories']['exports'], name, wantURLs)
				if validLocalExport:
					return validLocalExport
		
		# still haven't found what I'm looking for, collect list of new servers to search
		alreadySearched.extend(servers)
		servers= []
		for server in newServers:
			if server not in alreadySearched:
				servers.append(server)
	
	# we did not find what we were looking for anywhere
	if wantURLs:
		return []
	return None

def validateExport(verbose, preferences, export, actions= None, fix= True):
	""" makes sure that the contents of the export zip at exportPath matches the dependencies directory
		will create files if they don't exist
		will re-create files if they do not match the expected hash
		will delete files that are not in the zip (except of the extensions in kDoNotRemoveExtensionsFromExport)
		if fix is False or we are unable to validate the export, None will be returned instead of creating, re-creating and deleting
		otherwise returns package dict
	"""
	(identifier, url, server)= parseExport(export)
	validateInfo= validateExportFile(verbose, os.path.join(preferences['directories']['exports'], identifier), wantDetails= True)
	if not validateInfo:
		return None
	(exportFile, package)= validateInfo
	getPackageSubdirectory(preferences['directories']['dependencies'], 'in', package)
	getPackageSubdirectory(preferences['directories']['scratch'], 'out', package)
	if not os.path.isdir(package['directories']['in']):
		if fix:
			os.makedirs(package['directories']['in'])
		else:
			return None
	manifest= exportFile.read(kManifestFileNameInExport)
	validatedPaths= []
	for line in kEndOfLinePattern.split(manifest):
		if line.find(':') > 0:
			(hashes, relativeFilePath)= line.split(':', 2)
			testPath= os.path.join(package['directories']['in'], relativeFilePath)
			generate= fix
			if os.path.isfile(testPath):
				testFile= open(testPath, "r")
				testContents= testFile.read()
				testFile.close()
				if validateExportFileAgainstHash(hashes, testContents):
					generate= None
					validatedPaths.append(relativeFilePath)
				elif not fix:
					return None
			elif not fix:
				return None
			if generate:
				if os.path.isfile(testPath):
					if actions:
						actions.append("Fixing: '%s'"%(testPath))
					os.remove(testPath)
				else:
					if actions:
						actions.append("Creating: '%s'"%(testPath))
					fullyDeleteDirectoryHierarchy(testPath)
				parentDirectory= os.path.split(testPath)[0]
				if not os.path.isdir(parentDirectory):
					os.makedirs(parentDirectory)
				testFile= open(testPath, "w")
				testFile.write(exportFile.read(relativeFilePath))
				testFile.close()
				validatedPaths.append(relativeFilePath)
	for (root, dirs, files) in os.walk(package['directories']['in']):
		for file in files:
			fullPath= os.path.join(root, file)
			relPath= getSubPathRelative(package['directories']['in'], fullPath)
			if not relPath in validatedPaths and os.path.splitext(relPath)[1] not in kDoNotRemoveExtensionsFromExport:
				if fix:
					if actions:
						actions.append("Removing '%s'"%(fullPath))
					os.remove(fullPath)
				else:
					return None
	exportFile.close()
	return package

def getMissingTemplateFiles(verbose, buildPath, buildID, defaultName, preferences):
	""" If there are build template files that do not exist in this project,
		copy over the templates (replacing variables)
		If kThisScriptName is not the same as the script in the build export,
		copy over the kThisScriptName over the existing one in the project
		if kThisScriptName is created or modified, return true to notify caller
		not to do anything else, since this script was replaced
	"""
	templateParameters= {
		'name': defaultName,
		'domain': preferences['domain'],
		'author': preferences['author'],
		'email': preferences['email'],
		'company': preferences['company'],
		'build_dependency': buildID,
	}
	noNeedToRestart= True
	for item in os.listdir(buildPath):
		templatePos= item.find(kTemplateFilenameString)
		if templatePos > 0 or item == kThisScriptName:
			if item == kThisScriptName:
				templateName= item
			else:
				templateName= item[:templatePos]+item[templatePos + len(kTemplateFilenameString) - 1:]
			doesntExist= not os.path.isfile(os.path.join(preferences['cwd'], templateName))
			if doesntExist or item == kThisScriptName:
				sourceFile= open(os.path.join(buildPath, item), "r")
				sourceContents= sourceFile.read()
				sourceFile.close()
				if item == kThisScriptName:
					if os.path.isfile(os.path.join(preferences['cwd'], item)):
						destFile= open(os.path.join(preferences['cwd'], templateName), "r")
						destContents= destFile.read()
						destFile.close()
						writeOutTemplate= destContents != sourceContents
					else:
						writeOutTemplate= True
					noNeedToRestart= not writeOutTemplate
				else:
					writeOutTemplate= True
				if writeOutTemplate:
					if item == kThisScriptName and os.path.isfile(os.path.join(preferences['cwd'], templateName)):
						os.chmod(os.path.join(preferences['cwd'], templateName), stat.S_IREAD | stat.S_IEXEC | stat.S_IWRITE)
					destFile= open(os.path.join(preferences['cwd'], templateName), "w")
					if item == kThisScriptName:
						destFile.write(sourceContents)
					else:
						destFile.write(sourceContents%templateParameters)
					destFile.close()
					if item == kThisScriptName:
						os.chmod(os.path.join(preferences['cwd'], templateName), stat.S_IREAD | stat.S_IEXEC)
	return noNeedToRestart

def bootstrap(verbose, preferences, defaultName):
	""" TODO: Document
	"""
	buildDependencyURLs= ensureLocalExport(verbose, preferences, name= kThisFullName, serverList= kBootStrapServers, wantURLs= True)
	if not buildDependencyURLs:
		return "Unable to find %s anywhere locally or anywhere on the servers"%(kThisFullName)
	if verbose:
		print "buildDependencyURLs="+str(buildDependencyURLs)
	buildPackage= validateExport(verbose, preferences, buildDependencyURLs[0])
	if not buildPackage:
		return "Unable to validate export on local machine: '%s'"%(buildDependencyURLs[0])
	if verbose:
		print "buildPackage="+str(buildPackage)
	getMissingTemplateFiles(verbose, buildPackage['directories']['in'], buildDependencyURLs[0], defaultName, preferences)
	return None

def fillInPackageDependencies(verbose, package, preferences, defaultName):
	""" TODO: Document
	"""
	if not package.has_key(kDepByNameKey):
		package[kDepByNameKey]= {}
	for dependency in package['dependencies']:
		if not dependency.has_key('package'):
			urls= ensureLocalExport(verbose, preferences, export= dependency['id'], serverList= kBootStrapServers, wantURLs= True)
			if verbose:
				print "dependency="+str(dependency)
				print "\t urls="+str(urls)
			if not dependency['url']:
				dependency['url']= urls[0]
			if verbose:
				actions= []
			else:
				actions= None
			dependency['package']= validateExport(verbose, preferences, urls[0], actions)
			if actions:
				for action in actions:
					print "\t"+action
			if not package[kDepByNameKey].has_key(dependency['full_name']):
				package[kDepByNameKey][dependency['full_name']]= dependency
			if not package[kDepByNameKey].has_key(dependency['package']['name']):
				package[kDepByNameKey][dependency['package']['name']]= dependency

def export(preferences, package, changePhase):
	""" Performs an export on the current directory.
		TODO: document more
	"""
	if not os.path.isdir(preferences['directories']['exports']):
		os.makedirs(preferences['directories']['exports'])
	if changePhase:
		versionCorrect= kVersionPattern.match(package['version'])
		if not versionCorrect:
			raise SyntaxError("Version in the %s file is not correct %s"%(kPackageFileName, kVersionPattern.pattern))
		versionBase= package['version'][:versionCorrect.start(3)]
		patch= int(versionCorrect.group(3))
		phase= versionCorrect.group(4)
		phaseIndex= kBuildPhaseOrder.index(phase)
		phaseIndex+= 1
		if phaseIndex >= len(kBuildPhaseOrder):
			phaseIndex= 0 # 1.2.3f5 changePhase -> 1.2.4d0
			patch+= 1
		package['version']= versionBase+str(patch)+kBuildPhaseOrder[phaseIndex]+"0"
		packageDOM= xml.dom.minidom.parse(package['path'])
		setTagContentsByPath(packageDOM, "version", package['version'])
		packageFile= open(package['path'], "w")
		packageDOM.writexml(packageFile)
		packageFile.close()
		packageDOM.unlink()
	version= package['version']
	versionCorrect= kVersionPattern.match(version)
	if not versionCorrect:
		raise SyntaxError("Version (%s) in the %s file is not correct %s"%(version, kPackageFileName, kVersionPattern.pattern))
	packageDomain= package['domain']
	packageName= package['name']
	filenameVersion= version.replace(".", "_")
	zipBaseName= "%(domain)s_%(name)s_%(version)s_"%{
		'domain': packageDomain,
		'name': packageName,
		'version': filenameVersion,
	}
	workingZipPath= os.path.join(preferences['directories']['exports'], zipBaseName+".zip")
	zipFile= zipfile.ZipFile(workingZipPath, 'w', zipfile.ZIP_DEFLATED)
	manifestContents= ""
	for root, dirs, files in os.walk(preferences['cwd']):
		for file in files:
			if file not in kExportIgnoreFileList:
				fullPath= os.path.join(root, file)
				relativePath= getSubPathRelative(preferences['cwd'], fullPath)
				manifestContents+= fileHash(fullPath, isText= True)+":"+relativePath+kEndOfLineWhenWeDontKnowWhatToUse
				zipFile.write(relativePath)
	zipFile.writestr(kManifestFileNameInExport, manifestContents)
	zipFile.close()
	hashvalue= fileHash(workingZipPath, isText= False)
	correctZipName= zipBaseName+hashvalue+".zip"
	os.rename(workingZipPath, os.path.join(preferences['directories']['exports'], correctZipName))
	exportsFile= open(os.path.join(preferences['directories']['exports'], kExportsFile), "a")
	exportsFile.write(correctZipName+kEndOfLineWhenWeDontKnowWhatToUse)
	exportsFile.close()
	nextBuildNumber= int(versionCorrect.group(5)) + 1
	version= version[:versionCorrect.end(4)]+str(nextBuildNumber)
	packageDOM= xml.dom.minidom.parse(package['path'])
	setTagContentsByPath(packageDOM, "version", version)
	addTagToList(packageDOM, "previous", "version", correctZipName)
	packageFile= open(package['path'], "w")
	packageDOM.writexml(packageFile)
	packageFile.close()
	packageDOM.unlink()
	changesFile= open(os.path.join(preferences['cwd'], "changes.html"), "r")
	changes= changesFile.read()
	changesFile.close()
	changesCorrect= kChangeInsertPattern.search(changes)
	if not changesCorrect:
		raise SyntaxError("Missing %s in the changes.html file"%(kChangeInsertPattern.pattern))
	changes= changes[:changesCorrect.end()] + kNewChangeText%{'version': version} + changes[changesCorrect.end():]
	changesFile= open(os.path.join(preferences['cwd'], "changes.html"), "w")
	changesFile.write(changes)
	changesFile.close()

def runScript(path, mode, phase, context= None):
	""" Runs a python script in a clean (or given) context
		Sets the following environment variables:
			__file__: path to the script being run
			__mode__: __self__ if we are running a script on behalf of its own project
						__dependency__ if we are running a script on behalf of another project
			__phase__: __preflight__, __run__ or __postflight__ build phase
		Also adds the path of the script being run to the module search path,
			so modules next to this script can be imported
	"""
	if None == context:
		context= {}
	context['__file__']= path
	context['__mode__']= mode
	context['__phase__']= phase
	searchPathsBefore= list(sys.path)
	sys.path.append(os.path.split(path)[0])
	execfile(path, context)
	sys.path= searchPathsBefore
	return context

def runBuilds(verbose, package):
	""" TODO: Document
	"""
	if verbose:
		print "runBuilds(%s)"%(package['full_name'])
	for packageDependency in package['dependencies']:
		buildDir= packageDependency['package']['directories']['in']
		buildPath= os.path.join(buildDir, kThisScriptName)
		if verbose:
			print "Running build of dependency at: "+buildPath
		runScript(buildPath, "__dependency__", "__run__", {})

def runRules(verbose, phase, package, context= None, dependency= None):
	""" Runs the kRulesFileName for the top level package or the given dependency
			also runs the kRulesFileName for dependencies of the top level package
		The following context variables are set:
			__main__= the main package
			__running__= the package of the running kRulesFileName
	"""
	if None == context:
		context= {}
	context['__main__']= package
	if verbose:
		print "runRules(phase= %s, package= %s, dependency= %s)"%(phase, package['full_name'], str(dependency))
	if None == dependency:
		for packageDependency in package['dependencies']:
			runRules(verbose, phase, package, context, packageDependency['full_name'])
		context['__running__']= package
		mode= "__self__"
	else:
		context['__running__']= package[kDepByNameKey][dependency]['package']
		mode= "__dependency__"
	rulesPath= os.path.join(context['__running__']['directories']['in'], kRulesFileName)
	if os.path.isfile(rulesPath):
		runScript(rulesPath, mode, phase, context)
	return context


""" ****************** main ****************** """


if __name__ == "__main__" or __name__ == "__builtin__": # __builtin__ when being run as a dependency
	preferences= handleArguments(arguments, __name__ == "__builtin__")
	verbose= arguments['--verbose']
	if verbose:
		print "__file__: "+__file__
	if not isinstance(preferences, dict):
		print preferences # error message returned instead of preferences
		sys.exit(1)
	if not os.path.isfile(os.path.join(preferences['cwd'], kPackageFileName)):
		errorMessage= bootstrap(verbose, preferences, arguments['--name'])
		if errorMessage:
			print errorMessage
		else:
			print kThisScriptName+" was created, please re-run. No Further action has been taken."
		sys.exit(1)
	package= parsePackage(preferences)
	if verbose:
		print "Top Level Package"
		printPackage(package)
	fillInPackageDependencies(verbose, package, preferences, arguments['--name'])
	buildName= None
	if package[kDepByNameKey].has_key(kThisFullName):
		buildName= kThisFullName
	elif package[kDepByNameKey].has_key(kThisName):
		buildName= kThisName
	if buildName:
		buildInDirectory= package[kDepByNameKey][buildName]['package']['directories']['in']
		buildID= package[kDepByNameKey][buildName]['id']
		if not getMissingTemplateFiles(verbose, buildInDirectory, buildID, arguments['--name'], preferences):
			print kThisScriptName+" was updated, please re-run. No Further action has been taken."
			sys.exit(1)
	if arguments['--upgrade']:
		buildDirectory= package[kDepByNameKey][buildName]['package']['directories']['in']
		upgradePath= os.path.join(buildDirectory, "upgrade.py")
		searchPathsBefore= list(sys.path)
		sys.path.append(os.path.split(upgradePath)[0])
		execfile(upgradePath)
		sys.path= searchPathsBefore
		upgrade(verbose, package, preferences, arguments['--yes'])
	elif arguments['--merge']:
		pass
	elif arguments['--branch']:
		pass
	elif arguments['--revert']:
		pass
	else:
		runBuilds(verbose, package)
		context= runRules(verbose, "__preflight__", package)
		runRules(verbose, "__run__", package, context)
		runRules(verbose, "__postflight__", package, context)
		if arguments['--export']:
			if verbose:
				print "Exporting"
			export(preferences, package, arguments['--phase'])
