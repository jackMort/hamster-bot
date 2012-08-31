#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (C) 2011  lech.twarog@gmail.com
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import bbfreeze
import shutil
import os

f=bbfreeze.Freezer("Hamster Bot 2.0", 
    includes=(
		"platform",
		"logging","logging.handlers", 
		"glob", 
		"ctypes", "ctypes.*", "ctypes.wintypes.*", 
		"pdb", 
		"HTMLParser", 
		"inspect",
		"robotparser",
		"xml.sax",
		"scipy.sparse.csgraph.*",
	), 
    excludes=())
f.addScript("server.py")
f.addScript("tools/captcha.py")
distdir = f.distdir
f()

os.mkdir( os.path.join( distdir, "logs" ) )
os.mkdir( os.path.join( distdir, "resources" ) )
shutil.copyfile( os.path.join( os.getcwd(), "db/chomik.db" ), os.path.join( distdir, "chomik.db" ) )
#shutil.copytree(os.path.join(os.getcwd(), "bauk"), os.path.join(distdir, "bauk"))
#shutil.copytree(os.path.join(os.getcwd(), "liblouis"), os.path.join(distdir, "liblouis"))

