import os
import sys
import sqlite3 as lite

if getattr( sys, 'frozen', None ):
    BASE_DIR = os.path.dirname( sys.executable )
else:
    BASE_DIR = os.path.abspath( os.path.dirname( __file__ ) )

class Db( object ):

    DB_NAME = os.path.join( BASE_DIR, 'chomik.db' )

    @classmethod
    def get_connection( cls ):
        if getattr( cls, '__connection', None ) is None:
            cls.__connection = lite.connect( cls.DB_NAME )
        return cls.__connection

    @classmethod
    def get_cursor( cls ):
        return cls.get_connection().cursor()

    @classmethod
    def execute( cls, query, values=(), commit=False ):
        cursor = cls.get_cursor()
        connection = cls.__connection
        cursor.execute( query, values )
        if commit:
            connection.commit()
        return cursor

    @classmethod
    def executescript( cls, query ):
        cursor = cls.get_cursor()
        connection = cls.__connection
        cursor.executescript( query )
        connection.commit()

    @classmethod
    def fetchone( cls, query, values=() ):
        cursor = cls.execute( query, values )
        return cursor.fetchone()

    @classmethod
    def fetch( cls, query, values=(), headers=False ):
        cursor = cls.execute( query, values )
        result = cursor.fetchall()
        if headers:
            result.reverse()
            result.append( [ cn[0] for cn in cursor.description ] )
            result.reverse()
        return result

