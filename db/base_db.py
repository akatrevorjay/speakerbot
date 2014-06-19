import sqlite3
import MySQLdb
import re

from collections import OrderedDict

class base_db(object):

    def __init__(self, settings=None):

        if settings and type(settings) == "str":
            db_path = settings
            settings = {
                'driver':'sqlite3',
                'db_path':db_path
            }

        self.settings = settings

        if self.settings['driver'] == "sqlite3":

            self.conn = sqlite3.connect(db_path, check_same_thread=False)
            self.conn.row_factory = self.mysql_row_factory

        if self.settings['driver'] == "mysql":
            self.conn = MySQLdb.connect(host=self.settings['host'], user=self.settings['user'], passwd=self.settings['pass'], db=self.settings['database'])
            self.conn.cursor().execute("SET AUTOCOMMIT=1;")

        self.version = self.get_version()

        self.migrations = self.get_migrations()

        self.run_migrations()

    def row_factory(self, cursor, row):

        row_dict = OrderedDict()
        for idx, column in enumerate(cursor.description):
            row_dict[column[0]] = row[idx]
        return row_dict

    def rs_generator(self, results):

        class ResultSet(object):
            def __init__(self, results=None):
                self.results = results
                self.generator = self.self_generator()

            def self_generator(self):
                for result in self.results:
                    print "yielding"
                    yield result

            def __iter__(self):
                return self

            def next(self):
                return self.generator.next()

            def fetchone(self):
                try:
                    result = self.generator.next()
                except StopIteration:
                    result = None

                return result
            def fetchall(self):
                return self.results

        r = ResultSet(results)
        return r

    def update_version(self, version):
        
        self.version = version
        self.execute("update db_version set version = ?", [version])

    def fix_for_mysql(self, statement):

        statement = statement.replace("?","%s")
        statement = re.sub("random\(\)","RAND()", statement, flags=re.I)

        print statement

        return statement
    
    def execute(self, statement, query_vars=None):

        if not query_vars:
            query_vars = []

        if self.settings['driver'] == "mysql":
            cursor = self.conn.cursor(MySQLdb.cursors.DictCursor)
            statement = self.fix_for_mysql(statement)
            cursor.execute(statement, tuple(query_vars))
            result = self.rs_generator(cursor.fetchall())

        if self.settings['driver'] == "sqlite3":

            result = self.conn.execute(statement, query_vars)
            self.conn.commit()

        return result

    def run_migrations(self):

        for migration in self.migrations[self.version:]:
            new_version = self.version + 1
            print "updating to version %s" % new_version
            migration()
            self.update_version(new_version)
    
    def get_migrations(self):

        migrations = []

        for elem in dir(self):

            if elem[:8] == "_migrate":
                migrations.append(getattr(self, elem))

        migrations.sort(key=lambda f: int(f.__name__[9:]))

        return migrations
       
    def get_version(self):

        try:
            version_cursor = self.execute("select version from db_version limit 1")
            result = version_cursor.next()
        except sqlite3.OperationalError:
            return 0

        except StopIteration:
            return 0

        return int(result["version"])