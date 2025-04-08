from database import engine, Base
import models
import logging
from sqlalchemy import inspect

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_table_exists(table_name):
    inspector = inspect(engine)
    return table_name in inspector.get_table_names()

def check_table_columns(table_name):
    inspector = inspect(engine)
    columns = inspector.get_columns(table_name)
    return [column['name'] for column in columns]

def init_db():
    try:
        logger.info("Starting database initialization...")
        
        # Check if tables exist
        if check_table_exists('forms'):
            logger.info("Forms table exists, checking columns...")
            columns = check_table_columns('forms')
            logger.info(f"Existing columns: {columns}")
        
        logger.info("Dropping all existing tables...")
        Base.metadata.drop_all(bind=engine)
        
        logger.info("Creating all tables...")
        Base.metadata.create_all(bind=engine)
        
        # Verify table creation
        if check_table_exists('forms'):
            columns = check_table_columns('forms')
            logger.info(f"Forms table created successfully with columns: {columns}")
        else:
            raise Exception("Forms table was not created properly")
        
        logger.info("Database initialization completed successfully!")
        
    except Exception as e:
        logger.error(f"Error during database initialization: {str(e)}")
        raise

if __name__ == "__main__":
    init_db() 