import os
from lxml import etree
import logging
from typing import List, Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class PDMParser:
    """
    Parser for PowerDesigner physical data model (.pdm) files.
    Extracts tables, columns, and relationships.
    """
    
    # Common PDM namespaces
    NS = {
        'a': 'attribute',
        'c': 'collection',
        'o': 'object'
    }

    def __init__(self, file_path: str):
        self.file_path = file_path
        self.tree = None
        self.root = None

    def load(self):
        """Loads and parses the XML file."""
        if not os.path.exists(self.file_path):
            raise FileNotFoundError(f"File not found: {self.file_path}")
        
        logger.info(f"Parsing PDM file: {self.file_path}")
        try:
            # PDM files can be large, using etree.parse
            self.tree = etree.parse(self.file_path)
            self.root = self.tree.getroot()
        except Exception as e:
            logger.error(f"Failed to parse XML: {e}")
            raise

    def get_text(self, element, xpath: str) -> str:
        """Helper to get text from an attribute element."""
        found = element.xpath(xpath, namespaces=self.NS)
        if found and found[0].text:
            return found[0].text.strip()
        return ""

    def parse_tables(self) -> List[Dict[str, Any]]:
        """Extracts all table definitions from the model."""
        if self.root is None:
            self.load()

        tables = []
        # Tables are usually under //c:Tables/o:Table
        table_nodes = self.root.xpath('//o:Table[@Id]', namespaces=self.NS)
        
        logger.info(f"Found {len(table_nodes)} table definitions.")

        for table_node in table_nodes:
            table_id = table_node.get('Id')
            table_name = self.get_text(table_node, 'a:Name')
            table_code = self.get_text(table_node, 'a:Code')
            table_comment = self.get_text(table_node, 'a:Comment')

            columns = []
            column_nodes = table_node.xpath('.//c:Columns/o:Column[@Id]', namespaces=self.NS)
            for col_node in column_nodes:
                column = {
                    'id': col_node.get('Id'),
                    'name': self.get_text(col_node, 'a:Name'),
                    'code': self.get_text(col_node, 'a:Code'),
                    'comment': self.get_text(col_node, 'a:Comment'),
                    'data_type': self.get_text(col_node, 'a:DataType'),
                    'length': self.get_text(col_node, 'a:Length'),
                    'mandatory': self.get_text(col_node, 'a:Column.Mandatory') == '1'
                }
                columns.append(column)

            tables.append({
                'id': table_id,
                'name': table_name,
                'code': table_code,
                'comment': table_comment,
                'columns': columns
            })

        return tables

    def parse_references(self) -> List[Dict[str, Any]]:
        """Extracts foreign key relationships (references)."""
        if self.root is None:
            self.load()

        references = []
        ref_nodes = self.root.xpath('//o:Reference[@Id]', namespaces=self.NS)
        
        for ref_node in ref_nodes:
            ref_id = ref_node.get('Id')
            ref_name = self.get_text(ref_node, 'a:Name')
            ref_code = self.get_text(ref_node, 'a:Code')
            
            # Parent Table
            parent_node = ref_node.xpath('c:ParentTable/o:Table', namespaces=self.NS)
            parent_ref = parent_node[0].get('Ref') if parent_node else ""
            
            # Child Table
            child_node = ref_node.xpath('c:ChildTable/o:Table', namespaces=self.NS)
            child_ref = child_node[0].get('Ref') if child_node else ""

            references.append({
                'id': ref_id,
                'name': ref_name,
                'code': ref_code,
                'parent_table_ref': parent_ref,
                'child_table_ref': child_ref
            })

        return references

if __name__ == "__main__":
    # Quick debug test
    import json
    pdm_path = "files/100_bm_product_bm_spc_oracle.pdm"
    if os.path.exists(pdm_path):
        parser = PDMParser(pdm_path)
        tables = parser.parse_tables()
        print(f"Parsed {len(tables)} tables.")
        if tables:
            print(json.dumps(tables[0], indent=2, ensure_ascii=False))
