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

def sleep( timeout ):
    timeout = int( timeout )
    print "   -- going sleep for %d secs." % timeout
    time.sleep( timeout )

def user_done( type, username, user ):
    try:
        return user in [ u.strip() for u in open( "db/%s_%s.dat" % ( username, type ), 'r' ) ]
    except Exception:
        return False

def add_user_to_done( type, username, user ):
    if not os.path.isdir( 'db' ):
        os.mkdir( 'db' )

    f = open( "db/%s_%s.dat" % ( username, type ), 'a' )
    f.write( '%s\n' % user )
    f.close()

def query_number( question, default=0 ):
    prompt = " [%s] " % default
    while 1:
        sys.stdout.write( question + prompt )
        choice = raw_input().lower()
        if default is not None and choice == '':
            return default

        elif choice:
            return int( choice )

        else:
            sys.stdout.write( "Please select the number.\n" )


def query_yes_no_quit(question, default="yes"):
    """Ask a yes/no/quit question via raw_input() and return their answer.
    
    "question" is a string that is presented to the user.
    "default" is the presumed answer if the user just hits <Enter>.
        It must be "yes" (the default), "no", "quit" or None (meaning
        an answer is required of the user).

    The "answer" return value is one of "yes", "no" or "quit".
    """
    valid = {"yes":"yes",   "y":"yes",    "ye":"yes",
             "no":"no",     "n":"no",
             "quit":"quit", "qui":"quit", "qu":"quit", "q":"quit"}
    if default == None:
        prompt = " [y/n/q] "
    elif default == "yes":
        prompt = " [Y/n/q] "
    elif default == "no":
        prompt = " [y/N/q] "
    elif default == "quit":
        prompt = " [y/n/Q] "
    else:
        raise ValueError("invalid default answer: '%s'" % default)

    while 1:
        sys.stdout.write(question + prompt)
        choice = raw_input().lower()
        if default is not None and choice == '':
            return default
        elif choice in valid.keys():
            return valid[choice]
        else:
            sys.stdout.write("Please respond with 'yes', 'no' or 'quit'.\n")

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
    if options.copy:
        if chomik.connect():
            users = []
            if options.users:
                users = options.users
            else:
                users = [ u.strip() for u in open( options.file, 'r' ) ]

            for user in users:
                print chomik.copy_directory_tree( user )
                if options.timeout:
                    sleep( options.timeout )

    if options.invite:
        if chomik.connect():
            users = []
            if options.users:
                users = options.users
            else:
                users = [ u.strip() for u in open( options.file, 'r' ) ]

            for user in users:
                if not user_done( 'invite', options.username, user ):
                    chomik.invite( user )
                    add_user_to_done( 'invite', options.username, user )
                    if options.timeout:
                        sleep( options.timeout )

                else:
                   print " -- skipping user %s, already processed" % user

    if options.send_message:
        if chomik.connect():
            users = []
            if options.users:
                users = options.users
            else:
                users = [ u.strip() for u in open( options.file, 'r' ) ]

            for user in users:
                do_this = True
                while do_this:
                    try:
                        if not user_done( 'send_message', options.username, user ):
                            message = open( options.send_message, 'r' ).read()
                            chomik.send_chat_message( user, message )
                            add_user_to_done( 'send_message', options.username, user )
                            if options.timeout:
                                sleep( options.timeout )
                        else:
                            print " -- skipping user %s, already processed" % user

                        do_this = False

                    except CaptchNeededException:
                        if query_yes_no_quit( "   -- WRITE CAPTCHA AND TRY AGAIN, continue ?" ) <> 'yes':
                            sys.exit( 1 )

    if options.download:
        if chomik.connect():
            directory = options.download
            do_this = True
            while do_this:
                print " -- Reading directory %s" % directory
                do_this = False
                result = chomik.read_directory( directory )
                len_folders = len( result['folders'] )
                len_files = len( result['files'] )
                if  len_folders + len_files == 0:
                    print "directory contains 0 folders and 0 files ..."
                else:
                    i = 0
                    tmp_dict = {}
                    print " :: %d folders" % len_folders
                    for item in result['folders']:
                        i += 1
                        tmp_dict[i] = {
                            'type': 'folder',
                            'href': item[1]
                        }
                        print "[%d]  + %s ( %s )" % ( i, item[0], item[1] )

                    print " :: %d files" % len_files
                    for item in result['files']:
                        i += 1
                        tmp_dict[i] = {
                            'type': 'file',
                            'id': item[2],
                            'name': item[0]
                        }
                        print "[%d]  + %s ( %s )" % ( i, item[0], item[2] )

                    result = query_number( "Select a number of item ( 0 to download all files )" )
                    if result == 0:
                        print " -- downloading all files %d" % len_files
                        for key, item in tmp_dict.items():
                            if item['type'] == 'file':
                               print " -- downloading file %s" % item['name']
                               chomik.download_file_by_id( item['id'] )

                    elif tmp_dict.has_key( result ):
                        item = tmp_dict[result]
                        if item['type'] == 'file':
                            print " -- downloading file %s" % item['name']
                            chomik.download_file_by_id( item['id'] )
                        else:
                            do_this = True
                            directory = item['href']
                    else:
                        print "Bad choice ..."

    if options.stats:
        if chomik.connect():
            stats = chomik.get_stats()
            print " points: %s" % stats['points']
            print " size  : %s" % stats['size']
            print " files : %s" % stats['files']
            print "  - docs  : %s" % stats['docs']
            print "  - images: %s" % stats['images']
            print "  - video : %s" % stats['video']
            print "  - music : %s" % stats['music']
            print "--------------------------"
        else:
            print "Not connected ..."

    if options.mkdir:
        if chomik.connect():
            print chomik.create_directory( options.mkdir )

    if options.rmdir:
        if chomik.connect():
            print chomik.remove_directory( options.rmdir )

    if options.generate_list:
        chomik.generate_list( count=int( options.generate_list ) )

# vim: fdm=marker ts=4 sw=4 sts=4
