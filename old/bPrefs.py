#!/usr/bin/env python

__all__ = [ # exported symbols from this module
	"load",	# load and initialize user preference file
]

import bDOM
import bRSA

def load(preferencesPath):
	prefXML= bDOM.link(preferencesPath)
	value= {
		'exports': bDOM.extractTagTextByPath(prefXML, "exports"),
		'dependencies': bDOM.extractTagTextByPath(prefXML, "dependencies"),
		'scratch': bDOM.extractTagTextByPath(prefXML, "scratch"),
		'domain': bDOM.extractTagTextByPath(prefXML, "domain"),
		'author': bDOM.extractTagTextByPath(prefXML, "author"),
		'email': bDOM.extractTagTextByPath(prefXML, "email"),
		'company': bDOM.extractTagTextByPath(prefXML, "company"),
		'untitled': bDOM.extractTagTextByPath(prefXML, "untitled"),
		'base_url': bDOM.extractTagTextByPath(prefXML, "base_url"),
	}
	keyText= bDOM.extractTagTextByPath(prefXML, "key")
	if keyText:
		value['key']= bRSA.Key(keyText)
	else:
		value['key']= bRSA.Key(-512) # large enough to hash a sha512
		bDOM.appendText(prefXML.documentElement, "\t")
		element= bDOM.appendElement(prefXML.documentElement, "key")
		bDOM.appendText(element, str(value['key']))
		bDOM.appendText(prefXML.documentElement, "\n")
		prefFile= open(preferencesPath, 'w')
		prefXML.writexml(prefFile)
		prefFile.close()
	prefXML.unlink()
	return value
