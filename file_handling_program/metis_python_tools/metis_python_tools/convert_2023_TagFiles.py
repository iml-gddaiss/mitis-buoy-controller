"""
Descriptions
------------
- Convert 2023 TAG files to 2024 Tag File
- Use `<>_Raw.dat` to get Co2 Air Pressure
- Uses `<>_FileADCP.dat` to get `u,v,w` data.


Usage
-----
magnetic_declination = 0
source_dir = "/path/to/source/directory/"
target_file = "/path/to/target/file.dat"
raw_string_file = "/path/to/raw/dat/PMZA-RIKI_Raw.dat"
raw_adcp_file = "/path/to/raw/dat/PMZA-RIKI_FileADCP.dat"

convert_to_new_TAGFile(filename=target_file, source_dir=source_dir, raw_tag_file=raw_tag_file, magnetic_declination=magnetic_declination)


"""
import re
import os
from math import sin, cos, radians
from pathlib import Path

NEW_TAG_STRUCTURE = {
    'init': ['buoy_name', 'date', 'time', 'latitude', 'longitude', 'heading', 'pitch', 'roll', 'pitch_std', 'roll_std',
             'cog', 'sog', 'magnetic_declination', 'water_detection'],
    'powr': ['volt_batt_1', 'amp_batt_1', 'volt_batt_2', 'amp_batt_2', 'volt_solar', 'amp_solar', 'amp_main',
             'amp_turbine', 'amp_winch', 'pm_rh', 'relay_state'],
    'eco1': ['scattering', 'chlorophyll', 'fdom'],
    'ctd': ['temperature', 'conductivity', 'salinity', 'density'],
    'ph': ['ext_ph_calc', 'int_ph_calc', 'error_flag', 'ext_ph', 'int_ph'],
    'no3': ['nitrate', 'nitrogen', 'bromide', 'rmse'],
    'wind': ['source', 'wind_dir_min', 'wind_dir_ave', 'wind_dir_max', 'wind_spd_min', 'wind_spd_ave', 'wind_spd_max'],
    'atms': ['air_temperature', 'air_humidity', 'air_pressure', 'par', 'rain_total', 'rain_duration', 'rain_intensity'],
    'wave': ['date', 'time', 'period', 'hm0', 'h13', 'hmax'],
    'adcp': ['date', 'time', 'u', 'v', 'w', 'err'],  # ADCP data are not in ENU
    'pco2': ['co2_ppm_air', 'co2_ppm_water'], #'gas_pressure_air', 'gas_pressure_water', 'air_humidity'],
    'wnch': ['message']
}


def convert_to_new_TAGFile(filename: str, source_dir: str, raw_string_file: str, raw_adcp_file: str, magnetic_declination: float):
    raw_data = {} #load_pco2_water_irga_from_raw(raw_string_file=raw_string_file)
    adcp_data = load_uvw_from_adcp_raw(raw_adcp_file=raw_adcp_file)
    with open(filename, "w") as f:
        for old_file in  sorted(walk_old_tag_file(source_dir)):
            unpacked_data = unpack_old_tag_file(old_file, raw_data=raw_data, adcp_data=adcp_data, magnetic_declination=magnetic_declination)
            tag_string = ""
            for key, data in unpacked_data.items():
                if data:
                    value = [v if (v and "#" not in v and "nan" not in v) else "NAN" for v in data.values()]
                    tag_string += "[" + key.upper() + "]" + ",".join(str(v) for v in value)
            f.write(tag_string + "\n")


def walk_old_tag_file(path: str) -> list:
    old_tag_files = []
    for p in os.listdir(path):
        d = Path(path).joinpath(p)
        if d.is_dir():
            for f in os.listdir(d):
                if f.endswith('.dat'):
                    old_tag_files.append(d.joinpath(f))

    return old_tag_files


def unpack_old_tag_file(input_file: str, raw_data: dict, adcp_data: dict, magnetic_declination: float) -> dict:
    INSTRUMENTS_TAG = ["INIT", "POWR", "TRP1", "CTD", "PHPRO", "PH", "WIND", "W700", "W536", "ATMS", "WAVE", "PCO2", "RDI", "SUNA", "WNCH"]
    DATA_TAG_REGEX = re.compile(rf"\[({'|'.join(INSTRUMENTS_TAG)})],?((?:(?!\[).)*)", re.DOTALL)

    data = {key: {} for key in NEW_TAG_STRUCTURE}

    with (open(input_file, 'r') as f):
        # for line in f:
        for data_sequence in DATA_TAG_REGEX.finditer(f.read()):
            line = f"[{data_sequence.group(1)}]{data_sequence.group(2)}"
            # Remove the first characters if the file is modified (because of the BOM garbage)
            if line[0] != "[":
                line = line[3:]

            line = line.strip("\n")

            if line[1:5] == "INIT":
                line = line[6:]
                INIT = line.split(",")
                _d = data['init']
                _d["buoy_name"] = INIT[0]  # Name
                _d["date"] = INIT[1]  # Date
                _d["time"] = INIT[2]  # Hour
                _d["latitude"] = INIT[3]  # Lat
                _d["longitude"] = INIT[4]  # Lon
                _d["heading"] = str(round(float(INIT[5]),2))  # Heading
                _d["pitch"] = INIT[6]  # Pitch
                _d["roll"] = INIT[7]  # Roll
                _d["pitch_std"] = "NAN"
                _d["roll_std"] = "NAN"
                _d["cog"] = INIT[8]
                _d["sog"] = INIT[9]
                _d["magnetic_declination"] = str(magnetic_declination)
                _d["water_detection"] = INIT[10]

                if _d['time'] == "00:00:00":
                    _time_index = "24:00:00"
                else:
                    _time_index = _d['time']

                _datetime_index = f"{data['init']['date']} {_time_index}"

            elif line[1:5] == "POWR":
                line = line[6:]
                POWR = line.split(",")
                _d = data["powr"]
                _d['volt_batt_1'] = POWR[0]
                _d['amp_batt_1'] = POWR[1]
                _d['volt_batt_2'] = POWR[2]
                _d['amp_batt_2'] = POWR[3]
                _d['volt_solar'] = POWR[4]
                _d['amp_solar'] = POWR[5]
                _d['amp_main'] = POWR[6]
                _d['amp_turbine'] = POWR[7]
                _d['amp_winch'] = POWR[8]
                _d['pm_rh'] = POWR[9]
                _d['relay_state'] = POWR[10]
            
            elif line[1:5] == "TRP1":
                line = line[6:]
                TRP1 = line.split(",")
                _d = data["eco1"]
                _d['scattering'] = TRP1[0]
                _d['chlorophyll'] = TRP1[1]
                _d['fdom'] = TRP1[2]

            elif line[1:4] == "CTD":
                line = line[5:]
                CTD = line.split(",")
                _d = data["ctd"]
                _d['temperature'] = CTD[0]
                _d['conductivity'] = CTD[1]
                _d['salinity'] = CTD[2]
                _d['density'] = CTD[3]

            elif line[1:6] == "PHPRO":
                # Int_pH & "," & Ext_pH & "," & Error_Flag & "," & Int_pH_P & "," & Ext_pH_P
                line = line[7:]
                PHPRO = line.split(",")
                _d = data["ph"]
                _d['ext_ph_calc'] = "NAN"
                _d['int_ph_calc'] = "NAN"
                _d['error_flag'] = PHPRO[2]
                _d['ext_ph'] = PHPRO[4]
                _d['int_ph'] = PHPRO[3]
            
            elif line[1:3] == "PH":
                #  Ext_pH & "," & Int_pH & "," & Error_Flag
                line = line[4:]
                PH = line.split(",")
                _d = data["ph"]
                _d['ext_ph_calc'] = "NAN"
                _d['int_ph_calc'] = "NAN"
                _d['error_flag'] = PH[2]
                _d['ext_ph'] = PH[0]
                _d['int_ph'] = PH[1]

            elif line[1:5] == "WIND" or line[1:5] == "W700" or line[1:5] == "W536":
                # Wind_Dir_Min, Wind_Dir_Ave, Wind_Dir_Max, Wind_Spd_Min, Wind_Spd_Ave, Wind_Spd_Max
                source = "7" if line[1:5] == "W700" else "5"
                line = line[6:]
                WIND = line.split(",")
                _d = data["wind"]
                _d['source'] = source
                _d['wind_dir_min'] = WIND[0]
                _d['wind_dir_ave'] = WIND[1]
                _d['wind_dir_max'] = WIND[2]
                _d['wind_spd_min'] = WIND[3]
                _d['wind_spd_ave'] = WIND[4]
                _d['wind_spd_max'] = WIND[5]

            elif line[1:5] == "ATMS":
                #"[ATMS]" & Air_Temp & "," & Air_Humidity & "," & Air_Pressure & "," & PAR & "," & Rain_Total & "," & Rain_Duration & "," & Rain_Intensity
                line = line[6:]
                ATMS = line.split(",")
                _d = data["atms"]
                _d['air_temperature'] = ATMS[0]
                _d['air_humidity'] = ATMS[1]
                _d['air_pressure'] = ATMS[2]
                _d['par'] = ATMS[3]
                _d['rain_total'] = ATMS[4]
                _d['rain_duration'] = ATMS[5]
                _d['rain_intensity'] = ATMS[6]

            elif line[1:5] == "WAVE":
                # "[WAVE]" & Wave_Date & "," & Wave_Time & "," & Wave_Period & "," & Wave_Hm0 & "," & Wave_H13 & "," & Wave_Hmax
                line = line[6:]
                WAVE = line.split(",")
                _d = data["wave"]
                _d['date'] = WAVE[0].replace("/", "-")[:10]
                _d['time'] = WAVE[1][:8]
                if len(_d['date']) != 10 or len(_d['time']) != 8 or "#" in _d['date'] or "#" in _d['time']:
                    _d['date'] = "NA"
                    _d['time'] = "NA"
                _d['period'] = WAVE[2]
                _d['hm0'] = WAVE[3]
                _d['h13'] = WAVE[4]
                _d['hmax'] = WAVE[5]

            elif line[1:5] == "PCO2":
                # "[PCO2]" & CO2_ppm_Water & "," & CO2_ppm_Air

                line = line[6:]
                PCO2 = line.split(",")
                _d = data["pco2"]
                _d['co2_ppm_air'] = PCO2[1]
                _d['co2_ppm_water'] = PCO2[0]

            elif line[1:4] == "RDI":
                # "[RDI]" & ADCPDate & "," & ADCPTime & "," & ADCPDir & "," & ADCPMag
                # not in u,v,w,err format.
                line = line[5:]
                RDI = line.split(",")
                if len(RDI) < 4:
                    continue
                _d = data["adcp"]
                _d['date'] = RDI[0].replace("/", "-")[:10]
                _d['time'] = RDI[1][:8]
                if len(_d['date']) != 10 or len(_d['time']) != 8 or "#" in _d['date'] or "#" in _d['time']:
                    _d['date'] = "NA"
                    _d['time'] = "NA"
                if _datetime_index in adcp_data:
                    [_u, _v, _w, _e] = adcp_data[_datetime_index]
                else:
                    [_u, _v, _w, _e] = ["NAN", "NAN", "NAN", "NAN"]
                _d['u'] = str(_u)
                _d['v'] = str(_v)
                _d['w'] = str(_w)
                _d['err'] = str(_e)

            elif line[1:5] == "SUNA":
                #"[SUNA]" & Dark_Nitrate & "," & Light_Nitrate & "," & Dark_Nitrogen_in_Nitrate & "," & Light_Nitrogen_in_Nitrate & "," & Dark_Bromide & "," & Light_Bromide
                line = line[6:]
                SUNA = line.split(",")
                _d = data['no3']
                _d['nitrate'] = SUNA[1]
                _d['nitrogen'] = SUNA[3]
                _d['bromide'] = SUNA[5]
                _d['rmse'] = "NAN"

            elif line[1:5] == "WNCH":
                line = line[6:]
                data["wnch"]["message"] = line
    return data


def load_pco2_water_irga_from_raw(raw_string_file: str) -> dict:
    """
    raw string: "2023-05-23 15:30:00",...,"2023,05,26,09,21,20,51145,50256,101.80,40.00,6.90,10.00,1012,11.6 ",...
    col 14: water
    col 15: air
    pco2 pressure: indx: 12
    """
    pattern = re.compile(r'''((?:[^,"']|"[^"]*"|'[^']*')+)''')

    _data = {}
    with open(raw_string_file, 'r') as f:
        for line in f:
            _var_data = {}
            col = pattern.findall(line)
            _data[col[0].strip('"')] = {}

            _field = col[14].strip('"')
            if _field:
                _co2_water_irga = _field.split(',')[9]
            else:
                _co2_water_irga = "NAN"
            _data[col[0].strip('"')]["co2_water_irga"] = _co2_water_irga
    return _data


def load_uvw_from_adcp_raw(raw_adcp_file: str) -> dict:
    """
    Return ['E/W', 'N/S', 'Vert', 'Err'] of the first bin
    """
    pattern = re.compile(r'''((?:[^,"']|"[^"]*"|'[^']*')+)''')

    _data = {}
    with open(raw_adcp_file, 'r') as f:
        for line in f:
            col = pattern.findall(line)
            _uvwe = col[6].strip('"').split(",")[3:7]  # ['E/W', 'N/S', 'Vert', 'Err']
            _data[col[0].strip('"')] = _uvwe
    return _data
    
