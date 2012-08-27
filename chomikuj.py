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

import sys
reload( sys )
sys.setdefaultencoding( 'utf-8' )

import os
import re
import time
import string
import random
import urllib
import urllib2
import logging
from mechanize import Browser, LinkNotFoundError, HTMLForm
from BeautifulSoup import BeautifulSoup

#logger = logging.getLogger( 'mechanize' )
#logger.addHandler( logging.StreamHandler( sys.stderr ) )
#logger.setLevel( logging.DEBUG )

HTML_TAGS_PATTERN = re.compile( r'<.*?>' )
WHITE_SPACES_PATTERN = re.compile( r'\s+' )

def clean_html( text ):
    return HTML_TAGS_PATTERN.sub( '', str( text ) )

def convert_to_bytes( string ):
    print string

def convert_bytes( mbytes ):
    bytes = float( mbytes ) * 1048576
    if bytes >= 1099511627776:
        terabytes = bytes / 1099511627776
        size = '%.2fT' % terabytes
    elif bytes >= 1073741824:
        gigabytes = bytes / 1073741824
        size = '%.2fG' % gigabytes
    elif bytes >= 1048576:
        megabytes = bytes / 1048576
        size = '%.2fM' % megabytes
    elif bytes >= 1024:
        kilobytes = bytes / 1024
        size = '%.2fK' % kilobytes
    else:
        size = '%.2fb' % bytes

    return size

class CaptchNeededException( Exception ):
    pass

class Chomik:
    def __init__( self, name, password ):
        self.name = name
        self.password = password
        self.browser = Browser()
        self.browser.set_handle_robots( False )
        self._cached_directories = {}

    def connect( self ):
        self.browser.open( "http://chomikuj.pl" )
        self.browser.select_form( nr=0 )
        self.browser["Login"] = self.name
        self.browser["Password"] = self.password

        response = self.browser.submit()
        matcher = re.search( 'Pliki użytkownika (.*) - Chomikuj.pl', self.browser.title() )
        if matcher:
            self.chomik_name = matcher.group( 1 )
            matcher = re.search( '<input id="__accno" name="__accno" type="hidden" value="(\d+)" \/>', response.read() )
            if matcher:
                self.chomik_md5 = None
                self.chomik_id = matcher.group( 1 )
                #print "--------------------------"
                #print " Logged as %s[%s]" % ( self.chomik_name, self.chomik_id )
                #print "--------------------------"
                return True
        return False

    def check_directory( self, url ):
        #print "  -- checking %s" % url
        url = url if url.startswith( '/' ) else "/%s" % url
        if self._cached_directories.has_key( url ):
            return self._cached_directories[url], url

        url = '/'.join( [ urllib.quote_plus( p.encode( 'utf-8' ) ) for p in url.split('/') ] )
        full_url = "http://chomikuj.pl/%s%s" % ( self.chomik_name, url )

        response = self.browser.open( full_url )
        text = response.read()

        soup = BeautifulSoup( text )
        self.token = soup.find( 'input', { 'name': '__RequestVerificationToken' })['value']
        #print self.token

        matcher = re.search( '<input type="text" value="(.*)" style="display: none" id="FolderAddress">', text )
        if matcher:
            absolute_url = matcher.group( 1 )
            parts = absolute_url.split('/')
            name = parts[-1].replace( '*', '%' ).replace( '(', '%28' ).replace( ')', '%29' )
            if len( parts ) > 4  and full_url.endswith( name ):
                form = soup.find( 'form', id='FileListForm' )
                id = form.find( 'input', { 'name': 'folderId' } )['value']

                self._cached_directories[url] = id
                return id, full_url
        return None, None

    def remove_directory( self, url ):
        url = url[1:] if url.startswith( '/' ) else url
        folder_id = self.check_directory( url )
        if folder_id is not None:
            self._create_form( 'http://chomikuj.pl/action/FolderOptions/DeleteFolderAction', [
                { 'name': 'FolderId', 'type': 'hidden', 'value': folder_id, 'args': {} },
                { 'name': 'ChomikId', 'type': 'hidden', 'value': self.chomik_id, 'args': {} },
                { 'name': '__RequestVerificationToken', 'type': 'hidden', 'value': self.token, 'args': {} },
            ])

            response = self.browser.submit()
            return re.search( 'został usunięty', response.read() )
        return None

    def create_directory( self, url ):
        url = url[1:] if url.startswith( '/' ) else url
        folder_id = "0"
        dir_route = []
        for folder in url.split( '/' ):
            dir_route.append( folder )
            dir_id, full_url = self.check_directory( '/'.join( dir_route ) )
            if dir_id is not None:
                folder_id = dir_id
                continue

            self._create_form( 'http://chomikuj.pl/action/FolderOptions/NewFolderAction', [
                { 'name': 'FolderId', 'type': 'hidden', 'value': folder_id, 'args': {} },
                { 'name': 'ChomikId', 'type': 'hidden', 'value': self.chomik_id, 'args': {} },
                { 'name': 'FolderName', 'type': 'text', 'value': folder, 'args': {} },
                { 'name': 'AdultContent', 'type': 'text', 'value': "false", 'args': {} },
                { 'name': 'Password', 'type': 'text', 'value': "", 'args': {} },
                { 'name': '__RequestVerificationToken', 'type': 'text', 'value': self.token, 'args': {} },
            ])

            self.browser.submit()
            folder_id, full_url = self.check_directory( '/'.join( dir_route ).decode( 'latin1' ) )

        return folder_id, full_url

    def copy_directory_tree( self, url, db=None ):
        if db is None:
            db = {}

        url = url if url.startswith( '/' ) else "/%s" % url
        response = self.browser.open( "http://chomikuj.pl%s" % url )
        text = response.read()
        regex = re.compile( "</'", re.IGNORECASE )
        text = regex.sub( "<\/'", text )
        soup = BeautifulSoup( text )

        user_id, directory_id = None, None
        for button in soup.findAll( onclick=re.compile( "ch.CopyFilesAndFolders.ShowCopyFolderWindow\(.*\);" ) ):
            matcher = re.search( 'ch.CopyFilesAndFolders.ShowCopyFolderWindow\((\d+), (\d+)\);', button['onclick'] )
            user_id, directory_id = matcher.groups()

        if self._is_item_done( 'copy', url ):
            #print " -- url %s done [SKIPING]" % url
            pass

        elif user_id and directory_id:
            if not db.has_key( url ) or db[url] is None:
                db[url] = url.split( '/' )[:1][0]

            #print " -- cloning directory [%s] %s, %s" % ( db[url], user_id, directory_id )
            folder_id = self.create_directory( url )

            self._create_form( 'http://chomikuj.pl/Chomik/Content/Copy/CopyFolder', [
                { 'name': 'chosenFolder.ChomikId', 'type': 'hidden', 'value': user_id, 'args': {} },
                { 'name': 'chosenFolder.FolderId', 'type': 'hidden', 'value': directory_id, 'args': {} },
                { 'name': 'chosenFolder.Name', 'type': 'text', 'value': db[url], 'args': {} },
                { 'name': 'SelectedFolderId', 'type': 'text', 'value': folder_id, 'args': {} },
                { 'name': 'SelectTreeChomikId', 'type': 'text', 'value': self.chomik_id, 'args': {} },
                { 'name': 'SelectTreeMd5', 'type': 'text', 'value': self.chomik_md5, 'args': {} },
                { 'name': 'cfSubmitBtn', 'type': 'submit', 'args': {} },
            ])

            response = self.browser.submit()
            matcher = re.search( 'Folder został zachomikowany', response.read() )
            if matcher:
                #print " -- ZACHOMIKOWANO"
                pass
            else:
                pass
                #print " ------------------------------"
                #print " -- NIE ZACHOMIKOWANO KUUURWA !"
                #print " ------------------------------"
            
            self._add_item_to_done( 'copy', url )

        for folder in soup.findAll( onclick=re.compile( "return Ts\(.*" ), href=re.compile( "%s/.*" % re.escape( url ) ) ):
            if not db.has_key( folder['href'] ):
                #print " -- %s: %s" % ( folder.string, folder['href'] )
                db[folder['href']] = folder.string
                self.copy_directory_tree( folder['href'], db )

        return len( db )

    def get_stats( self, name=None ):
        r = {
            'points': 0,
            'files' : 0,
            'size'  : 0,
            # ----
            'docs'  : 0,
            'images': 0,
            'video' : 0,
            'music' : 0
        }
        if name is None:
            name = self.chomik_name
        response = self.browser.open( "http://chomikuj.pl/%s" % name )
        soup = BeautifulSoup( response.read() )
        #convert_bytes( float( matcher.group( 1 ).replace( ',', '.' ) ) )
        fileInfo = soup.find( 'div', { 'class': re.compile( "fileInfoFrame" ) } )
        files, size = [ o.string for o in fileInfo.p.findAll( 'span' ) ]
        
        r['points'] = float( soup.find( 'a', id='topbarPoints' ).strong.string )
        r['files'] = int( files )
        r['music'], r['video'], r['images'], r['docs'] = [ int( o.span.string ) for o in fileInfo.findAll( 'li' ) ]
        r['size'] = '%s %s' % ( float( size.replace( ',', '.' ) ), fileInfo.p.contents[-1].strip() )

        return r

    def invite( self, user ):
        #print " -- inviting %s" % user
        response = self.browser.open( "http://chomikuj.pl/%s" % user )
        matcher = re.search( '<input name="ctl00\$CT\$ChomikID" type="hidden" id="ctl00_CT_ChomikID" value="(\d+)" \/>', response.read() )
        if matcher:
            chomik_id = matcher.group( 1 )
            self._create_form( 'http://chomikuj.pl/Chomik/Friends/NewFriend', [
                { 'name': 'chomikFriendId', 'type': 'hidden', 'value': chomik_id, 'args': {} },
                { 'name': 'frDescr', 'type': 'text', 'value': '', 'args': {} },
                { 'name': 'frMsg', 'type': 'text', 'value': '', 'args': {} },
                { 'name': 'fromPMBox', 'type': 'hidden', 'value': 'false', 'args': {} },
                { 'name': 'groupId', 'type': 'text', 'value': '0', 'args': {} },
                { 'name': 'page', 'type': 'text', 'value': '1', 'args': {} },
            ])

            response = self.browser.submit()
            text = response.read()
            if re.search( 'Nie można dodać tego samego Chomika jako przyjaciela', text ):
                #print "  -- already invited"
                pass

            elif re.search( 'Chomik został dodany', text ):
                #print "  -- INVITED"
                pass

            else:
                #print "  -- ivite ERROR :("
                pass

    def send_chat_message( self, user, message, recaptchaChallengeVal='', recaptchaResponseVal='' ):
        #print " -- sending chat message %s" % user
        response = self.browser.open( "http://chomikuj.pl/%s" % user )
        matcher = re.search( '<input name="ctl00\$CT\$ChomikID" type="hidden" id="ctl00_CT_ChomikID" value="(\d+)" \/>', response.read() )
        if matcher:
            chomik_id = matcher.group( 1 )
            self._create_form( 'http://chomikuj.pl/services/ChomikChatService.asmx/AddChatMessage', [
                { 'name': 'idChomikTo', 'type': 'hidden', 'value': chomik_id, 'args': {} },
                { 'name': 'nick', 'type': 'text', 'value': '', 'args': {} },
                { 'name': 'pageNum', 'type': 'text', 'value': '0', 'args': {} },
                { 'name': 'recaptchaChallengeVal', 'type': 'hidden', 'value': recaptchaChallengeVal, 'args': {} },
                { 'name': 'recaptchaResponseVal', 'type': 'hidden', 'value': recaptchaResponseVal, 'args': {} },
                { 'name': 'timeFilter', 'type': 'text', 'value': '0', 'args': {} },
                { 'name': 'text', 'type': 'text', 'value': message, 'args': {} },
            ])

            response = self.browser.submit()
            text = response.read()
            if re.search( '<NeedCaptcha>true</NeedCaptcha>', text ):
                raise CaptchNeededException()
                
            elif re.search( '<Status>true</Status>', text ):
                print "  -- SENDED"

            else:
                print " -- ERROR"

    def read_directory( self, url ):
        sub_url = url if url.startswith( '/' ) else "/%s" % url
        response = self.browser.open( "http://chomikuj.pl%s" % sub_url )
        text = response.read()
        regex = re.compile( "</'", re.IGNORECASE )
        text = regex.sub( "<\/'", text )
        soup = BeautifulSoup( text )
        
        result = {
            "folders": [],
            "files": []
        }
        main_panel = soup.find( id='ctl00_CT_FW_FolderList' )
        for folder in main_panel.findAll( 'a', onclick=re.compile( "return Ts\(.*" ), href=re.compile( "%s/.*" % re.escape( sub_url ) ) ):
            result['folders'].append( ( folder.string, folder['href'] ) )

        for a in soup.findAll( 'a', { 'class': 'FileName' } ):
            matcher = re.search( 'FileNameAnchor_(\d+)', a['id'] )
            result['files'].append( ( clean_html( a.b ), a['href'], matcher.group( 1 ) ) )

        return result

    def download_file_by_id( self, id ):
        self._create_form( 'http://chomikuj.pl/Chomik/License/Download', [
            { 'name': 'fileId', 'type': 'hidden', 'value': id, 'args': {} },
        ])
        response = self.browser.submit()
        matcher = re.search( '{"redirectUrl":"([^"]*)"', response.read() )
        if matcher:
            url = matcher.group( 1 )
            name = re.search( '&name=(.*)&', url ).group( 1 )
            os.system( "wget -c '%s' -O '%s'" % ( url, name ) )

    def generate_list( self, count=100, filename="list.txt" ):
        print " -- generating list of %d users to %s" % ( count, filename )
        users = []
        file = open( filename, 'r' )
        if file:
            users = [ u.strip() for u in file ]
            file.close()

        response = self.browser.open( "http://chomikuj.pl/action/LastAccounts/RecommendedAccounts" )
        soup = BeautifulSoup( response.read() )
        for item in soup.findAll( 'a' ):
            if len( users ) >= count:
                print " -- users list contains %d users [CLOSING]" % len( users )
                return
            item = item.string
            if item is not None:
                if item in users:
                    print "  -- user %s already exists [SKIPING]" % item
                else:
                    print "  -- ... %s" % item
                    users.append( item )

        file = open( filename, 'w' )
        for u in users:
            file.write( "%s\n" % u )
        file.close()

        if len( users ) < count:
            print "  -- we already have %d [CONTINUE]" % len( users )
            time.sleep( 10 )
            return self.generate_list( count, filename )

    def _create_form( self, url, fields, method='POST' ):
        self.browser._factory.is_html = True
        self.browser.form = HTMLForm( url, method=method )
        for field in fields:
            self.browser.form.new_control( field['type'], field['name'], field['args'] )

        self.browser.form.set_all_readonly( False )
        self.browser.form.fixup()

        for field in fields:
            if field.has_key( 'value' ):
                self.browser[ field['name'] ] = field['value']


    def _is_item_done( self, type, item ):
        try:
            return item in [ u.strip() for u in open( "db/%s_%s.dat" % ( self.name, type ), 'r' ) ]
        except Exception:
            return False

    def _add_item_to_done( self, type, item ):
        if not os.path.isdir( 'db' ):
            os.mkdir( 'db' )

        f = open( "db/%s_%s.dat" % ( self.name, type ), 'a' )
        f.write( '%s\n' % item )
        f.close()

# vim: fdm=marker ts=4 sw=4 sts=4
