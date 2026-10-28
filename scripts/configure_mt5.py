#!/usr/bin/env python3
"""Prepare local MT5 configuration without displaying or transmitting secrets."""
import argparse
from pathlib import Path
import re
import secrets

ROOT=Path(__file__).resolve().parents[1]

def configure(symbol):
    if not re.fullmatch(r'XAUUSD[A-Za-z0-9._-]*',symbol):
        raise ValueError('Use the exact Valetax XAUUSD symbol from Market Watch.')
    path=ROOT/'backend/.env'
    text=path.read_text() if path.exists() else (ROOT/'backend/.env.example').read_text()
    existing=re.search(r'^MT5_BRIDGE_TOKEN=(.+)$',text,re.M)
    token=existing.group(1).strip() if existing else ''
    if len(token)<32:
        token=secrets.token_urlsafe(32)
    values={'DATA_MODE':'mt5','MT5_SYMBOL':symbol,'MT5_BRIDGE_TOKEN':token,'MT5_STALE_SECONDS':'15'}
    for key,value in values.items():
        pattern=r'^'+key+r'=.*$'
        if re.search(pattern,text,re.M):text=re.sub(pattern,lambda _:key+'='+value,text,flags=re.M)
        else:text+='\n'+key+'='+value+'\n'
    # Local file only: the key is not sent to an external app or emitted as output.
    path.write_text(text)
    path.chmod(0o600)
    print('MT5 configuration saved. Restart Aurum. Copy the local token from backend/.env into the EA input privately.')

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--symbol',required=True)
    configure(parser.parse_args().symbol)
