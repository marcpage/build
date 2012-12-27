#!/usr/bin/env python

__all__ = [ # exported symbols from this module
	"ID",	# Export ID class
]
import bConstants
import os.path

class ID:
	def __init__(self, identifier):
		""" identifier could be:
			fullName
			fullName_version
			fullName_version_hash.zip
			/path/to/fullName_version_hash.zip
			http://url/to/fullName_version_hash.zip
		"""
		if isinstance(identifier, ID):
			self.__fullName= identifier.__fullName
			self.__name= identifier.__name
			self.__version= identifier.__version
			self.__hash= identifier.__hash
			self.__url= identifier.__url
			self.__path= identifier.__path
		else:
			if os.path.isfile(identifier):
				(self.__path, self.__name)= os.path.split(identifier)
				self.__url= ""
			elif identifier.lower().startswith("http://"):
				self.__url= identifier
				self.__name= identifier.split('/')[-1]
				self.__path= ""
			else:
				self.__name= identifier
				self.__url= ""
				self.__path= ""
			#print identifier,"::",self.__dict__
			match= bConstants.kExportNamePattern.match(self.__name)
			if match:
				self.__fullName= match.group(1)
				self.__version= match.group(2)
				self.__hash= match.group(3)
			else:
				isNameAndVersion= bConstants.kExportNameAndVersionPattern.match(identifier)
				if isNameAndVersion:
					self.__fullName= isNameAndVersion.group(1)
					self.__version= isNameAndVersion.group(2)
					#print "isNameAndVersion: ",self.__fullName,self.__version
				else:
					self.__fullName= identifier
					self.__version= ""
				self.__url= ""
				self.__path= ""
				self.__hash= ""
				self.__name= ""
	def __stringCompare(self, s1, s2):
		if s1 < s2:
			return -1
		if s1 > s2:
			return 1
		return 0
	def __mergeCompare(self, other, mine):
		if not other or not mine:
			return True
		return other == mine
	def compareVersions(self, otherID):
		if otherID.__fullName != self.__fullName:
			raise AssertionError("Cannot compareVersions of "+otherID.__fullName+" and "+self.__fullName)
		if self.version() == otherID.version():
			return 0
		if not self.version():
			return -1
		if not otherID.version():
			return 1
		m1= bConstants.kVersionPattern.match(self.version())
		m2= bConstants.kVersionPattern.match(otherID.version())
		if int(m1.group(1)) != int(m2.group(1)):
			return int(m1.group(1)) - int(m2.group(1))
		if int(m1.group(2)) != int(m2.group(2)):
			return int(m1.group(2)) - int(m2.group(2))
		if int(m1.group(3)) != int(m2.group(3)):
			return int(m1.group(3)) - int(m2.group(3))
		if bConstants.kBuildPhaseOrder.find(m1.group(4)) != bConstants.kBuildPhaseOrder.find(m2.group(4)):
			return bConstants.kBuildPhaseOrder.find(m1.group(4)) - bConstants.kBuildPhaseOrder.find(m2.group(4))
		return int(m1.group(5)) - int(m2.group(5))
	def compare(self, otherID):
		nameCompare= self.__stringCompare(self.__fullName, otherID.__fullName)
		if nameCompare != 0:
			return nameCompare
		versionCompare= self.compareVersions(otherID)
		if versionCompare != 0:
			return versionCompare
		hashCompare= self.__stringCompare(self.__hash, otherID.__hash)
		if hashCompare != 0:
			return hashCompare
		urlCompare= self.__stringCompare(self.__url, otherID.__url)
		if urlCompare != 0:
			return urlCompare
		pathCompare= self.__stringCompare(self.__path, otherID.__path)
		if pathCompare != 0:
			return pathCompare
		return 0
	def foundOnServer(self, server):
		if server[-1*len(bConstants.kExportsFile):] == bConstants.kExportsFile:
			server= server[:-1*len(bConstants.kExportsFile)]
		self.__url= server+"/"+self.filename()
		#print "url=",self.__url,"server=",server,"filename=",self.filename()
	def server(self):
		if not self.__url:
			return ""
		return self.__url+"/"+bConstants.kExportsFile
	def url(self):
		if not self.__url:
			return ""
		filename= self.filename()
		if not filename:
			return ""
		return self.__url+"/"+filename
	def __repr__(self):
		return "ID(fullName="+self.__fullName+",name="+self.__name+",version="+self.__version+",hash="+self.__hash+",url="+self.__url+",path="+self.__path+")"
	def path(self):
		return self.__path
	def fullName(self):
		return self.__fullName
	def version(self):
		return self.__version.replace('_', '.')
	def filenameVersion(self):
		return self.__version.replace('.', '_')
	def hash(self):
		return self.__hash
	def dependency(self):
		if self.server():
			return self.url()
		return self.filename()
	def filename(self):
		if not self.__name and self.__fullName and self.__version and self.__hash:
			return self.__fullName+"_"+self.filenameVersion()+"_"+self.__hash+".zip"
		return self.__name
	def equals(self, otherID):
		#print "equals(",self,",",otherID,")"
		if otherID.__fullName != self.__fullName:
			#print "\t", "fullname fail"
			return False
		if not self.__mergeCompare(otherID.__version.replace('_','.'), self.__version.replace('_','.')):
			#print "\t", "version fail",otherID.__version,self.__version
			return False
		if not self.__mergeCompare(otherID.__hash, self.__hash):
			#print "\t", "hash fail"
			return False
		return True
	def merge(self, otherID):
		if otherID.__fullName != self.__fullName:
			raise AssertionError("Cannot merge "+otherID.__fullName+" into "+self.__fullName)
		if otherID.__url:
			self.__url= otherID.__url
		if otherID.__path:
			self.__path= otherID.__path
		if otherID.__version:
			self.__version= otherID.__version
		if otherID.__hash:
			self.__hash= otherID.__hash
		if otherID.__name:
			self.__name= otherID.__name
