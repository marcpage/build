#!/usr/bin/env python

import re
import os

# name of the build script
kBuildScriptName= "build.py"

# Name of the package file
kPackageFileName= "package.xml"

# default name of the changes file
kChangesDefaultFileName= "changes.html"

# name of the todo template file
kTodoDefaultFileName= "todo.html"

# path to the todo file template
kTodoTemplate= os.path.join("templates", kTodoDefaultFileName)

# path to default changes file template
kChangesTemplate= os.path.join('templates', kChangesDefaultFileName)

# Pattern to replace in changes file
kChangesVersionDefaultXMLPattern= "&lt;!-- Insert New Version Here --&gt;"
kChangesVersionPattern= "<!-- Insert New Version Here -->";

# path to package file template
kPackageFileTemplatePath= os.path.join('templates', kPackageFileName)

# Name of the exports list file in the export directory
kExportsFile= "exports.txt"

# Name of directory in export zip that has metadata
kExportMetaDataDir= "_._metadata_._"

# Name of directory metadata file
kMetaDataFilename= "_._metadata_._"

# Name of the manifest file in the exports
kManifestFileNameInExport= "manifest.xml"

# Name of the signature file in the exports
kSignatureFileNameInExport= "signature.xml"

# Manifest Line Pattern
kManifestLinePattern= re.compile(r"^\s*([0-9a-fA-F]+),([0-9a-fA-F]+)\s+(.*)$", re.MULTILINE)

# Manifest Directory "hashes"
kManifestDirectoryString= "[directory]"

# Manifest Directory Pattern
kManifestDirectoryPattern= re.compile(r"^\[directory\]\s+(.*)$", re.MULTILINE)

# Manifest Link "hashes"
kManifestLinkPrefix= "[link="
kManifestLinkSuffix= "]"
kManifestLinkString= kManifestLinkPrefix+"%s"+kManifestLinkSuffix

# Manifest Link Pattern
kManifestLinkPattern= re.compile(r"^\[link=(.*)\]\s+(.*)$", re.MULTILINE)

# Search these servers if there is not build on the local machine
kBootStrapServers= [
	"http://markiv/~marcp/testexports/exports.txt",
	"http://markiv/~marcp/%s/%s"%(kBuildScriptName.replace('.','_'), kExportsFile),
	"http://itscommunity.com/%s/%s"%(kBuildScriptName.replace('.','_'), kExportsFile),
]

# The order in which the build phases progress, from lowest to highest value
kBuildPhaseOrder= "dabf"

# Pattern to split on to get lines
kEndOfLinePattern= re.compile(r"(\r\n|\r|\n)")

# Used to break up the zip file name, 1 = full name (domain and name), 2= version, 3= hash
kExportNamePattern= re.compile(r"^(.*)_([0-9]+_[0-9]+_[0-9]+[%(phases)s][0-9]+)_([a-zA-Z0-9]+)\.zip$"%{'phases': kBuildPhaseOrder})

# Used to break up full name and version
kExportNameAndVersionPattern= re.compile(r"^(.*)_([0-9]+[._][0-9]+[._][0-9]+[%(phases)s][0-9]+)"%{'phases': kBuildPhaseOrder})

# The parts of a version, used to compare versions
kVersionPattern= re.compile(r"^([0-9]+)[._]([0-9]+)[._]([0-9]+)([%(phases)s])([0-9]+)$"%{'phases': kBuildPhaseOrder})

# the size of blocks to do I/O with
kReadBlockSize= 4096
