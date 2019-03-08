# See https://docs.python.org/2/library/struct.html for byteFormatChar settings
# Note that strings require special formatting:
# >>> stringByteSize = len(somestr)
# >>> dm_exp_stage.append_buffer([somestr], [['{0}s'.format(stringByteSize), stringByteSize]])

import psycopg2
import dbconstants_server as dbconstants
from io import BytesIO
from struct import pack
from pdb import set_trace
# byteFormatChars take the format of: [['q', 8], ['q', 8], ['d', 8], ['d', 8], ['d', 8], ['d', 8], ['d', 8], ['q', 8], ['q', 8], ['q', 8], ['q', 8]]


class DBconnector(object):
	def __init__(self):
		self._dbParams = {'dbname':dbconstants.DB_NAME,
					'user':dbconstants.DB_USER,
					'password':dbconstants.DB_PASSWORD,
					'host':dbconstants.HOST,
					'port':dbconstants.PORT,
					'sslmode':dbconstants.SSLMODE}

		self._connection = None
		self._queriedCursor = None

	def connect(self):
		self._connection = psycopg2.connect(**self._dbParams)

	def query(self, query):
		self.cursor = self._connection.cursor()
		self.cursor.execute(query)
		self._data = self.cursor.fetchall()
		self.cursor.close()

	# def write(self, command, values=[[]]):
	# 	values = tuple(values)
	# 	fieldCount = len(values[0])
	# 	subs = '%s,' * fieldCount
	# 	subs = subs[:len(subs)-1]
	# 	cursor = self._connection.cursor()
	# 	values = ','.join(cursor.mogrify('({subs})'.format(subs=subs), row) for row in values)
	# 	cursor.close()
	# 	command = command.format(values=values)
	# 	self.execute(command)

	def insert(self, values, fields, table, onConflictDoNothing=False, returnFields=[]):
		assert len(values[0]) == len(fields), 'Number of fields and number of entries across row values do not match.'
		fieldCount = len(fields)
		fields = str(tuple(fields))
		fields = fields.replace("'", '"')
		if fieldCount == 1:
			fields = fields.replace('",)', '")')
		rFields = ','.join(returnFields)
		subs = '%s,' * fieldCount
		subs = subs[:len(subs)-1]
		cursor = self._connection.cursor()
		values = ','.join(cursor.mogrify('({subs})'.format(subs=subs), row) for row in values)
		cursor.close()
		command = """
				INSERT INTO "{table}" {fields} VALUES {values}
				{onConflictCommand}
				{returnCommand}
				"""
		if onConflictDoNothing:
			onConflictCommand = 'ON CONFLICT DO NOTHING'
		else:
			onConflictCommand = ''

		if returnFields:
			returnCommand = 'RETURNING ' + rFields
		else:
			returnCommand = ''

		command = command.format(table=table, fields=fields, values=values, onConflictCommand=onConflictCommand, returnCommand=returnCommand)
		return self.execute(command)

	def update(self, values, fields, table, condition=''):
		# WARNING THIS MAY NOT WORK!
		fields = ','.join(fields)
		if condition:
			conditionCommand = 'WHERE {condition}'.format(condition)
		else:
			conditionCommand = ''

		command = """
				UPDATE {table}
				d ({fields}) = {values}
				{conditionCommand}
				"""
		command = command.format(table=table, fields=fields, values=values, conditionCommand=conditionCommand)
		return self.execute(command)

	def upsert(self, values, fields, table, keys=[]):
		whereClause = self._createWhereClause(keys)
		setClause = self._createSetClause(fields)
		fieldCount = len(fields)
		fields = str(tuple(fields))
		fields = fields.replace("'", '"')
		if fieldCount == 1:
			fields = fields.replace('",)', '")')
		keys = ','.join(keys)
		subs = '%s,' * fieldCount
		subs = subs[:len(subs)-1]
		cursor = self._connection.cursor()
		values = ','.join(cursor.mogrify('({subs})'.format(subs=subs), row) for row in values)
		cursor.close()
		# command = """
		# 		INSERT INTO {table} {fields} VALUES {values}
		# 		ON CONFLICT ({keys})
		# 		DO UPDATE SET {fields} = {values}
		# 		"""
		# command = command.format(table=table, fields=fields, values=values, keys=keys)
		# self.execute(command)

		commandUpdate = """
				UPDATE {table} AS desttable
				SET {setClause}
				FROM (VALUES {values}) AS sourcetable{fields}
				WHERE {whereClause}
				"""

		commandInsert = """
				INSERT INTO {table} {fields}
				VALUES {values}
				ON CONFLICT DO NOTHING
				"""
		self.execute(commandUpdate.format(table=table, setClause=setClause, values=values, fields=fields, whereClause=whereClause))
		self.execute(commandInsert.format(table=table, fields=fields, values=values))

	def _createSetClause(self, fields):
		setClause = ''
		templateClause = '"{field}" = sourcetable."{field}"'
		for i, field in enumerate(fields):
			if i == 0:
				setClause += templateClause.format(field=field)
			elif i > 0:
				setClause += ', ' + templateClause.format(field=field)

		return setClause

	def _createWhereClause(self, keys):
		whereClause = ''
		templateClause = 'sourcetable."{key}" = desttable."{key}"'
		for i, key in enumerate(keys):
			if i == 0:
				whereClause += templateClause.format(key=key)
			elif i > 0:
				whereClause += ' AND ' + templateClause.format(key=key)

		return whereClause

	def execute(self, command):
		"""Execute arbitrary command. Only use for purely internal facing programs."""
		cursor = self._connection.cursor()

		try:
			cursor.execute(command)
			self._connection.commit()
			self._data = cursor.fetchall()
		except Exception as e:
			pass
			# print(command)
			# print(e.pgerror)
			# set_trace()
		cursor.close()

	def executemany(self, command, datarows):
		"""Execute arbitrary command. Only use for purely internal facing programs."""
		cursor = self._connection.cursor()

		try:
			cursor.executemany(command, datarows)
			self._connection.commit()
		except Exception as e:
			pass
			# print(command)
			# print(e.pgerror)
		cursor.close()

	def fetchall(self):
		data = self._data
		self._data = None
		return data

	def close(self):
		try:
			self._connection.close()
		except:
			print('Unable to close connection.')
