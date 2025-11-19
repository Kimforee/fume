import csv
import io
from typing import List, Dict, Tuple, Optional
from app.models.product import Product


def parse_csv_file(file_content: bytes, delimiter: str = '\t') -> List[Dict[str, str]]:
    """
    Parse CSV file content and return list of dictionaries.
    
    Expected format: name, sku, description (tab-separated)
    
    Args:
        file_content: Bytes content of the CSV file
        delimiter: CSV delimiter (default: tab)
    
    Returns:
        List of dictionaries with keys: name, sku, description
    """
    rows = []
    text_content = file_content.decode('utf-8')
    reader = csv.DictReader(io.StringIO(text_content), delimiter=delimiter)
    
    for row_num, row in enumerate(reader, start=2):  # Start at 2 (header is row 1)
        # Normalize keys (strip whitespace, lowercase)
        normalized_row = {k.strip().lower(): v.strip() if v else '' for k, v in row.items()}
        
        # Validate required fields
        if not normalized_row.get('name') or not normalized_row.get('sku'):
            continue  # Skip rows with missing required fields
        
        rows.append({
            'row_number': row_num,
            'name': normalized_row.get('name', '').strip(),
            'sku': normalized_row.get('sku', '').strip(),
            'description': normalized_row.get('description', '').strip() or None,
        })
    
    return rows


def validate_product_row(row: Dict[str, str]) -> Tuple[bool, Optional[str]]:
    """
    Validate a product row.
    
    Args:
        row: Dictionary with name, sku, description
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not row.get('name') or not row['name'].strip():
        return False, "Name is required"
    
    if not row.get('sku') or not row['sku'].strip():
        return False, "SKU is required"
    
    if len(row['name']) > 255:
        return False, "Name exceeds 255 characters"
    
    if len(row['sku']) > 255:
        return False, "SKU exceeds 255 characters"
    
    return True, None


def normalize_sku(sku: str) -> str:
    """
    Normalize SKU for case-insensitive comparison.
    
    Args:
        sku: SKU string
    
    Returns:
        Lowercase SKU
    """
    return sku.lower().strip()

