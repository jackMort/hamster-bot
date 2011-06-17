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
import string
import random
import urllib2
import logging
from mechanize import Browser, LinkNotFoundError, HTMLForm
from BeautifulSoup import BeautifulSoup

#logger = logging.getLogger( 'mechanize' )
#logger.addHandler( logging.StreamHandler( sys.stderr ) )
#logger.setLevel( logging.DEBUG )

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

            self.browser.form = HTMLForm( 'http://chomikuj.pl/Chomik/FolderOptions/NewFolderAction', method='POST' )
            self.browser.form.new_control( 'hidden', 'IdFolder', {} )
            self.browser.form.new_control( 'hidden', 'IdChomik', {} )
            self.browser.form.new_control( 'text', 'FolderName', {} )
            self.browser.form.new_control( 'text', 'GalleryMode', {} )
            self.browser.form.new_control( 'text', 'AdultContent', {} )
            self.browser.form.new_control( 'text', 'Description', {} )
            self.browser.form.new_control( 'text', 'Password', {} )

            self.browser.form.set_all_readonly( False )
            self.browser.form.fixup()
            
            self.browser['IdFolder'] = folder_id
            self.browser['IdChomik'] = self.chomik_id
            self.browser['FolderName'] = folder
            self.browser['GalleryMode'] = "false"
            self.browser['AdultContent'] = "false"
        
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
        soup = BeautifulSoup( response.read() )
        
        user_id, directory_id = None, None
        for button in soup.findAll( onclick=re.compile( "ch.CopyFilesAndFolders.ShowCopyFolderWindow\(.*\);" ) ):
            matcher = re.search( 'ch.CopyFilesAndFolders.ShowCopyFolderWindow\((\d+), (\d+)\);', button['onclick'] )
            user_id, directory_id = matcher.groups()

        if user_id and directory_id:
            if not db.has_key( url ) or db[url] is None:
                db[url] = url.split( '/' )[:1][0]

            print " -- cloning directory [%s] %s, %s" % ( db[url], user_id, directory_id )
            folder_id = self.create_directory( sub_url )

            self.browser._factory.is_html = True

            self.browser.form = HTMLForm( 'http://chomikuj.pl/Chomik/Content/Copy/CopyFolder', method='POST' )
            self.browser.form.new_control( 'hidden', 'chosenFolder.ChomikId', {} )
            self.browser.form.new_control( 'hidden', 'chosenFolder.FolderId', {} )
            self.browser.form.new_control( 'text', 'chosenFolder.Name', {} )
            self.browser.form.new_control( 'hidden', 'SelectedFolderId', {} )
            self.browser.form.new_control( 'hidden', 'SelectTreeChomikId', {} )
            self.browser.form.new_control( 'hidden', 'SelectTreeMd5', {} )
            self.browser.form.new_control( 'submit', 'cfSubmitBtn', {} )

            self.browser.form.set_all_readonly( False )
            self.browser.form.fixup()
            
            self.browser['chosenFolder.ChomikId'] = user_id
            self.browser['chosenFolder.FolderId'] = directory_id
            self.browser['chosenFolder.Name'] = db[url]
            self.browser['SelectedFolderId'] = folder_id
            self.browser['SelectTreeChomikId'] = self.chomik_id
            self.browser['SelectTreeMd5'] = self.chomik_md5
            
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

# vim: fdm=marker ts=4 sw=4 sts=4
