#!/usr/bin/env python3
"""Validate architecture source/SVG/PNG parity, metadata, size and secret hygiene."""
from pathlib import Path
import json, re, struct, sys

BASE=Path(__file__).resolve().parent.parent
expected=[f"{i:02d}-{name}" for i,name in enumerate(["platform-context","current-platform-architecture","target-aws-architecture","aws-network-architecture","frontend-architecture","backend-service-architecture","ai-runtime-architecture","agent-and-tool-architecture","data-architecture","security-and-authorization","integration-architecture","knowledge-and-evidence","approval-and-action-flow","observability-and-operations","cicd-deployment","backup-recovery","runtime-request-sequence","copilot-evidence-sequence","approved-action-sequence"])]
errors=[]
def png_size(path):
    with path.open('rb') as f:
        if f.read(8)!=b'\x89PNG\r\n\x1a\n': return (0,0)
        f.read(8); return struct.unpack('>II',f.read(8))
for stem in expected:
    src=BASE/'source'/f'{stem}.json'; svg=BASE/'svg'/f'{stem}.svg'; png=BASE/'png'/f'{stem}.png'
    for p in (src,svg,png):
        if not p.exists() or p.stat().st_size<100: errors.append(f'missing/empty: {p}')
    if not all(p.exists() for p in (src,svg,png)): continue
    data=json.loads(src.read_text()); text=svg.read_text(); w,h=png_size(png)
    if w<2560 or h<1400: errors.append(f'undersized: {png} {w}x{h}')
    for token in ('Legend','Generated','Git',data['title'],data['state']):
        if token not in text: errors.append(f'{svg}: missing {token}')
    statuses={node['status'] for col in data['columns'] for node in col[1:]}
    if not statuses <= {'IMPLEMENTED','PARTIALLY_IMPLEMENTED','CONFIGURED_NOT_VERIFIED','PROPOSED','EXTERNAL','UNKNOWN'}: errors.append(f'{src}: invalid status')
    for node in (node for col in data['columns'] for node in col[1:]):
        evidence=node.get('evidence','')
        if evidence and not (BASE.parents[1]/evidence).exists(): errors.append(f'{src}: missing evidence path {evidence}')
contact=BASE/'png'/'architecture-contact-sheet.png'
if not contact.exists() or png_size(contact)[0]<3840: errors.append('contact sheet missing/undersized')
secret_patterns=[r'AKIA[0-9A-Z]{16}',r'ATATT[0-9A-Za-z_=-]{20,}',r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',r'(?i)(?:api[_-]?key|client[_-]?secret|password)\s*[:=]\s*["\'][^"\']{8,}']
for folder in ('source','svg'):
    for path in (BASE/folder).glob('*'):
        text=path.read_text(errors='ignore')
        if any(re.search(pattern,text) for pattern in secret_patterns): errors.append(f'possible secret: {path}')
if errors:
    print('\n'.join(errors)); sys.exit(1)
print(f'Architecture validation passed: {len(expected)} diagrams + contact sheet')
