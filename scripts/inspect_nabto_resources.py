#!/usr/bin/env python3
"""Offline, read-only discovery of RPC query models in APK/APKS/XAPK/HTML-DD ZIP.

No application execution, no network calls, no secrets or raw resource dumping.
Requires Python >=3.10, standard library only.
"""
import argparse
import hashlib
import io
import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

MAX_MEMBER = 16 * 1024 * 1024
MAX_BYTES = 256 * 1024 * 1024
MAX_ENTRIES = 15000
TEXT = {'.xml', '.js', '.json', '.html', '.htm', '.txt', '.css', '.properties'}
NESTED = {'.apk', '.zip'}
SYMBOLS = re.compile(rb'rpcSetDefaultInterface|rpcSetInterface|rpcInvoke|unabto_queries|ping\.json|query_model\.xsd', re.I)
IDENT = re.compile(r'^[A-Za-z][A-Za-z0-9_.:-]{0,90}$')

def safe_path(s):
    return re.sub(r'[^A-Za-z0-9_./+\-]', '_', s)[-150:]

def parse_xml(data):
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        return []
    output = []
    for query in root.iter():
        if query.tag.split('}')[-1] != 'query':
            continue
        qname, qid = query.get('name', ''), query.get('id', '')
        if not IDENT.fullmatch(qname) or not qid.isdigit():
            continue
        parameters = {}
        for child in query:
            kind = child.tag.split('}')[-1]
            if kind not in ('request', 'response'):
                continue
            fields = []
            for node in child.iter():
                if node.tag.split('}')[-1] == 'parameter':
                    name, typ = node.get('name', ''), node.get('type', '')
                    if IDENT.fullmatch(name) and IDENT.fullmatch(typ):
                        fields.append(f'{name}:{typ}')
            parameters[kind] = fields
        output.append((qid, qname, parameters))
        if len(output) == 200:
            break
    return output

def scan(z, prefix, depth, result, budget):
    for entry in z.infolist():
        budget['entries'] += 1
        if budget['entries'] > MAX_ENTRIES or budget['bytes'] >= MAX_BYTES:
            budget['limited'] = True
            return
        if entry.is_dir() or not 0 < entry.file_size <= MAX_MEMBER:
            continue
        if entry.flag_bits & 1:
            budget['encrypted'] += 1
            continue
        suffix = Path(entry.filename).suffix.lower()
        if suffix not in TEXT | NESTED:
            continue
        try:
            data = z.read(entry)
        except (RuntimeError, OSError, zipfile.BadZipFile):
            continue
        budget['bytes'] += len(data)
        path = safe_path(prefix + '/' + entry.filename)
        if suffix in NESTED and depth < 2:
            try:
                with zipfile.ZipFile(io.BytesIO(data)) as inner:
                    scan(inner, path, depth+1, result, budget)
            except (OSError, zipfile.BadZipFile):
                pass
            continue
        if suffix == '.xml' or b'<unabto_queries' in data[:50000]:
            queries = parse_xml(data)
            if queries:
                result['queries'].append((path, queries))
        matches = sorted({v.decode('ascii').lower() for v in SYMBOLS.findall(data)})
        if matches:
            result['symbols'].append((path, matches))

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path, help='Official APK/APKS/XAPK/ZIP you obtained lawfully')
    args = parser.parse_args()
    archive = args.archive
    if not archive.is_file():
        parser.error('Archive not found')
    if archive.stat().st_size > (1 << 30):
        parser.error('Archive exceeds 1 GiB limit')
    result = {'queries': [], 'symbols': []}
    budget = {'entries': 0, 'bytes': 0, 'limited': False, 'encrypted': 0}
    try:
        with zipfile.ZipFile(archive) as z:
            scan(z, 'PACKAGE', 0, result, budget)
    except zipfile.BadZipFile:
        parser.error('Not a ZIP/APK container')
    with archive.open('rb') as f:
        digest = hashlib.file_digest(f, 'sha256').hexdigest()
    print('===== NABTO APP RESOURCE SCAN =====')
    print('SHA256:', digest)
    print('Entries:', budget['entries'], 'Bytes:', budget['bytes'])
    print('Limited:', budget['limited'], 'Encrypted entries skipped:', budget['encrypted'])
    print('XML queries:', sum(len(q) for _, q in result['queries']))
    for path, queries in result['queries'][:25]:
        print('SCHEMA:', path)
        for qid, name, parameters in queries:
            print('  QUERY:', qid, name)
            for kind, fields in parameters.items():
                print('   ', kind + ':', ', '.join(fields) or '(none)')
    print('Files with RPC-related symbols:', len(result['symbols']))
    for path, matches in result['symbols'][:40]:
        print('SYMBOLS:', path, '=>', ', '.join(matches))
    print('===== COMPLETE =====')
    if not result['queries']:
        print('No XML query model found; compiled DEX/native and runtime-loaded models not ruled out.')

if __name__ == '__main__':
    main()
