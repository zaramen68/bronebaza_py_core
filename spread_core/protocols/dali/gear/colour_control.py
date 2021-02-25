"""Commands and responses from IEC 62386 part 209."""

from __future__ import unicode_literals

from spread_core.protocols.dali import command
from spread_core.protocols.dali.gear.general import _StandardCommand


class FeatureStatusResponse(command.BitmapResponse):
    bits = ["Automatic Activation"]


class ColourStatusResponse(command.BitmapResponse):
    bits = [
        "xy-coordinate colour point out of range",
        "Colour temperature TC out of range",
        "Auto calibration running",
        "Auto calibration successful",
        "Colour type xy-coordinate active",
        "Colour type colour temperature TC active",
        "Colour type primary N active",
        "Colour type RGBWAF active"
    ]


class ColourTypeFeaturesResponse(command.BitmapResponse):
    bits = ['xy-coordinate capable', 'Colour temperature TC capable']
    ranges = {(2, 4): 'Number of primaries',
              (5, 7): 'Number of RGBWAF channels'}


class _ColourControlCommand(_StandardCommand):
    _devicetype = 8


class Activate(_ColourControlCommand):
    _cmdval = 226


class SetTemperature(_ColourControlCommand):
    _uses_dtr0 = True
    _uses_dtr1 = True
    _cmdval = 231
    _levels_dependent = True


class StoreColourTemperatureLimit(_ColourControlCommand):
    COOLEST = 0
    WARMEST = 1
    PHYSICAL_COOLEST = 2
    PHYSICAL_WARMEST = 3
    _uses_dtr0 = True
    _uses_dtr1 = True
    _uses_dtr2 = True
    _cmdval = 242


class StoreGearFeaturesStatus(_ColourControlCommand):
    _uses_dtr0 = True
    _cmdval = 243


class QueryGearFeaturesStatus(_ColourControlCommand):
    _cmdval = 247
    _response = FeatureStatusResponse


class QueryColorStatus(_ColourControlCommand):
    _cmdval = 248
    _response = ColourStatusResponse


class QueryColorTypeFeatures(_ColourControlCommand):
    _cmdval = 248
    _response = ColourTypeFeaturesResponse


class QueryColorValue(_ColourControlCommand):
    TEMPERATURE = 2
    COOLEST = 128
    PHYSICAL_COOLEST = 129
    WARMEST = 130
    PHYSICAL_WARMEST = 131
    _cmdval = 250
    _uses_dtr0 = True
    _response = command.Response
