import sys
from app import create_app
from models.public import db, User
from datetime import datetime
import getpass

def create_admin():
    app = create_app()
    with app.app_context():
        print("=== Create Admin User ===")
        
        # Username
        while True:
            username = input("Username: ").strip()
            if not username:
                print("Username is required.")
                continue
            if User.query.filter_by(username=username).first():
                print("Username already taken.")
                continue
            break
        
        # Phone
        while True:
            phone = input("Phone: ").strip()
            if not phone:
                print("Phone is required.")
                continue
            item = User.query.filter_by(phone=phone).first()
            if item:
                print(f"User with phone {phone} already exists (ID: {item.id}, Role: {item.role}).")
                confirm = input("Do you want to update this user to admin? (y/n): ").lower()
                if confirm == 'y':
                    item.role = 'admin'
                    item.username = username # Update username if we overlap
                    item.set_password(getpass.getpass("New Password: "))
                    db.session.commit()
                    print("User updated to admin.")
                    return
                else:
                    continue
            break
            
        # Name
        name = input("Name: ").strip()
        
        # Password
        while True:
            password = getpass.getpass("Password: ")
            if not password:
                print("Password is required.")
                continue
            confirm = getpass.getpass("Confirm Password: ")
            if password != confirm:
                print("Passwords do not match.")
                continue
            break
            
        try:
            user = User(
                name=name,
                username=username,
                phone=phone,
                role='admin',
                created_at=datetime.utcnow()
            )
            user.set_password(password)
            
            db.session.add(user)
            db.session.commit()
            print(f"Admin user '{username}' created successfully.")
            
        except Exception as e:
            db.session.rollback()
            print(f"Error creating admin: {e}")

if __name__ == "__main__":
    create_admin()
