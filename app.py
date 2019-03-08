from flask import Blueprint
from flask import Flask
from flask_restful import Api
from flask_restful import Resource
from flask import request
import json
import postgres_server as postgres
import re
from math import ceil as roundup
# from pdb import set_trace

app = Flask(__name__)
# app.config.from_object("config")
api_bp = Blueprint('api', __name__)
api = Api(api_bp)

db = postgres.DBconnector()
db.connect()


defaultResponse = {'payload': 'error'}, 401


class Validator:
	"""Helper methods to validate incoming request parameters"""

	@staticmethod
	def validatePayload(q, request):
		"""Check content type of query and normalize to standard payload structure"""
		assert type(q) is str
		# Queries with subtitutions must have the format {var.type} for input validation purposes.
		formatType = Validator.getFormatType(request)
		if formatType == 'str':
			items = request.args.items()
			payload = {}
			[payload.update({item[0]: item[1]}) for item in items]
		elif formatType == 'json':
			payload = request.get_json()
			payload = json.loads(payload) if payload else None
		elif formatType == 'urlencoded':
			payload = {item:request.form[item] for item in request.form}
			if payload is None:
				items = request.args.items()
				payload = {}
				[payload.update({item[0]: item[1]}) for item in items]
		newQuery, expectedParamsAndTypes = Validator.extractQueryParams(q)
		payload = Validator.validateJsonRequestParams(payload, expectedParamsAndTypes, formatType)
		return (payload, newQuery)

	@staticmethod
	def getFormatType(request):
		contentType = request.content_type

		if contentType == 'application/json':
			return 'json'
		elif contentType == 'application/x-www-form-urlencoded':
			return 'urlencoded'
		elif contentType is None:
			return 'str'

	@staticmethod
	def extractQueryParams(q):
		assert type(q) is str
		expectedParams = re.findall(r'\{.*?\}',q)
		expectedParamsAndTypes = {}
		for expectedParam in expectedParams:
			expectedParam = expectedParam.replace('{','').replace('}','')
			expectedParam = expectedParam.split('.')
			expectedParamsAndTypes.update({expectedParam[0]: eval(expectedParam[1])})  # Strictly controlled use of eval().
		newQuery = re.sub(r'\..*?\}','}', q)
		return (newQuery, expectedParamsAndTypes)

	@staticmethod
	def validateJsonRequestParams(payload, expectedParamsAndTypes, formatType):
		assert type(payload) is dict
		assert type(expectedParamsAndTypes) is dict

		result = None
		payloadParams = payload.keys()
		if payloadParams:
			expectedParams = expectedParamsAndTypes.keys()
			if len(payloadParams) >= len(expectedParams):
				# for payloadParam in payloadParams:
				for expectedParam in expectedParamsAndTypes:
					if expectedParam not in payloadParams:
						return None

					param = payload[expectedParam]

					if formatType == 'str' or formatType == 'urlencoded':
						try:  # Edge case where string parameters cannot be properly cast (i.e. string decimal into an int)
							payload[expectedParam] = expectedParamsAndTypes[expectedParam](param)  # Cast string value into expected type
						except:
							return None
					elif formatType == 'json':
						if type(param) != expectedParamsAndTypes[expectedParam]:
							return None

				result = payload
				assert type(payload) is dict
		return result


class ScooterAvailability(Resource):
	def get(self):
		"""Return list of available scooters in terms of id, lat, and lng"""
		dataResponse = defaultResponse
		q = """SELECT row_to_json(t) FROM (SELECT "id", "lat", "lon" as lng FROM "scooters"
				WHERE ST_Distance(location, ST_MakePoint({lng.float}, {lat.float})) <= {radius.float}
				AND "is_reserved" = false) t"""
		payload, newQuery = Validator.validatePayload(q, request)
		if payload:
			dataResponse = getQueryResponse(payload, newQuery, queryType='query')
		return dataResponse


class ScooterReserve(Resource):
	def post(self):
		"""Mark a scooter as reserved and return success or fail status boolean"""
		dataResponse = defaultResponse
		q = """UPDATE scooters
				SET is_reserved = true
				WHERE id={id.int}
				AND is_reserved = false
				RETURNING true"""
		payload, newQuery = Validator.validatePayload(q, request)
		if payload:
			dataResponse = getQueryResponse(payload, newQuery, queryType='update')
		# print(dataResponse)
		return dataResponse


class ScooterEnd(Resource):
	def post(self):
		"""Mark a scooter as not reserved and return success or fail status boolean. Also charge customer and update scooter location."""
		dataResponse = defaultResponse
		q = """	UPDATE scooters
				SET is_reserved = false
				WHERE id={id.int}
				AND is_reserved = true
				RETURNING true;
				"""
		payload, newQuery = Validator.validatePayload(q, request)
		if payload:
			# End reservation success code
			dataResponse = getQueryResponse(payload, newQuery, queryType='update')

		if dataResponse[0]:
			q = """SELECT ST_Distance(location, ST_MakePoint({endlng.float}, {endlat.float})) FROM scooters WHERE id = {id.int}"""
			payload, newQuery = Validator.validatePayload(q, request)
			if payload:
				# Charge customer and update scooter location.
				distanceTraveled = getQueryResponse(payload, newQuery, queryType='query')[0]
				distanceTraveled = distanceTraveled[0]
				while type(distanceTraveled) is tuple:
					distanceTraveled = distanceTraveled[0]
				distanceTraveled = roundup(distanceTraveled) if distanceTraveled > 0 else 1  # Min distance traveled is always 1.
				pricePerMeter = 1.0  # Ideally, this value is should not be hard coded
				fareCost = pricePerMeter * distanceTraveled

				q = """UPDATE users
					SET (last_fare, fares, scooter_ids, distances_traveled) = ({fareCost}::real, array_append(fares, {fareCost}::real),
															array_append(scooter_ids, {id.int}::bigint),
															array_append(distances_traveled, {distanceTraveled}::bigint))
					WHERE id={userid.int};

					UPDATE scooters
					SET (lon, lat, distances_traveled, rider_ids, location) = ({endlng.float}, {endlat.float},
																		array_append(distances_traveled, {distanceTraveled}::bigint),
																		array_append(rider_ids, {userid.int}::bigint),
																		ST_POINT({endlng.float}, {endlat.float}))
					WHERE id = {id.int};

					"""
				q = q.replace('{fareCost}', str(fareCost)).replace('{distanceTraveled}', str(distanceTraveled))  # Partial format subtitution

				payload, newQuery = Validator.validatePayload(q, request)
				if payload:
					_ = getQueryResponse(payload, newQuery, queryType='update')

		return dataResponse


class UserTrips(Resource):
	def get(self):
		"""Return a summary of a user's trip"""
		dataResponse = defaultResponse
		q = """SELECT row_to_json(t)
				FROM (SELECT id,
					last_fare,
					(SELECT SUM(s) FROM UNNEST("fares") s) as total_fares,
					(SELECT SUM(s) FROM UNNEST("scooter_ids") s) as total_trips,
					(SELECT SUM(s) FROM UNNEST("distances_traveled") s) as total_distance_traveled
				FROM users
				WHERE id = {userid.int}) t"""

		payload, newQuery = Validator.validatePayload(q, request)
		if payload:
			dataResponse = getQueryResponse(payload, newQuery, queryType='query')

		return dataResponse


class ScooterTrips(Resource):
	def get(self):
		"""Return a summary of a scooter's trips"""
		dataResponse = defaultResponse
		q = """SELECT row_to_json(t)
				FROM (SELECT id,
					is_reserved,
					(SELECT SUM(s) FROM UNNEST("rider_ids") s) as total_ride_sessions,
					lat as last_lat,
					lon as last_lng,
					(SELECT SUM(s) FROM UNNEST("distances_traveled") s) as total_distance_traveled
				FROM scooters
				WHERE id = {id.int}) t"""

		payload, newQuery = Validator.validatePayload(q, request)
		if payload:
			dataResponse = getQueryResponse(payload, newQuery, queryType='query')

		return dataResponse


class Default(Resource):
	def get(self):
		return 404


def getQueryResponse(payload, newQuery, queryType='query'):
	"""Execute Postgres command and return data response"""
	assert type(payload) is dict
	assert type(newQuery) is str
	assert type(queryType) is str

	dataResponse = None, 200

	if payload:
		if queryType == 'query':
			data = executeQuery(payload, newQuery)
			if data:
				data = [d[0] for d in data]
		elif queryType == 'update':
			data = executeUpdate(payload, newQuery)
			if data:
				data = [d[0] for d in data]
			else:
				data = [False]

		assert type(data) is list

		dataResponse = data, 200

	return dataResponse


def executeUpdate(payload, newQuery):
	"""Execute Update command and return data (if applicable)"""
	q = newQuery.format(**payload)
	db.execute(q)
	data = db.fetchall()
	return data


def executeQuery(payload, newQuery):
	"""Execute query command and return data"""
	q = newQuery.format(**payload)
	db.query(q)
	data = db.fetchall()
	return data

# Route
api.add_resource(ScooterAvailability, '/api/v1/scooters/available')
api.add_resource(ScooterReserve, '/api/v1/scooters/reserve')
api.add_resource(ScooterEnd, '/api/v1/scooters/end')
api.add_resource(UserTrips, '/api/v1/users/trips')
api.add_resource(ScooterTrips, '/api/v1/scooters/trips')
