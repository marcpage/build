#!/usr/bin/env python

__all__= [ # exported items
	"compress",	# compresses some types of python code
]

import re
import sys
import tokenize

kTokenNames= ['ENDMARKER', 'NAME', 'NUMBER', 'STRING', 'NEWLINE', 'INDENT', 'DEDENT', 'LPAR', 'RPAR', 'LSQB', 'RSQB', 'COLON', 'COMMA', 'SEMI', 'PLUS', 'MINUS', 'STAR', 'SLASH', 'VBAR', 'AMPER', 'LESS', 'GREATER', 'EQUAL', 'DOT', 'PERCENT', 'BACKQUOTE', 'LBRACE', 'RBRACE', 'EQEQUAL', 'NOTEQUAL', 'LESSEQUAL', 'GREATEREQUAL', 'TILDE', 'CIRCUMFLEX', 'LEFTSHIFT', 'RIGHTSHIFT', 'DOUBLESTAR', 'PLUSEQUAL', 'MINEQUAL', 'STAREQUAL', 'SLASHEQUAL', 'PERCENTEQUAL', 'AMPEREQUAL', 'VBAREQUAL', 'CIRCUMFLEXEQUAL', 'LEFTSHIFTEQUAL', 'RIGHTSHIFTEQUAL', 'DOUBLESTAREQUAL', 'DOUBLESLASH', 'DOUBLESLASHEQUAL', 'AT', 'OP', 'ERRORTOKEN', 'COMMENT', 'NL', 'N_TOKENS']
kTokenNames.extend(["[UNKNOWN]"]*(tokenize.NT_OFFSET - len(kTokenNames)))
kTokenNames.append('NT_OFFSET')
kNothingTokens= [tokenize.NL, tokenize.COMMENT]

def mutalateLine(lineOfTokens, mapping):
	for index in range(0, len(lineOfTokens)):
		token= lineOfTokens[index]
		if token[0] == tokenize.NAME and mapping.has_key(token[1]):
			lineOfTokens[index]= (tokenize.NAME, mapping[token[1]])
	return lineOfTokens

kVariableCharacters= "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
kVariableCharactersCount= len(kVariableCharacters)
def variableName(map, name):
	if len(name) <= 3:
		return name
	if not map.has_key(name):
		index= len(map)
		if index == 0:
			value= kVariableCharacters[0]
		else:
			value= ""
			while index > 0:
				value+= kVariableCharacters[index % kVariableCharactersCount]
				index= index / kVariableCharactersCount
		map[name]= "_"+value
	return map[name]

def updateStatement(map, statement):
	firstItemIsName= len(statement) > 1 and statement[0][0] == tokenize.NAME
	secondItemIsAssignment= len(statement) > 2 and statement[1][0] == tokenize.OP and statement[1][1] == "="
	isVariableAssignment= firstItemIsName and secondItemIsAssignment
	if len(statement) == 2 and statement[0][1] == "import" and len(statement[1][1]) > 3:
		statement.extend( [(tokenize.NAME, "as"), (tokenize.NAME, variableName(map, statement[1][1]))] )
		# handle module names
		if statement[1][1] not in map['']:
			map[''].append(statement[1][1])
	elif isVariableAssignment and len(statement[0][1]) > 3:
		statement[0]= (tokenize.NAME, variableName(map, statement[0][1]))
	outStatement= []
	for index in range(0, len(statement)):
		element= statement[index]
		if element[0] == tokenize.NAME and map.has_key(element[1]):
			noDotBefore= index == 0 or statement[index - 1][1] != '.'
			dotAfter= index +1 < len(statement) and statement[index + 1][1] == '.'
			notDotAfter= index +1 >= len(statement) or statement[index + 1][1] == '.'
			isModuleName= element[1] in map['']
			if noDotBefore and (dotAfter or not isModuleName):
				element= (tokenize.NAME, map[element[1]])
		outStatement.append(element)
	return outStatement

def compress(readliner):
	nameIndex= 0
	map= {
		'': [],		# module list
	}
	tokens= []
	statement= None
	firstToken= True
	forceNextToken= False
	for token in tokenize.generate_tokens(readliner):
		#print kTokenNames[token[0]],token[1:]
		isShebang= firstToken and tokenize.COMMENT == token[0] and token[1][:2] == "#!"
		if forceNextToken or isShebang:
			tokens.append( (token[0], token[1]) )
			forceNextToken= isShebang
			firstToken= False
			continue
		if token[0] in kNothingTokens:
			continue
		if None == statement:
			statement= [ (token[0], token[1]) ]
		elif tokenize.NEWLINE == token[0]:
			tokens.extend(updateStatement(map, statement))
			statement= None
			tokens.append( (token[0], token[1]) )
		else:
			statement.append( (token[0], token[1]) )
	#print tokens
	return tokenize.untokenize(tokens)

if __name__ == "__main__":
	sys.stdout.write(compress(open(sys.argv[1],'r').readline))
