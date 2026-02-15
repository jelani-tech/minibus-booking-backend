from app import create_app
from models.public import db
from sqlalchemy import text

app = create_app()

def run_migration():
    with app.app_context():
        # 1. Add role to users (public schema)
        try:
            with db.engine.connect() as conn:
                conn.execute(text("ALTER TABLE public.users ADD COLUMN IF NOT EXISTS role VARCHAR(20) DEFAULT 'client'"))
                conn.commit()
                print("Added role to users")
        except Exception as e:
            print(f"Error adding role: {e}")

        # 2. Create vehicles table (partners schema)
        try:
           with db.engine.connect() as conn:
               conn.execute(text("""
                   CREATE TABLE IF NOT EXISTS partners.vehicles (
                       id UUID PRIMARY KEY,
                       plate_number VARCHAR(20) UNIQUE NOT NULL,
                       make VARCHAR(50) NOT NULL,
                       model VARCHAR(50) NOT NULL,
                       capacity INTEGER NOT NULL,
                       image_url VARCHAR(255),
                       status VARCHAR(20) DEFAULT 'ACTIVE',
                       created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                       updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                   )
               """))
               conn.commit()
               print("Created vehicles table")
        except Exception as e:
            print(f"Error creating vehicles table: {e}")

        # 3. Add vehicle_id to scheduled_trips (partners schema)
        try:
            with db.engine.connect() as conn:
                conn.execute(text("ALTER TABLE partners.scheduled_trips ADD COLUMN IF NOT EXISTS vehicle_id UUID REFERENCES partners.vehicles(id)"))
                conn.commit()
                print("Added vehicle_id to scheduled_trips")
        except Exception as e:
            print(f"Error adding vehicle_id: {e}")

        print("Migration completed.")

if __name__ == "__main__":
    run_migration()
