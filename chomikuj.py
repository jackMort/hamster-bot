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
import urllib2
import logging
from mechanize import Browser, LinkNotFoundError, HTMLForm
from BeautifulSoup import BeautifulSoup

#logger = logging.getLogger( 'mechanize' )
#logger.addHandler( logging.StreamHandler( sys.stderr ) )
#logger.setLevel( logging.DEBUG )

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
        self._cached_directories = {}

    def connect( self ):
        self.browser.open( "http://chomikuj.pl" )
        self.browser.select_form( nr=0 )
        self.browser["ctl00$LoginTop$LoginChomikName"] = self.name
        self.browser["ctl00$LoginTop$LoginChomikPassword"] = self.password

        response = self.browser.submit()
        text = response.read()
        matcher = re.search( 'Pliki użytkownika (.*) - Chomikuj.pl', self.browser.title() )
        if matcher:
            self.chomik_name = matcher.group( 1 )
            matcher = re.search( '<input name="ctl00\$CT\$ChomikID" type="hidden" id="ctl00_CT_ChomikID" value="(\d+)" \/>', text )
            if matcher:
                self.chomik_id = matcher.group( 1 )
                matcher = re.search( 'ch.ChomikTree.Md5 = \'(.*)\'', text )
                if matcher:
                    self.chomik_md5 = matcher.group( 1 )
                    print "--------------------------"
                    print " Logged as %s(%s) [%s]" % ( self.chomik_name, self.chomik_id, self.chomik_md5 )
                    print "--------------------------"
                    return True
        return False

    def check_directory( self, url ):
        print "  -- checking %s" % url
        url = url if url.startswith( '/' ) else "/%s" % url
        if self._cached_directories.has_key( url ):
            return self._cached_directories[url]

        full_url = "http://chomikuj.pl/%s%s" % ( self.chomik_name, url )
        response = self.browser.open( full_url )
        text = response.read()
        matcher = re.search( '<input name="ctl00\$CT\$FW\$inpFolderAddress" type="text" id="ctl00_CT_FW_inpFolderAddress" class="text" style="display: none; font-size: 11px; width: 300px;" value="(.*)" \/>', text )
        if matcher:
            absolute_url = matcher.group( 1 )
            if absolute_url == full_url:
                matcher = re.search( '<input id="ChomikSubfolderId" name="ChomikSubfolderId" type="hidden" value="(\d+)" \/>', text )
                if matcher:
                    id = matcher.group( 1 )
                    self._cached_directories[url] = id
                    return id
        return None

    def remove_directory( self, url ):
        url = url[1:] if url.startswith( '/' ) else url
        folder_id = self.check_directory( url )
        if folder_id is not None:
            self._create_form( 'http://chomikuj.pl/Chomik/FolderOptions/DeleteFolderAction', [
                { 'name': 'FolderId', 'type': 'hidden', 'value': folder_id, 'args': {} },
                { 'name': 'ChomikId', 'type': 'hidden', 'value': self.chomik_id, 'args': {} },
            ])

            response = self.browser.submit()
            return re.search( 'został pomyślnie usunięty', response.read() )
        return None

    def create_directory( self, url ):
        url = url[1:] if url.startswith( '/' ) else url
        folder_id = "0"
        dir_route = []
        for folder in url.split( '/' ):
            dir_route.append( folder )
            dir_id = self.check_directory( '/'.join( dir_route ) )
            if dir_id is not None:
                folder_id = dir_id
                continue

            self._create_form( 'http://chomikuj.pl/Chomik/FolderOptions/NewFolderAction', [
                { 'name': 'IdFolder', 'type': 'hidden', 'value': folder_id, 'args': {} },
                { 'name': 'IdChomik', 'type': 'hidden', 'value': self.chomik_id, 'args': {} },
                { 'name': 'FolderName', 'type': 'text', 'value': folder, 'args': {} },
                { 'name': 'GalleryMode', 'type': 'text', 'value': "false", 'args': {} },
                { 'name': 'AdultContent', 'type': 'text', 'value': "false", 'args': {} },
                { 'name': 'Description', 'type': 'text', 'value': "", 'args': {} },
                { 'name': 'Password', 'type': 'text', 'value': "", 'args': {} } 
            ])

            response = self.browser.submit()
            matcher = re.search( 'switchFolder\((\d+)\)', response.read() )
            if matcher:
                folder_id = matcher.group( 1 )
            else:
                break

        return folder_id

    def copy_directory_tree( self, url, db=None ):
        if db is None:
            db = {}

        sub_url = url if url.startswith( '/' ) else "/%s" % url
        response = self.browser.open( "http://chomikuj.pl%s" % sub_url )
        text = response.read()
        regex = re.compile( "</'", re.IGNORECASE )
        text = regex.sub( "<\/'", text )
        soup = BeautifulSoup( text )

        user_id, directory_id = None, None
        for button in soup.findAll( onclick=re.compile( "ch.CopyFilesAndFolders.ShowCopyFolderWindow\(.*\);" ) ):
            matcher = re.search( 'ch.CopyFilesAndFolders.ShowCopyFolderWindow\((\d+), (\d+)\);', button['onclick'] )
            user_id, directory_id = matcher.groups()

        if user_id and directory_id:
            if not db.has_key( url ) or db[url] is None:
                db[url] = url.split( '/' )[:1][0]

            print " -- cloning directory [%s] %s, %s" % ( db[url], user_id, directory_id )
            folder_id = self.create_directory( sub_url )

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
                print " -- ZACHOMIKOWANO"
            else:
                print " ------------------------------"
                print " -- NIE ZACHOMIKOWANO KUUURWA !"
                print " ------------------------------"

        for folder in soup.findAll( onclick=re.compile( "return Ts\(.*" ), href=re.compile( "%s/.*" % re.escape( sub_url ) ) ):
            if not db.has_key( folder['href'] ):
                print " -- %s: %s" % ( folder.string, folder['href'] )
                db[folder['href']] = folder.string
                self.copy_directory_tree( folder['href'], db )

        return len( db )

    def get_stats( self ):
        result = {
            'points': 0,
            'files': 0,
            'size': 0
        }
        response = self.browser.open( "http://chomikuj.pl/%s" % self.chomik_name )
        text = response.read()
        matcher = re.search( '<span id="ctl00_CT_StatsSize"><b>(.*) MB</b></span>', text )
        if matcher:
            result['size'] = convert_bytes( float( matcher.group( 1 ).replace( ',', '.' ) ) )

        matcher = re.search( '<span id="ctl00_CT_StatsFilesCount"><b>(.*)</b></span>', text )
        if matcher:
            result['files'] = matcher.group( 1 )

        matcher = re.search( '<span id="ctl00_CT_PointsLabel">(.*)</span>', text )
        if matcher:
            result['points'] = matcher.group( 1 )

        return result

    def invite( self, user ):
        print " -- inviting %s" % user
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
                print "  -- already invited"

            elif re.search( 'Chomik został dodany', text ):
                print "  -- INVITED"

            else:
                print "  -- ivite ERROR :("

    def send_chat_message( self, user, message, recaptchaChallengeVal='', recaptchaResponseVal='' ):
        print " -- sending chat message %s" % user
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

    def generate_list( self, count=100, filename="list.txt" ):
        print " -- generating list of %d users to %s" % ( count, filename )
        users = []
        file = open( filename, 'r' )
        if file:
            users = [ u.strip() for u in file ]
            file.close()

        response = self.browser.open( "http://chomikuj.pl/services/GetLastSeen.aspx?_=1&maxNum=18&colNum=1&pauseTime=500" )
        for item in re.findall( '<a class="name" href="\/(.*)"', response.read() ):
            if len( users ) >= count:
                print " -- users list contains %d users [CLOSING]" % len( users )
                return

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


# vim: fdm=marker ts=4 sw=4 sts=4
