
from app import create_app
from models.transport import Line, Stop
from models.public import db

app = create_app()

with app.app_context():
    print("--- Verifying Transport Data ---")
    lines_count = Line.query.count()
    stops_count = Stop.query.count()
    
    print(f"Total Lines: {lines_count}")
    print(f"Total Stops: {stops_count}")
    
    if lines_count > 0:
        line = Line.query.first()
        print(f"Sample Line: {line.name}")
        stops = Stop.query.filter_by(line_id=line.id).order_by(Stop.order).limit(3).all()
        for stop in stops:
            print(f"  - Stop {stop.order}: {stop.name} ({stop.latitude}, {stop.longitude})")
    else:
        print("No lines found!")
