"""Deterministic inspection only. Uploaded code is parsed, never executed."""
import ast
import csv
import io
import math


def inspect_python(source):
    if len(source) > 200000:
        raise ValueError('Source exceeds inspection limit')
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return {'valid_syntax': False, 'line': exc.lineno, 'column': exc.offset, 'error': exc.msg,
                'executed': False}
    return {'valid_syntax': True, 'executed': False,
            'functions': [n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))][:100],
            'classes': [n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)][:100]}


def analyze_csv(text):
    if len(text) > 500000:
        raise ValueError('CSV exceeds 500KB analysis limit')
    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        return {'rows': 0, 'columns': [], 'numeric': {}}
    header, records = rows[0], rows[1:]
    numeric = {}
    for i, name in enumerate(header[:100]):
        values = []
        for row in records:
            try:
                value = float(row[i].strip())
                if math.isfinite(value): values.append(value)
            except (IndexError, ValueError):
                continue
        if values:
            numeric[f'{i+1}:{name}'] = {'count': len(values), 'sum': sum(values), 'mean': sum(values)/len(values),
                                      'min': min(values), 'max': max(values)}
    return {'rows': len(records), 'columns': header[:100], 'numeric': numeric,
            'ragged_rows': sum(len(row)!=len(header) for row in records),
            'empty_cells': sum(not cell.strip() for row in records for cell in row),
            'note': 'Numeric aggregates use plain finite numbers only; dates, currency, and locale-formatted numbers require interpretation.'}
