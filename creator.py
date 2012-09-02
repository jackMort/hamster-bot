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

import os
import sys
import time

from optparse import OptionParser, OptionGroup
from chomikuj import Chomik, CaptchNeededException

parser = OptionParser( usage="usage: %prog [OPTIONS]" )

parser.add_option( "-c", "--copy", dest="copy", action="store_true", help="recursivly copy directories" )
parser.add_option( "-m", "--mkdir", dest="mkdir", help="mkdir" )
parser.add_option( "-r", "--rmdir", dest="rmdir", help="remove directory" )
parser.add_option( "-s", "--stats", dest="stats", action="store_true", help="print user stats" )
parser.add_option( "-i", "--invite", dest="invite", action="store_true", help="invite users" )
parser.add_option( "-g", "--generate", dest="generate_list", help="generate users list" )
parser.add_option( "-x", "--send-message", dest="send_message", help="send chat message" )
parser.add_option( "-d", "--download", dest="download", help="download file from given directory" )

parser.add_option( "-u", "--username", dest="username", help="chomik username" )
parser.add_option( "-p", "--password", dest="password", help="chomik password" )

parser.add_option( "-f", "--file", dest="file", help="users file" )
parser.add_option( "-b", "--users", dest="users", help="list of users" )
parser.add_option( "-t", "--timeout", dest="timeout", help="timeout in secs" )

if __name__ == "__main__":
    ( options, args ) = parser.parse_args()
    
    chomik = Chomik( options.username, options.password )
    chomik.connect()
    print chomik.transfer( 'jackMort' )
    
    #chomik.search( "Drop Zone (1994)" )
# vim: fdm=marker ts=4 sw=4 sts=4
