# https://www.unitedstateszipcodes.org/zip-code-database/
import pandas as pd
from geopy import distance

filename = 'zip_code_database.csv'


class GeoSpatial:
    data = pd.read_csv(filename)

    def __init__(self, zip_code: int):
        self.latitude = GeoSpatial.data.loc[GeoSpatial.data['zip'] == zip_code, 'latitude'].iloc[0]
        self.longitude = GeoSpatial.data.loc[GeoSpatial.data['zip'] == zip_code, 'longitude'].iloc[0]

    def __sub__(self, other):
        return distance.distance((self.latitude, self.longitude), (other.latitude, other.longitude))
