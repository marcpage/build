#!/usr/bin/env python

if True: # Exports
	import os
	import bID
	import sys
	import bDOM
	import bRSA
	import stat
	import time
	import bPrefs
	import random
	import shutil
	import bExport
	import bArchive
	import bPackage
	import cStringIO
	import bConstants
	import bPythonCompress

def makeExecutable(path):
	info= os.stat(path)
	os.chmod(path, info.st_mode|stat.S_IEXEC)

def buildScriptValidate(triggerScript, sourceScript):
	if os.path.realpath(triggerScript) != os.path.realpath(sourceScript):
		theirBuildScriptFile= open(triggerScript, 'r')
		theirBuildScriptHashes= bArchive.transferAndHash(
								theirBuildScriptFile, bArchive.kAllKnownHashes,
								output= None, detectText= None, changeLineEndingsTo= None,
								blockTransferSize= bConstants.kReadBlockSize
							)[1]
		theirBuildScriptFile.close()
		ourBuildScriptFile= open(sourceScript, 'r')
		ourBuildScriptContentsCompressed= bPythonCompress.compress(ourBuildScriptFile.readline)
		#print [ourBuildScriptContentsCompressed]
		ourBuildScriptFile.close()
		ourBuildScriptHashes= bArchive.transferAndHash(
								cStringIO.StringIO(ourBuildScriptContentsCompressed), bArchive.kAllKnownHashes,
								output= None, detectText= None, changeLineEndingsTo= None,
								blockTransferSize= bConstants.kReadBlockSize
							)[1]
		#print os.path.join(buildBasePath, bConstants.kBuildScriptName),triggerScript
		#print ourBuildScriptHashes,theirBuildScriptHashes
		if not bArchive.hashListsMatch(theirBuildScriptHashes, ourBuildScriptHashes, isText= True):
			#print "Removing ",triggerScript
			os.remove(triggerScript)
			#print "Copying",sourceScript, triggerScript
			#shutil.copy2(sourceScript, triggerScript)
			triggerFile= open(triggerScript, 'w')
			triggerFile.write(ourBuildScriptContentsCompressed)
			triggerFile.close()
			makeExecutable(triggerScript)
			return False
	makeExecutable(triggerScript)
	return True

def packageValidate(packagePath, packageTemplate, buildPackage):
	if not os.path.isfile(packagePath):
		packageTemplateFile= open(packageTemplate, "r")
		defaultPackage= packageTemplateFile.read()
		packageTemplateFile.close()
		packageFile= open(packagePath, "w")
		#print "buildPackage",buildPackage
		buildID= buildPackage.asID()
		#buildID.foundOnServer(preferences['base_url'])
		#print "buildID",buildID
		foundBuildDeps= exports.get(buildID)
		#print "foundBuildDeps",foundBuildDeps
		if foundBuildDeps:
			buildDepID= foundBuildDeps[-1].dependency()
		else:
			buildDepID= "Cannot get build dependency"
		packageFile.write(defaultPackage%({
			'name': preferences['untitled'],
			'domain': preferences['domain'],
			'author': preferences['author'],
			'email': preferences['email'],
			'company': preferences['company'],
			'changes': bConstants.kChangesDefaultFileName,
			'todo': bConstants.kTodoDefaultFileName,
			'changepat': bConstants.kChangesVersionDefaultXMLPattern,
			'build_dependency': buildDepID,
		}))
		packageFile.close()
		return False
	return True

def todoValidate(package):
	if not os.path.isfile(package.todoFilePath()):
		todoTemplateFile= open(os.path.join(buildBasePath, bConstants.kTodoTemplate), 'r')
		todoFile= open(package.todoFilePath(), 'w')
		todoFile.write(todoTemplateFile.read())
		todoFile.close()
		todoTemplateFile.close()
		return False
	return True

def validateBuildDep(package, buildPackage, exports):
	needToRerun= False
	for dependency in package['dependencies']:
		if dependency.fullName() == buildPackage.asID().fullName():
			if not exports.has(buildPackage.asID()):
				needToRerun= True
		location= exports.pathTo(dependency, ensure= False)
	return not needToRerun

def changesValidate(package):
	if not os.path.isfile(package.changesFilePath()):
		changesTemplatePath= os.path.join(buildBasePath, bConstants.kChangesTemplate)
		changesTemplateFile= open(changesTemplatePath, 'r')
		defaultChanges= changesTemplateFile.read()
		changesTemplateFile.close()
		defaultChanges= defaultChanges.replace(package.changesPattern(), package.changesPattern()+"\n\n<li><b>%(version)s</b><br>\nDescription of changes here\n</li><br>\n\n"%{
			'version': package['version'],
		})
		changesFile= open(package.changesFilePath(), 'w')
		changesFile.write(defaultChanges%{
				'name': package['name'],
				'email': package['email'],
				'author': package['author'],
				'domain': package['domain'],
				'company': package['company'],
		})
		changesFile.close()
		return False
	return True

def upgrade(package, exports):
	for dependency in package['dependencies']:
		upgrades= exports.get(dependency, upgrade= True)
		#print "upgrades",upgrades
		if not upgrades:
			print "No updated dependencies found"
		else:
			print "Upgrade",dependency.fullName(),"to:"
			print "\t","(0)",dependency.version(),"(no change)"
			index= 1
			for upgrade in upgrades:
				print "\t","(%d)"%(index),upgrade.version()
				index+= 1
			while True:
				try:
					selection= raw_input("Selection (0, no change): ").strip()
					if len(selection) == 0:
						selection= 0
					else:
						selection= int(selection)
					if 0 == selection:
						print "Not upgrading",dependency.fullName()
						selection= dependency
					elif selection > 0:
						selection= upgrades[selection - 1]
					else:
						continue
					break
				except KeyboardInterrupt:
					print "Cancelled"
					sys.exit(1)
				except:
					pass
			if selection != dependency:
				print "Upgrading ",dependency.fullName(),"from",dependency.version(),"to",selection.version()
				package.upgrade(dependency, selection)
				exports.pathTo(selection, ensure= True)

"""
print "__file__=",__file__
print "__build__=",__build__
print "__script_name_no_dots__=",__script_name_no_dots__
print 'preferencesPath=',preferencesPath
print 'exportDir=',exportDir
print 'depDir=',depDir
print 'packageFilePath=',packageFilePath
print 'buildBasePath=',buildBasePath
print 'buildExportPath=',buildExportPath
"""

sourceScript= os.path.join(buildBasePath, bConstants.kBuildScriptName)
if not buildScriptValidate(__file__, sourceScript):
	print __file__+" was updated. Please re-run"
	sys.exit(1)

buildPackage= bPackage.Package(os.path.join(buildBasePath, bConstants.kPackageFileName))
preferences= bPrefs.load(preferencesPath)
exports= bExport.Store(preferences['exports'], preferences['dependencies'])
packagePath= os.path.join(__build__, bConstants.kPackageFileName)

if not packageValidate(packagePath, os.path.join(buildBasePath, bConstants.kPackageFileTemplatePath), buildPackage):
	print "Please re-run %s after updating %s"%(__file__, packagePath)
	sys.exit(1)

package= bPackage.Package(packagePath)
if not validateBuildDep(package, buildPackage, exports):
	print "Your build version was updated. Please rerun",__file__
	sys.exit(1)
changesValidate(package)
todoValidate(package)

if ((len(sys.argv) == 2) or (len(sys.argv) == 3)) and sys.argv[1] == 'export':
	(path, url)= exports.create(package, preferences)
	print "Export created:",url
	print "\t",path
elif len(sys.argv) == 2 and sys.argv[1] == "upgrade":
	upgrade(package, exports)
