#!/usr/bin/env python

__all__ = [ 						# exported symbols from this module
	"link",							# loads DOM from string, path or file object
	"create", 						# creates a new DOM
	"appendElement",				# creates a new tag
	"appendText",					# appends text inside a tag
	"findTagByPath",				# Gets the first tag in a hierarchy
	"removeTagContents",			# Removes all elements in a tag
	"changeTagContents",			# Changes tag contents to the given text
	"setTagContentsByPath",			# Changes the tag's contents
	"extractTextFromTagContents",	# gets tag content text
	"extractTagTextByPath",			# gets tag content text by path
]

import os
import xml.dom.minidom

def link(pathOrContents):
	if isinstance(pathOrContents, basestring):
		if os.path.isfile(pathOrContents):
			return xml.dom.minidom.parse(pathOrContents)
		return xml.dom.minidom.parseString(pathOrContents)
	return xml.dom.minidom.parse(pathOrContents)

def create(docElementType):
	return xml.dom.minidom.getDOMImplementation().createDocument(None, docElementType, None)

def appendElement(intoElement, elementType, properties= None):
	element= intoElement.ownerDocument.createElement(elementType)
	if properties:
		for property in properties:
			element.setAttribute(property, properties[property])
	intoElement.appendChild(element)
	return element

def appendText(intoElement, text):
	node= intoElement.ownerDocument.createTextNode(text)
	intoElement.appendChild(node)
	return node

def findTagByPath(xml, path):
	""" returns a tag who is the first element of each path element (separated by slash (/))
		For instance:
		<document>
			<file>
				<name>test</name>
			</file>
		</document>
		findTagByPath(xml, "file/name")
		would return a tag that contains the text "test"
		note: document, the top level tag, is considered the documentElement, and ignored
		Returns None if there is nothing in the XML of that path
	"""
	element= xml.documentElement
	parts= path.split('/')
	for part in parts:
		elementList= element.getElementsByTagName(part)
		if len(elementList) == 0:
			return None
		element= elementList[0]
	return element

def removeTagContents(tagElement):
	while tagElement.hasChildNodes():
		tagElement.removeChild(tagElement.firstChild)

def changeTagContents(tagElement, newContents):
	removeTagContents(tagElement)
	appendText(tagElement, newContents)

def setTagContentsByPath(xml, path, newContents):
	""" See: findTagByPath for path explanation
		changes the contents of a tag
		NOTE: if it has sub-tags, they will be deleted also
	"""
	element= findTagByPath(xml, path)
	changeTagContents(element, newContents)

def extractTextFromTagContents(tagElement):
	""" given an XML tag element, extract all text elements from it,
		appending them into one string
	"""
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

def extractTagTextByPath(xml, path):
	""" See: findTagByPath for path explanation
		gets the containing text from a tag
		return None if path does not exist in the XML
	"""
	tag= findTagByPath(xml, path)
	if not tag:
		return None
	return extractTextFromTagContents(tag)


