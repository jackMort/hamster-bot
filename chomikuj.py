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
import json
import string
import random
import urllib
import urllib2
import logging
import collections
from mechanize import Browser, LinkNotFoundError, HTMLForm
from BeautifulSoup import BeautifulSoup

import logging
logging.basicConfig( filename='logs/all.log', level=logging.DEBUG )

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
        self.logger = logging.getLogger( name )
        self.logger.setLevel( logging.DEBUG )

        formatter = logging.Formatter( '%(asctime)s - %(name)s - %(levelname)s - %(message)s' )

        handler = logging.FileHandler( os.path.join( 'logs', '%s.log' % name ) )
        handler.setFormatter( formatter )
        self.logger.addHandler( handler )

        self.name = name
        self.password = password
        self.chomik_id = None
        self.browser = Browser()
        self.browser.set_handle_robots( False )
        self._cached_directories = {}
        self.captcha = None
        self.captcha_attempt = 0
        self.captcha_latest = []

    def connect( self ):
        if not self.chomik_id:
            self.browser = Browser()
            self.browser.set_handle_robots( False )
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
                    return True
            return False
        return True

    def diconnect( self ):
        if self.chomik_id:
            self._create_form( 'http://chomikuj.pl/action/Login/LogOut', [
                { 'name': 'redirect', 'type': 'hidden', 'value': '/%s' % self.chomik_name, 'args': {} },
                { 'name': 'logout.x', 'type': 'hidden', 'value': '4', 'args': {} },
                { 'name': 'logout.y', 'type': 'hidden', 'value': '10', 'args': {} },
            ])

            self.browser.submit()
            self.chomik_id = self.chomik_name = self.token = None
        return True

    def check_directory( self, url ):
        raw_url = url
        url = url if url.startswith( '/' ) else "/%s" % url
        if self._cached_directories.has_key( url ):
            return self._cached_directories[url], url

        parts = []
        parts_raw = []
        for p in url.split( '/' ):
            for ch, code in self.CHAR_MAP.items():
                p = p.replace( ch, code )
            parts_raw.append(p)
            p = urllib.quote_plus( p.encode( 'utf-8' ) )
            parts.append( p )
        
        name = parts_raw[-1]

        url = '/'.join( parts )
        full_url = "http://chomikuj.pl/%s%s" % ( self.chomik_name, url )
        full_url = full_url.replace( '%', '*' )
        #print "----"
        #print "url     :", [url]
        #print "full_url:", full_url

        response = self.browser.open( full_url )
        text = response.read()

        soup = BeautifulSoup( text )
        self.token = str( soup.find( 'input', { 'name': '__RequestVerificationToken' })['value'] )
        if not self.token:
            self.check_directory( url )

        try:
            title = soup.find( 'div', { 'class': 'frameHeaderNoImage frameHeader borderTopRadius' } ).h1.a.string
            if name.lower() == title.lower():
                form = soup.find( 'form', id='FileListForm' )
                id = form.find( 'input', { 'name': 'folderId' } )['value']

                self._cached_directories[url] = id
                return id, full_url
        except Exception, e:
            print e

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


    CHAR_MAP = {
        '\\': '&#92;',
        '/' : '&#48;',
        '*' : '&#42;',
        '?' : '&#63;',
        '"' : '&#34;',
        '<' : '&#60;',
        '>' : '&#62;',
        '|' : '&#124;',
        '.' : '&#46;',
        ':' : '&#58;',
    }
    def create_directory( self, url ):
        url = url[1:] if url.startswith( '/' ) else url
        folder_id = "0"
        dir_route = []
        raw_dir_route = []
        for folder in url.split( '/' ):
            raw_dir_route.append( folder )
            for ch, code in self.CHAR_MAP.items():
                folder = folder.replace( ch, code )
            
            dir_route.append( folder )
            dir_id, full_url = self.check_directory( '/'.join( dir_route ) )
            if dir_id is not None:
                folder_id = dir_id
                continue

            if folder and folder_id:
                self._create_form( 'http://chomikuj.pl/action/FolderOptions/NewFolderAction', [
                    { 'name': 'FolderId', 'type': 'hidden', 'value': folder_id, 'args': {} },
                    { 'name': 'ChomikId', 'type': 'hidden', 'value': self.chomik_id, 'args': {} },
                    { 'name': 'FolderName', 'type': 'text', 'value': folder, 'args': {} },
                    { 'name': 'AdultContent', 'type': 'text', 'value': "false", 'args': {} },
                    { 'name': 'Password', 'type': 'text', 'value': "", 'args': {} },
                    { 'name': '__RequestVerificationToken', 'type': 'text', 'value': self.token, 'args': {} },
                ])

                response = self.browser.submit()
                folder_id, full_url = self.check_directory( '/'.join( raw_dir_route ) )

        return folder_id, full_url

    def set_folder_description( self, url, description ):
        folder_id, full_url = self.create_directory( url )
        self._create_form( 'http://chomikuj.pl/action/FolderOptions/ChangeDescription', [
            { 'name': 'folderId', 'type': 'hidden', 'value': folder_id, 'args': {} },
            { 'name': 'chomikId', 'type': 'hidden', 'value': self.chomik_id, 'args': {} },
            { 'name': 'description', 'type': 'text', 'value': description, 'args': {} },
            { 'name': '__RequestVerificationToken', 'type': 'text', 'value': self.token, 'args': {} },
        ])

        data = json.loads( self.browser.submit().read() )
        return data['IsSuccess']

    def copy_directory_tree( self, url, db=None, captcha='', timeout=0 ):
        if db is None:
            db = {}

        full_url = '/'.join( [ urllib.quote_plus( p.encode( 'utf-8' ) ) for p in url.split('/') ] )
        response = self.browser.open( "http://chomikuj.pl%s" % full_url )

        soup = BeautifulSoup( response.read() )
        self.token = soup.find( 'input', { 'name': '__RequestVerificationToken' })['value'] # TODO

        directory_id = soup.find( 'input', { 'name': 'FolderId' } )['value']
        user_id = soup.find( 'input', { 'name' :'__accno' } )['value']
        private = soup.find( 'table', { 'class':'LoginToFolderForm' } ) is not None
        disabled = soup.find( 'a', { 'class': 'button disabled bigButton copyFolderButton' } )
        
        if private:
            self.logger.info( "%s, is private skipping ..." % full_url )
            return db
 
        if disabled:
            self.logger.info( "%s, coping folders disabled ..." % full_url )
            return db

        folder_id, folder_url = self.check_directory( url )
        if folder_id is None:
            if user_id and directory_id:
                if not db.has_key( url ) or db[url] is None:
                    db[url] = url.split( '/' )[-1]

                self.logger.info( "cloning directory [%s] %s, %s" % ( db[url], user_id, directory_id ) )
                folder_id = '0'
                parent = '/'.join( url.split( '/' )[:-1] )
                if parent:
                    folder_id, folder_url = self.check_directory( parent )

                self._create_form( 'http://chomikuj.pl/action/content/copy/CopyFolder', [
                    { 'name': 'chosenFolder.ChomikId', 'type': 'hidden', 'value': user_id, 'args': {} },
                    { 'name': 'chosenFolder.FolderId', 'type': 'hidden', 'value': directory_id, 'args': {} },
                    { 'name': 'chosenFolder.Name', 'type': 'text', 'value': db[url], 'args': {} },
                    { 'name': 'SelectedFolderId', 'type': 'text', 'value': folder_id, 'args': {} },
                    { 'name': 'ChomikId', 'type': 'text', 'value': self.chomik_id, 'args': {} },
                    { 'name': 'recaptcha_response_field', 'type': 'text', 'value': captcha, 'args': {} },
                    { 'name': '__RequestVerificationToken', 'type': 'hidden', 'value': self.token, 'args': {} },
                ])

                self.sleep( timeout )
                response = self.browser.submit()
                text = response.read()
                try:
                    result = json.loads( text )
                    self.logger.debug( result['isSuccess'], result['Content'] )
                except:
                    pass
                if "Folder został zachomikowany" in text:
                    self.logger.info( "%s, zachomikowany ..." % full_url )
                    self.captcha_attempt = 0
                    self.captcha_latest = []
                else:
                    inner_soup = BeautifulSoup( text )
                    captcha = inner_soup.find( 'img', { 'alt': 'captcha' } )
                    if captcha:
                        captcha = self.read_captcha( captcha['src'] )
                        if captcha:
                            self.logger.info( "trying with captcha: %s" % captcha )
                            self.captcha_attempt += 1
                            return self.copy_directory_tree( url, db, captcha )
                        else:
                            raise NeedCaptcha()
                    else:
                        self.logger.debug( "copy error response: %s" % text )

        div = soup.find( 'div', { 'id': 'foldersList' } )
        if div:
            for a in div.findAll( 'a' ):
                db[a['href']] = a['title']
                self.copy_directory_tree( '%s/%s' % ( url, a['title'] ), db )

        return db

    def read_captcha( self, captcha_src ):
        
        if self.captcha_attempt >= 10:
            self.logger.info( "diconnecting for new captcha ..." )
            self.diconnect()
            self.connect()
            self.captcha = None
            self.captcha_attempt = 0
            self.captcha_latest = []

        self.captcha_latest = filter ( lambda a: a != self.captcha, self.captcha_latest )

        captcha_url = "http://chomikuj.pl%s" % captcha_src
        captcha_filename = "%s-captcha.jpg" % self.chomik_id

        if not self.captcha_latest:
            self.logger.debug( "READING CAPTCHA, ATTEMPT: %s" % self.captcha_attempt )
            self.captchas_v2 = []
            count = 0
            while count < 10:

                file = open( captcha_filename, mode='wb' )
                file.write( self.browser.open_novisit( captcha_url ).read() )
                file.close()

                from tools.captcha import read_captcha
                captcha = read_captcha( captcha_filename )
                if captcha and len( captcha ) == 5:
                    self.captcha_latest.append( captcha )

                count+=1

        most_common = collections.Counter( self.captcha_latest ).most_common()
        self.logger.debug( '%s' % most_common )

        letters = {
            0: [],
            1: [],
            2: [],
            3: [],
            4: [],
        }
        for s in self.captcha_latest:
            for i, l in enumerate( s ):
                letters[i].append( l )
       
        min_match = None
        captcha_v2 = ""
        for l in letters.values():
            mc = collections.Counter( l ).most_common(1)
            if len( mc ):
                captcha_v2 += mc[0][0]
                if min_match is None or mc[0][1] < min_match:
                    min_match = mc[0][1]

        if len( most_common ) and most_common[0][1] >= 3:
            captcha = most_common[0][0]
        elif len( captcha_v2 ) == 5 and not captcha_v2 in self.captchas_v2:
            captcha = captcha_v2
        else:
            captcha = most_common[0][0]

        self.captchas_v2.append( captcha )
        self.captcha = captcha
        return captcha

    def search( self, query, type='Video', limit_pages=3, **kwargs ):
        page = 0
        results = []
        has_next = True

        while has_next:
            page += 1
            extra = ''
            for k, v in kwargs.items():
                extra += '&%s=%s' % ( k, v )
        
            response = self.browser.open( 'http://chomikuj.pl/action/SearchFiles?FileName=%s&FileType=%s&Page=%d%s' % ( urllib.quote_plus( query.encode( 'utf-8' ) ), type, page, extra ) )

            soup = BeautifulSoup( response.read() )
            self.token = soup.find( 'input', { 'name': '__RequestVerificationToken' })['value'] # TODO

            has_next = page < limit_pages and soup.find( 'a', { 'class': 'right' } )

            for div in soup.findAll( 'div', { 'class': 'filerow fileItemContainer' } ):
                a = div.find( 'a', { 'class': 'expanderHeader downloadAction'} )
                extension = a.contents[-1].strip()
                id = div.find( 'div', { 'class': 'fileActionsButtons clear visibleButtons  fileIdContainer' } )['rel']
                size = div.find( 'ul', { 'class': 'borderRadius tabGradientBg' } ).li.span.string
                results.append( dict( title=a['title'], id=id, url="http://chomikuj.pl%s" % a['href'], size=size, extension=extension, full_name=a['title'] + extension ) )

        return results

    def clone( self, file_id, folder_id, captcha='' ):
        if not self.token:
            self.search( 'asdsd asd asd as da sdasd' )#TODO
            print " --- dupa"
        time.sleep( 2 )
        self._create_form( 'http://chomikuj.pl/action/content/copy/CopyFile', [
            { 'name': 'ChomikId', 'type': 'hidden', 'value': self.chomik_id, 'args': {} },
            { 'name': 'chosenFile.FileId', 'type': 'hidden', 'value': str( file_id ), 'args': {} },
            { 'name': 'chosenFile.FolderSelection', 'type': 'text', 'value': '2', 'args': {} },

            { 'name': 'SelectedFolderId', 'type': 'text', 'value': str( folder_id ), 'args': {} },
            { 'name': '__RequestVerificationToken', 'type': 'hidden', 'value': self.token, 'args': {} },
            { 'name': 'recaptcha_response_field', 'type': 'text', 'value': captcha, 'args': {} },
        ])

        response = self.browser.submit()
        text = response.read()

        if "Plik został zachomikowany" in text:
            self.logger.info( "%s, zachomikowany ..." % file_id )
            self.captcha_attempt = 0
            self.captcha_latest = []

            return True

        inner_soup = BeautifulSoup( text )
        captcha = inner_soup.find( 'img', { 'alt': 'captcha' } )
        if captcha:
            self.token = str( inner_soup.find( 'input', { 'name': '__RequestVerificationToken' })['value'] )
            captcha = self.read_captcha( captcha['src'] )
            if captcha:
                self.logger.info( "trying with captcha: %s" % captcha )
                self.captcha_attempt += 1
                return self.clone( file_id, folder_id, captcha )
            else:
                raise NeedCaptcha()
        else:
            self.logger.debug( "copy error response: %s" % text )

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

    def transfer( self, to, points=None ):

        my_points = self.get_stats()['points']
        max_points = self.max_points_to_transfer( my_points )
        if not points:
            points = max_points
        
        self.logger.debug( 'transfering %s points to %s ( max points: %s )  ...' % ( points, to, max_points ) )

        if points > max_points:
            raise AttributeError( "Your points %s, max points %s to transfer" % ( my_points, max_points ) )
        
        if points < 100:
            raise AttributeError( "Your points %s, min point to transfer is 100" % ( my_points, ) )

        points = int( points )
        print " --- transfering %s points to %s" % ( points, to )

        # 1 fetch token
        self._create_form( 'http://chomikuj.pl/Punkty.aspx', [
            { 'name': 'ctl00$SM', 'type': 'hidden', 'value': 'ctl00$CT$upPoints|ctl00$CT$btnTransferSubmit', 'args': {} },
            { 'name': 'PageCmd', 'type': 'hidden', 'value': '', 'args': {} },
            { 'name': 'PageArg', 'type': 'hidden', 'value': '', 'args': {} },
            { 'name': 'ctl00$CT$txtChomik', 'type': 'hidden', 'value': to, 'args': {} },
            { 'name': 'ctl00$CT$txtTitle', 'type': 'hidden', 'value': 'przelew', 'args': {} },
            { 'name': 'ctl00$CT$txtPointsQuota', 'type': 'hidden', 'value': points, 'args': {} },
            { 'name': '__EVENTTARGET', 'type': 'hidden', 'value': '', 'args': {} },
            { 'name': '__EVENTARGUMENT', 'type': 'hidden', 'value': '', 'args': {} },
            { 'name': '__VIEWSTATE', 'type': 'hidden', 'value': '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', 'args': {} },
            { 'name': '__EVENTVALIDATION', 'type': 'hidden', 'value': '/wEWCQLK5teHBQKfxMnVCwKhouGmCwKG0LXLBgKhupnlAgLhuo3bCwKO77aPCQLSgOePAwKK2Le+Aw==', 'args': {} },
            { 'name': '__ASYNCPOST', 'type': 'hidden', 'value': 'false', 'args': {} },
            { 'name': 'ctl00$CT$btnTransferSubmit', 'type': 'submit', 'value': 'true', 'args': {} },
        ])

        # step 2 make transfer
        response = self.browser.submit()
        soup = BeautifulSoup( response.read() )

        viewstate = str( soup.find( 'input', { 'name': '__VIEWSTATE' })['value'] )
        eventvalidation = str( soup.find( 'input', { 'name': '__EVENTVALIDATION' })['value'] )
        token = str( soup.find( 'input', { 'name': 'ctl00$CT$ahfToken2' })['value'] )
        time = str( soup.find( 'input', { 'name': 'ctl00$CT$ahfTime' })['value'] )

        self._create_form( 'http://chomikuj.pl/Punkty.aspx', [
            { 'name': 'ctl00$SM', 'type': 'hidden', 'value': 'ctl00$CT$upPoints|ctl00$CT$btnMakePointsTransfer', 'args': {} },
            { 'name': 'PageCmd', 'type': 'hidden', 'value': '', 'args': {} },
            { 'name': 'PageArg', 'type': 'hidden', 'value': '', 'args': {} },
            { 'name': 'ctl00$CT$ahfToken2', 'type': 'hidden', 'value': token, 'args': {} },
            { 'name': 'ctl00$CT$ahfTime', 'type': 'hidden', 'value': time, 'args': {} },
            { 'name': 'ctl00$CT$ahfChomikId', 'type': 'hidden', 'value': self.chomik_id, 'args': {} },
            { 'name': 'ctl00$CT$ahfTransferTitle', 'type': 'hidden', 'value': 'testowy przelew', 'args': {} },
            { 'name': 'ctl00$CT$ahfPointsQuota', 'type': 'hidden', 'value': points, 'args': {} },
            { 'name': 'ctl00$CT$ahfChomikName', 'type': 'hidden', 'value': to, 'args': {} },
            { 'name': '__EVENTTARGET', 'type': 'hidden', 'value': '', 'args': {} },
            { 'name': '__EVENTARGUMENT', 'type': 'hidden', 'value': '', 'args': {} },
            { 'name': '__VIEWSTATE', 'type': 'hidden', 'value': viewstate, 'args': {} },
            { 'name': '__EVENTVALIDATION', 'type': 'hidden', 'value': eventvalidation, 'args': {} },
            { 'name': '__ASYNCPOST', 'type': 'hidden', 'value': 'false', 'args': {} },
            { 'name': 'ctl00$CT$btnMakePointsTransfer', 'type': 'hidden', 'value': '', 'args': {} },
        ])

        self.browser.submit()
        self.browser.select_form( name='aspnetForm' )
        self.browser.submit()

        self.browser.select_form( name='aspnetForm' )
        text = self.browser.submit().read()
        if re.search( 'Przelew został wykonany', text ):
            return True
        return False

    def invite( self, user ):
        self.logger.info( 'inviting: %s' % user )
        
        response = self.browser.open( "http://chomikuj.pl/%s" % user )
        soup = BeautifulSoup( response.read() )

        form = soup.find( 'form', id='FormAccountInfoAddFriend' )
        is_active = form['style'] != 'display: none;'
        friend_id = form.find( 'input', id='chomikFriendId' )['value']
        token = str( soup.find( 'input', { 'name': '__RequestVerificationToken' })['value'] )
        if is_active:
            self._create_form( 'http://chomikuj.pl/action/Friends/NewFriend', [
                { 'name': 'ChomikFriendId', 'type': 'hidden', 'value': friend_id, 'args': {} },
                { 'name': 'Descr', 'type': 'text', 'value': '', 'args': {} },
                { 'name': 'FroPMBox', 'type': 'text', 'value': '', 'args': {} },
                { 'name': 'Group', 'type': 'text', 'value': '0', 'args': {} },
                { 'name': 'Page', 'type': 'text', 'value': '1', 'args': {} },
                { 'name': 'Msg', 'type': 'text', 'value': '', 'args': {} },
                { 'name': '__RequestVerificationToken', 'type': 'text', 'value': token, 'args': {} },
            ])

            response = self.browser.submit()
            data = json.loads( response.read() )
            
            self.logger.info( data.get( 'Content' ) )
            return data.get( 'isSuccess' )
        return False

    def get_downloaded_files( self ):
        viewstate = '/wEPDwULLTEyMzE5NjI3NTIQZGQWAmYPZBYCAgEPZBYCAgcPZBYCAgEPZBYCZg9kFgICAQ9kFgJmD2QWBAICD2QWAgIBDw9kFgIeBWNsYXNzBQhzZWxlY3RlZGQCBg9kFgQCAg9kFgICAg8UKwACZGRkAgMPZBYCAgsPDxYCHgxNYXhpbXVtVmFsdWUFCjIxNDc0ODM2NDdkZBgEBRFjdGwwMCRDVCRtdlBvaW50cw8PZGZkBRdjdGwwMCRDVCRtdlBvaW50c1dpbmRvdw8PZGZkBRNjdGwwMCRDVCRsdkxpY2Vuc2VzD2dkBRJjdGwwMCRDVCRsdkhpc3RvcnkPZ2Q='
        eventvalidation = '/wEWBALwt/+MBAKfxMnVCwKhouGmCwKG0LXLBg=='

        self._create_form( 'http://chomikuj.pl/Punkty.aspx', [
            { 'name': 'ctl00$SM', 'type': 'hidden', 'value': 'ctl00$CT$upPoints|ctl00$CT$lbHistory', 'args': {} },
            { 'name': '__EVENTTARGET', 'type': 'hidden', 'value': 'ctl00$CT$lbHistory', 'args': {} },
            { 'name': '__EVENTARGUMENT', 'type': 'hidden', 'value': '', 'args': {} },
            { 'name': '__VIEWSTATE', 'type': 'hidden', 'value': viewstate, 'args': {} },
            { 'name': '__EVENTVALIDATION', 'type': 'hidden', 'value': eventvalidation, 'args': {} },
            { 'name': 'PageCmd', 'type': 'hidden', 'value': '', 'args': {} },
            { 'name': 'PageArg', 'type': 'hidden', 'value': '', 'args': {} },
            { 'name': '__ASYNCPOST', 'type': 'hidden', 'value': 'false', 'args': {} },
        ])

        result = {}
        response = self.browser.submit()
        soup = BeautifulSoup( response.read() )
        for a in soup.find( 'table' ).findAll( 'a', {'class': 'pointsDetails' } ):
            page=1
            while True:
                response = self.browser.open( "http://chomikuj.pl%s&page=%d" % ( a['href'], page ) )
                data = json.loads( response.read() )
                soup = BeautifulSoup( data['Content'] )
                trs = soup.findAll('tr')
                if len( trs ) == 1:
                    break

                for tr in trs:
                    tds = tr.findAll( 'td' )
                    if len( tds ):
                        url, size, count, points = tr.findAll( 'td' )
                        count = int( count.string.strip() )
                        if result.has_key( url.a['href'] ):
                            count += result[ url.a['href'] ]['count']

                        result[url.a['href']] = { 'url': url.a['href'], 'count': count }
                page+=1
        return result.values()

    def send_chat_message( self, user, message, recaptchaChallengeVal='', recaptchaResponseVal='' ):
        response = self.browser.open( "http://chomikuj.pl/%s" % user )
        soup = BeautifulSoup( response.read() )
        form = soup.find( 'form', { 'id': 'chatSendMessage' } )
        if form:
            chomik_id = form.find( 'input', { 'id': 'TargetChomikId' } )['value']
            mode = form.find( 'input', { 'id': 'Mode' } )['value']
            bskr = form.find( 'input', { 'id': 'bskr' } )['value']
            self.token = str( soup.find( 'input', { 'name': '__RequestVerificationToken' })['value'] )

            self._create_form( 'http://chomikuj.pl/action/ChomikChat/SendMessage', [
                { 'name': 'TargetChomikId', 'type': 'hidden', 'value': chomik_id, 'args': {} },
                { 'name': 'mode', 'type': 'text', 'value': mode, 'args': {} },
                { 'name': 'bskr', 'type': 'text', 'value': bskr, 'args': {} },
                { 'name': 'Message', 'type': 'text', 'value': message, 'args': {} },
                { 'name': '__RequestVerificationToken', 'type': 'text', 'value': self.token, 'args': {} },
            ])
            self.browser.addheaders.append(['X-Requested-With', 'XMLHttpRequest'])

            response = self.browser.submit()
            text = response.read()
            print text

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

    def editDescription( self, description ):
        response = self.browser.open( 'http://chomikuj.pl/action/Account/Edit' )
        soup = BeautifulSoup( response.read() )

        description = description.replace( '\n', '\n\r' )
        self.token = str( soup.find( 'input', { 'name': '__RequestVerificationToken' })['value'] )

        self._create_form( 'http://chomikuj.pl/action/Account/ChangeDescription', [
            { 'name': 'description', 'type': 'text', 'value': description, 'args': {} },
            { 'name': '__RequestVerificationToken', 'type': 'hidden', 'value': self.token, 'args': {} },
        ])

        response = self.browser.submit()
        return 'redirectUrl' in response.read()

    def generate_list( self, count=100, to_file=True, filename="list.txt" ):
        self.logger.info( "generating list of users" )
        users = []
        if to_file:
            file = open( filename, 'r' )
            if file:
                users = [ u.strip() for u in file ]
                file.close()

        response = self.browser.open( "http://chomikuj.pl/action/LastAccounts/RecommendedAccounts" )
        soup = BeautifulSoup( response.read() )
        for item in soup.findAll( 'a' ):
            if len( users ) >= count:
                return users
            item = item.string
            if item is not None:
                if not item in users:
                    self.logger.debug( " adding user %s" % item )
                    users.append( item )

        if to_file:
            file = open( filename, 'w' )
            for u in users:
                file.write( "%s\n" % u )
            file.close()

            if len( users ) < count:
                time.sleep( 10 )
                return self.generate_list( count, filename )
        else:
            return users

    def _create_form( self, url, fields, method='POST' ):
        self.browser._factory.is_html = True
        self.browser.form = HTMLForm( url, method=method )
        for field in fields:
            self.browser.form.new_control( field['type'], field['name'], field['args'] )

        self.browser.form.set_all_readonly( False )
        self.browser.form.fixup()

        for field in fields:
            if field.has_key( 'value' ):
                self.browser[ field['name'] ] = str( field['value'] )


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

    def max_points_to_transfer( self, points ):
        if points <= 1000:
            return 0
        result = points - 1000
        sum = 0
        while sum <= 1000:
            result -= 5
            profit = ( result/100. ) * 5
            sum = points - ( result + profit )
        return result

    def sleep( self, timeout ):
        self.logger.debug( "going sleep for: %d ..." % timeout )
        time.sleep( timeout )

# vim: fdm=marker ts=4 sw=4 sts=4
