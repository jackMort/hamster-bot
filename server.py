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
import gc
import sys
import time
import atexit
import random
import readline
import multiprocessing

from termcolor import colored
from texttable import Texttable
from imdb.utils import analyze_title
from colorama import init as colorama_init

from db import Db
from chomikuj import Chomik, CaptchNeededException


# INIT CONSOLE
colorama_init()

if not os.environ.has_key('HOME'):
    os.environ['HOME'] = os.path.join(os.environ['HOMEDRIVE'], \
                                           os.environ['HOMEPATH'])

history_file = os.path.join(os.environ['HOME'], '.chomik_history')
try:
    readline.read_history_file(history_file)
except IOError:
    pass
readline.set_history_length(1000)
atexit.register(readline.write_history_file, history_file)


class AInput:  # We can't use input as it is a existent function name, so we use AInput for Advance Input
   ''' This class will create a object with a simpler coding interface to retrieve console input'''
   def __init__(self, msg="", req=0):
      ''' This will create a instance of ainput object'''
      self.data = ""  # Initialize a empty data variable
      if not msg == "":
         self.ask(msg, req)
 
   def ask(self, msg, req=0):
      ''' This will display the prompt and retrieve the user input.'''
      if req == 0:
         self.data = raw_input(msg)  # Save the user input to a local object variable
      else:
         self.data = raw_input(msg + " (Require)")
 
      # Verify that the information was entered and its not empty. This will accept a space character. Better Validation needed
      if req == 1 and self.data == "":
         self.ask(msg, req)
 
   def getString(self):
      ''' Returns the user input as String'''
      return self.data
 
   def getInteger(self):
      ''' Returns the user input as a Integer'''
      return int(self.data)
 
   def getNumber(self):
      ''' Returns the user input as a Float number'''
      return float(self.data)


def run_chomik_thread( *args, **kwargs ):
    thread = ChomikThread( *args, **kwargs )
    return thread.run()

class ChomikThread( object ):
    def __init__( self, id, login, password, strategy ):
        self.id = id
        self.login = login
        self.password = password
        self.strategy = strategy

        self.chomik = Chomik( login, password )

    def run( self ):
        try:
            if self.strategy == 'film_db': #TODO
                self.chomik.connect()

                movies = []
                file = open( 'db/movies.list', 'r' )
                for line in file.readlines():
                    title = line.split('\t')[0].decode( 'latin1' )
                    analized = analyze_title( title )
                    title = analized['title']

                    if analized['kind'] in ( 'movie', 'tv series', 'tv movie', 'tv mini series', 'episode' ):
                        movies.append( analized )

                file.close()

                random.shuffle( movies )
                for movie in movies:

                    title = movie['title'].replace( '/', '\\')
                    year = movie['year'] if movie.has_key( 'year' ) else ''

                    FIRST_LETTER = title[0].upper()
                    if movie['kind'] == 'episode':
                        pattern1 = [
                            'Seriale',
                            'Alfabetycznie',
                            movie['episode of']['title'][0].upper(),
                            movie['episode of']['title'] + ' (%s)' % movie['episode of']['year'] if movie['episode of'].has_key( 'year' ) else '', 
                        ]
                        if movie.has_key( 'season' ):
                            pattern1.append( 'Sezon %s' % movie['season'] )
                        if movie.has_key( 'episode' ):
                            pattern1.append( 'Odcinek %s, %s' % ( movie['episode'], movie['title'] ) )
                        else:
                            pattern1.append( title )
                        pattern1 = '/'.join( pattern1 )
                            
                        patterns = [ pattern1 ]
                        if movie['episode of'].has_key( 'year' ):
                            pattern2 = [
                                'Seriale',
                                'Chronologicznie',
                                str( movie['episode of']['year'] ), 
                                movie['episode of']['title'] + ' (%s)' % movie['episode of']['year'] if movie['episode of'].has_key( 'year' ) else '', 
                            ]
                            if movie.has_key( 'season' ):
                                pattern2.append( 'Sezon %s' % movie['season'] )
                            if movie.has_key( 'episode' ):
                                pattern2.append( 'Odcinek %s, %s' % ( movie['episode'], movie['title'] ) )
                            else:
                                pattern2.append( title )
                            pattern2 = '/'.join( pattern2 )
                            patterns.append( pattern2 )

                    else:
                        title = '%s (%s)' % ( title, year ) if year else title
                        if movie['kind'] in ( 'tv series', 'tv mini series' ):
                            folder = 'Seriale'
                        else:
                            folder = 'Filmy'

                        full_title = ( "%s (%s)" % ( movie['title'], year ) ).decode( 'latin1' )
                        patterns = ( '%s/Alfabetycznie/%s/%s' % ( folder, FIRST_LETTER, title ), 
                                     '%s/Chronologicznie/%s/%s' % ( folder, year, title ) 
                                   )

                    if not Db.fetchone( "SELECT * FROM folders WHERE user_id=? AND name=?", ( self.id, title ) ):

                        good = []
                        if movie['kind'] in ( 'movie', 'tv movie' ): # TODO search series
                            sizes = []
                            items = self.chomik.search( full_title )
                            for item in items:
                                if item['title'].lower() == full_title.lower() or item['title'].lower().startswith( full_title.lower() ) or item['title'].lower() == movie['title'].lower() or item['title'].lower == ( '%s %s' % ( movie['title'], year ) ).lower():
                                    if not item['size'] in sizes:
                                        good.append( item )
                                        sizes.append( item['size'] )

                        for pattern in patterns:
                            id, url = self.chomik.create_directory( pattern )
                            if id and url:
                                Db.execute( "INSERT INTO folders VALUES (?, ?, ?, ?)", ( id, self.id, title, url ), commit=True )

                                for item in good:
                                    self.chomik.clone( item['id'], id )

            elif self.strategy == 'smieciarz':
                self.chomik.connect()

                self.generate_other_users()

                users = Db.fetch( "SELECT login from other_users" )
                random.shuffle( users )
                for user in users:
                    url = '/%s' % user
                    full_url = 'http://chomikuj.pl/%s%s' % ( self.login, url )
                    #if not server.db.fetchone( "SELECT * FROM folders WHERE user_id=? AND url=?", ( self.id, full_url ) ):
                    if not self.chomik.check_directory( url )[0]:
                        self.chomik.copy_directory_tree( url )
                        #server.db.execute( "INSERT INTO folders VALUES (?, ?, ?, ?)", ( id, self.id, title, url ), commit=True )

        except Exception, e:
            print e
            self.chomik.logger.exception( e )
            self.chomik.logger.info( "going to sleep for 60 seconds" )
            time.sleep( 60 )

            self.run()

    def generate_other_users( self, limit=10 ):
        users = self.chomik.generate_list( limit, to_file=False )
        for user in users if users else []:
            if not Db.fetchone( "SELECT * FROM other_users WHERE login=?", ( user, ) ):
                Db.execute( "INSERT INTO other_users ( login ) VALUES ( ? )", ( user, ), commit=True )


class CommandError( Exception ):
    pass

class Command( object ):
    TEXT = 1
    INT = 2
    FLOAT = 3

    ARGS = {}
    ARGS_ORDER = []
    DONE = colored( "DONE", 'green', attrs=['bold'] )
    ERROR = colored( "ERROR", 'red', attrs=['bold'] )

    def __init__( self, server, *args ):
        self.server = server
        all_args = []
        required_args = []
        for a, o in self.ARGS.items():
            if not isinstance( o, dict ) or not o.has_key( 'default' ):
                required_args.append( a )
            all_args.append( a )
        
        if len( args ) != len( required_args ) and len( args ) != len( all_args ):
            raise CommandError( "Bad arguments: use %s %s" % ( self.name, self.ARGS_ORDER or self.ARGS.keys() ) )

        i = 0
        order = self.ARGS_ORDER or self.ARGS.keys()
        for name in order:
            setattr( self, name, args[i] if len( args ) >= i+1 else self.ARGS[name].get( 'default', None ) )
            i += 1
    
    def execute( self ):
        pass

class HelpCommand( Command ):
    name = 'help'

class QuitCommand( Command ):
    name = 'quit'

    def execute( self ):
        for login, thread in self.server.threads.items():
            print "stopping %s ... " % colored( login, 'blue', attrs=['bold'] )
            self.server.threads[login].terminate()
        time.sleep( 1 )
        print
        print "GOODBYE ME LITTLE FRIENDOooo !"
        sys.exit( 1 )


class ListCommand( Command ):
    name = 'list'
    ARGS = {
        'type': Command.TEXT,
    }

    def execute( self ):
        count = self.server.db.fetchone( "SELECT count(*) FROM %s;" % self.type )
        items = self.server.db.fetch( "SELECT * FROM %s;" % self.type, headers=True )
        table = Texttable()
        table.add_rows( items )
        print table.draw()
        print " -- %d records." % count
        print


class AddCommand( Command ):
    name = 'add'
    ARGS_ORDER = ['type', 'login', 'password', 'strategy', 'on_start' ]
    ARGS = {
        'type': Command.TEXT,
        'login': Command.TEXT,
        'password': Command.TEXT,
        'strategy': Command.TEXT,
        'on_start': Command.TEXT,
    }

    def execute( self ):
        if not server.db.fetchone( "SELECT * FROM users WHERE login=?", ( self.login, ) ):
            self.server.db.execute( "INSERT INTO users(login, password, strategy, on_start) VALUES ( ?, ?, ?, ? )", ( self.login, self.password, self.strategy, self.on_start ), commit=True )

            print "user %s added ..." % self.login, self.DONE
            return True
        print "user %s already exists ..." % self.login, self.ERROR
        return False

class StopCommand( Command ):
    name = 'stop'

    ARGS = {
        'login': Command.TEXT,
    }

    def execute( self ):
        if not self.server.threads.has_key( self.login ):
            raise CommandError( "Thread '%s' does not exists" % self.login )

        self.server.threads[self.login].terminate()
        sys.stdout.write ( "stopping %s ... " % self.login )
        sys.stdout.flush()
        time.sleep( 2 )
        sys.stdout.write( self.ERROR if self.server.threads[self.login].is_alive() else self.DONE )
        sys.stdout.write( "\n" )
        sys.stdout.flush()

class StartCommand( Command ):
    name = 'start'

    ARGS = {
        'login': Command.TEXT,
    }

    def execute( self ):
        self.server.start_thread( self.login )
        sys.stdout.write ( "starting %s ... " % self.login )
        sys.stdout.flush()
        time.sleep( 2 )
        sys.stdout.write( self.ERROR if not self.server.threads[self.login].is_alive() else self.DONE )
        sys.stdout.write( "\n" )
        sys.stdout.flush()

class RemoveFromStartCommand( Command ):
    name = 'remove-on-start'

    ARGS = {
        'login': Command.TEXT,
    }

    def execute( self ):
        if not server.db.fetchone( "SELECT * FROM users WHERE login=?", ( self.login, ) ):
            print colored( 'user %s does not exit ...', 'red', attrs=['bold'] )
        else:
            server.db.execute( 'UPDATE users set on_start=0 WHERE login=?', ( self.login, ), commit=True )
            print self.DONE

class AddTOStartCommand( Command ):
    name = 'add-on-start'

    ARGS_ORDER = ['login', 'strategy']
    ARGS = {
        'login': Command.TEXT,
        'strategy': Command.TEXT,
    }

    def execute( self ):
        if not server.db.fetchone( "SELECT * FROM users WHERE login=?", ( self.login, ) ):
            print colored( 'user %s does not exit ...', 'red', attrs=['bold'] )
        else:
            server.db.execute( 'UPDATE users set on_start=1, strategy=? WHERE login=?', ( self.strategy, self.login ), commit=True )
            print self.DONE

class StatusCommand( Command ):
    name = 'status'

    def execute( self ):
        alive = colored( "RUNNING", 'green', attrs=[] )
        dead = colored( "STOPPED", 'red', attrs=[] )
        for login, user in self.server.users.items():
            id, login, password, strategy = user
            is_alive = self.server.threads.has_key( login ) and self.server.threads[login].is_alive()
            print " `", login, "using strategy:",strategy, "\t", alive if is_alive else dead


class ClearMemoryCommand( Command ):
    name = 'clear-memory'

    def execute( self ):
        print gc.collect()

class DeleteCommand( Command ):
    name = 'delete'
    ARGS_ORDER = ['type', 'id' ]
    ARGS = {
        'type': Command.TEXT,
        'id': Command.TEXT,
    }

    def execute( self ):
        self.server.db.execute( "DELETE FROM %s WHERE id = ?" % self.type, ( self.id ), commit=True )
        print "%s deleted!" % self.type

class LoadUsersCommand( Command ):
    name = 'load-users'
    ARGS = {
        'file': Command.TEXT,
    }

    def execute( self ):
        file = open( self.file, 'r' )
        for line in file.readlines():
            parts = line.strip().split(':')
            if len( parts ) < 2:
                print "skipping line ...", parts
            else:
                strategy = 'smieciarz'
                on_start = 0
                user = parts[0]
                password = parts[1]
                if len( parts ) > 2:
                    strategy = parts[2]
                    if len( parts ) > 3:
                        on_start = parts[3] == '1'
        
                success = AddCommand( self.server, 'user', user, password, strategy, on_start ).execute()
                if success and on_start:
                    StartCommand( self.server, user ).execute()

        file.close()

class UserStatsCommand( Command ):
    name = 'user-stats'
    ARGS = {
        'login': { 'default': None, 'type': Command.TEXT }
    }

    def execute( self ):
        if self.login:
            user = self.server.db.fetchone( 'SELECT login, password FROM users WHERE login=?', ( self.login, ) )
            if user:
                users = [ user ]
            else:
                raise CommandError( "User %s does not exist" % self.login )

        else:
            users = self.server.db.fetch( 'SELECT login, password FROM users' )

        for user in users:
            print "fetching stats for user %s ..." % colored( user[0], 'green', attrs=['bold'] )
            chomik = Chomik( user[0], user[1] )
            if chomik.connect():
                stats = chomik.get_stats()
                print
                print "  -- points: %s" % colored( stats['points'], 'yellow', attrs=['bold', 'underline'] )
                print "  -- size  : %s" % colored( stats['size'], 'yellow', attrs=['bold', 'underline'] )
                print "  -- files : %s" % colored( stats['files'], 'yellow', attrs=['bold', 'underline'] )
                print
            else:
                print colored( "Error cannot connect ...", 'red', attrs=['bold'] )


class TransferPoints( Command ):
    name = 'transfer-points'
    ARGS_ORDER = ['login', 'to', 'points']
    ARGS = {
        'login': Command.TEXT,
        'to': Command.TEXT,
        'points': { 'default': None, 'type': Command.TEXT }
    }

    def execute( self ):
        user = self.server.db.fetchone( 'SELECT login, password FROM users WHERE login=?', ( self.login, ) )
        if user:
            users = [ user ]
        else:
            raise CommandError( "User %s does not exist" % self.login )

        chomik = Chomik( user[0], user[1] )
        if chomik.connect():
            if chomik.transfer( self.to, self.points ):
                print self.DONE
            else:
                print self.ERROR
        else:
            print colored( "Error cannot connect ...", 'red', attrs=['bold'] )

class TransferAllPoints( Command ):
    name = 'transfer-all-points'
    ARGS_ORDER = ['login']
    ARGS = {
        'login': Command.TEXT,
    }

    def execute( self ):
        all_points = 0
        for user, password in self.server.db.fetch( 'SELECT login, password FROM users WHERE login !=?', (self.login,) ):
            chomik = Chomik( user, password )
            if chomik.connect():
                stats = chomik.get_stats()
                max = chomik.max_points_to_transfer( stats['points'] )
                print "user %s, points: %s, to transfer: %s" % ( colored( user, 'green', attrs=['bold'] ), colored( stats['points'], 'white', attrs=['bold'] ), colored( max, 'white', attrs=['bold'] ) )
                if max > 99:
                    if chomik.transfer( self.login ):
                        print self.DONE
                        all_points += max
                    else:
                        print self.ERROR
            else:
                print colored( "Error cannot connect ...", 'red', attrs=['bold'] )

            print "TRANSFERED: %s" % colored( all_points, 'yellow', attrs=['bold'] ) 


class ChomikServer( object ):

    PROMPT = "%s> " % colored( "CHOMIK_BOT", "white", attrs=['bold'] )

    commands = {
        'help'           : HelpCommand,
        'quit'           : QuitCommand,
        'list'           : ListCommand,
        'add'            : AddCommand,
        'stop'           : StopCommand,
        'start'          : StartCommand,
        'status'         : StatusCommand,
        'load-users'     : LoadUsersCommand,
        'add-on-start'   : AddTOStartCommand,
        'remove-on-start': RemoveFromStartCommand,
        'user-stats'     : UserStatsCommand,
        'clear-memory'   : ClearMemoryCommand,
        'transfer-points': TransferPoints,
        'transfer-all-points': TransferAllPoints,
    }

    def __init__( self ):
        self.db = Db
        self.users = {}
        self.threads = {}

        multiprocessing.freeze_support()

    def run( self ):
        print
        print colored( "####################################", 'white', attrs=['bold'] )
        print colored( "#         HAMSTER BOT v 2.0        #", 'white', attrs=['bold'] )
        print colored( "####################################", 'white', attrs=['bold'] )

        print

        self.check_db()
        users = self.db.fetch( "SELECT * FROM users WHERE on_start=1" )
        self.log( "starting background strategy" )

        for user in users:
            id, chomik_id, login, password, strategy, on_start = user
            self.users[login] = ( id, login, password, strategy )
            self.start_thread( login )

        print 
        while True:
            try:
                command = AInput( self.PROMPT ).getString()
                self.parse_command( command )
            except ( KeyboardInterrupt, EOFError ):
                try:
                    self.parse_command( 'quit' )
                except: pass
            except Exception, e:
                print colored( "Command error: %s" % e, 'red', attrs=['bold'] )

    def start_thread( self, login ):
        if self.threads.has_key( login ) and self.threads[login].is_alive():
            print "%s already runnig ..." % login
            return

        user = self.db.fetchone( "SELECT * FROM users WHERE login=?", ( login, ) )
        if user:
            id, chomik_id, login, password, strategy, on_start = user
            self.users[login] = ( id, login, password, strategy )
            self.threads[login] = multiprocessing.Process( target=run_chomik_thread, args=( id, login, password, strategy ) )
            self.threads[login].start()
        else:
            print "user %s not found ..." % login

    def check_db( self ):
        self.log( "checking db structure ..." )

        self.db.executescript(
        """
        CREATE TABLE IF NOT EXISTS users ( id INTEGER PRIMARY KEY, chomik_id INT, login TEXT, password TEXT, strategy TEXT, on_start INT );
        CREATE TABLE IF NOT EXISTS folders ( id INTEGER, user_id INTEGER, name TEXT, url TEXT );
        CREATE TABLE IF NOT EXISTS other_users ( id INTEGER PRIMARY KEY, login TEXT );
        """
        )

    def parse_command( self, command ):
        parts = command.split()
        if len( parts ):
            command, args = parts[0], parts[1:]
            if command:
                if command in self.commands.keys():
                    self.commands[command]( self, *args ).execute()
                else:
                    print colored( "Unknown command [%s] ..." % command, 'red', attrs=['bold'] )

    def log( self, msg ):
        print " --- %s" % msg

if __name__ == "__main__":
    server = ChomikServer()
    server.run()

# vim: fdm=marker ts=4 sw=4 sts=4
