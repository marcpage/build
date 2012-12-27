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

def newHasher():
	if kUseHashlib:
		return hashlib.sha1()
	return sha.new()

global gEnvironment
global kDefaultPreferences

gEnvironment= {}
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

def extractTagTextByPath(xml, path):
	tag= findTagByPath(xml, path)
	if not tag:
		return None
	return extractTextFromTagContents(tag)

global kExportNamePattern
kExportNamePattern= re.compile(r"^(.*[/\\])?(.*)_([0-9]+_[0-9]+_[0-9]+[dabf][0-9]+)_([a-zA-Z0-9]+)\.zip$")
def splitIdIntoParts(item):
	parts= {}
	if os.path.isfile(item):
		(parts['path'], parts['filename'])= os.path.split(item)
	elif item.find("http://") == 0:
		(parts['url'], parts['filename'])= item.rsplit('/', 1)
	else:
		parts['filename']= item
	match= kExportNamePattern.match(parts['filename'])
	if not match:
		return (None, None, None, None, None, None)
	parts.update({
		'fullname': match.group(2),
		'version': match.group(3),
		'hash': match.group(4),
	})
	return parts

def __init(environment):
	basename= os.path.splitext(os.path.split(__file__)[1][0]
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
	buildName= os.splitext(idParts['fullname'])[0]
	environment['build_path']= os.path.join(environment['dependencies_path'], buildName)
	if not os.path.isdir(environment['build_path']):
		# fill in

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

