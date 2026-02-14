import os
import sqlite3
import logging
from dotenv import load_dotenv
from parser import PDMParser
import chromadb
from chromadb.utils import embedding_functions
from typing import List, Dict, Any

# Load environment variables
load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class PDMIndexer:
    def __init__(self):
        self.db_path = os.getenv("SQLITE_DB_PATH", "./data/metadata.db")
        self.chroma_path = os.getenv("CHROMA_DB_PATH", "./data/chroma_db")
        self.pdm_dir = os.getenv("PDM_FILES_DIR", "./files")
        self.model_name = os.getenv("MODEL_NAME", "paraphrase-multilingual-MiniLM-L12-v2")
        
        # Initialize SQLite
        self.conn = sqlite3.connect(self.db_path)
        self._init_sqlite()
        
        # Initialize Chroma
        self.chroma_client = chromadb.PersistentClient(path=self.chroma_path)
        # Use built-in ONNX model (very lightweight, no API key, no PyTorch)
        self.embedding_fn = embedding_functions.ONNXMiniLM_L6_V2()
        
        try:
            self.collection = self.chroma_client.get_or_create_collection(
                name="pdm_metadata", 
                embedding_function=self.embedding_fn
            )
        except ValueError as e:
            if "already exists" in str(e):
                logger.info("Embedding function conflict detected. Recreating collection for ONNX...")
                self.chroma_client.delete_collection("pdm_metadata")
                self.collection = self.chroma_client.create_collection(
                    name="pdm_metadata", 
                    embedding_function=self.embedding_fn
                )
            else:
                raise e

    def _init_sqlite(self):
        cursor = self.conn.cursor()
        # Create tables
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pdm_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_name TEXT UNIQUE,
                last_indexed TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tables (
                id TEXT PRIMARY KEY,
                file_id INTEGER,
                name TEXT,
                code TEXT,
                comment TEXT,
                FOREIGN KEY(file_id) REFERENCES pdm_files(id)
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS columns (
                id TEXT PRIMARY KEY,
                table_id TEXT,
                name TEXT,
                code TEXT,
                comment TEXT,
                data_type TEXT,
                length TEXT,
                mandatory INTEGER,
                FOREIGN KEY(table_id) REFERENCES tables(id)
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS references_rels (
                id TEXT PRIMARY KEY,
                file_id INTEGER,
                name TEXT,
                code TEXT,
                parent_table_id TEXT,
                child_table_id TEXT,
                FOREIGN KEY(file_id) REFERENCES pdm_files(id)
            )
        ''')
        self.conn.commit()

    def index_all(self):
        """Scans the PDM directory and indexes all files."""
        if not os.path.exists(self.pdm_dir):
            logger.error(f"PDM directory not found: {self.pdm_dir}")
            return

        for file_name in os.listdir(self.pdm_dir):
            if file_name.endswith(".pdm"):
                file_path = os.path.join(self.pdm_dir, file_name)
                self.index_file(file_path)

    def index_file(self, file_path: str):
        file_name = os.path.basename(file_path)
        logger.info(f"Indexing file: {file_name}")
        
        cursor = self.conn.cursor()
        # Register file
        cursor.execute("INSERT OR REPLACE INTO pdm_files (file_name) VALUES (?)", (file_name,))
        file_id = cursor.lastrowid
        
        parser = PDMParser(file_path)
        tables = parser.parse_tables()
        references = parser.parse_references()

        # Index Tables and Columns
        for table in tables:
            cursor.execute('''
                INSERT OR REPLACE INTO tables (id, file_id, name, code, comment)
                VALUES (?, ?, ?, ?, ?)
            ''', (table['id'], file_id, table['name'], table['code'], table['comment']))
            
            # Prepare for Chroma indexing
            # We index table name, code, and comment
            table_content = f"Table: {table['name']} ({table['code']}). Comment: {table['comment']}"
            self.collection.upsert(
                ids=[table['id']],
                documents=[table_content],
                metadatas=[{"type": "table", "name": table['name'], "code": table['code'], "file": file_name}]
            )

            for col in table['columns']:
                cursor.execute('''
                    INSERT OR REPLACE INTO columns (id, table_id, name, code, comment, data_type, length, mandatory)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (col['id'], table['id'], col['name'], col['code'], col['comment'], 
                      col['data_type'], col['length'], 1 if col['mandatory'] else 0))
                
                # Optionally index columns if they have comments
                if col['comment']:
                    col_content = f"Column in {table['name']}: {col['name']} ({col['code']}). Comment: {col['comment']}"
                    self.collection.upsert(
                        ids=[col['id']],
                        documents=[col_content],
                        metadatas=[{"type": "column", "table_id": table['id'], "name": col['name'], "code": col['code'], "file": file_name}]
                    )

        # Index References
        for ref in references:
            cursor.execute('''
                INSERT OR REPLACE INTO references_rels (id, file_id, name, code, parent_table_id, child_table_id)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (ref['id'], file_id, ref['name'], ref['code'], ref['parent_table_ref'], ref['child_table_ref']))

        self.conn.commit()
        logger.info(f"Finished indexing {file_name}")

if __name__ == "__main__":
    indexer = PDMIndexer()
    indexer.index_all()
