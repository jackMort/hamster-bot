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

import json
import guessit
from tools.imghus import Imghus
from tools.filmweb import Filmweb

DESCRIPTION = """<img src="%s" alt="" style="float:left;margin:3px;margin-right:10px;width:200px;" /><div style="padding:5px;"><h3>%s (%s)</h3>%s<a href="%s" rel="nofollow">%s</a>
"""
DESCRIPTION = """<div style="padding-left:10px;"><img src="%s" alt="" style="float:right;width:200px;margin:10px;" /><div style="padding:5px;"><h3>%s (%s)</h3><h4>%s</h4>%s<a style="clear:both" href="%s" rel="nofollow">%s</a></div></div>"""

def set_description( chomik ):
    file = open( 'description.html', 'r' )
    description = file.read()
    file.close()

    file = open( 'index.json', 'r' )
    json = file.read()
    file.close()
    
    print "setting description ..."
    description = description.replace( '{{INDEX_PLACE}}', json )
    chomik.editDescription( description )

def get_genres( genres, chomik ):
    out = []
    for g in genres:
        id, direct_url = chomik.create_directory( "/Filmy/Wg. Gatunku/%s" % g )
        out.append( '<a href="%s#folderContentContainer">%s</a>' % ( direct_url, g ) )
    return ', '.join( out )


def set_gen_description__( film, chomik, g ):
    try:
        rows = json.loads( open( 'genres/%s.json' % g, 'r' ).read() )
    except:
        rows = []
    
    row = '<li style="clear:both; padding: 7px 0;"><a href="%s"><img src="http://src.sencha.io/%s" width="25" height="25" style="border: 1px solid black; float: left; margin: -3px 0;margin-right: 5px;"/> %s</a></li>' % ( film['direct_url'] + '#folderContentContainer', film['thumb'], film['title'] )
    if not row in rows:
        rows.append( row )

        year = None
        try:
            year = int( g )
        except: pass
        is_year = year is not None

        pages = list( getrows_byslice( rows, 25 ) )
        print len( rows ), len( pages )

        if is_year:
           parent = "/Filmy/Chronologicznie/%s" % g
           parent_description = '<h3>Filmy wyprodukowane w <u>%s</u> roku</h3><p>FILMÓW: <b>%s</b></p>' % ( g, len( rows ) )
        else:
           parent = "/Filmy/Wg. Gatunku/%s" % g
           parent_description = '<h3>Filmy w kategorii <u>%s</u></h3><p>FILMÓW: <b>%s</b></p>' % ( g, len( rows ) )

        chomik.set_folder_description( parent, parent_description )
        start = 1
        end = 0
        for i, page in enumerate( pages ):
            end += 25
            if i+1 == len( pages ):
                description = """<ol style="padding-left: 50px" start="%d">%s</ol>""" % ( start, ''.join( page ) )
                chomik.set_folder_description( '%s/%s' % ( parent, '%d - %d' % ( start, end ) ), description ) 
            start += 25

    f = open( 'genres/%s.json' % g, 'w' )
    f.write( json.dumps( rows ) )
    f.close()

def getrows_byslice(seq, rowlen):
    for start in xrange(0, len(seq), rowlen):
        yield seq[start:start+rowlen]

def set_gen_description( film, chomik ):
    for g in film['genres']:
        set_gen_description__( film, chomik, g )
    
    set_gen_description__( film, chomik, film['year'] )

if __name__ == "__main__":
    ( options, args ) = parser.parse_args()
    
    chomik = Chomik( options.username, options.password )
    chomik.connect()

    index = json.loads( open( 'index.json', 'r' ).read() )
    #index2 = []
    #for it in index:
    #    index2.append( [ it[0], it[1].replace( '/Alfabetycznie', '/Filmy' ), it[2] ] )
    #f = open( 'index.json', 'w' )
    #f.write( json.dumps( index2 ) )
    #f.close()
    #set_description( chomik )

    fw = Filmweb()
    for page in range( 300, 350 ):
        print "------------------------------------------ ", page
        films = fw.get_films(page=page)

        for film in films:
            try:
                title = film['title']#.encode( 'latin1' )
                desc  = film['description']
                genres = get_genres( film['genres'], chomik )
                director  = film['director']
                cast  = film['cast']
                year = film['year']
                title_year = '%s %s' % ( title, year )
                FIRST_LETTER = title[0].upper()
                img ='http://src.sencha.io/%s' % film['img'] #imghus.upload( film['img'] )

                print "---", title, desc, genres

                url = "/Filmy/Alfabetycznie/%s/%s" % ( FIRST_LETTER, title )
                _, direct_url = chomik.check_directory( url )
                film['direct_url'] = direct_url

                description = DESCRIPTION % ( img, title, year, genres, desc, film['url'], film['url'] )

                if direct_url:
                    index_row = [ '%s (%s)' % (title,year), direct_url, film['thumb'] ]
                    chomik.set_folder_description( url, description )
                    set_gen_description( film, chomik )

                else:
                    _, direct_url = chomik.create_directory( url )
                    film['direct_url'] = direct_url
                    set_gen_description( film, chomik )

                    chomik.set_folder_description( url, description )

                    index_row = [ '%s (%s)' % (title,year), direct_url, film['thumb'] ]


                    mkvs = chomik.search( title_year, limit_pages=1, Extension='mkv' )
                    avis = chomik.search( title_year, limit_pages=1, Extension='avi' )
                    rmvb = chomik.search( title_year, limit_pages=1, Extension='rmvb' )
                    gps3 = chomik.search( title_year, limit_pages=1, Extension='3gp' )

                    sizes = []
                    containers = { 'avi': 0, 'mkv': 0, 'rmvb': 0, '3gp': 0 }
                    for arr in ( mkvs, avis, rmvb, gps3 ):
                        for movie in arr:
                            meta = guessit.guess_movie_info( movie['full_name'] )
                            if not meta.has_key( 'cdNumber' ) and ( meta.has_key( 'container' ) or meta.has_key( 'extension' ) ):
                                if meta.has_key( 'container' ):
                                    type = meta['container']
                                else:
                                    type = meta['extension']

                                if not movie['size'] in sizes and containers[type] < 3:
                                    folder_id, _ = chomik.create_directory( '%s/%s/' % ( url, type ) )
                                    if chomik.clone( movie['id'], folder_id ):
                                        print meta
                                        print "--------------------- 0K"
                                        containers[type] += 1
                                        sizes.append( movie['size'] )

                if not index_row in index:
                    index.append( index_row )
                    f = open( 'index.json', 'w' )
                    f.write( json.dumps( index ) )
                    f.close()
            
                    set_description( chomik )

            except Exception, e:
                f = open( 'errors.txt', 'a' )
                f.write( '%s -- %s' % ( film, e ) )
                f.close()
                print "Upps exception:", e, "going sleep ..."
                time.sleep( 60 )

#
# is_ok = False
#    for file in os.listdir( 'genres' ):
#        if file.endswith( '.json' ):
#            print "--",file
#            genre = file.replace( '.json', '' )
#            if genre == 'Komedia':
#                is_ok = True
#            if is_ok:
#                year = None
#                try:
#                    year = int( genre )
#                except: pass
#                is_year = year is not None
#                    
#                print genre, is_year
#                f = open( 'genres/%s.json' % genre, 'r' )
#                rows = json.loads( f.read() )
#                f.close()
#                
#                pages = list( getrows_byslice( rows, 25 ) )
#                print len( rows ), len( pages )
#
#                if is_year:
#                    parent = "/Filmy/Chronologicznie/%s" % genre
#                    parent_description = '<h3>Filmy wyprodukowane w <u>%s</u> roku</h3><p>FILMÓW: <b>%s</b></p>' % ( genre, len( rows ) )
#                else:
#                    parent = "/Filmy/Wg. Gatunku/%s" % genre
#                    parent_description = '<h3>Filmy w kategorii <u>%s</u></h3><p>FILMÓW: <b>%s</b></p>' % ( genre, len( rows ) )
#
#                chomik.set_folder_description( parent, parent_description )
#                start = 1
#                end = 0
#                for i, page in enumerate( pages ):
#                    end += 25
#                    description = """<ol style="padding-left: 50px" start="%d">%s</ol>""" % ( start, ''.join( page ) )
#                    chomik.set_folder_description( '%s/%s' % ( parent, '%d - %d' % ( start, end ) ), description ) 
#                    start += 25

#    sys.exit(1)


# vim: fdm=marker ts=4 sw=4 sts=4
