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
try:
	import hashlib
	kUseHashlib= True
except:
	import sha
	kUseHashlib= False

global gEnvironment
global gFallbackServers
gEnvironment= {}
gFallbackServers= [
	"http://itscommunity.com/build/exports.xml",
]

def newHasher():
	if kUseHashlib:
		return hashlib.sha1()
	return sha.new()

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

def findTagByPath(xml, path):
	element= xml.documentElement
	parts= path.split('/')
	for part in parts:
		elementList= element.getElementsByTagName(part)
		if len(elementList) == 0:
			return None
		element= elementList[0]
	return element

def extractTagTextByPath(xml, path):
	tag= findTagByPath(xml, path)
	if not tag:
		return None
	return extractTextFromTagContents(tag)

def splitIdIntoParts(item):
	kExportNamePattern= re.compile(r"^(.*[/\\])?([^/\\]+)\.([^/\\.]+)_([0-9]+\.[0-9]+\.[0-9]+[dabf][0-9]+)_([a-zA-Z0-9]+)\.zip$")
	parts= {}
	if os.path.isfile(item):
		(parts['path'], parts['filename'])= os.path.split(item)
	elif item.find("http://") == 0:
		(parts['url'], parts['filename'])= item.rsplit('/', 1)
	else:
		parts['filename']= item
	match= kExportNamePattern.match(parts['filename'])
	if not match:
		return None
	parts.update({
		'domain': match.group(2),
		'name': match.group(3),
		'version': match.group(3),
		'hash': match.group(4),
	})
	return parts

def compareVersions(v1, v2):
	kVersionPattern= re.compile(r"^([0-9]+)[._]([0-9]+)[._]([0-9]+)([dabf])([0-9]+)$")
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

def parseServerManifest(contents):
	serverInfo= {'servers':[],'exports':[]}
	serverXML= xml.dom.minidom.parseString(contents)
	serverList= findTagByPath(serverXML, "servers")
	if serverList:
		for server in serverList.getElementsBytTagName("server"):
			serverInfo['servers'].append(extractTextFromTagContents(server))
	serverList= findTagByPath(serverXML, "exports")
	if serverList:
		for server in serverList.getElementsBytTagName("export"):
			serverInfo['exports'].append(extractTextFromTagContents(server))
	serverXML.unlink()
	return serverInfo

def __filterArchiveList(environment, exports, domain, name, firstOnly= True, minimumVersion= None):
	found= []
	items= filter(lambda x: splitIdIntoParts(x) != None,exports)
	items.sort(lambda x,y: compareVersions(
								splitIdIntoParts(y)['version'],
								splitIdIntoParts(x)['version']
	))
	for item in items:
		parts= splitIdIntoParts(item)
		matches= False
		if parts['domain'].lower() == domain.lower():
			if parts['name'].lower() == name.lower():
				if not minimumVersion or compareVersions(parts['version'],minimumVersion) >= 0:
					matches= True
		if matches:
			if firstOnly:
				return os.path.join(environment['export_path'], item)
			else:
				found.append(os.path.join(environment['export_path'], item))
	return found

def __getLocalExportArchivePath(environment, domain, name, firstOnly= True, minimumVersion= None):
	return __filterArchiveList(environment, os.listdir(environment['export_path']), domain, name, firstOnly, minimumVersion)

def getExports(environment, domain, name, firstOnly= True, minimumVersion= None):
	found= __getLocalExportArchivePath(environment, domain, name, firstOnly, minimumVersion)
	if found:
		return found
	servers= list(gFallbackServers)
	try:
		exportsFile= open(os.path.join(environment['export_path'], "exports.xml"))
		contents= exportsFile.read()
		exportsFile.close()
		info= parseServerManifest(contents)
		for server in info['servers']:
			if server not in servers:
				servers.append(server)
	except:
		pass
	allServers= []
	goodServers= []
	while len(servers) > 0:
		server= pop(servers)
		if server not in allServers:
			allServers.append(server)
		try:
			serverConnection= urllib2.urlopen(server)
			contents= serverConnection.read()
			serverConnection.close()
		except:
			contents= None
		if contents:
			goodServers.append(server)
			info= parseServerManifest(contents)
			for server in info['servers']:
				if server not in allServers:
					servers.append(server)
					allServers.append(server)
			remote= __filterArchiveList(
						environment, info['exports'], domain, name,
						firstOnly= False, minimumVersion= minimumVersion
			)
			baseURL= server.rsplit('/', 1)[0].strip()
			found.extend(map(lambda x:baseURL+'/'+x,remote))
			while firstOnly and len(remote) > 0:
				item= remote.pop(0)
				url= baseURL+'/'+item
				destinationPath= os.path.join(environment['export_path'], item)
				try:
					sourceConnection= urllib2.urlopen(url)
					destinationFile= open(destinationPath, 'w')
					while True:
						block= sourceConnection.read(kReadBlockSize)
						if not block:
							break
						destinationFile.write(block)
					destinationFile.close()
					sourceConnection.close()
					return destinationPath
				except:
					pass
	if firstOnly:
		return None
	return (found, goodServers)

def __init(environment):
	basename= os.path.splitext(os.path.split(__file__)[1])[0]
	startPath= os.path.split(os.path.realpath(__file__))[0]
	if os.name == 'posix' and os.uname()[0] == 'Darwin':
		environment.update({
			'start_script_basename': basename,
			'start_path': startPath,
			'preferences_path': os.path.join(os.environ['HOME'], "Library", "Preferences", basename+".xml"),
			'export_path': os.path.join(os.environ['HOME'], "Sites", basename),
			'export_url': "".join((
				"http://",socket.gethostname(),"/~",getpass.getuser(),"/",basename
			)),
			'scratch_path': os.path.join(os.environ['HOME'], "Library", "Caches", basename+"_scratch"),
			'dependencies_path': os.path.join(os.environ['HOME'], "Library", "Caches", basename),
			'operating_system': 'mac',
			'start_script': __file__,
			'start_script_name': os.path.split(__file__)[1],
			'package_path': os.path.join(startPath, "package.xml"),
			'export_name_pattern': re.compile(r"^(.*[/\\])?(.*)_([0-9]+_[0-9]+_[0-9]+[dabf][0-9]+)_([a-zA-Z0-9]+)\.zip$"),
			'findTagByPath': findTagByPath,
			'extractTextFromTagContents': extractTextFromTagContents,
			'extractTagTextByPath': extractTagTextByPath,
			'splitIdIntoParts': splitIdIntoParts,
			'newHasher': newHasher,
		})
	else:
		raise AssertionError("This OS needs some values supported")

def __getPrefInfo(environment):
	preferenceXML= xml.dom.minidom.parse(environment['preferences_path'])
	environment['export_path']= extractTagTextByPath(preferenceXML, "exports")
	environment['dependencies_path']= extractTagTextByPath(preferenceXML, "dependencies")
	preferenceXML.unlink()

def __findBuild(environment, location):
	idParts= splitIdIntoParts(location)
	environment['build_path']= os.path.join(environment['dependencies_path'], idParts['domain'], idParts['name'], idParts['version'])
	if not os.path.isdir(environment['build_path']):
		buildArchive= getExports(environment, "com.itscommunity", "build", firstOnly= True)
		if None == buildArchive:
			print "Cannot find com.itscommunity.build export, please download one to:"
			print "\t",environment['export_path']
			sys.exit(1)

def __loadPackage(environment):
	packageXML= xml.dom.minidom.parse(environment['package_path'])
	packageName= extractTagTextByPath(packageXML, "name")
	packageDomain= extractTagTextByPath(packageXML, "domain")
	if 'com.itscommunity' == packageDomain and environment['start_script_basename'] == packageName:
		environment['build_path']= environment['start_path']
	else:
		itemXMLList= findTagByPath(packageXML, "dependencies")
		if itemXMLList:
			for export in itemXMLList.getElementsByTagName("dependency"):
				location= extractTextFromTagContents(export)
				isExportName= environment['export_name_pattern'].match(location.split("/")[-1].strip())
				if isExportName and isExportName.group(2) == "com.itscommunity.build":
					__findBuild(environment, location.strip())
					break
	packageXML.unlink()

def __getBuildPath(environment):
	if os.path.isfile(environment['package_path']):
		__loadPackage(environment)


global kDefaultPreferences
kDefaultPreferences= """<build>
	<exports>%(export)s</exports>
	<dependencies>%(dependencies)s</dependencies>
	<base_url>%(url)s</base_url>
	<scratch>%(scratch)s</scratch>
	<domain>com.yourdomain</domain>
	<author>Your Name</author>
	<email>your@email.address</email>
	<company>Your Company Name</company>
</build>"""
if __name__ == "__main__":
	__init(gEnvironment)
	if not os.path.isfile(gEnvironment['preferences_path']):
		prefFile= open(gEnvironment['preferences_path'], "w")
		prefFile.write(kDefaultPreferences%({
			'export': gEnvironment['export_path'],
			'dependencies': gEnvironment['dependencies_path'],
			'scratch': gEnvironment['scratch_path'],
			'url': gEnvironment['export_url'],
		}))
		prefFile.close()
		print "Please re-run %s after updating %s"%(gEnvironment['start_script_name'], gEnvironment['preferences_path'])
		sys.exit(1)
	__getPrefInfo(gEnvironment)
	if not os.path.isdir(gEnvironment['export_path']):
		os.makedirs(gEnvironment['export_path'])
	if not os.path.isdir(gEnvironment['dependencies_path']):
		os.makedirs(gEnvironment['dependencies_path'])
	__getBuildPath(environment)
