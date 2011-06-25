def findNewerVersions(names, urls, dependencyMap, server= None):
	""" TODO: Document
	"""
	for name in names:
		nameParts= kExportNamePattern.match(name)
		fullName= nameParts.group(1)
		version= nameParts.group(2).replace('_', '.')
		hash= nameParts.group(3)
		if dependencyMap.has_key(fullName):
			versions= dependencyMap[fullName].keys()
			versions.sort(lambda x,y: compareVersions(x,y))
			if version not in versions and compareVersions(versions[0], version) < 0:
				if server:
					lastSlash= server.rfind('/')
					serverBase= server[:lastSlash + 1]
					url= serverBase+name
				else:
					url= name
				for someURL in urls: # prefer to use a URL version specified
					if someURL.find(name) > 0:
						url= someURL
						break
				dependencyMap[fullName][version]= url

def upgrade(verbose, package, preferences, autoYes):
	""" TODO: Document
	"""
	dependencyMap= {}
	servers= []
	for dependency in package['dependencies']:
		url= dependency['url']
		identifier= dependency['id']
		version= dependency['version']
		server= dependency['server']
		fullName= dependency['full_name']
		if not url:
			url= identifier
		if server and server not in servers:
			servers.append(server)
		dependencyMap[fullName]= {version: url}
	(names, urls, servers)= parseLocalExports(preferences['directories']['exports'])
	findNewerVersions(names, urls, dependencyMap) # get upgrades on local machine
	for server in servers: # get upgrades on servers listed in the local exports.txt
		(names, urls, servers)= parseServerExports(server)
		findNewerVersions(names, urls, dependencyMap, server)
	dependencies= dependencyMap.keys()
	# thin out dependencies that have no upgrades
	for dependency in dependencies:
		if len(dependencyMap[dependency].keys()) <= 1:
			dependencies.remove(dependency)
	upgrades= {}
	if len(dependencies) > 0:
		dependencies.sort()
		for dependency in dependencies:
			if verbose:
				print "Evaluating: "+dependency
			versions= dependencyMap[dependency].keys()
			versions.sort(lambda x,y: compareVersions(x,y))
			firstParts= kVersionPattern.match(versions[0])
			if verbose:
				print "Current version: '%s'"%(versions[0])
				if not firstParts:
					print "\t BAD VERSION! "+kVersionPattern.pattern
			suggestedIndex= 0
			for index in range(1, len(versions)):
				secondParts= kVersionPattern.match(versions[index])
				if verbose:
					print "version: '%s'"%(versions[index])
					if not secondParts:
						print "\t BAD VERSION! "+kVersionPattern.pattern
				majorVersionsMatch= firstParts.group(1) == secondParts.group(1)
				minorVersionsMatch= firstParts.group(2) == secondParts.group(2)
				if not majorVersionsMatch or not minorVersionsMatch:
					# major version and minor version do not match, we're done
					break
				suggestedIndex= index
			print "There are newer versions of "+dependency
			for index in range(0, len(versions)):
				url= dependencyMap[dependency][versions[index]]
				if 0 == index:
					comment= " (current)"
				else:
					comment= ""
				print "%d. %s%s (%s)"%(index, versions[index].replace('_', '.'), comment, url)
			if not autoYes:
				result= raw_input("Which version to use (%d):"%(suggestedIndex))
			try:
				result= int(result)
			except:
				result= suggestedIndex # used default, no action
			if result > 0 and result < len(versions):
				upgrades[dependency]= dependencyMap[dependency][versions[result]]
	if len(upgrades.keys()) > 0:
		packageDOM= xml.dom.minidom.parse(package['path'])
		dependencies= findTagByPath(packageDOM, "dependencies")
		for dependencyTag in dependencies.getElementsByTagName("dependency"):
			dependency=extractTextFromTagContents(dependencyTag)
			(name, url, server)= parseExport(dependency)
			nameParts= kExportNamePattern.match(name)
			fullName= nameParts.group(1)
			version= nameParts.group(2).replace('_', '.')
			hash= nameParts.group(3)
			if upgrades.has_key(fullName):
				print "Upgrading %s:"%(fullName)
				print "\t From: "+dependency
				print "\t To:   "+upgrades[fullName]
				while dependencyTag.hasChildNodes():
					dependencyTag.removeChild(dependencyTag.firstChild)
				textNode= packageDOM.createTextNode(upgrades[fullName])
				dependencyTag.appendChild(textNode)
		packageFile= open(package['path'], "w")
		packageDOM.writexml(packageFile)
		packageFile.close()
		packageDOM.unlink()
