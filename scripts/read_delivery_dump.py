"""Read mysqldump INSERT data without executing SQL from an incoming archive."""
import json
from pathlib import Path
import re
import sys


def values(text):
    rows, row, i = [], None, 0
    escapes = {'0': '\0', 'b': '\b', 'n': '\n', 'r': '\r', 't': '\t', 'Z': '\x1a'}
    while i < len(text):
        c = text[i]
        if c.isspace() or c == ',':
            i += 1
            continue
        if c == '(':
            if row is not None: raise ValueError('Unexpected nested SQL value')
            row = []
            i += 1
        elif c == ')':
            if row is None: raise ValueError('Unexpected SQL row end')
            rows.append(row)
            row = None
            i += 1
        elif c == "'":
            i += 1
            out = []
            while i < len(text):
                if text[i] == '\\':
                    i += 1
                    out.append(escapes.get(text[i], text[i]))
                    i += 1
                elif text[i] == "'":
                    if i + 1 < len(text) and text[i + 1] == "'":
                        out.append("'"); i += 2
                    else:
                        i += 1
                        break
                else:
                    out.append(text[i]); i += 1
            else:
                raise ValueError('Unterminated SQL string')
            if row is None: raise ValueError('String outside SQL row')
            row.append(''.join(out))
        else:
            match = re.match(r'NULL|-?\d+(?:\.\d+)?', text[i:])
            if not match or row is None: raise ValueError('Unsupported SQL value')
            raw = match.group()
            row.append(None if raw == 'NULL' else float(raw) if '.' in raw else int(raw))
            i += len(raw)
    if row is not None: raise ValueError('Unterminated SQL row')
    return rows


def read_dump(path):
    raw = Path(path).read_bytes()
    return parse_dump(raw)


def parse_dump(raw):
    sql = raw.decode('utf-16' if raw.startswith(b'\xff\xfe') else 'utf-8-sig')
    schemas = {m[1]: re.findall(r'^\s+`([^`]+)`\s', m[2], re.M)
               for m in re.finditer(r'CREATE TABLE `(\w+)` \((.*?)\) ENGINE=', sql, re.S)}
    tables = {name: [] for name in schemas}
    matches = list(re.finditer(r'^INSERT INTO `(\w+)` VALUES (.*);[ \r]*$', sql, re.M))
    if len(matches) != len(re.findall(r'^INSERT INTO ', sql, re.M)):
        raise ValueError('Not all INSERT statements could be read')
    for match in matches:
        name = match[1]
        for row in values(match[2]):
            if len(row) != len(schemas[name]): raise ValueError('SQL column count mismatch')
            tables[name].append(dict(zip(schemas[name], row)))
    return tables


if __name__ == '__main__':
    tables = read_dump(sys.argv[1])
    print(json.dumps({'counts': {k: len(v) for k, v in tables.items()},
                      'users': [{k: r[k] for k in ('id', 'username', 'role')} for r in tables.get('users', [])],
                      'pipelines': [{k: r[k] for k in ('id', 'title', 'status')} for r in tables.get('pipeline_jobs', [])],
                      'results': [{k: r[k] for k in ('id', 'title', 'status')} for r in tables.get('evaluation_results', [])]}, ensure_ascii=False, indent=2))
