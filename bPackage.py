#!/usr/bin/env python

__all__ = [ 					# exported symbols from this module
	"Packge",					# Wrapping package file into useful functions
	#"parseXMLListOfExports",	# used internally
]

import bID
import bDOM
import os.path
import bConstants

def parseXMLListOfExports(xml, pathToList, itemName, itemList, warningList):
	itemXMLList= bDOM.findTagByPath(xml, pathToList)
	if itemXMLList:
		for export in itemXMLList.getElementsByTagName(itemName):
			location= bDOM.extractTextFromTagContents(export)
			itemList.append(bID.ID(location))

class Package:
	def __init__(self, contents):
		self.__path= None
		if os.path.isfile(contents):
			self.__path= contents
		packageXML= bDOM.link(contents)
		self.__contents= {
			'name': bDOM.extractTagTextByPath(packageXML, "name"),
			'domain': bDOM.extractTagTextByPath(packageXML, "domain"),
			'author': bDOM.extractTagTextByPath(packageXML, "author"),
			'email': bDOM.extractTagTextByPath(packageXML, "email"),
			'version': bDOM.extractTagTextByPath(packageXML, "version"),
			'company': bDOM.extractTagTextByPath(packageXML, "company"),
			'changes': bDOM.extractTagTextByPath(packageXML, "changes"),
			'todo': bDOM.extractTagTextByPath(packageXML, "todo"),
			'changepat': bDOM.extractTagTextByPath(packageXML, "changepat"),
			'filterExtensions': [],
			'filterPaths': [],
			'filterNames': [],
			'errors': [],
			'warnings': [],
			'dependencies': [],
			'previous': [],
		}
		parseXMLListOfExports(packageXML, "dependencies", "dependency", self.__contents['dependencies'], self.__contents['warnings'])
		parseXMLListOfExports(packageXML, "previous", "version", self.__contents['previous'], self.__contents['warnings'])
		if self.__contents['domain'] and self.__contents['name']:
			self.__contents['full_name']= self.__contents['domain']+"_"+self.__contents['name']
		else:
			self.__contents['full_name']= None
		for filter in packageXML.getElementsByTagName('filter'):
			ext= filter.getAttribute('extension')
			if ext:
				self.__contents['filterExtensions'].append(ext)
			path= filter.getAttribute('path')
			if path:
				self.__contents['filterPaths'].append(path)
			name= filter.getAttribute('name')
			if name:
				self.__contents['filterNames'].append(name)
		packageXML.unlink()
	def __repr__(self):
		return "Packge(path="+str(self.__path)+",contents="+str(self.__contents)+")"
	def __getitem__(self, key):
		return self.__contents[key]
	def directory(self):
		return os.path.split(self.__path)[0]
	def upgrade(self, dependency, upgraded):
		#print "Upgrading from ",dependency,"to",upgraded
		packageXML= bDOM.link(self.__path)
		dependencyList= bDOM.findTagByPath(packageXML, "dependencies")
		if dependencyList:
			for dep in dependencyList.getElementsByTagName("dependency"):
				location= bDOM.extractTextFromTagContents(dep)
				depID= bID.ID(location)
				if depID.equals(dependency):
					bDOM.changeTagContents(packageXML, dep, upgraded.filename())
					break
		packageFile= open(self.__path, 'w')
		packageXML.writexml(packageFile)
		packageFile.close()
		packageXML.unlink()
	def changesFilePath(self):
		return os.path.join(os.path.split(self.__path)[0], *self['changes'].split('/'))
	def todoFilePath(self):
		return os.path.join(os.path.split(self.__path)[0], *self['todo'].split('/'))
	def changesPattern(self):
		return self['changepat']
	def addPrevious(self, identifier):
		packageXML= bDOM.link(self.__path)
		previousList= bDOM.findTagByPath(packageXML, "previous")
		if not previousList:
			previousList= packageXML.createElement('previous')
			previousList.appendChild(packageXML.createTextNode("\n\t"))
			packageXML.documentElement.appendChild(packageXML.createTextNode("\t"))
			packageXML.documentElement.appendChild(previousList)
			packageXML.documentElement.appendChild(packageXML.createTextNode("\n"))
		nextVersion= packageXML.createElement('version')
		versionText= packageXML.createTextNode(identifier.filename())
		nextVersion.appendChild(versionText)
		previousList.appendChild(packageXML.createTextNode("\t"))
		previousList.appendChild(nextVersion)
		previousList.appendChild(packageXML.createTextNode("\n\t"))
		packageFile= open(self.__path, 'w')
		packageXML.writexml(packageFile)
		packageFile.close()
		packageXML.unlink()
	def asID(self):
		return bID.ID(self.__contents['full_name']+"_"+self.__contents['version'])
	def bumpVersion(self, bumpPhase= False):
		packageXML= bDOM.link(self.__path)
		version= bDOM.extractTagTextByPath(packageXML, 'version')
		if version != self.__contents['version']:
			print "WARNING: package version changed from ",self.__contents['version']," to ",version
		#print "version",version
		parts= bConstants.kVersionPattern.match(version)
		newVersion= parts.group(1)+"."+parts.group(2)+"."
		#print "newVersion",newVersion
		patchNumber= int(parts.group(3))
		#print "patchNumber",patchNumber
		phase= parts.group(4)
		#print "phase",phase
		buildNumber= int(parts.group(5))
		#print "buildNumber",buildNumber
		if bumpPhase and phase == bConstants.kBuildPhaseOrder[-1]:
			patchNumber+= 1
			phase= bConstants.kBuildPhaseOrder[0]
			buildNumber= 0
		elif bumpPhase and bConstants.kBuildPhaseOrder.find(phase) >= 0:
			phase= bConstants.kBuildPhaseOrder[bConstants.kBuildPhaseOrder.find(phase) + 1]
			buildNumber= 0
		else:
			buildNumber+= 1
		newVersion+= str(patchNumber)+phase+str(buildNumber)
		#print "newVersion",newVersion
		bDOM.setTagContentsByPath(packageXML, 'version', newVersion)
		#print "Updating ",self.__path
		packageFile= open(self.__path, 'w')
		packageXML.writexml(packageFile)
		packageFile.close()
		packageXML.unlink()
		self.__contents['version']= newVersion
