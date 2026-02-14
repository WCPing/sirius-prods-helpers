import os
import sqlite3
from langchain.tools import BaseTool
from chromadb import PersistentClient
from chromadb.utils import embedding_functions
from typing import Optional, List, Dict, Any

class ListTablesTool(BaseTool):
    name: str = "list_tables"
    description: str = "Lists all tables available in the PDM document."

    def _run(self, query: str = ""):
        db_path = os.getenv("SQLITE_DB_PATH", "./data/metadata.db")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT code, name, comment FROM tables")
        results = cursor.fetchall()
        conn.close()
        
        if not results:
            return "No tables found in the metadata."
            
        output = "Available Tables:\n"
        for code, name, comment in results:
            output += f"- {code} ({name}): {comment[:50]}...\n"
        return output

class TableSchemaTool(BaseTool):
    name: str = "get_table_schema"
    description: str = "Gets the detailed schema (columns, types, comments) for a specific table by its CODE."

    def _run(self, table_code: str):
        db_path = os.getenv("SQLITE_DB_PATH", "./data/metadata.db")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get table info
        cursor.execute("SELECT id, name, comment FROM tables WHERE code = ?", (table_code,))
        table = cursor.fetchone()
        if not table:
            return f"Table '{table_code}' not found."
            
        table_id, table_name, table_comment = table
        
        # Get columns
        cursor.execute("""
            SELECT name, code, data_type, length, mandatory, comment 
            FROM columns WHERE table_id = ?
        """, (table_id,))
        columns = cursor.fetchall()
        conn.close()
        
        output = f"Schema for table: {table_name} ({table_code})\n"
        output += f"Comment: {table_comment}\n\n"
        output += "Columns:\n"
        output += f"{'Name':<20} | {'Code':<20} | {'Type':<15} | {'Mandatory':<10} | {'Comment'}\n"
        output += "-" * 100 + "\n"
        
        for name, code, d_type, length, mandatory, comment in columns:
            m_str = "Yes" if mandatory else "No"
            type_str = f"{d_type}({length})" if length else d_type
            output += f"{name:<20} | {code:<20} | {type_str:<15} | {m_str:<10} | {comment}\n"
            
        return output

class SearchTablesTool(BaseTool):
    name: str = "search_tables"
    description: str = "Performs a semantic search to find relevant tables based on a conceptual query (e.g., 'user info', 'orders')."

    def _run(self, query: str):
        chroma_path = os.getenv("CHROMA_DB_PATH", "./data/chroma_db")
        # Use built-in ONNX model (matching the indexer)
        embedding_fn = embedding_functions.ONNXMiniLM_L6_V2()
        
        client = PersistentClient(path=chroma_path)
        collection = client.get_collection(name="pdm_metadata", embedding_function=embedding_fn)
        
        results = collection.query(
            query_texts=[query],
            n_results=5,
            where={"type": "table"}
        )
        
        if not results['documents'][0]:
            return "No matching tables found for your query."
            
        output = "Search Results (Top 5):\n"
        for doc, metadata in zip(results['documents'][0], results['metadatas'][0]):
            output += f"- {metadata['name']} ({metadata['code']}): {doc}\n"
        return output

class RelationshipTool(BaseTool):
    name: str = "find_relationships"
    description: str = "Finds all foreign key relationships for a specific table by its CODE."

    def _run(self, table_code: str):
        db_path = os.getenv("SQLITE_DB_PATH", "./data/metadata.db")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get table ID
        cursor.execute("SELECT id FROM tables WHERE code = ?", (table_code,))
        table = cursor.fetchone()
        if not table:
            return f"Table '{table_code}' not found."
        
        table_id = table[0]
        
        # Find incoming and outgoing references
        cursor.execute("""
            SELECT r.name, pt.code as parent, ct.code as child 
            FROM references_rels r
            JOIN tables pt ON r.parent_table_id = pt.id
            JOIN tables ct ON r.child_table_id = ct.id
            WHERE r.parent_table_id = ? OR r.child_table_id = ?
        """, (table_id, table_id))
        
        rels = cursor.fetchall()
        conn.close()
        
        if not rels:
            return f"No relationships found for table {table_code}."
            
        output = f"Relationships involving {table_code}:\n"
        for name, parent, child in rels:
            direction = "Parent" if parent == table_code else "Child"
            other = child if parent == table_code else parent
            output += f"- {name}: {table_code} ({direction}) <-> {other}\n"
        return output
