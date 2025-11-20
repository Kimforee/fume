import csv
import io
from typing import List, Dict, Tuple, Optional, Iterator
from app.models.product import Product


def detect_column_mapping(headers: List[str]) -> Dict[str, str]:
    """
    Intelligently map CSV columns to our expected fields.
    Accepts any column names and tries to match them.
    
    Args:
        headers: List of column names from CSV header
    
    Returns:
        Dictionary mapping our field names to CSV column names
    """
    normalized_headers = {h.strip().lower(): h for h in headers}
    mapping = {}
    
    # Try to find name column (case-insensitive, partial matches)
    name_keywords = ['name', 'product name', 'product_name', 'title', 'product']
    for keyword in name_keywords:
        for header_key, original_header in normalized_headers.items():
            if keyword in header_key:
                mapping['name'] = original_header
                break
        if 'name' in mapping:
            break
    
    # Try to find SKU column
    sku_keywords = ['sku', 'product_sku', 'product sku', 'code', 'product_code', 'id']
    for keyword in sku_keywords:
        for header_key, original_header in normalized_headers.items():
            if keyword in header_key:
                mapping['sku'] = original_header
                break
        if 'sku' in mapping:
            break
    
    # Try to find description column
    desc_keywords = ['description', 'desc', 'details', 'detail', 'notes', 'note']
    for keyword in desc_keywords:
        for header_key, original_header in normalized_headers.items():
            if keyword in header_key:
                mapping['description'] = original_header
                break
        if 'description' in mapping:
            break
    
    return mapping


def parse_csv_file_streaming(file_content: bytes, delimiter: str = None) -> Iterator[Dict[str, str]]:
    """
    Parse CSV file content as a generator (streaming) to avoid loading entire file into memory.
    
    Accepts any column names and auto-detects the mapping.
    
    Args:
        file_content: Bytes content of the CSV file
        delimiter: CSV delimiter (None = auto-detect)
    
    Yields:
        Dictionary with keys: row_number, name, sku, description
    """
    # Decode in chunks to avoid memory issues
    text_content = file_content.decode('utf-8')
    
    # Normalize line endings (handle Windows \r\n)
    text_content = text_content.replace('\r\n', '\n').replace('\r', '\n')
    
    # Auto-detect delimiter if not specified
    if delimiter is None:
        first_line = text_content.split('\n')[0] if '\n' in text_content else text_content
        if ',' in first_line:
            delimiter = ','
        elif '\t' in first_line:
            delimiter = '\t'
        else:
            delimiter = ','  # Default to comma
    
    reader = csv.DictReader(io.StringIO(text_content), delimiter=delimiter)
    
    # Get column mapping from headers
    if reader.fieldnames:
        column_mapping = detect_column_mapping(reader.fieldnames)
    else:
        column_mapping = {}
    
    for row_num, row in enumerate(reader, start=2):  # Start at 2 (header is row 1)
        # Normalize keys (strip whitespace, lowercase)
        normalized_row = {k.strip().lower(): (v.strip() if v else '') for k, v in row.items()}
        
        # Skip empty rows
        if not any(normalized_row.values()):
            continue
        
        # Extract values using column mapping
        name = None
        sku = None
        description = None
        
        # Try mapped column first, then fallback to direct lookup
        if 'name' in column_mapping:
            name = normalized_row.get(column_mapping['name'].strip().lower(), '').strip()
        else:
            # Fallback: try common variations
            for key in ['name', 'product name', 'product_name', 'title']:
                if key in normalized_row:
                    name = normalized_row[key].strip()
                    break
        
        if 'sku' in column_mapping:
            sku = normalized_row.get(column_mapping['sku'].strip().lower(), '').strip()
        else:
            # Fallback: try common variations
            for key in ['sku', 'product_sku', 'product sku', 'code', 'product_code']:
                if key in normalized_row:
                    sku = normalized_row[key].strip()
                    break
        
        if 'description' in column_mapping:
            desc_val = normalized_row.get(column_mapping['description'].strip().lower(), '').strip()
            description = desc_val if desc_val else None
        else:
            # Fallback: try common variations
            for key in ['description', 'desc', 'details', 'detail']:
                if key in normalized_row:
                    description = normalized_row[key].strip() or None
                    break
        
        # Validate required fields
        if not name or not sku:
            continue  # Skip rows with missing required fields
        
        yield {
            'row_number': row_num,
            'name': name,
            'sku': sku,
            'description': description,
        }


def parse_csv_file(file_content: bytes, delimiter: str = None) -> List[Dict[str, str]]:
    """
    Parse CSV file content and return list of dictionaries.
    For large files, use parse_csv_file_streaming instead.
    
    Args:
        file_content: Bytes content of the CSV file
        delimiter: CSV delimiter (None = auto-detect)
    
    Returns:
        List of dictionaries with keys: name, sku, description
    """
    return list(parse_csv_file_streaming(file_content, delimiter))


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
