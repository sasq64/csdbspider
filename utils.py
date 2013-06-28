#!/usr/bin/python

import string
import re
import os
import htmlentitydefs


nametrans = string.maketrans('\/:*"<>|', "....'().")
nametrans = nametrans[:128] + "CueaaaaceeeiiiAAEaAooouu_OU.$Y_faiounN''" + ('.' * 24) + 'AAAAAAACEEEEIIIIDNOOOOOx0UUUUYdBaaaaaaaceeeeiiiidnooooo+ouuuuyDy'

def fixname(s, removeDots = True):
	ss = s.encode('iso8859_2', 'ignore')		
	if removeDots :		
		x = string.translate(ss, nametrans, '?')
		while x and len(x) and (x[-1] == '.' or x[-1] == ' ') :
			x = x[:-1]
	else :
			x = string.translate(ss, nametrans)
	return x


def dospath(x):
	return x.replace('/cygdrive/c', 'c:').replace('/', '\\')

def convertentity(m):
	"""Convert a HTML entity into normal string (ISO-8859-1)"""
	if m.group(1)=='#':
		try:
			return unichr(int(m.group(2)))
		except ValueError:
			return unicode('&#%s;' % m.group(2))
	try:
		i = htmlentitydefs.name2codepoint[m.group(2)]
		if i == 160 :
			i = 32
		return unichr(i)
	except KeyError:
		return unicode('&%s;' % m.group(2))

				
def fixhtml(s):
	x = re.sub(r'&(#?)(.+?);', convertentity, unicode(s))
	return x

def fat32names(dirname) :
	for f in os.listdir(dirname) :
		fixed = fixname(f)
		if f != fixed :
			os.rename(dirname + '/' + f, dirname + '/' + fixed)
			f = fixed
		fullname = dirname + '/' + f
		if os.path.isdir(fullname) :
			fat32names(fullname)
