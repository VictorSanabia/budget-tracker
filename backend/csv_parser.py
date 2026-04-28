import pandas as pd
import io
from categorizer import categorize

def parse_usbank_csv(file_bytes: bytes, source: str) -> list[dict]:
    """
    US Bank checking/credit card CSV columns:
    Date, Transaction, Name, Memo, Amount
    """
    text = file_bytes.decode('utf-8', errors='replace')
    df = pd.read_csv(io.StringIO(text))
    df.columns = [c.strip() for c in df.columns]

    # Normalize column names
    col_map = {}
    for col in df.columns:
        cl = col.lower()
        if 'date' in cl:
            col_map[col] = 'date'
        elif 'name' in cl or 'description' in cl or 'merchant' in cl:
            col_map[col] = 'description'
        elif 'amount' in cl:
            col_map[col] = 'amount'
    df = df.rename(columns=col_map)

    # Keep only what we need
    needed = [c for c in ['date', 'description', 'amount'] if c in df.columns]
    df = df[needed].dropna(subset=['date', 'amount'])

    df['date'] = pd.to_datetime(df['date'], errors='coerce').dt.strftime('%Y-%m-%d')
    df = df.dropna(subset=['date'])

    df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0)

    if 'description' not in df.columns:
        df['description'] = 'Unknown'

    df['description'] = df['description'].fillna('Unknown').astype(str)
    df['category'] = df['description'].apply(categorize)
    df['source'] = source
    df['month'] = df['date'].str[:7]  # YYYY-MM

    return df.to_dict(orient='records')
