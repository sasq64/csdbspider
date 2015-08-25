#!/usr/bin/python

import sys
import struct
import string
import socket
import re
import os
import subprocess
import shutil
import tempfile
import socket
import optparse
import exceptions
import copy
from select import *
from threading import *

from utils import *

import zipfile

import htmllib, formatter, urllib, urlparse, HTMLParser, htmlentitydefs
from BeautifulSoup import BeautifulSoup

from tools64 import unpack
from urlgetter import URLGetter


baseUrl = 'http://csdb.dk'
no_clobber = False


class Release :

	typeLetters = { 'One-File' : 'o', 'Game'  : 'e', 'Graphics Coll' : 'G', 'Graphic' : 'g', 'Demo' : 'd', 'Dentro' : 'd', 'Intro' : 'i',
	'intro' :  'i', 'Crack' : 'c', 'Music Coll' : 'M', 'Music' : 'm', 'Diskmag' : 's', 'Invit' : 'v', 'Tool' : 't',  'Misc' :'x' }

	def __init__(self, id, name = '?', group = '?', type = '?', date = '?', dls = []):
		self.id = int(id)
		self.name = name
		self.group = group
		self.date = date
		self.type = type
		self.downloads = dls
		self.rating = ''
		self.loaded = False
		self.update()
		
		
	def __repr__(self):
		name = self.name.encode('ascii', 'ignore')
		return "[" + str(self.id) + "] " + name + " (" + self.type + ")"
		
	def update(self):

		m = re.compile('.*(\d\d\d\d)').match(self.date)
		if m :
			self.year = m.group(1)
		else :
			self.year = '????'

		self.tletter = '?'
		for t in Release.typeLetters :
			if self.type.find(t) >= 0 :
				self.tletter = Release.typeLetters[t]
				break

		self.dict = {}
		for d in self.__dict__ :
			self.dict[d] = fixname(unicode(self.__dict__[d]), False)
			
		
			

	def load(self):
		doc = URLGetter(baseUrl + '/release/?id=%s' % (self.id)).getsoup()
		start = doc.find(text=re.compile('MAIN CONTENT')).parent

		anyword = re.compile('\w+')
		name = '?'
		#gid = -1
		group = '?'
		type = '?'
		rdate = '?'
		downloads = None		

		try :
			name = start.find('font').string
			release_by = start.find(text=re.compile('Release.*by'))
			ag = release_by.findNext('a')
			#gid = int(re.compile('id=(\w+)').findall(ag.attrs[0][1])[0])
			group = release_by.findNext(text=anyword)
		except :
			pass
		try :					
			type = start.find(text=re.compile('Type')).findNext(text=anyword)
			rdate = start.find(text=re.compile('Release.*ate')).findNext(text=anyword)
		except :
			pass
		try :
			downloads = start.find(text=re.compile('Download')).findNext('table').findAll(text=re.compile('tp://'))
		except :
			pass
		#print "'%s' by '%s' (%d), Release date '%s'" % (name, group, gid, rdate)


		if name != '?' :
			self.name = fixhtml(name)
		if group != '?' :
			self.group = fixhtml(group)
		if type != '?' :
			self.type = fixhtml(type)
		if rdate != '?' :
			self.date = fixhtml(rdate)
		if downloads :
			self.downloads = downloads
		self.loaded = True
		self.update()
	
	def getdict(self):
		return self.dict


	def makename(self, templ):
		st = string.Template(templ)
		s = st.safe_substitute(self.getdict())
		s = re.sub('{.*?\?+.*?}', '', s)
		return s.replace('{','').replace('}','')

	def download_from_url(self, url, targetdir, to_d64 = False, to_prg = False):
		u = URLGetter(url)			
		print "Reading from url '%s'" % u.geturl()						
		contents = u.read()
		print "Got %d bytes" % len(contents)							
		fname = fixname(os.path.basename(u.geturl()))

		filter = None
		#if to_prg and self.name and self.name != '?' :
		#	filter = fixname(self.name).lower()

		try :
			path = tempfile.mkdtemp()
			fullname = path + '/' + fname.lstrip('-')
			f = open(fullname, 'w')
			f.write(contents)
			f.close()
			print "Handling file '%s' to '%s'" % (fullname, targetdir)
			if to_d64 and to_prg :
				if 'oicgm'.find(self.tletter) >= 0 :
					unpack(fullname, targetdir, False, True, filter)
				else :
					unpack(fullname, targetdir, filter)
			else :
				unpack(fullname, targetdir, to_d64, to_prg, filter)
		#except :
		#	print "FAILED to unpack file"
		finally :
			shutil.rmtree(path)
		
		count = 0
		res = os.listdir(targetdir)
		for r in res :
			ext = os.path.splitext(r)[1].upper()
			if ext == '.PRG' or ext == '.D64' or ext == '.TAP' :
			   count += 1

		if count == 0 :
			for r in res :
				f = open(targetdir + '/' + r)
				x = f.read(2)
				if x == '\x01\x08' :
					count += 1
					os.rename(targetdir + '/' + r, targetdir + '/' + r + '.prg')

			if count == 0 :
				print "Download did not contain any C64 files."
				for r in res :
					os.remove(targetdir + '/' + r)
				raise IOError
				return
		elif count > 4 :
			print "Directory '%s' contains %d files" % (targetdir, count)		


	def download(self, to_d64 = False, to_prg = False, templ = 'DEMOS/$group/$name {- $year} {($type)}'):
		
		targetdir = self.makename(templ)
		targetdir = targetdir.replace('?', '')

		res = []
		try :
			res = os.listdir(targetdir)
		except exceptions.OSError :
			pass

		if no_clobber and len(res) > 0 :
			print "Leaving non-enpty directory alone"
			return

		success = False
		
		while not success :
			for url in self.downloads :
				try :
					self.download_from_url(url, targetdir, to_d64, to_prg)
					success = True
					break
				except Exception, e:
					print e
					print "Download failed"
					continue
				
			if not self.loaded and not success :
				self.load()
				continue
			else :
				break

class Group :
	def __init__(self, id, name, tla, rels):
		self.id = id
		self.name = name
		self.tla = tla
		self.releases = rels


class CSDBSpider :
	def __init__(self):
		pass

	@staticmethod
	def getReleases(url, max = -1, full = False):
		"Find all releases on a given URL"
		if url[:4] != 'http' :
			url = baseUrl + '/' + url
		rels = []	
		doc = URLGetter(url).getsoup()

		start = doc.find(text=re.compile('MAIN CONTENT')).parent
		if start :
			doc = start

		relp = re.compile('/release/\?id=(\d+)')
		alist = doc.findAll('a', href=relp)
		#print alist
		for a in alist :
			#print a.contents
			for at in a.attrs :
				#print at
				if at[0] == 'href' :
					m = relp.match(at[1])
					if a.contents :
						r = Release(int(m.group(1)), a.contents[0])
					else :
						r = Release(int(m.group(1)))
					if full :
						r.load()
					rels.append(r)
			if max > 0 and len(rels) >= max :
				break
		return rels
	
	@staticmethod
	def findGroups(name):
		groups = []
		print '"%s"' % (name)
		doc = URLGetter(baseUrl + '/search/?seinsel=groups&search=%s' % (name)).getsoup()
		#doc = BeautifulSoup(urllib.urlopen('http://noname.c64.org/csdb/search/?seinsel=groups&search=%s' % name))
		try :
			res = doc.ol.findAll('a')
		except :
			print 'Direct result, figuring out ID'
			r = re.compile('/csdb/group/\?id=(\d+).*votes')
			x = doc.find(href=r)
			id = int(r.findall(x.attrs[0][1])[0])
			return [(id, name)]			
			
		for r in res :
			id = int(re.compile('id=(\w+)').findall(r.attrs[0][1])[0])
			name = r.string
			groups.append((id, name))
		return groups

	@staticmethod
	def findReleases(name):
		return CSDBSpider.getReleases(baseUrl + "/search/?seinsel=releases&search=" + name +"&all=1")
	
	@staticmethod
	def getGroup(id):
		doc = URLGetter(baseUrl + '/group/?id=%s' % (id)).getsoup()
		start = doc.find(text=re.compile('MAIN CONTENT')).parent
		group = start.find('font')
		name = fixhtml(group.string.strip())
		t = re.compile('\((.*)\)').findall(group.next.next)
		tla = ''
		if t :
			tla = t[0]
		reltab = doc.body.find(text=re.compile('Releases')).findNext('table')
		alist = reltab.findAll('tr')
		releases = []
		url = ''
		for tr in alist :
			rname = '???????'
			rid = -1
			url = ''
			event = ''
			year = '?'
			type = '?'
			
			try :
				f = tr.findAll('font')
				year = f[1].string.strip()
				if len(f) >= 3 :
					type = fixhtml(f[2].string).strip()
			except :
				pass			
			
			t = tr.find('a', href=re.compile('/release/\?'))
			if t :
				rname = fixhtml(t.string).strip()
				try :
					rid = int(re.compile('id=(\w+)').findall(t.attrs[0][1])[0])
				except :
					print "Could not parse ID"
					pass
			t = tr.find('a', href=re.compile('/release/download'))
			if t :
				url = baseUrl + t.attrs[0][1]
				url = url.strip()				
			releases.append(Release(rid, rname, name, type, year, [url]))

		return Group(id, name, tla, releases)
		
		
# Main operation
# Derive a set of webpages from where to find all release links
# List or download them
# Can be - set of groups webpages
# Top demos page
# 
def main(argv) :
	
	global no_clobber
	
	csdb = CSDBSpider()
	rel = None
	group = None
	#while True:
	#line = raw_input('>')
	#line = argv
	
	p = optparse.OptionParser(usage ="usage: %prog [options] <command> [args...]\n\nCommands:\n findgrp <groupname> = Search for a group by name\n list = List releases (with filtering) for a groupid\n findrel = Find releases")
	p.add_option("-D", "--download",
				  action="store_true", dest="download", default=False,
				  help="Download matching releases")
	p.add_option("-m", "--max",
				  type="int", dest="max", action="store", default=10,
				  help="Max number of releases")
	p.add_option("-g", "--group",
				  type="int", dest="groupid", action="append",
				  help="Set the Demo group ID to use")
	p.add_option("-d", "--to-d64",
				  action="store_true", dest="to_d64", default=False,
				  help="Convert all formats to D64 (disk images)")
	p.add_option("-p", "--to-prg",
				  action="store_true", dest="to_prg", default=False,
				  help="Convert all formats to disk PRG files")
	p.add_option("-N", "--no-clobber",
				  action="store_true", dest="no_clobber", default=False,
				  help="Dont write files to non-empty directories")
	p.add_option("-T", "--template",
				  type="string", dest="template", default='DEMOS/%group/%name{ - %year}{ (%type)}',
				  help="Template for output files")
	
	p.add_option("-G", "--redo-groups",
				  action="store_true", dest="redo_groups", default=False,
				  help="Add all previously cached groups to the grouplist")
	
	p.add_option("-F", "--filter", dest="filter", default='A',help=
'''Filter out only certain types of productions - each letter in the given argument represents one type of release;
'd' = demo, 'o' = one-file demo / dentro, 'i' = intro, 'v' = invitro, 'e' = game, 'c' = crack
'm' = music, 'g' = graphics, 'M' = music collection, 'G' = graphics collection, 't' = tool, 's' = diskmag, 'x' = misc. 'A' = All!''')

	opts, arguments = p.parse_args()
	opts.template = opts.template.replace('%', '$')

	if not len(arguments) :
		print "Try `csdb --help` for more information\n\nExample:\n> csdb find horizon\n> csdb list -g 2315 -F doiv\n> csdb dl -g 2315 -F io"

	no_clobber = opts.no_clobber

#	print opts
#	print arguments

	if opts.redo_groups :
		if not opts.groupid :
			opts.groupid = []
			
		b2 = urllib.urlencode(baseUrl)		
		print b2	
		gr = re.compile(b2 + '%2Fgroup%2F%3Fid%3D(\d+)')

		res = os.listdir('urlcache')
		for r in res :
			m = gr.match(r)
			if m :
				opts.groupid.append(int(m.group(1)))


	print opts.groupid
	what = opts.filter

	rels = []
	
	#l = argv #line.split()
	l = arguments;
	if len(l) >= 1 :
		if l[0] == 'findgrp' :
			groups = csdb.findGroups(l[1])
			if groups :
				for g in groups :
					print '(%d) %s' % g
			else :
				print "Could not find any groups"
		elif l[0] == 'group' :
			if not len(opts.groupid) :
				print "You must specify a groupid!"
				return
			for gid in opts.groupid :
				#try :
					group = csdb.getGroup(gid)
					if group :		
						print 'Trying to download releases from %s' % group.name
						print "\n"
						rels.append(group.releases.sort(lambda x, y : x.year > y.year))

		elif l[0] == 'findrel' :
			print "Searching for %s" % l[1]
			rels = CSDBSpider.findReleases(l[1])

		elif l[0] == 'toplist' :
			print "Getting Release info for the Top %d" % opts.max
			rels = CSDBSpider.getReleases(baseUrl + '/toplist.php?type=release&subtype=(1%2C2)', opts.max, True)

		if rels :


			if what != 'A' :				
				for r in rels :
					r.load()
				rels = [r for r in rels if what.find(r.tletter) >= 0]

			if opts.download :
				print "\nDownloading releases"
			else :
				print "\nListing releases"
			i = 1
			for r in rels :
				r.i = "%d" % i
				r.i2 = "%02d" % i
				r.i3 = "%03d" % i
				print r
				if opts.download :
					r.update()
					r.download(opts.to_d64, opts.to_prg, templ = opts.template)
				i += 1


if __name__ == "__main__":
	main(sys.argv[1:])
