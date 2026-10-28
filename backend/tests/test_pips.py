import pytest
from app.engine import advance,realized_pips,metrics

@pytest.mark.parametrize('side,fill,exit_price,pips', [('BUY',4200,4204,40),('SELL',4200,4197,30),('BUY',4200,4197,-30),('SELL',4200,4203,-30)])
def test_signed_price_movement_in_pips(side,fill,exit_price,pips):
 s=dict(status='TP3',side=side,fill_price=fill,exit_price=exit_price,result_r=1)
 assert realized_pips(s)==pips
 assert metrics([s])['net_pips']==pips

def test_missing_exit_is_unknown_not_zero():
 assert realized_pips(dict(status='STOPPED',side='BUY',fill_price=4200,result_r=-1)) is None
 assert metrics([])['average_pips'] is None

def test_stop_gap_records_actual_pips():
 s=dict(status='OPEN',side='BUY',fill_price=4200,stop=4198,targets=[4202,4203,4204],targets_hit=0)
 advance(s,4197,1)
 assert s['result_pips']==-30 and s['result_r']==-1.5
