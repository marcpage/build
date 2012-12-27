#!/usr/bin/env python

__all__ = [ 	# exported symbols from this module
	"Store",	# The export store object
]

import os
import bID
import sys
import bRSA
import glob
import time
import random
import zipfile
import urllib2
import bArchive
import bPackage
import bConstants

class Store:
	def __init__(self, exportDir, dependencyDir):
		self.__exportDir= exportDir
		self.__dependencyDir= dependencyDir
		self.__locationCache= {}
	def create(self, package, preferences):
		identifier= package.asID()
		filename= "%s_%s_%x-%x-%x.zip"%(
			identifier.fullName(),
			identifier.filenameVersion(),
			time.time(),
			random.randrange(0,100000),
			os.getpid(),
		)
		intermedeateExportPath= os.path.join(preferences['exports'], filename)
		intermedeateExportFile= bArchive.ZipArchive(intermedeateExportPath, 'w')
		manifestFile= intermedeateExportFile.open(bConstants.kManifestFileNameInExport, 'w')
		signatureFile= intermedeateExportFile.open(bConstants.kSignatureFileNameInExport, 'w')
		bArchive.generate(
			package.directory(), manifestFile, bArchive.kAllKnownHashes, bArchive.kStandardCodecs,
			preferences['key'], signatureFile,
			intermedeateExportFile, detectText= True, blockTransferSize= bConstants.kReadBlockSize,
			skipPaths= package['filterPaths'],
			skipExtensions= package['filterExtensions'],
			skipNames= package['filterNames']
		)
		signatureFile.close()
		manifestFile.close()
		intermedeateExportFile.close()
		intermedeateContents= open(intermedeateExportPath, 'r')
		hash= bArchive.transferAndHash(
			intermedeateContents, bArchive.kMD5Hash, blockTransferSize= bConstants.kReadBlockSize,
			output= None, detectText= False, changeLineEndingsTo= None
		)[1][0][1] # 1 = hashes (instead of number of lines), 0 = 1st, 1 = digest (instead of algorithm or is text)
		finalExportPath= os.path.join(preferences['exports'], identifier.fullName()+"_"+identifier.filenameVersion()+"_"+hash+".zip")
		os.rename(intermedeateExportPath, finalExportPath)
		#print "finalExportPath",finalExportPath,os.path.isfile(finalExportPath)
		identifier.merge(bID.ID(finalExportPath))
		exportURL= preferences['base_url']+"/"+os.path.split(finalExportPath)[1]
		package.addPrevious(identifier)
		package.bumpVersion(bumpPhase= (len(sys.argv) == 3) and ('phase' == sys.argv[2]))
		changesPath= os.path.join(package.directory(), os.path.join(*package['changes'].split('/')))
		changesFile= open(changesPath, "r")
		changes= changesFile.read()
		changesFile.close()
		#print [changes]
		changes= changes.replace(package.changesPattern(), package.changesPattern()+"\n\n<li><b>%(version)s</b><br>\nDescription of changes here\n</li><br>\n\n"%{
			'version': package['version'],
		})
		#print [changes]
		changesFile= open(changesPath, "w")
		changesFile.write(changes)
		changesFile.close()
		#print identifier
		#print identifier.filename()
		self.addExport(identifier.filename())
		return (finalExportPath, exportURL)
	def addExport(self, name):
		if not os.path.isfile(os.path.join(self.__exportDir, name)):
			raise SyntaxError(name+" not in "+self.__exportDir)
		exportListPath= os.path.join(self.__exportDir, bConstants.kExportsFile)
		exportListFile= open(exportListPath, 'a')
		exportListFile.write(name+"\n")
		exportListFile.close()
	def has(self, identifier):
		return self.__haveLocal(identifier)
	def get(self, identifier, upgrade= False):
		return self.__find(identifier, upgrade)
	def pathTo(self, identifier, ensure= True):
		allFound= self.get(identifier)
		allFound.sort(lambda x,y: x.compare(y))
		#print "allFound",allFound
		if not allFound:
			raise SyntaxError("Unable to find "+str(identifier))
		pathToZip= os.path.join(self.__exportDir, allFound[-1].filename())
		localPath= os.path.join(
			self.__dependencyDir,
			allFound[-1].fullName(),
			allFound[-1].filenameVersion()
		)
		exportFile= bArchive.ZipArchive(pathToZip, 'r')
		manifestFile= exportFile.open(bConstants.kManifestFileNameInExport, 'r')
		signatureFile= exportFile.open(bConstants.kSignatureFileNameInExport, 'r')
		if ensure:
			fixLevel= 2 # use hashes to validate the contents of the files
		else:
			fixLevel= 1 # quick fix, rely on filesize and mod time
		signatures= bArchive.getSignatures(signatureFile)
		changed= bArchive.validate(
					manifestFile, localPath, fixLevel= fixLevel, archive= exportFile,
					key= bRSA.Key(signatures[0]), signatures= signatures[1],
					hashers= bArchive.kAllKnownHashes, decoders= bArchive.kStandardCodecs,
					platformEOL= bArchive.platformEOL(), blockTransferSize= bConstants.kReadBlockSize
				)
		signatureFile.close()
		manifestFile.close()
		exportFile.close()
		return localPath
	def __matchesIdentifier(self, name, identifier= None, upgrade= False):
		#print ">__matchesIdentifier(",name,",",identifier,",",upgrade,")"
		if bConstants.kExportNamePattern.match(name):
			#print "\t", "Matches"
			thisIdentifier= bID.ID(name)
			#print "\t", "thisIdentifier",thisIdentifier
			isSameItem= identifier and identifier.fullName() == thisIdentifier.fullName()
			#print "\t", "isSameItem",isSameItem
			isUpgrade= upgrade and isSameItem and identifier.compareVersions(thisIdentifier) < 0
			#print "\t", "isUpgrade",isUpgrade
			isMatch= identifier and not upgrade and identifier.equals(thisIdentifier)
			#print "\t", "isMatch",isMatch,"identifier",identifier,"thisIdentifier",thisIdentifier
			if not identifier or isMatch or isUpgrade:
				#print "\t\t", "found"
				return thisIdentifier
		#print "<__matchesIdentifier(",name,",",identifier,",",upgrade,")"
		return None
	def __haveLocal(self, identifier= None, upgrade= False):
		#print ">__haveLocal(",identifier,",",upgrade,")"
		exportsToFind= []
		possibleExports= glob.glob(os.path.join(self.__exportDir, "*.zip"))
		for possibleExport in possibleExports:
			#print "\t","possibleExport",possibleExport
			filename= os.path.split(possibleExport)[1]
			#print "\t\t","filename",filename
			thisIdentifier= self.__matchesIdentifier(filename, identifier, upgrade)
			#print "\t\t","thisIdentifier",thisIdentifier
			if thisIdentifier:
				#print "\t\tMatch!"
				thisIdentifier.merge(bID.ID(possibleExport))
				exportsToFind.append(thisIdentifier)
		#print "<__haveLocal(",identifier,",",upgrade,")"
		return exportsToFind
	def __downloadFromCache(self, identifier):
		if self.__locationCache.has_key(identifier.filename()):
			for server in self.__locationCache[identifier.filename()]:
				found= self.__download(identifier, server)
				if found:
					return found
		return None
	def __findInStream(self, readlines, servers= None, identifier= None, upgrade= False, listAll= False, onServer= None):
		#print "__findInStream(readlines,",servers,",",identifier,",",upgrade,",",listAll,")"
		found= []
		if None == servers:
			servers= []
		while True:
			line= readlines.readline()
			if not line:
				break
			line= line.strip()
			if line.startswith("http://"):
				if line not in servers:
					servers.append(line)
			else:
				#print "\t","line:",line.strip()
				if onServer and bConstants.kExportNamePattern.match(line):
					identifierForCache= bID.ID(line).filename()
					if not self.c.has_key(identifierForCache.filename()):
						self.__locationCache[identifierForCache]= [onServer]
					else:
						self.__locationCache[identifierForCache].append(onServer)
				thisIdentifier= self.__matchesIdentifier(line, identifier, upgrade)
				if thisIdentifier:
					#print "\t","match"
					found.append(thisIdentifier)
					#print "\t","found another",found
					if not listAll:
						#print "\t","found all we need",found
						break # we found what we were looking for
		#print "\t","found all",found
		return (found, servers)
	def __download(self, identifier, server):
		#print "__download(",identifier,",",server,")"
		url= server.rsplit('/',1)[0]+'/'+identifier.filename()
		localPath= os.path.join(self.__exportDir, identifier.filename())
		#print "\t","localPath",localPath,url
		source= urllib2.urlopen(url)
		#print "\t","Downloading"
		destination= open(localPath, 'w')
		#print "\t","Saving"
		hash= bArchive.transferAndHash( input= source, output= destination,
			hashers= bArchive.kMD5Hash, blockTransferSize= bConstants.kReadBlockSize,
			detextText= False, changeLineEndingsTo= None
		)[1][0][1] # 1 = hashes (instead of number of lines), 0 = 1st, 1 = digest (instead of algorithm or is text)
		destination.close()
		source.close()
		hashMatch= hash.lower() == identifier.hash().lower()
		#print "\t","hashMatch",hashMatch,"hash",hash,"identifier.hash()",identifier.hash()
		idMatch= False
		if hashMatch:
			#print "\t","Looks good so far"
			exportZip= zipfile.ZipFile(localPath, 'r')
			package= bPackage.Package(exportZip.read(bConstants.kPackageFileName))
			idMatch= package.asID().equals(identifier)
			exportZip.close()
			if idMatch:
				#print "\t","Still looking good"
				identifier.merge(package.asID())
				identifier.merge(bID.ID(localPath))
				identifier.merge(bID.ID(url))
				self.addExport(identifier.filename())
				return identifier
		#print "\t","bummer, we failed"
		os.remove(localPath)
		return None
	def __find(self, identifier= None, upgrade= False, timeoutInSeconds= 1.0):
		start= time.time()
		found= self.__haveLocal(identifier, upgrade)
		if not found:
			if identifier.hash():
				foundInCache= self.__downloadFromCache(identifier)
				if foundInCache:
					found= [foundInCache]
		if not found:
			exportListPath= os.path.join(self.__exportDir, bConstants.kExportsFile)
			localServers= list(bConstants.kBootStrapServers)
			if os.path.isfile(exportListPath):
				exportListFile= open(exportListPath, 'r')
				(reported, localServers)= self.__findInStream(exportListFile, localServers, identifier, upgrade, listAll= True)
				exportListFile.close()
				if reported:
					pass # we report to have things we don't have
			serversToSearch= list(localServers)
			serversToSearch.sort(lambda x,y: random.randrange(-1, 2, 2)) # shuffle servers
			index= 0
			while index < len(serversToSearch) and time.time() - start < timeoutInSeconds:
				try:
					#print "Getting publicized Exports from",serversToSearch[index]
					server= urllib2.urlopen(serversToSearch[index])
					(foundOnServer, servers)= self.__findInStream(server, serversToSearch, identifier, upgrade, listAll= True, onServer= serversToSearch[index])
					#print "\t","foundOnServer:",foundOnServer,servers
					server.close()
					if foundOnServer:
						found= []
						for item in foundOnServer:
							downloaded= self.__download(item, serversToSearch[index])
							if downloaded:
								found.append(downloaded)
						if found:
							break # don't search every server if we find something suitable
				except:
					#bArchive.reportException()
					pass # ignore bad URLs, servers down, etc
				index+= 1
			if len(localServers) < len(serversToSearch): # we found some new servers, add them to our list
				exportListFile= open(exportListPath, 'a')
				for server in serversToSearch:
					if server not in localServers:
						exportListFile.write(server+"\n")
				exportListFile.close()
		return found
