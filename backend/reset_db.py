from backend import database, models
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def reset_database():
    print("WARNING: This will DROP ALL TABLES in the database. Are you sure? (y/n)")
    # Since this is run via tool, we skip interactive input and assume 'y' if run manually or force it.
    # For safety in script, let's just proceed as this is a specific user request.
    
    logger.info("Dropping all tables...")
    try:
        models.Base.metadata.drop_all(bind=database.engine)
        logger.info("Tables dropped successfully.")
    except Exception as e:
        logger.error(f"Error dropping tables: {e}")
        return

    logger.info("Creating all tables from models...")
    try:
        models.Base.metadata.create_all(bind=database.engine)
        logger.info("Tables created successfully.")
    except Exception as e:
        logger.error(f"Error creating tables: {e}")

if __name__ == "__main__":
    reset_database()
