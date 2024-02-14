"""
Tag String Structure

[INIT]Buoy_Name,Date,Time,Latitude,Longitude,Heading,Pitch,Roll,COG,SOG,Magnetic_Variation,Water_Detection_Main
[POWR]VBatt1,ABatt1,VBatt2,ABatt2,VSolar,ASolar,AMain,ATurbine,AWinch,PM_RH,Relay_State
[ECO1]Scattering,Chlorophyll,FDOM
[CTD]Temperature,Conductivity,Salinity,Density
[PH]Ext_pH_Calc,Int_pH_Calc,Error_Flag,Ext_pH,Int_pH
[NO2]Dark_Nitrate,Light_Nitrate,Dark_Nitrogen_in_Nitrate,Light_Nitrogen_in_Nitrate,Dark_Bromide,Light_Bromide
[Wind]Source,Wind_Dir_Min,Wind_Dir_Ave,Wind_Dir_Max,Wind_Spd_Min,Wind_Spd_Ave,Wind_Spd_Max
                Source: 7: wmt700, 5: wxt536
[ATMS]Air_Temp,Air_Humidity,Air_Pressure,PAR,Rain_Total,Rain_Duration,Rain_Intensity
[WAVE]Wave_Date,Wave_Time,Wave_Period,Wave_Hm0,Wave_H13,Wave_Hmax
[ADCP]ADCPDate,ADCPTime,EW,NS,Vert,Err
[PCO2]CO2_Air,CO2_Water,Pressure_Air,Pressure_Water,Air_Humidity
[WNCH]messages
    messages:
        Air temperature is too low
        Waves are too high
        Wave period is too short
        Buoy is moving too fast
        Voltage is too low
        Mission Completed
        No Mission in Progress
        Mission in Progress
        Mission Started
        No String received from CTD
        Interval not reach
[END]

Notes
-----
    Wind velocities are in knots,
    Velocities in "mm/s"


"""
import json
import os
import re
import math
from typing import Dict, List
from pathlib import Path

# Tag found in transmitted file.
INSTRUMENTS_TAG = ['INIT', 'POWR', 'ECO1', 'CTD', 'PH', 'NO2', 'WIND', 'ATMS', 'WAVE', 'ADCP', 'PCO2', 'WNCH']

DATA_TAG_REGEX = re.compile(rf"\[({'|'.join(INSTRUMENTS_TAG)})]((?:(?!\[).)*)", re.DOTALL)

TAG_VARIABLES = {
    'init': ['buoy_name', 'date', 'time', 'latitude', 'longitude', 'heading', 'pitch', 'roll', 'cog', 'sog',
             'magnetic_declination', 'water_detection'],
    'powr': ['volt_batt_1', 'amp_batt_1', 'volt_batt_2', 'amp_batt_2', 'volt_solar', 'amp_solar', 'amp_main',
             'amp_turbine', 'amp_winch', 'pm_rh', 'relay_state'],
    'eco1': ['scattering', 'chlorophyll', 'fdom'],
    'ctd': ['temperature', 'conductivity', 'salinity', 'density'],
    'ph': ['ext_ph_calc', 'int_ph_calc', 'error_flag', 'ext_ph', 'int_ph'],
    'no2': ['dark_nitrate', 'light_nitrate', 'dark_nitrogen_in_nitrate', 'light_nitrogen_in_nitrate', 'dark_bromide',
            'light_bromide'],
    'wind': ['source', 'wind_dir_min', 'wind_dir_ave', 'wind_dir_max', 'wind_spd_min', 'wind_spd_ave', 'wind_spd_max'],
    'atms': ['air_temperature', 'air_humidity', 'air_pressure', 'par', 'rain_total', 'rain_duration', 'rain_intensity'],
    'wave': ['date', 'time', 'period', 'hm0', 'h13', 'hmax'],
    'adcp': ['date', 'time', 'u', 'v', 'w', 'err'],
    'pco2': ['co2_air', 'co2_water', 'gas_pressure_air', 'gas_pressure_water', 'air_humidity'],
    'wnch': ['message']
}

_KNOTS_TO_KPH = 1.852
_MMS_TO_MS = 1 / 1000

STATION_INDEX_FILE = ".sd_current_index.json"


def process_SD(filename: str, source_dir: str, sd_directory: str, sd_padding: bool) -> None:

    start_index = _get_current_file_index(filename)

    data = load_raw_data(filename=Path(source_dir).joinpath(filename), start_index=start_index)

    if data:

        station_name = data[0]['init']['buoy_name']
        station_directory = Path(sd_directory).joinpath(station_name)
        Path(station_directory).mkdir(parents=True, exist_ok=True)

        for d in data:
            SD_data_string = _make_SD_string(data=d, sd_padding=sd_padding)
            SD_filename = f"{station_name}_SD_{d['init']['date'].replace('-', '')}.dat"
            SD_target_file = station_directory.joinpath(SD_filename)

            _write_SD(dest_file=SD_target_file, data=SD_data_string)
            start_index += 1
            _update_file_current_index(file_name=filename, pointer_index=start_index)
    else:
        print("No New Sample")
        'Fixme maybe add an error code'


def load_raw_data(filename: str, start_index: int = 0) -> List[Dict[str, dict[str, str]]]:
    """
    :param start_index: Number of line to skip in raw file.
    :param filename: Path to file

    """

    unpacked_data = []
    with open(filename, 'r') as f:
        for _ in range(start_index):
            next(f)

        for line in f:
            unpacked_data.append(_unpack_data(line))

    return unpacked_data


def _get_current_file_index(file_name: str) -> int:
    with open(STATION_INDEX_FILE) as f:
         pointers = json.load(f)
    if file_name in pointers.keys():
        return pointers[file_name]
    else:
        return 0


def _update_file_current_index(file_name: str, pointer_index: int):
    with open(STATION_INDEX_FILE) as f:
        pointers = json.load(f)
    pointers[file_name] = pointer_index

    with open(STATION_INDEX_FILE, "w") as f:
        json.dump(pointers, f, indent=4)


def _write_SD(dest_file: str, data: str):
    """Append data to the end of dest_file.

    :param dest_file: SD file to append to.
    :param data: SD data string.
    """
    with open(dest_file, 'a') as f:
        f.write(data + '\n')


def _unpack_data(data: str) -> Dict[str, dict[str, str]]:
    """Unpack Mitis Tag Data
    Returns Data as a dictionary of {TAG:DATA}
    """

    unpacked_data = {}
    for data_sequence in DATA_TAG_REGEX.finditer(data):
        tag = data_sequence.group(1).lower()
        data = data_sequence.group(2).split(",")

        unpacked_data[tag] = {key: value for key, value in zip(TAG_VARIABLES[tag], data)}

    return unpacked_data


def _format_lonlat(value: str):
    """ Round and format lon-lat string
    48°38.459'N -> 48 38.46N
    068°09.406'W -> 68 09.406W
    """
    _match = re.match("(\d+)°(\d+.\d+)\'([A-z])", value)
    if _match:
        _deg = float(_match.group(1))
        _min = float(_match.group(2))
        _hem = _match.group(3)
        lat_minutes = round(_min, 2)

        if lat_minutes == 60:
            _deg += + 1
            _min = 0
        return f"{_deg:0.0f} {_min:05.2f}{_hem}"
    return ""


def _make_SD_string(data: Dict[str, List[str]], sd_padding: bool) -> str:
    """Make SD string from unpacked Mitis Tag Data
    <buoy name>_SD_<date>.dat

    #1 Name of the buoy
    #2 date buoy = 2017/02/28
    #3 hour buoy = 00:00:46
    #4 latitude buoy = 48 28.97N
    #5 longitude buoy - 68 29.99W
    #6 speed of the wind in km/h = 5
    #7 maximal speed of the wind in km/h = 6
    #8 Wind direction in degree = 177
    #9 air temperature in degree Celsius = 24.1
    #10 air humidity relative in % = 31
    #11 air pressure in millibar = 1028.6
    #12 water temperature in degree Celsius = 2.3
    #13 water salinity in ppm = 12.0
    #14 Density of water =1016.3 in Kg/cubic meter
    #15 Fluorescent at 700nm (Scattering) in m-1 = 7.208E-03
    #16 Fluorescent at 695nm (Chlorophyll) in µg/L = 1.098E+01
    #17 Fluorescent at 460nm (Fluorescent Dissolved Organic Matter (FDOM)) in ppb = 2.822E+02
    #18 PAR value in µmol photons•m-2•s-1 = 20
    #19 Co2 in the water in ppm = 103.6 ppm
    #20 Co2 in the air in ppm = 103.6 ppm
    #21 pH = 7.6543
    #22 Wave, period in second = 8.0
    #23 Wave, average height in meter = 1.2
    #24 Wave, height of the biggest wave in meter = 2.3
    #25 Voltage of the batteries in Volt = 13.0
    #26 Power of the charging solar in ampere = 0.2
    #27 Power of the charging Wind turbine in ampere = 0.5
    #28 Power consuming in ampere = 0.9
    #29 pitch in degree (compass) = 0
    #30 roll in degree (compass) = 0
    #31 Power flow of the surface measured in m/s = 2.1
    #32 Heading buoy (compass) in degree = 128
    #33 Moving speed (GPS) in m/s = 0.0
    #34 Moving direction (GPS) in degree =264
    #35 Rain accumulation since midnight = #.#
    #36 Current (ADCP RTI or RDI) bin #1 in m/s = 2.4
    #37 Current direction (ADCP RTI ou RDI) in degree = 358
    #38 Water presence in the buoy controller box (0= no water, 1= water)
    #39 Water presence in the Power controller box (0= no water, 1= water)
    #40 Water presence in the Winch controller box (0= no water, 1= water)
    """
    sd_data = ["#" for x in range(39)]

    if "init" in data:
        sd_data[0] = data["init"]['buoy_name']  # Buoy_Name
        sd_data[1] = data["init"]['date'].replace("-", "/")
        sd_data[2] = data["init"]['time']  # Buoy_Hour

        sd_data[3] = _format_lonlat(data['init']['latitude'])
        sd_data[4] = _format_lonlat(data['init']['longitude'])

        sd_data[31] = f"{float(data['init']['heading']):.0f}"
        sd_data[28] = f"{float(data['init']['pitch']):.1f}"
        sd_data[29] = f"{float(data['init']['roll']):.1f}"

        sd_data[33] = f"{float(data['init']['cog']) % 360:.0f}"
        sd_data[32] = f"{float(data['init']['sog']):.1f}"

        _water_detection = float(data['init']['water_detection'])
        if _water_detection < 2000 and not math.isnan(_water_detection):
            _water_detection = 0
        sd_data[37] = f"{_water_detection:.0f}"

    if "powr" in data:
        _max_battery = max(float(data['powr']['volt_batt_1']), float(data['powr']['volt_batt_2']))
        _sum_amp = (float(data['powr']['amp_main']) + float(data['powr']['amp_winch']))

        sd_data[24] = f"{_max_battery:.1f}"
        sd_data[27] = f"{_sum_amp:.1f}"
        sd_data[25] = f"{float(data['powr']['amp_solar']):.1f}"
        sd_data[26] = f"{float(data['powr']['amp_turbine']):.1f}"
        sd_data[38] = data['powr']['relay_state'][7]

    if "eco1" in data:
        sd_data[14] = f"{float(data['eco1']['scattering']):.7f}"
        sd_data[15] = f"{float(data['eco1']['chlorophyll']):.4f}"
        sd_data[16] = f"{float(data['eco1']['fdom']):.2f}"

    if "ctd" in data:
        sd_data[11] = f"{float(data['ctd']['temperature']):.2f}"
        sd_data[12] = f"{float(data['ctd']['salinity']):.2f}"
        sd_data[13] = f"{float(data['ctd']['density']):.2f}"

    if "ph" in data:
        sd_data[20] = f"{float(data['ph']['ext_ph_calc']):.4f}"

    if "wind" in data:
        sd_data[5] = f"{float(data['wind']['wind_spd_ave']) * _KNOTS_TO_KPH:.0f}"
        sd_data[6] = f"{float(data['wind']['wind_spd_max']) * _KNOTS_TO_KPH:.0f}"
        sd_data[7] = f"{float(data['wind']['wind_dir_ave']):.0f}"

    if "atms" in data:
        sd_data[8] = f"{float(data['atms']['air_temperature']):.1f}"
        sd_data[9] = f"{float(data['atms']['air_humidity']):.0f}"
        sd_data[10] = f"{float(data['atms']['air_pressure']):.1f}"
        sd_data[17] = f"{float(data['atms']['par']):.0f}"
        sd_data[34] = f"{float(data['atms']['rain_total']):.1f}"

    if "wave" in data:
        sd_data[11] = f"{float(data['wave']['period']):.1f}"
        sd_data[22] = f"{float(data['wave']['h13']):.1f}"
        sd_data[23] = f"{float(data['wave']['hmax']):.1f}"

    if "pco2" in data:
        sd_data[18] = f"{float(data['pco2']['co2_air']):.1f}"
        sd_data[19] = f"{float(data['pco2']['co2_water']):.1f}"

    if 'adcp' in data:
        _u = float(data['adcp']['u'])
        _v = float(data['adcp']['v'])
        _uv = math.sqrt(_u ** 2 + _v ** 2) * _MMS_TO_MS
        _dir = math.atan2(_u, _v) % 360

        sd_data[35] = f"{_uv:.1f}"
        sd_data[36] = f"{_dir:.0f}"

    # fixme replace nan not need for try, except

    for index, value in enumerate(sd_data):
        if value in ['nan', 'NA']:
            sd_data[index] = '#'

    if sd_padding is True:
        padding = {
            0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 2, 6: 2, 7: 3, 8: 4, 9: 3, 10: 6, 11: 5, 12: 5, 13: 5,
            14: 9, 15: 6, 16: 5, 17: 4, 18: 5, 19: 5, 20: 6, 21: 4, 22: 4, 23: 4, 24: 4, 25: 4, 26: 4,
            27: 4, 28: 3, 29: 3, 30: 0, 31: 3, 32: 4, 33: 3, 34: 4, 35: 3, 36: 3, 37: 0, 38: 0,
        }
        for index, _just in padding.items():
            sd_data[index] = sd_data[index].rjust(_just)

    return ','.join(sd_data)


def _ensure_target_dir(path: str):
    Path(path).mkdir(parents=True, exist_ok=True)


def _get_output_path(target_dir: str, station_name: str) -> str:
    return Path(target_dir).joinpath(station_name)

