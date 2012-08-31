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
            self.chomik_id = self.chomik_name = None
        return True

    def check_directory( self, url ):
        name = url.split( '/' )[-1]
        url = url if url.startswith( '/' ) else "/%s" % url
        if self._cached_directories.has_key( url ):
            return self._cached_directories[url], url

        url = '/'.join( [ urllib.quote_plus( p.encode( 'utf-8' ) ) for p in url.split('/') ] )
        full_url = "http://chomikuj.pl/%s%s" % ( self.chomik_name, url )
        full_url = full_url.replace( '%', '*' )

        response = self.browser.open( full_url )
        text = response.read()

        soup = BeautifulSoup( text )
        self.token = str( soup.find( 'input', { 'name': '__RequestVerificationToken' })['value'] )
        if not self.token:
            self.check_directory( url )

        try:
            title = soup.find( 'div', { 'class': 'frameHeaderNoImage frameHeader borderTopRadius' } ).h1.a.string
            if name == title:
                form = soup.find( 'form', id='FileListForm' )
                id = form.find( 'input', { 'name': 'folderId' } )['value']

                self._cached_directories[url] = id
                return id, full_url
        except:
            pass

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
    }
    def create_directory( self, url ):
        url = url[1:] if url.startswith( '/' ) else url
        folder_id = "0"
        dir_route = []
        for folder in url.split( '/' ):
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
                folder_id, full_url = self.check_directory( '/'.join( dir_route ).decode( 'latin1' ) )

        return folder_id, full_url

    def copy_directory_tree( self, url, db=None, captcha='' ):
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
        
        if self.captcha_attempt >= 3:
            self.logger.info( "diconnecting for new captcha ..." )
            self.diconnect()
            self.connect()
            self.captcha = None
            self.captcha_attempt = 0
            self.captcha_latest = []

        self.captcha_latest = filter ( lambda a: a != self.captcha, self.captcha_latest )

        captcha_url = "http://chomikuj.pl%s" % captcha_src
        captcha_filename = "%s-captcha.jpg" % self.chomik_id

        count = 0
        while count < 10:
            self.logger.debug( "READING CAPTCHA, ATTEMPT: %s" % self.captcha_attempt )

            file = open( captcha_filename, mode='wb' )
            file.write( self.browser.open_novisit( captcha_url ).read() )
            file.close()

            from tools.captcha import read_captcha
            captcha = read_captcha( captcha_filename )
            if captcha and len( captcha ) == 5:
                self.captcha_latest.append( captcha )

            count+=1
            most_common = collections.Counter( self.captcha_latest ).most_common()
            self.logger.debug( '%s, %s' % (count, most_common ) )

        if len( most_common ) and most_common[0][1] >= 2:
            captcha = most_common[0][0]
        else:
            captcha = len( self.captcha_latest ) and self.captcha_latest[0]

        self.captcha = captcha
        return captcha

    def search( self, query, type='Video' ):
        page = 0
        results = []
        has_next = True

        while has_next:
            page += 1
            response = self.browser.open( 'http://chomikuj.pl/action/SearchFiles?FileName=%s&FileType=%s&Page=%d' % ( urllib.quote_plus( query.encode( 'utf-8' ) ), type, page ) )

            soup = BeautifulSoup( response.read() )
            self.token = soup.find( 'input', { 'name': '__RequestVerificationToken' })['value'] # TODO

            has_next = page < 3 and soup.find( 'a', { 'class': 'right' } )

            for div in soup.findAll( 'div', { 'class': 'filerow fileItemContainer' } ):
                a = div.find( 'a', { 'class': 'expanderHeader downloadAction'} )
                id = div.find( 'div', { 'class': 'fileActionsButtons clear visibleButtons  fileIdContainer' } )['rel']
                size = div.find( 'ul', { 'class': 'borderRadius tabGradientBg' } ).li.span.string
                results.append( dict( title=a['title'], id=id, url="http://chomikuj.pl%s" % a['href'], size=size ) )

        return results

    def clone( self, file_id, folder_id ):
        if not self.token:
            self.search( 'asdsd asd asd as da sdasd' )#TODO
        time.sleep( 2 )
        self._create_form( 'http://chomikuj.pl/action/content/copy/CopyFile', [
            { 'name': 'ChomikId', 'type': 'hidden', 'value': self.chomik_id, 'args': {} },
            { 'name': 'chosenFile.FileId', 'type': 'hidden', 'value': str( file_id ), 'args': {} },
            { 'name': 'chosenFile.FolderSelection', 'type': 'text', 'value': '2', 'args': {} },

            { 'name': 'SelectedFolderId', 'type': 'text', 'value': str( folder_id ), 'args': {} },
            { 'name': '__RequestVerificationToken', 'type': 'hidden', 'value': self.token, 'args': {} },
        ])

        response = self.browser.submit()
        print response.read()

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
