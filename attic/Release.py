
class Release :
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
		return self.name + " (" + self.type + ")"
		
	def update(self):
		
		m = re.compile('.*(\d\d\d\d)').match(self.date)
		if m :
			self.year = m.group(1)
		else :
			self.year = '????'
		type = self.type
		if type.find('One-File') >= 0 :
			self.tletter = 'o'			
		elif type.find('Game') >= 0  :
			self.tletter = 'e'
		elif type.find('Graphics Coll') >= 0 :
			self.tletter = 'G'
		elif type.find('Graphic') >= 0 :
			self.tletter = 'g'
		elif type.find('Demo') >= 0 or type.find('Dentro') >= 0 :
			self.tletter = 'd'
		elif type.find('Intro') >= 0 or type.find('intro') >= 0 : 
			self.tletter = 'i'
		elif type.find('Crack') >= 0 :
			self.tletter = 'c'
		elif type.find('Music Coll') >= 0 :
			self.tletter = 'M'
		elif type.find('Music') >= 0 :
			self.tletter = 'm'
		elif type.find('Diskmag') >= 0 :
			self.tletter = 's'
		elif type.find('Invit') >= 0 :
			self.tletter = 'v'
		elif type.find('Tool') >= 0 :
			self.tletter = 't'
		elif type.find('Misc') >= 0 :
			self.tletter = 'x'
		else :
			self.tletter = '?'
		self.dict = {}
		for d in self.__dict__ :
			self.dict[d] = fixname(unicode(self.__dict__[d]), False)
			
		
			

	def load(self):
		doc = URLGetter(baseUrl + '/release/?id=%s' % (self.id)).getsoup()
		start = doc.find(text=re.compile('MAIN CONTENT')).parent

		anyword = re.compile('\w+')
		name = '?'
		gid = -1
		group = '?'
		type = '?'
		rdate = '?'
		downloads = None		

		try :
			name = start.find('font').string
			ag = start.find(text=re.compile('Release.*by')).findNext('a')
			gid = int(re.compile('id=(\w+)').findall(ag.attrs[0][1])[0])
			group = start.find(text=re.compile('Release.*by')).findNext(text=anyword)
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
		print "'%s' by '%s' (%d), Release date '%s'" % (name, group, gid, rdate)

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

		try :
			path = tempfile.mkdtemp()
			fullname = path + '/' + fname.lstrip('-')
			f = open(fullname, 'w')
			f.write(contents)
			f.close()
			print "Handling file '%s' to '%s'" % (fullname, targetdir)
			if to_d64 and to_prg :
				if 'oicgm'.find(self.tletter) >= 0 :
					unpack(fullname, targetdir, False, True)
				else :
					unpack(fullname, targetdir)
			else :
				unpack(fullname, targetdir, to_d64, to_prg)
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
			
			
		

		#dt = self.date
		#if self.date[0] == '?' :
		#	d = u'%s (%s)' % (self.name, self.type)
		#else :
		#	d = u'%s - %s (%s)' % (self.name, self.date, self.type)
		#targetdir = 'DEMOS/%s/%s' % (fixname(self.group), fixname(d))

#		if fname :
#			try :
#				path = tempfile.mkdtemp()
#				fullname = path + '/' + fname.lstrip('-')
#				f = open(fullname, 'w')
#				f.write(contents)
#				f.close()
#				print "Handling file '%s' to '%s'" % (fullname, targetdir)
#				if to_d64 and to_prg :
#					if 'oicgm'.find(self.tletter) >= 0 :
#						unpack(fullname, targetdir, False, True)
#					else :
#					   unpack(fullname, targetdir)
#				else :
#					unpack(fullname, targetdir, to_d64, to_prg)
#			except :
#				print "FAILED to unpack file"
#			finally :
#				shutil.rmtree(path)
