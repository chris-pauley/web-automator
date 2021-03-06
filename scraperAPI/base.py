import json
from scraperAPI.utils import map_row
from scraperAPI.database import MySQLDB, sqliteDB

class Config:
	config = {}
	instance = None
	def __init__(self, config_json=None, config_filename='config.json'):
		if not Config.instance:
			if config_json is None:
				with open(config_filename) as config_file:
					self.config = json.load(config_file)
			else:
				self.config = config_json
			Config.instance = self.config
	
	def __getattr__(self,name):
		return getattr(self.instance, name)
	
	def __getitem__(self, idx):
		return Config.instance[idx]

# Singleton DB connection so I don't leave a million open
class APIDBConnection:
	instance = None
	def __init__(self):
		if not APIDBConnection.instance:
			config = Config()
			if 'db_filename' in config.keys():
				self.connection = sqliteDB(config)
			else:
				self.connection = MySQLDB(config)
			APIDBConnection.instance = self.connection

	def __getattr__(self, name):
		return getattr(APIDBConnection.instance, name)


# Gives every type a DB connection and basic functionality
class APIEndpoint(object):
	default_limit = 250
	type_name=''
	
	def __init__(self):
		self.conn = APIDBConnection()
		self.c = self.conn.cursor()
		
		self.type_description = self.c.table_definition(self.type_name)

	def limit_fields(self, fields):
		if isinstance(fields, dict):
			final_fields = {}
			for field in fields.keys():
				if field in self.type_description.keys():
					final_fields[field] = fields[field]
			return final_fields
		elif isinstance(fields, list):
			final_fields = []
			for field in fields:
				if field in self.type_description.keys():
					final_fields.append(field)
			return final_fields
		return None

	def get_all(self, limit=None, sort=None, sort_direction='DESC'):
		all_results = []
		limit = limit or self.default_limit
		self.c.buildAndExecute(action='select', table=self.type_name, fields=self.type_description, limit=limit, sort=sort, sort_direction=sort_direction)
		
		query_description = self.c.description()

		for raw in self.c.fetchall():
			row = map_row(query_description, raw)
			all_results.append(row)

		return all_results

	def get_by_fields(self, fields=None, field='', value='', sort=None, sort_direction='DESC'):
		where_dict = {}
		if fields is None:
			where_dict[field] = value
		else:
			where_dict = fields
		self.c.buildAndExecute(action='select', table=self.type_name, fields=self.type_description, where=where_dict, sort=sort, sort_direction=sort_direction)
		
		query_description = self.c.description()

		all_results = []
		for raw in self.c.fetchall():
			row = map_row(query_description, raw)
			all_results.append(row)

		return all_results

	def update_or_insert(self, fields, where_key="id", allow_nulls=True):
		existing_items = []

		fields = self.limit_fields(fields)

		if not allow_nulls:
			to_loop = fields.keys()
			for field in to_loop:
				if fields[field] is None:
					del fields[field]

		if where_key in fields:
			existing_items = self.get_by_fields(field=where_key, value=fields[where_key])

		if len(existing_items) > 0:
			self.update_by_fields(fields, where_key=where_key)
		else:
			self.c.buildAndExecute(action='insert', table=self.type_name, fields=fields)
			self.conn.commit()
		return self.c.lastrowid()

	def update_by_fields(self, item, fields=None, where_key='id'):	
		fields = self.limit_fields(fields)

		if fields is None and where_key is not None and where_key in item:
			fields = {}
			fields[where_key] = item[where_key]

		self.c.buildAndExecute(action='update', table=self.type_name, fields=item, where=fields)
		self.conn.commit()
		return self.c.lastrowid()
	
	def insert(self, item, ignore=False):
		item = self.limit_fields(item)
		self.c.buildAndExecute(action='insert', table=self.type_name, fields=item, ignore=ignore)
		self.conn.commit()
		return self.c.lastrowid()

	def insert_many(self, items):
		return_ids = []
		for item in items:
			item = self.limit_fields(item)
			self.c.buildAndExecute(action='insert', table=self.type_name, fields=item)
			return_ids.append(self.c.lastrowid())
		self.conn.commit()
		return return_ids
