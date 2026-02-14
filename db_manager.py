import os
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
# Suppress noisy library logs
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

load_dotenv()

class DBConnectionManager:
    """Manages connections to multiple databases (MySQL, Oracle) using SQLAlchemy."""
    
    def __init__(self):
        self.engines = {}
        self._init_engines()

    def _init_engines(self):
        """Initialize database engines from environment variables."""
        # MySQL
        mysql_url = os.getenv("MYSQL_URL")
        if mysql_url and "your_mysql_url_here" not in mysql_url:
            try:
                self.engines["mysql"] = create_engine(mysql_url)
                logger.info("Successfully initialized MySQL engine.")
            except Exception as e:
                logger.error(f"Failed to initialize MySQL engine: {e}")

        # Oracle
        oracle_url = os.getenv("ORACLE_URL")
        if oracle_url and "your_oracle_url_here" not in oracle_url:
            try:
                # oracledb is the modern driver for Oracle
                self.engines["oracle"] = create_engine(oracle_url)
                logger.info("Successfully initialized Oracle engine.")
            except Exception as e:
                logger.error(f"Failed to initialize Oracle engine: {e}")

    def execute_query(self, db_type: str, sql: str, params: dict = None):
        """
        Executes a SQL query safely and returns results as a list of dictionaries.
        
        Args:
            db_type: 'mysql' or 'oracle'
            sql: The SQL string to execute
            params: Dictionary of parameters for the SQL query
        """
        if db_type not in self.engines:
            return f"Error: Database engine for '{db_type}' is not configured or failed to initialize."
        
        engine = self.engines[db_type]
        
        try:
            with engine.connect() as connection:
                # Use pandas for easy result formatting or manual cursor
                result = connection.execute(text(sql), params or {})
                if result.returns_rows:
                    rows = [dict(row._mapping) for row in result.all()]
                    return rows
                else:
                    connection.commit()
                    return f"Execution successful. Rows affected: {result.rowcount}"
        except Exception as e:
            logger.error(f"SQL Execution Error on {db_type}: {e}")
            return f"SQL Error: {str(e)}"

    def get_preview(self, db_type: str, table_name: str, limit: int = 5):
        """Quickly fetches a preview of table data."""
        sql = f"SELECT * FROM {table_name}"
        # Adjust limit syntax for Oracle vs MySQL
        if db_type == "oracle":
            sql = f"SELECT * FROM {table_name} FETCH FIRST {limit} ROWS ONLY"
        else:
            sql = f"SELECT * FROM {table_name} LIMIT {limit}"
            
        return self.execute_query(db_type, sql)

# Singleton instance
db_manager = DBConnectionManager()
