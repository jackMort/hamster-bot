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
import atexit
import random
import readline

from threading import Thread
from termcolor import colored
from texttable import Texttable
from colorama import init as colorama_init

from db import Db
from chomikuj import Chomik, CaptchNeededException


# INIT CONSOLE
colorama_init()

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


class ChomikThread( Thread ):
    def __init__( self, id, login, password, strategy ):
        Thread.__init__( self )

        self.id = id
        self.login = login
        self.password = password
        self.strategy = strategy

        self.chomik = Chomik( login, password )

    def run( self ):
        if self.strategy == 'film_db': #TODO
            self.chomik.connect()

            LETTERS = map( chr, range( 65, 91 ) )
            movies = []
            
            file = open( 'db/movies.list', 'r' )
            for line in file.readlines():
                title = line.split('\t')[0].decode( 'latin1' )
                first_letter = title[0]
                FIRST_LETTER = first_letter.upper()
                if FIRST_LETTER in LETTERS:
                    movies.append( title )
            file.close()

        random.shuffle( movies )
        for title in movies:
            FIRST_LETTER = title[0].upper()
            if not server.db.fetchone( "SELECT * FROM folders WHERE user_id=? AND name=?", ( self.id, title ) ):
                id, url = self.chomik.create_directory( 'Filmy/%s/%s' % ( FIRST_LETTER, title ) )
                if id and url:
                    server.db.execute( "INSERT INTO folders VALUES (?, ?, ?, ?)", ( id, self.id, title, url ), commit=True )


        else:
            pass


class CommandError( Exception ):
    pass

class Command( object ):
    TEXT = 1
    INT = 2
    FLOAT = 3

    ARGS = {}
    def __init__( self, server, *args ):
        self.server = server
        if len( args ) != len( self.ARGS.keys() ):
            raise CommandError( "Bad arguments: use %s %s" % ( self.name, self.ARGS.keys() ) )

        i = 0
        for name, type in self.ARGS.items():
            setattr( self, name, args[i] )
            i += 1
    
    def execute( self ):
        pass

class HelpCommand( Command ):
    name = 'help'

class QuitCommand( Command ):
    name = 'quit'

    def execute( self ):
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
    ARGS = {
        'type': Command.TEXT,
        'name': Command.TEXT,
        'password': Command.TEXT,
    }

    def execute( self ):
        self.server.db.execute( "INSERT INTO users(login, password) VALUES ('%s', '%s');" % ( self.name, self.password ), commit=True )
        print "user added!"



class ChomikServer( object ):

    commands = {
        'help': HelpCommand,
        'quit': QuitCommand,
        'list': ListCommand,
        'add' : AddCommand,
    }

    def __init__( self ):
        self.db = Db
        self.threads = {}

    def run( self ):
        print
        print "####################################"
        print "#         HAMSTER BOT v 2.0        #"
        print "####################################"
        print

        self.check_db()
        users = self.db.fetch( "SELECT * FROM users;" )
        self.log( "starting background strategy" )
        for user in users:
            id, chomik_id, login, password, strategy = user
            self.threads[login] = ChomikThread( id, login, password, strategy )
            self.threads[login].setName( login )
            self.threads[login].start()

        print 
        while True:
            command = AInput( "CHOMIK_BOT> ").getString()
            self.parse_command( command )

    def check_db( self ):
        self.log( "checking db structure ..." )

        self.db.executescript(
        """
        CREATE TABLE IF NOT EXISTS users ( id INTEGER PRIMARY KEY, chomik_id INT, login TEXT, password TEXT, strategy TEXT );
        CREATE TABLE IF NOT EXISTS folders ( id INTEGER, user_id INTEGER, name TEXT, url TEXT );

        DELETE FROM users;
        INSERT INTO users VALUES ( 1, 0, 'top_chomik', 'Robinhooj752!', 'film_db' );
        """
        )

    def parse_command( self, command ):
        parts = command.split()
        command, args = parts[0], parts[1:]
        if command:
            if command in self.commands.keys():
                self.commands[command]( self, *args ).execute()
            else:
                print colored( " Unknown command [%s] ..." % command, 'red', attrs=['bold'] )

    def log( self, msg ):
        print " --- %s" % msg

if __name__ == "__main__":
    server = ChomikServer()
    server.run()

# vim: fdm=marker ts=4 sw=4 sts=4
