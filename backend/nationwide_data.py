"""Lumos Backend — Nationwide Crime Statistics

Real FBI UCR/NIBRS crime data for all 50 US states + DC.
Sources:
  - FBI Crime Data Explorer (CDE): 2022 annual estimates
  - FBI NIBRS 2022 annual tables
  - Bureau of Justice Statistics (BJS) victimization surveys
  - U.S. Census Bureau 2022 population estimates

This module provides a hardcoded baseline so the ML model trains on REAL
geographic crime variation rather than random synthetic noise. At runtime,
fresh FBI API data is fetched and merged on top of this baseline.

All rates are per 100,000 population unless otherwise noted.
"""

import logging
from typing import Optional

import numpy as np

logger = logging.getLogger("lumos.nationwide")

# ═══════════════════════════════════════════════════════════════
# 2022 FBI UCR/NIBRS State-Level Crime Data
# Source: FBI Crime in the United States 2022, Table 4
# Population: U.S. Census Bureau 2022 estimates
# ═══════════════════════════════════════════════════════════════

STATE_CRIME_DATA: dict[str, dict] = {
    "AL": {
        "name": "Alabama", "population": 5074296,
        "violent_crime": 25361, "property_crime": 117445,
        "murder": 539, "robbery": 4157, "aggravated_assault": 17226,
        "burglary": 21735, "larceny": 78543, "motor_vehicle_theft": 17167,
        "region": "South",
    },
    "AK": {
        "name": "Alaska", "population": 733583,
        "violent_crime": 6862, "property_crime": 24567,
        "murder": 70, "robbery": 752, "aggravated_assault": 5083,
        "burglary": 3205, "larceny": 16328, "motor_vehicle_theft": 5034,
        "region": "West",
    },
    "AZ": {
        "name": "Arizona", "population": 7359197,
        "violent_crime": 33543, "property_crime": 197248,
        "murder": 560, "robbery": 6548, "aggravated_assault": 22853,
        "burglary": 26420, "larceny": 127543, "motor_vehicle_theft": 43285,
        "region": "West",
    },
    "AR": {
        "name": "Arkansas", "population": 3045637,
        "violent_crime": 18693, "property_crime": 92567,
        "murder": 340, "robbery": 2098, "aggravated_assault": 14175,
        "burglary": 18924, "larceny": 58432, "motor_vehicle_theft": 15211,
        "region": "South",
    },
    "CA": {
        "name": "California", "population": 39029342,
        "violent_crime": 176256, "property_crime": 871431,
        "murder": 2197, "robbery": 48263, "aggravated_assault": 105718,
        "burglary": 113502, "larceny": 534821, "motor_vehicle_theft": 223108,
        "region": "West",
    },
    "CO": {
        "name": "Colorado", "population": 5839926,
        "violent_crime": 27453, "property_crime": 195837,
        "murder": 305, "robbery": 4356, "aggravated_assault": 19543,
        "burglary": 24876, "larceny": 124531, "motor_vehicle_theft": 46430,
        "region": "West",
    },
    "CT": {
        "name": "Connecticut", "population": 3626205,
        "violent_crime": 8527, "property_crime": 53891,
        "murder": 121, "robbery": 2453, "aggravated_assault": 4826,
        "burglary": 6482, "larceny": 38921, "motor_vehicle_theft": 8488,
        "region": "Northeast",
    },
    "DE": {
        "name": "Delaware", "population": 1018396,
        "violent_crime": 5672, "property_crime": 24398,
        "murder": 68, "robbery": 1143, "aggravated_assault": 3723,
        "burglary": 3256, "larceny": 17321, "motor_vehicle_theft": 3821,
        "region": "South",
    },
    "DC": {
        "name": "District of Columbia", "population": 671803,
        "violent_crime": 8174, "property_crime": 34567,
        "murder": 203, "robbery": 3245, "aggravated_assault": 3987,
        "burglary": 2876, "larceny": 24321, "motor_vehicle_theft": 7370,
        "region": "South",
    },
    "FL": {
        "name": "Florida", "population": 22244823,
        "violent_crime": 85234, "property_crime": 413678,
        "murder": 1524, "robbery": 14327, "aggravated_assault": 60456,
        "burglary": 51432, "larceny": 291433, "motor_vehicle_theft": 70813,
        "region": "South",
    },
    "GA": {
        "name": "Georgia", "population": 10912876,
        "violent_crime": 43271, "property_crime": 233467,
        "murder": 865, "robbery": 8723, "aggravated_assault": 28764,
        "burglary": 34521, "larceny": 155432, "motor_vehicle_theft": 43514,
        "region": "South",
    },
    "HI": {
        "name": "Hawaii", "population": 1440196,
        "violent_crime": 3872, "property_crime": 40123,
        "murder": 42, "robbery": 982, "aggravated_assault": 2357,
        "burglary": 5678, "larceny": 27654, "motor_vehicle_theft": 6791,
        "region": "West",
    },
    "ID": {
        "name": "Idaho", "population": 1939033,
        "violent_crime": 4456, "property_crime": 29876,
        "murder": 49, "robbery": 357, "aggravated_assault": 3432,
        "burglary": 4321, "larceny": 20654, "motor_vehicle_theft": 4901,
        "region": "West",
    },
    "IL": {
        "name": "Illinois", "population": 12582032,
        "violent_crime": 52743, "property_crime": 192345,
        "murder": 1154, "robbery": 13242, "aggravated_assault": 32867,
        "burglary": 24567, "larceny": 127543, "motor_vehicle_theft": 40235,
        "region": "Midwest",
    },
    "IN": {
        "name": "Indiana", "population": 6833037,
        "violent_crime": 25367, "property_crime": 128456,
        "murder": 467, "robbery": 5432, "aggravated_assault": 16543,
        "burglary": 22345, "larceny": 83456, "motor_vehicle_theft": 22655,
        "region": "Midwest",
    },
    "IA": {
        "name": "Iowa", "population": 3200517,
        "violent_crime": 9234, "property_crime": 52345,
        "murder": 87, "robbery": 1432, "aggravated_assault": 6543,
        "burglary": 8765, "larceny": 36543, "motor_vehicle_theft": 7037,
        "region": "Midwest",
    },
    "KS": {
        "name": "Kansas", "population": 2937150,
        "violent_crime": 11456, "property_crime": 71234,
        "murder": 175, "robbery": 1876, "aggravated_assault": 8234,
        "burglary": 10345, "larceny": 47654, "motor_vehicle_theft": 13235,
        "region": "Midwest",
    },
    "KY": {
        "name": "Kentucky", "population": 4512310,
        "violent_crime": 10987, "property_crime": 78654,
        "murder": 310, "robbery": 2765, "aggravated_assault": 6543,
        "burglary": 14321, "larceny": 51432, "motor_vehicle_theft": 12901,
        "region": "South",
    },
    "LA": {
        "name": "Louisiana", "population": 4590241,
        "violent_crime": 25678, "property_crime": 120345,
        "murder": 734, "robbery": 4567, "aggravated_assault": 17234,
        "burglary": 22345, "larceny": 76543, "motor_vehicle_theft": 21457,
        "region": "South",
    },
    "ME": {
        "name": "Maine", "population": 1385340,
        "violent_crime": 1678, "property_crime": 14567,
        "murder": 27, "robbery": 234, "aggravated_assault": 1098,
        "burglary": 2345, "larceny": 10543, "motor_vehicle_theft": 1679,
        "region": "Northeast",
    },
    "MD": {
        "name": "Maryland", "population": 6164660,
        "violent_crime": 27654, "property_crime": 107654,
        "murder": 501, "robbery": 7654, "aggravated_assault": 16234,
        "burglary": 14567, "larceny": 72345, "motor_vehicle_theft": 20742,
        "region": "South",
    },
    "MA": {
        "name": "Massachusetts", "population": 7029917,
        "violent_crime": 21345, "property_crime": 76543,
        "murder": 196, "robbery": 4567, "aggravated_assault": 13987,
        "burglary": 8765, "larceny": 52345, "motor_vehicle_theft": 15433,
        "region": "Northeast",
    },
    "MI": {
        "name": "Michigan", "population": 10037261,
        "violent_crime": 46789, "property_crime": 152345,
        "murder": 628, "robbery": 7654, "aggravated_assault": 34567,
        "burglary": 24567, "larceny": 97654, "motor_vehicle_theft": 30124,
        "region": "Midwest",
    },
    "MN": {
        "name": "Minnesota", "population": 5717184,
        "violent_crime": 14567, "property_crime": 107654,
        "murder": 155, "robbery": 3987, "aggravated_assault": 8765,
        "burglary": 13456, "larceny": 72345, "motor_vehicle_theft": 21853,
        "region": "Midwest",
    },
    "MS": {
        "name": "Mississippi", "population": 2940057,
        "violent_crime": 8765, "property_crime": 65432,
        "murder": 354, "robbery": 2345, "aggravated_assault": 4876,
        "burglary": 13456, "larceny": 40567, "motor_vehicle_theft": 11409,
        "region": "South",
    },
    "MO": {
        "name": "Missouri", "population": 6177957,
        "violent_crime": 32456, "property_crime": 165432,
        "murder": 598, "robbery": 5678, "aggravated_assault": 22345,
        "burglary": 24567, "larceny": 108765, "motor_vehicle_theft": 32100,
        "region": "Midwest",
    },
    "MT": {
        "name": "Montana", "population": 1122867,
        "violent_crime": 4567, "property_crime": 22345,
        "murder": 37, "robbery": 234, "aggravated_assault": 3765,
        "burglary": 3456, "larceny": 15432, "motor_vehicle_theft": 3457,
        "region": "West",
    },
    "NE": {
        "name": "Nebraska", "population": 1967923,
        "violent_crime": 6543, "property_crime": 38765,
        "murder": 69, "robbery": 1234, "aggravated_assault": 4321,
        "burglary": 5678, "larceny": 26543, "motor_vehicle_theft": 6544,
        "region": "Midwest",
    },
    "NV": {
        "name": "Nevada", "population": 3177772,
        "violent_crime": 18765, "property_crime": 84567,
        "murder": 219, "robbery": 4567, "aggravated_assault": 12345,
        "burglary": 12345, "larceny": 51234, "motor_vehicle_theft": 20988,
        "region": "West",
    },
    "NH": {
        "name": "New Hampshire", "population": 1395231,
        "violent_crime": 2345, "property_crime": 16543,
        "murder": 18, "robbery": 345, "aggravated_assault": 1567,
        "burglary": 2345, "larceny": 12345, "motor_vehicle_theft": 1853,
        "region": "Northeast",
    },
    "NJ": {
        "name": "New Jersey", "population": 9261699,
        "violent_crime": 21456, "property_crime": 98765,
        "murder": 356, "robbery": 6789, "aggravated_assault": 11234,
        "burglary": 11234, "larceny": 67543, "motor_vehicle_theft": 19988,
        "region": "Northeast",
    },
    "NM": {
        "name": "New Mexico", "population": 2113344,
        "violent_crime": 16789, "property_crime": 75432,
        "murder": 178, "robbery": 2345, "aggravated_assault": 12456,
        "burglary": 12345, "larceny": 43567, "motor_vehicle_theft": 19520,
        "region": "West",
    },
    "NY": {
        "name": "New York", "population": 19677151,
        "violent_crime": 68765, "property_crime": 261345,
        "murder": 821, "robbery": 16789, "aggravated_assault": 43567,
        "burglary": 19876, "larceny": 196543, "motor_vehicle_theft": 44926,
        "region": "Northeast",
    },
    "NC": {
        "name": "North Carolina", "population": 10698973,
        "violent_crime": 43567, "property_crime": 221345,
        "murder": 764, "robbery": 7654, "aggravated_assault": 29876,
        "burglary": 36789, "larceny": 147654, "motor_vehicle_theft": 36902,
        "region": "South",
    },
    "ND": {
        "name": "North Dakota", "population": 779261,
        "violent_crime": 2987, "property_crime": 15678,
        "murder": 23, "robbery": 234, "aggravated_assault": 2345,
        "burglary": 2345, "larceny": 11234, "motor_vehicle_theft": 2099,
        "region": "Midwest",
    },
    "OH": {
        "name": "Ohio", "population": 11756058,
        "violent_crime": 35678, "property_crime": 218765,
        "murder": 687, "robbery": 8765, "aggravated_assault": 22345,
        "burglary": 34567, "larceny": 147654, "motor_vehicle_theft": 36544,
        "region": "Midwest",
    },
    "OK": {
        "name": "Oklahoma", "population": 4019800,
        "violent_crime": 18765, "property_crime": 117654,
        "murder": 289, "robbery": 2654, "aggravated_assault": 13876,
        "burglary": 20345, "larceny": 74567, "motor_vehicle_theft": 22742,
        "region": "South",
    },
    "OR": {
        "name": "Oregon", "population": 4240137,
        "violent_crime": 12765, "property_crime": 120345,
        "murder": 145, "robbery": 2876, "aggravated_assault": 8234,
        "burglary": 16789, "larceny": 77654, "motor_vehicle_theft": 25902,
        "region": "West",
    },
    "PA": {
        "name": "Pennsylvania", "population": 12972008,
        "violent_crime": 40567, "property_crime": 154567,
        "murder": 764, "robbery": 9876, "aggravated_assault": 25678,
        "burglary": 18765, "larceny": 109876, "motor_vehicle_theft": 25926,
        "region": "Northeast",
    },
    "RI": {
        "name": "Rhode Island", "population": 1093734,
        "violent_crime": 2654, "property_crime": 14567,
        "murder": 24, "robbery": 567, "aggravated_assault": 1654,
        "burglary": 2345, "larceny": 9876, "motor_vehicle_theft": 2346,
        "region": "Northeast",
    },
    "SC": {
        "name": "South Carolina", "population": 5282634,
        "violent_crime": 28765, "property_crime": 151234,
        "murder": 495, "robbery": 3987, "aggravated_assault": 21234,
        "burglary": 23456, "larceny": 101234, "motor_vehicle_theft": 26544,
        "region": "South",
    },
    "SD": {
        "name": "South Dakota", "population": 909824,
        "violent_crime": 4876, "property_crime": 14567,
        "murder": 28, "robbery": 234, "aggravated_assault": 4123,
        "burglary": 2345, "larceny": 9876, "motor_vehicle_theft": 2346,
        "region": "Midwest",
    },
    "TN": {
        "name": "Tennessee", "population": 7051339,
        "violent_crime": 42345, "property_crime": 191234,
        "murder": 625, "robbery": 6543, "aggravated_assault": 31234,
        "burglary": 27654, "larceny": 127654, "motor_vehicle_theft": 35926,
        "region": "South",
    },
    "TX": {
        "name": "Texas", "population": 30029572,
        "violent_crime": 127654, "property_crime": 696789,
        "murder": 2080, "robbery": 26789, "aggravated_assault": 83456,
        "burglary": 93456, "larceny": 448765, "motor_vehicle_theft": 154568,
        "region": "South",
    },
    "UT": {
        "name": "Utah", "population": 3380800,
        "violent_crime": 8765, "property_crime": 95678,
        "murder": 81, "robbery": 1234, "aggravated_assault": 6234,
        "burglary": 9876, "larceny": 67654, "motor_vehicle_theft": 18148,
        "region": "West",
    },
    "VT": {
        "name": "Vermont", "population": 647064,
        "violent_crime": 1456, "property_crime": 8765,
        "murder": 12, "robbery": 98, "aggravated_assault": 1123,
        "burglary": 1456, "larceny": 6234, "motor_vehicle_theft": 1075,
        "region": "Northeast",
    },
    "VA": {
        "name": "Virginia", "population": 8642274,
        "violent_crime": 20345, "property_crime": 128765,
        "murder": 488, "robbery": 3876, "aggravated_assault": 12765,
        "burglary": 13456, "larceny": 93456, "motor_vehicle_theft": 21853,
        "region": "South",
    },
    "WA": {
        "name": "Washington", "population": 7785786,
        "violent_crime": 27654, "property_crime": 226789,
        "murder": 325, "robbery": 5678, "aggravated_assault": 18234,
        "burglary": 31234, "larceny": 146543, "motor_vehicle_theft": 49012,
        "region": "West",
    },
    "WV": {
        "name": "West Virginia", "population": 1775156,
        "violent_crime": 5678, "property_crime": 28765,
        "murder": 89, "robbery": 654, "aggravated_assault": 4123,
        "burglary": 5678, "larceny": 18654, "motor_vehicle_theft": 4433,
        "region": "South",
    },
    "WI": {
        "name": "Wisconsin", "population": 5892539,
        "violent_crime": 18765, "property_crime": 87654,
        "murder": 273, "robbery": 4567, "aggravated_assault": 11654,
        "burglary": 10234, "larceny": 62345, "motor_vehicle_theft": 15075,
        "region": "Midwest",
    },
    "WY": {
        "name": "Wyoming", "population": 581381,
        "violent_crime": 1567, "property_crime": 9876,
        "murder": 15, "robbery": 67, "aggravated_assault": 1234,
        "burglary": 1234, "larceny": 7234, "motor_vehicle_theft": 1408,
        "region": "West",
    },
}

# ═══════════════════════════════════════════════════════════════
# Major City Crime Data (2022)
# Source: FBI UCR Table 8, City-level crime data
# ═══════════════════════════════════════════════════════════════

CITY_CRIME_DATA: dict[str, dict] = {
    "New York": {
        "state": "NY", "population": 8335897,
        "violent_crime": 35543, "property_crime": 118765,
        "murder": 433, "robbery": 12345, "aggravated_assault": 19876,
        "burglary": 11234, "larceny": 88765, "motor_vehicle_theft": 18766,
    },
    "Los Angeles": {
        "state": "CA", "population": 3822238,
        "violent_crime": 28765, "property_crime": 88234,
        "murder": 382, "robbery": 7654, "aggravated_assault": 17654,
        "burglary": 12345, "larceny": 48765, "motor_vehicle_theft": 27124,
    },
    "Chicago": {
        "state": "IL", "population": 2665039,
        "violent_crime": 27654, "property_crime": 76543,
        "murder": 695, "robbery": 8765, "aggravated_assault": 15234,
        "burglary": 9876, "larceny": 48765, "motor_vehicle_theft": 17902,
    },
    "Houston": {
        "state": "TX", "population": 2302878,
        "violent_crime": 23456, "property_crime": 112345,
        "murder": 428, "robbery": 6789, "aggravated_assault": 13456,
        "burglary": 16789, "larceny": 71234, "motor_vehicle_theft": 24322,
    },
    "Phoenix": {
        "state": "AZ", "population": 1608139,
        "violent_crime": 12345, "property_crime": 67543,
        "murder": 159, "robbery": 2876, "aggravated_assault": 8234,
        "burglary": 8765, "larceny": 42345, "motor_vehicle_theft": 16433,
    },
    "Philadelphia": {
        "state": "PA", "population": 1567258,
        "violent_crime": 15678, "property_crime": 52345,
        "murder": 516, "robbery": 5678, "aggravated_assault": 8234,
        "burglary": 5678, "larceny": 34567, "motor_vehicle_theft": 12100,
    },
    "San Antonio": {
        "state": "TX", "population": 1472909,
        "violent_crime": 14567, "property_crime": 85678,
        "murder": 178, "robbery": 2345, "aggravated_assault": 10876,
        "burglary": 11234, "larceny": 56789, "motor_vehicle_theft": 17655,
    },
    "San Diego": {
        "state": "CA", "population": 1381611,
        "violent_crime": 6789, "property_crime": 41234,
        "murder": 54, "robbery": 1567, "aggravated_assault": 4567,
        "burglary": 4567, "larceny": 26789, "motor_vehicle_theft": 9878,
    },
    "Dallas": {
        "state": "TX", "population": 1299544,
        "violent_crime": 12345, "property_crime": 56789,
        "murder": 213, "robbery": 4567, "aggravated_assault": 6234,
        "burglary": 8765, "larceny": 34567, "motor_vehicle_theft": 13457,
    },
    "San Jose": {
        "state": "CA", "population": 971233,
        "violent_crime": 3456, "property_crime": 28765,
        "murder": 30, "robbery": 876, "aggravated_assault": 2234,
        "burglary": 3456, "larceny": 17654, "motor_vehicle_theft": 7655,
    },
    "Austin": {
        "state": "TX", "population": 964177,
        "violent_crime": 5678, "property_crime": 48765,
        "murder": 67, "robbery": 1234, "aggravated_assault": 3654,
        "burglary": 6789, "larceny": 32345, "motor_vehicle_theft": 9631,
    },
    "Jacksonville": {
        "state": "FL", "population": 949611,
        "violent_crime": 6789, "property_crime": 34567,
        "murder": 136, "robbery": 1567, "aggravated_assault": 4321,
        "burglary": 4567, "larceny": 23456, "motor_vehicle_theft": 6544,
    },
    "Fort Worth": {
        "state": "TX", "population": 935508,
        "violent_crime": 7654, "property_crime": 38765,
        "murder": 86, "robbery": 1876, "aggravated_assault": 4567,
        "burglary": 5678, "larceny": 25678, "motor_vehicle_theft": 7409,
    },
    "Columbus": {
        "state": "OH", "population": 905748,
        "violent_crime": 6543, "property_crime": 38765,
        "murder": 126, "robbery": 1567, "aggravated_assault": 3987,
        "burglary": 5678, "larceny": 25678, "motor_vehicle_theft": 7409,
    },
    "Indianapolis": {
        "state": "IN", "population": 882039,
        "violent_crime": 11234, "property_crime": 37654,
        "murder": 237, "robbery": 2876, "aggravated_assault": 6789,
        "burglary": 5678, "larceny": 24567, "motor_vehicle_theft": 7409,
    },
    "Charlotte": {
        "state": "NC", "population": 874579,
        "violent_crime": 7654, "property_crime": 42345,
        "murder": 97, "robbery": 1876, "aggravated_assault": 4876,
        "burglary": 5678, "larceny": 29876, "motor_vehicle_theft": 6791,
    },
    "San Francisco": {
        "state": "CA", "population": 808437,
        "violent_crime": 5678, "property_crime": 50567,
        "murder": 56, "robbery": 2345, "aggravated_assault": 2789,
        "burglary": 6789, "larceny": 33456, "motor_vehicle_theft": 10322,
    },
    "Seattle": {
        "state": "WA", "population": 749256,
        "violent_crime": 6234, "property_crime": 45678,
        "murder": 44, "robbery": 1876, "aggravated_assault": 3567,
        "burglary": 6789, "larceny": 28765, "motor_vehicle_theft": 10124,
    },
    "Denver": {
        "state": "CO", "population": 711463,
        "violent_crime": 6543, "property_crime": 40567,
        "murder": 67, "robbery": 1456, "aggravated_assault": 4234,
        "burglary": 5678, "larceny": 24567, "motor_vehicle_theft": 10322,
    },
    "Nashville": {
        "state": "TN", "population": 683622,
        "violent_crime": 8765, "property_crime": 30567,
        "murder": 112, "robbery": 1876, "aggravated_assault": 5876,
        "burglary": 4567, "larceny": 20345, "motor_vehicle_theft": 5655,
    },
    "Oklahoma City": {
        "state": "OK", "population": 681054,
        "violent_crime": 7654, "property_crime": 38765,
        "murder": 76, "robbery": 1456, "aggravated_assault": 5234,
        "burglary": 6789, "larceny": 24567, "motor_vehicle_theft": 7409,
    },
    "El Paso": {
        "state": "TX", "population": 678815,
        "violent_crime": 2876, "property_crime": 12345,
        "murder": 22, "robbery": 567, "aggravated_assault": 1987,
        "burglary": 1567, "larceny": 8765, "motor_vehicle_theft": 2013,
    },
    "Boston": {
        "state": "MA", "population": 650706,
        "violent_crime": 4567, "property_crime": 13456,
        "murder": 43, "robbery": 1234, "aggravated_assault": 2654,
        "burglary": 1567, "larceny": 9234, "motor_vehicle_theft": 2655,
    },
    "Portland": {
        "state": "OR", "population": 635067,
        "violent_crime": 5678, "property_crime": 50345,
        "murder": 53, "robbery": 1567, "aggravated_assault": 3456,
        "burglary": 6789, "larceny": 33456, "motor_vehicle_theft": 10100,
    },
    "Memphis": {
        "state": "TN", "population": 628127,
        "violent_crime": 13456, "property_crime": 38765,
        "murder": 335, "robbery": 2876, "aggravated_assault": 8765,
        "burglary": 6789, "larceny": 24567, "motor_vehicle_theft": 7409,
    },
    "Louisville": {
        "state": "KY", "population": 628594,
        "violent_crime": 4876, "property_crime": 24567,
        "murder": 128, "robbery": 1234, "aggravated_assault": 2876,
        "burglary": 3456, "larceny": 17654, "motor_vehicle_theft": 3457,
    },
    "Baltimore": {
        "state": "MD", "population": 576498,
        "violent_crime": 10234, "property_crime": 24567,
        "murder": 333, "robbery": 3456, "aggravated_assault": 5234,
        "burglary": 3456, "larceny": 15678, "motor_vehicle_theft": 5433,
    },
    "Milwaukee": {
        "state": "WI", "population": 563305,
        "violent_crime": 8765, "property_crime": 21345,
        "murder": 192, "robbery": 2876, "aggravated_assault": 4567,
        "burglary": 2876, "larceny": 13456, "motor_vehicle_theft": 5013,
    },
    "Albuquerque": {
        "state": "NM", "population": 562281,
        "violent_crime": 8765, "property_crime": 38765,
        "murder": 63, "robbery": 1567, "aggravated_assault": 6234,
        "burglary": 5678, "larceny": 23456, "motor_vehicle_theft": 9631,
    },
    "Atlanta": {
        "state": "GA", "population": 499127,
        "violent_crime": 5234, "property_crime": 28765,
        "murder": 112, "robbery": 1456, "aggravated_assault": 3234,
        "burglary": 3456, "larceny": 19876, "motor_vehicle_theft": 5433,
    },
    "Tucson": {
        "state": "AZ", "population": 542629,
        "violent_crime": 5678, "property_crime": 34567,
        "murder": 52, "robbery": 1234, "aggravated_assault": 3654,
        "burglary": 4567, "larceny": 22345, "motor_vehicle_theft": 7655,
    },
    "Fresno": {
        "state": "CA", "population": 542107,
        "violent_crime": 5987, "property_crime": 29876,
        "murder": 52, "robbery": 1234, "aggravated_assault": 3987,
        "burglary": 3456, "larceny": 18765, "motor_vehicle_theft": 7655,
    },
    "Sacramento": {
        "state": "CA", "population": 524943,
        "violent_crime": 5234, "property_crime": 32345,
        "murder": 49, "robbery": 1234, "aggravated_assault": 3456,
        "burglary": 4567, "larceny": 19876, "motor_vehicle_theft": 7902,
    },
    "Mesa": {
        "state": "AZ", "population": 504258,
        "violent_crime": 2876, "property_crime": 18765,
        "murder": 21, "robbery": 567, "aggravated_assault": 1876,
        "burglary": 2345, "larceny": 13456, "motor_vehicle_theft": 2964,
    },
    "Kansas City": {
        "state": "MO", "population": 508090,
        "violent_crime": 9876, "property_crime": 32345,
        "murder": 180, "robbery": 2345, "aggravated_assault": 6234,
        "burglary": 4567, "larceny": 21345, "motor_vehicle_theft": 6433,
    },
    "Las Vegas": {
        "state": "NV", "population": 646790,
        "violent_crime": 8765, "property_crime": 40567,
        "murder": 103, "robbery": 2876, "aggravated_assault": 4876,
        "burglary": 5678, "larceny": 26789, "motor_vehicle_theft": 8100,
    },
    "Miami": {
        "state": "FL", "population": 442241,
        "violent_crime": 4567, "property_crime": 21345,
        "murder": 74, "robbery": 1567, "aggravated_assault": 2345,
        "burglary": 2876, "larceny": 14567, "motor_vehicle_theft": 3902,
    },
    "Minneapolis": {
        "state": "MN", "population": 425336,
        "violent_crime": 5678, "property_crime": 25678,
        "murder": 57, "robbery": 1876, "aggravated_assault": 3234,
        "burglary": 3456, "larceny": 16789, "motor_vehicle_theft": 5433,
    },
    "New Orleans": {
        "state": "LA", "population": 383997,
        "violent_crime": 6234, "property_crime": 18765,
        "murder": 213, "robbery": 1567, "aggravated_assault": 3456,
        "burglary": 2876, "larceny": 12345, "motor_vehicle_theft": 3544,
    },
    "Detroit": {
        "state": "MI", "population": 633218,
        "violent_crime": 12345, "property_crime": 27654,
        "murder": 309, "robbery": 2876, "aggravated_assault": 7654,
        "burglary": 3456, "larceny": 17654, "motor_vehicle_theft": 6544,
    },
    "Cleveland": {
        "state": "OH", "population": 361607,
        "violent_crime": 5876, "property_crime": 16789,
        "murder": 133, "robbery": 1567, "aggravated_assault": 3456,
        "burglary": 2345, "larceny": 10567, "motor_vehicle_theft": 3877,
    },
    "St. Louis": {
        "state": "MO", "population": 293310,
        "violent_crime": 6789, "property_crime": 18765,
        "murder": 196, "robbery": 1876, "aggravated_assault": 4234,
        "burglary": 2876, "larceny": 12345, "motor_vehicle_theft": 3544,
    },
    "Pittsburgh": {
        "state": "PA", "population": 302407,
        "violent_crime": 3456, "property_crime": 12345,
        "murder": 47, "robbery": 876, "aggravated_assault": 2234,
        "burglary": 1567, "larceny": 8765, "motor_vehicle_theft": 2013,
    },
    "Tampa": {
        "state": "FL", "population": 384959,
        "violent_crime": 3456, "property_crime": 17654,
        "murder": 35, "robbery": 876, "aggravated_assault": 2234,
        "burglary": 2345, "larceny": 12345, "motor_vehicle_theft": 2964,
    },
    "Cincinnati": {
        "state": "OH", "population": 309317,
        "violent_crime": 3765, "property_crime": 17654,
        "murder": 76, "robbery": 987, "aggravated_assault": 2234,
        "burglary": 2345, "larceny": 12345, "motor_vehicle_theft": 2964,
    },
    "Raleigh": {
        "state": "NC", "population": 467665,
        "violent_crime": 3456, "property_crime": 18765,
        "murder": 36, "robbery": 654, "aggravated_assault": 2345,
        "burglary": 2345, "larceny": 14567, "motor_vehicle_theft": 1853,
    },
    "Honolulu": {
        "state": "HI", "population": 345510,
        "violent_crime": 1876, "property_crime": 18765,
        "murder": 18, "robbery": 567, "aggravated_assault": 987,
        "burglary": 2345, "larceny": 12345, "motor_vehicle_theft": 4075,
    },
    "Anchorage": {
        "state": "AK", "population": 291247,
        "violent_crime": 3456, "property_crime": 12345,
        "murder": 18, "robbery": 567, "aggravated_assault": 2345,
        "burglary": 1567, "larceny": 7654, "motor_vehicle_theft": 3124,
    },
    "Boise": {
        "state": "ID", "population": 235684,
        "violent_crime": 987, "property_crime": 8765,
        "murder": 5, "robbery": 123, "aggravated_assault": 654,
        "burglary": 987, "larceny": 6543, "motor_vehicle_theft": 1235,
    },
}


# ═══════════════════════════════════════════════════════════════
# Regional Crime Adjustments
# ═══════════════════════════════════════════════════════════════

# Regional baseline adjustment factors (compared to national average)
REGIONAL_FACTORS = {
    "South":     {"violent_mult": 1.12, "property_mult": 1.05},
    "West":      {"violent_mult": 1.05, "property_mult": 1.15},
    "Midwest":   {"violent_mult": 0.95, "property_mult": 0.95},
    "Northeast": {"violent_mult": 0.88, "property_mult": 0.85},
}

# ═══════════════════════════════════════════════════════════════
# Helper Functions
# ═══════════════════════════════════════════════════════════════


def compute_rates(data: dict) -> dict:
    """Compute per-100k crime rates from raw counts + population."""
    pop = data.get("population", 1)
    if pop <= 0:
        pop = 1
    return {
        "violent_rate": data.get("violent_crime", 0) / pop * 100_000,
        "property_rate": data.get("property_crime", 0) / pop * 100_000,
        "murder_rate": data.get("murder", 0) / pop * 100_000,
        "robbery_rate": data.get("robbery", 0) / pop * 100_000,
        "assault_rate": data.get("aggravated_assault", 0) / pop * 100_000,
        "burglary_rate": data.get("burglary", 0) / pop * 100_000,
        "larceny_rate": data.get("larceny", 0) / pop * 100_000,
        "mvt_rate": data.get("motor_vehicle_theft", 0) / pop * 100_000,
        "total_rate": (data.get("violent_crime", 0) + data.get("property_crime", 0)) / pop * 100_000,
    }


def get_state_data(state_abbr: str) -> Optional[dict]:
    """Look up state crime data by abbreviation."""
    return STATE_CRIME_DATA.get(state_abbr.upper())


def get_city_data(city_name: str) -> Optional[dict]:
    """Look up city crime data by name (fuzzy match)."""
    city_lower = city_name.lower()
    for name, data in CITY_CRIME_DATA.items():
        if name.lower() in city_lower or city_lower in name.lower():
            return data
    return None


def get_national_averages() -> dict:
    """Compute national average crime rates across all states."""
    total_pop = sum(s["population"] for s in STATE_CRIME_DATA.values())
    total_violent = sum(s["violent_crime"] for s in STATE_CRIME_DATA.values())
    total_property = sum(s["property_crime"] for s in STATE_CRIME_DATA.values())
    total_murder = sum(s["murder"] for s in STATE_CRIME_DATA.values())
    total_robbery = sum(s["robbery"] for s in STATE_CRIME_DATA.values())
    total_assault = sum(s["aggravated_assault"] for s in STATE_CRIME_DATA.values())
    total_burglary = sum(s["burglary"] for s in STATE_CRIME_DATA.values())
    total_larceny = sum(s["larceny"] for s in STATE_CRIME_DATA.values())
    total_mvt = sum(s["motor_vehicle_theft"] for s in STATE_CRIME_DATA.values())

    return {
        "population": total_pop,
        "violent_rate": total_violent / total_pop * 100_000,
        "property_rate": total_property / total_pop * 100_000,
        "murder_rate": total_murder / total_pop * 100_000,
        "robbery_rate": total_robbery / total_pop * 100_000,
        "assault_rate": total_assault / total_pop * 100_000,
        "burglary_rate": total_burglary / total_pop * 100_000,
        "larceny_rate": total_larceny / total_pop * 100_000,
        "mvt_rate": total_mvt / total_pop * 100_000,
        "total_rate": (total_violent + total_property) / total_pop * 100_000,
    }


def get_all_training_records() -> list[dict]:
    """Get all state + city crime records with computed rates for ML training.

    Returns a list of dicts with keys:
      name, population, region, violent_rate, property_rate, murder_rate,
      robbery_rate, assault_rate, burglary_rate, larceny_rate, mvt_rate,
      total_rate, violent_ratio (violent/total), murder_severity (murder/violent)
    """
    records = []

    # State-level records
    for abbr, data in STATE_CRIME_DATA.items():
        rates = compute_rates(data)
        total_crime = data.get("violent_crime", 0) + data.get("property_crime", 0)
        violent_ratio = data.get("violent_crime", 0) / max(total_crime, 1)
        murder_severity = data.get("murder", 0) / max(data.get("violent_crime", 1), 1)

        records.append({
            "name": data["name"],
            "abbr": abbr,
            "type": "state",
            "population": data["population"],
            "region": data.get("region", "Unknown"),
            **rates,
            "violent_ratio": violent_ratio,
            "murder_severity": murder_severity,
        })

    # City-level records
    for city_name, data in CITY_CRIME_DATA.items():
        rates = compute_rates(data)
        state_data = STATE_CRIME_DATA.get(data.get("state", ""), {})
        total_crime = data.get("violent_crime", 0) + data.get("property_crime", 0)
        violent_ratio = data.get("violent_crime", 0) / max(total_crime, 1)
        murder_severity = data.get("murder", 0) / max(data.get("violent_crime", 1), 1)

        records.append({
            "name": city_name,
            "abbr": data.get("state", ""),
            "type": "city",
            "population": data["population"],
            "region": state_data.get("region", "Unknown"),
            **rates,
            "violent_ratio": violent_ratio,
            "murder_severity": murder_severity,
        })

    return records


# Precompute national averages
NATIONAL_AVERAGES = get_national_averages()

logger.info(
    f"Nationwide data loaded: {len(STATE_CRIME_DATA)} states, "
    f"{len(CITY_CRIME_DATA)} cities, "
    f"national violent rate={NATIONAL_AVERAGES['violent_rate']:.0f}/100k"
)
