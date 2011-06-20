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

from chomikuj import Chomik
from optparse import OptionParser, OptionGroup

parser = OptionParser( usage="usage: %prog [OPTIONS]" )

parser.add_option( "-c", "--copy", dest="copy", action="store_true", help="recursivly copy directories" )
parser.add_option( "-s", "--stats", dest="stats", action="store_true", help="print user stats" )

parser.add_option( "-u", "--username", dest="username", help="chomik username" )
parser.add_option( "-p", "--password", dest="password", help="chomik password" )

parser.add_option( "-f", "--file", dest="file", help="users file" )

if __name__ == "__main__":
    ( options, args ) = parser.parse_args()
    
    chomik = Chomik( options.username, options.password )
    if options.copy:
        if chomik.connect():
            users = []
            if options.users:
                users = options.users
            else:
                users = [ u for u in open( options.file, 'r' ) ]

            for user in users:
                print chomik.copy_directory_tree( user )
    
    if options.stats:
        if chomik.connect():
            stats = chomik.get_stats()
            print " points: %s" % stats['points']
            print " files : %s" % stats['files']
            print " size  : %s" % stats['size']
            print "--------------------------"
        
# vim: fdm=marker ts=4 sw=4 sts=4
