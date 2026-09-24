# helsinki-bikes-weather
How does weather influence the number of city bike rides in Helsinki?

1. ## Type of data:
   1.1. The Origin–Destination (OD) data of city bike stations includes all journeys made by city bikes in Helsinki and Espoo. The data includes        information about the origin and destination station, start and end times, distance (in meters) and duration (in seconds) of each journey.

   Data period: June 2025.
   
2. ## Data exploration (June 2025)
- 387,257 trips, 8 columns, no missing values
- Departure/Return stored as text → convert to datetime
- Outliers: negative distances (min −4,294 km, likely an overflow bug),
  distances up to 3,680 km, trips of 0 seconds and up to 114 days
- Typical trip: ~11.5 min, ~2.1 km (median)
