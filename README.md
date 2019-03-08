The API is live at http://104.248.209.135:8000/, and can be accessed using the GET and POST commands listed below. Additionally, you'll find the ability to end a scooter ride (with an updated coordinate location), view a user's trip and fare history, as well as a scooter's ride history.

Example commands below that can be executed in a linux environment.

```
curl -X GET 'http://104.248.209.135:8000/api/v1/scooters/available?lat=37.788989&lng=-122.404810&radius=200000'
curl -d "id=1" -X POST "http://104.248.209.135:8000/api/v1/scooters/reserve"
curl -d "id=1&userid=1&endlng=-122.404911&endlat=37.8990" -X POST "http://104.248.209.135:8000/api/v1/scooters/end"
curl -d "userid=1" -X GET "http://104.248.209.135:8000/api/v1/users/trips"
curl -d "id=1" -X GET "http://104.248.209.135:8000/api/v1/scooters/trips"
```

Planning and Learning Log
-------------------------
- Mental vizualization of how the situation would work for the user, and possible edge cases to be aware of (like user riding around and returning to same location) that would rule out various naive implementations
- Map out the system requirements for such a use case, and consider a few logical extensions to that use case that can be built in with little extra effort (such as trip analytics)
- How to enable PostGIS Extension
- What WGS84 Standard represents
- Postgres / PostGISHow to return a coordinate point that could be mapped to an interactive image within pgAdmin
- Postgres / PostGISHow to return records within the distance of a point
- Postgres: Append value to array
- Postgres: Return sum of array
- Postgres: Return a single element from array (use slicers for a range)
- Postgres: Return last element from array


Blockers
--------
- Coming up with a partial substitution formatting for an input parameter validation/sanitation scheme
- Postgres remote connection not working - parameter input problem
- pip uwsgi not working - found that a special version compiled for Conda was needed
- uwsgi execution kept returning "python application not found" - The effect of multiple issues (needed flag: --callable app, and uwsgi execution to be run from the app direcctory)


Improvements
------------
Assuming a likely use case for this is mobile device (or the scooter device) communication with a server, I think it would be important to add authentication and encryption features to protect things such as payment transactions and location information (so no one gets stalked), as well as to prevent abuse from unauthorized actors. I would certainly like to add more functionality around scooter and user analytics, as I could see this as necessary for the coordination of large scooter fleets. Additional improvements would be for the API to receive submissions for scooters that are non functioning / in need of repair. Maybe even drop off zone recommendations, and offer a steep discount off of one ride for enough compliant drop offs (avoid fines by cities). One thing I would like to do is to finish the transition to have the API server fully running on NGNIX, but with time at an end, I opted to run it through a nohup uwsgi command. 
