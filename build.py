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

def __init(environment):
	basename= os.path.splitext(os.path.split(__file__)[1][0]
	if os.name == kPOSIXOSName and os.uname()[0] == kDarwinOSUName:
		environment.update({
			'basename': basename,
			'pref_path': os.path.join(os.environ['HOME'], "Library", "Preferences", basename+".xml"),
			'export_path': os.path.join(os.environ['HOME'], "Sites", basename),
			'export_url': "".join((
				"http://",socket.gethostname(),"/~",getpass.getuser(),"/",basename
			)),
			'scratch_path': os.path.join(os.environ['HOME'], "Library", "Caches", basename+"_scratch"),
			'dependencies_path': os.path.join(os.environ['HOME'], "Library", "Caches", basename),
			'operating_system': 'mac',
			'start_script': __file__,
			'start_script_name': os.path.split(__file__)[1],
		})
	else:
		raise AssertionError("This OS needs some values supported")

if __name__ == "__main__":
	__init(gEnvironment)
	if not os.path.isfile(gEnvironment['pref_path']):
		prefFile= open(gEnvironment['pref_path'], "w")
		prefFile.write(kDefaultPreferences%({
			'export': gEnvironment['export_path'],
			'dependencies': gEnvironment['dependencies_path'],
			'scratch': gEnvironment['scratch_path'],
			'url': gEnvironment['export_url'],
		}))
		prefFile.close()
		print "Please re-run %s after updating %s"%(gEnvironment['start_script_name'], gEnvironment['pref_path'])
		sys.exit(1)

