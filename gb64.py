#!/usr/bin/python

import csv
import sys
import string

from cbmtools import d64
from cbmtools import convert

def csv2dict(name):
	reader = csv.reader(open(name))
	reader.next()
	dict = {}
	for g in reader :
		dict[int(g[0])] = g[1]
	return dict
	

def gamescore(d, ex):
	score = 0
	if int(d['Extras']) != 0 :
		score += 1000
	#print "     ### " + d['LA_Id']
	if langs[int(d['LA_Id'])].find('nglish') >= 0 :
		score += 10000
	score += int(d['V_Length'])
	if not len(d['Filename']) :
		score = -1
	return score


def main(argv) :

	genres = csv2dict('Genres.csv')
	langs = csv2dict('Languages.csv')	
	years = csv2dict('Years.csv')

	#gbpath = '/cygdrive/c/c64/gamebase64/Games/'
	#gbpath = '/cygdrive/c/EMU/GB64/Games/'
	gbpath = '/home/sasq/c64/Games/'
	st = string.Template('GAMES/$Letter/$Name ($Year)')

	
	# For each letter of the alphabet, count how many game names starts with it
	fileCount = {}
	totalCount = {}
	dirCount = {}
	reader = csv.DictReader(open('Games.csv'))
	reader.next()	
	for r in reader :
		#if len(r['Filename']) :	
		if len(r['Filename']) and langs[int(r['LA_Id'])].find('nglish') >= 0 :
			n = r['Name'][0].upper()
			if n.isdigit() :
				n = '0'
			elif not n.isalpha() :
				n = '!'
			if not fileCount.has_key(n) :
				fileCount[n] = 1
				totalCount[n] = 0
				dirCount[n] = 0
			else :
				fileCount[n] += 1

	# Maximum number of files in each directory
	max_files = 256
	
	reader = csv.DictReader(open('Games.csv'))
	reader.next()
	exreader = csv.reader(open('Extras.csv'))
	exreader.next()
	
	count = 0
	
	lastname = None
	same = []
	
	extra = exreader.next()
	
	for r in reader :
		
		extras = []
		#print extra
		while int(extra[1]) == int(r['GA_Id']) :			
			extras.append(extra)
			extra = exreader.next()
		
		if True :		
		#if r['Name'][0] == 'A' : #.find('Arc') >= 0 : #lastname and lastname != r['Name'] :
			#realse = {}
			#max_score = 0
			#if len(same) > 1 :
			#	for se in same :
			#		score = gamescore(se[0], se[1])			
			#		if score > max_score :
			#			realse = se
			#			max_score = score
			#	d = realse[0]								
			#	ex = realse[1]
			#else :
			#	d = same[0][0]
			#	ex = same[0][1]
			
			d = r			

			if len(d['Filename']) and langs[int(d['LA_Id'])].find('nglish') >= 0 :
				name = d['Name']
				d['Name'] = convert.fixname(name)
				d['Genre'] = convert.fixname(genres[int(r['GE_Id'])])
				d['Language'] = convert.fixname(langs[int(r['LA_Id'])])
				year = int(years[int(r['YE_Id'])])
				if year > 9900 :
					d['Year'] = '19xx'
				else :
					d['Year'] = year
				if name[0].isdigit() :
					d['Letter'] = '0'
				elif name[0].isalpha() :
					d['Letter'] = d['Name'][0].upper()
				else :
					d['Letter'] = '!'
				
				if totalCount[d['Letter']] >= max_files :
					totalCount[d['Letter']] = 0
					dirCount[d['Letter']] += 1
				totalCount[d['Letter']] += 1

			
				if fileCount[d['Letter']] >= max_files :
					d['Letter'] += str(dirCount[d['Letter']])
				
				targetdir = st.safe_substitute(d)
				print targetdir
				filename = d['Filename'].replace('\\', '/')
				#try :
				print "Looking for " + gbpath + filename
				convert.unpack(gbpath + filename, targetdir)
				#except :
				#	print "Could not unpack file"
			else :
				print "## Rejected " + d['Name']	
									
			count += 1
			if count % 100 == 0 :
				print count
			#if count == 500 :
			#	break
			same = []

		#lastname = r['Name']
		#same.append((r,extras))
			



if __name__ == "__main__":
	main(sys.argv[1:])
