import pandas as pd
import uuid
from models.public import db
from models.transport import Line, Stop

def parse_coordinates(coord_str):
    """
    Parses a coordinate string like '5,2602077, -3,60606' to (5.2602077, -3.60606).
    Handles potential variations in delimiters.
    """
    if not isinstance(coord_str, str):
        return None, None
    
    try:
        # Normalize the string: replace commas used as decimal separators (?) or splitters
        # The example '5,2602077, -3,60606' is tricky. It looks like comma is decimal separator AND splitter?
        # Let's assume standard format might be "lat, lon" or "lat,lon". 
        # But if comma is decimal separator (French locale), it's ambiguous: "5,26, -3,60" -> "5.26", "-3.60"
        
        # Heuristic: split by comma. 
        # If 2 parts: lat, lon (dot decimal)
        # If 4 parts: lat_int, lat_dec, lon_int, lon_dec (comma decimal)
        # Let's clean up first.
        
        parts = [p.strip() for p in coord_str.split(',')]
        
        if len(parts) == 2:
            # Case: 5.26, -3.60 OR 5,26 (if single number? no) OR 526, 360
            # If parts contain dots, likely "lat, lon"
            lat = float(parts[0])
            lon = float(parts[1])
            return lat, lon
            
        elif len(parts) >= 3:
            # Case '5,2602077, -3,60606' -> ['5', '2602077', '-3', '60606']
            # Reconstruct: 5.2602077, -3.60606
            # This logic assumes the structure is specifically [lat_int, lat_dec, lon_int, lon_dec]
            # And that the second and fourth parts are the decimals.
            
            # Note: "Geographic Coordinates" column in inspection showed '5,2602077, -3,60606'
            # This strongly suggests "5,2602077" is lat and "-3,60606" is lon, using comma as decimal separator.
            # And they are separated by ", " (comma space).
            
            # Let's try to interpret as "float(dots) , float(dots)" first?
            # Or split by space?
            pass

        # Robust approach for "5,2602077, -3,60606":
        # Replace first comma with dot, find the split between numbers, replace second comma with dot.
        # Maybe simply replacing all commas with dots is wrong if comma is the separator.
        
        # Let's look at the example again: '5,2602077, -3,60606'
        # It seems like there is a space after the middle comma.
        # Strategy: Split by " " (space).
        # "5,2602077," and "-3,60606"
        
        parts_space = coord_str.split()
        if len(parts_space) == 2:
            lat_str = parts_space[0].replace(',', '.').rstrip('.')
            lon_str = parts_space[1].replace(',', '.').rstrip('.')
            # Remove trailing comma from lat_str if it was "5,2602077,"
            if lat_str.endswith(','): lat_str = lat_str[:-1] # Already replaced by dot? No, replace(',', '.') makes it dot.
            
            # If the original string was "5,2602077, -3,60606", split by space gives: "5,2602077," and "-3,60606"
            # lat_str: "5.2602077." (if trailing comma) or just "5.2602077"
            # Let's be safer.
            
            raw_lat = parts_space[0].strip().rstrip(',')
            raw_lon = parts_space[1].strip()
            
            lat = float(raw_lat.replace(',', '.'))
            lon = float(raw_lon.replace(',', '.'))
            return lat, lon
            
    except Exception as e:
        print(f"Error parsing coordinates '{coord_str}': {e}")
        return None, None
        
    return None, None

def import_lines_from_excel(file_path='lines.xlsx'):
    print(f"Starting import from {file_path}...")
    try:
        xl = pd.ExcelFile(file_path)
    except FileNotFoundError:
        print(f"File {file_path} not found. Skipping import.")
        return

    for sheet_name in xl.sheet_names:
        print(f"Processing line: {sheet_name}")
        
        # Check if line exists, if not create
        line = Line.query.filter_by(name=sheet_name).first()
        if not line:
            line = Line(id=uuid.uuid4(), name=sheet_name)
            db.session.add(line)
            db.session.flush() # Get ID
        
        # Process stops
        df = xl.parse(sheet_name)
        
        # Clear existing stops for this line to avoid duplicates/conflicts on re-import?
        # Or simple update? "Sync" implies matching state.
        # Safest for now: delete all stops for this line and recreate them.
        Stop.query.filter_by(line_id=line.id).delete()
        
        for index, row in df.iterrows():
            stop_name = row.get('Stops')
            geo_coords = row.get('Geographic Coordinates')
            
            if pd.isna(stop_name):
                continue
                
            lat, lon = parse_coordinates(geo_coords)
            
            stop = Stop(
                id=uuid.uuid4(),
                line_id=line.id,
                name=stop_name,
                latitude=lat,
                longitude=lon,
                order=index
            )
            db.session.add(stop)
            
        try:
            db.session.commit()
            print(f"Successfully imported line: {sheet_name}")
        except Exception as e:
            db.session.rollback()
            print(f"Error saving line {sheet_name}: {e}")

    print("Import completed.")
