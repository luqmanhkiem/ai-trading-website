from app.engine import Candle
from app.market_analysis import AnalysisService, confirmed_swings, fair_value_gaps, swing_sweeps
from test_engine import fixture_bars


def test_timeframes_show_real_history_requirements_and_m1_unavailable():
    d=AnalysisService().snapshot(fixture_bars(),36000)
    assert d['by_timeframe']['M5']['ready']
    assert d['by_timeframe']['M15']['bar_count']==40
    assert not d['by_timeframe']['H1']['ready']
    assert not d['by_timeframe']['M1']['ready'] and d['by_timeframe']['M1']['candles']==[]
    assert sum(d['alignment'].values())==6
    assert 'H4' not in d['timeframes'] and 'H4' not in d['by_timeframe']


def test_open_fvg_partial_fill_then_full_mitigation():
    bars=[Candle(0,100,101,99,100),Candle(300,100,105,100,104),Candle(600,105,107,104,106)]
    gap=fair_value_gaps(bars)[0]
    assert (gap['low'],gap['high'],gap['side'],gap['partial'])==(101,104,'bullish',False)
    bars.append(Candle(900,106,107,103,105))
    assert next(g for g in fair_value_gaps(bars) if g['time']==600)['partial']
    bars.append(Candle(1200,105,106,101,102))
    assert all(g['time']!=600 for g in fair_value_gaps(bars))


def test_swings_are_not_known_until_two_right_hand_closes():
    bars=[Candle(i*300,100,h,99,100) for i,h in enumerate([101,102,110,103,102])]
    assert confirmed_swings(bars[:4])==[]
    swing=confirmed_swings(bars)[0]
    assert swing['time']==600 and swing['confirmed_at']==1500


def test_sweeps_require_previously_confirmed_swing_and_close_back_inside():
    bars=[Candle(i*300,100,h,99,100) for i,h in enumerate([101,102,110,103,102])]
    bars.append(Candle(1500,109,112,108,109))
    sweep=swing_sweeps(bars,confirmed_swings(bars))[-1]
    assert sweep['side']=='bearish' and sweep['price']==110
    bars[-1]=Candle(1500,109,112,108,111)
    assert swing_sweeps(bars,confirmed_swings(bars))==[]


def test_cache_and_incomplete_higher_candles_do_not_leak_future():
    service=AnalysisService();bars=fixture_bars()
    d=service.snapshot(bars,36000)
    assert service.snapshot(bars,36001) is d
    future=bars+[Candle(36000,118,150,110,140)]
    unchanged=service.snapshot(future,36000)
    assert unchanged['by_timeframe']==d['by_timeframe']
    changed=service.snapshot(future,36300)
    assert changed['by_timeframe']['M5']['last_close']==140


def test_revised_closed_candle_refreshes_analysis():
    service=AnalysisService();bars=fixture_bars()
    d=service.snapshot(bars,36000)
    bars[-1].close-=.1
    assert service.snapshot(bars,36000) is not d


def test_possible_supply_demand_zones_are_separate_from_entries():
    from app.market_analysis import possible_zones
    for direction,kind in [(1,'demand'),(-1,'supply')]:
        candles=fixture_bars(direction)
        zones=possible_zones(candles)
        assert zones and zones[0]['kind']==kind
        assert zones[0]['low']<zones[0]['high']
        assert 'not a confirmed entry' in zones[0]['method']
        assert 'targets' not in zones[0]
        z=zones[0]
        # Distal breach removes the candidate rather than displaying an invalid zone.
        candles.append(Candle(36000,z['low']-1,z['high']+1,z['low']-2,z['low']-1))
        assert all(v['time']!=z['time'] for v in possible_zones(candles))


def test_open_candle_cannot_create_possible_zone():
    service=AnalysisService();bars=fixture_bars()
    original=service.snapshot(bars,36000)['by_timeframe']['M5']['zones']
    bars.append(Candle(36000,118,150,100,140))
    assert service.snapshot(bars,36000)['by_timeframe']['M5']['zones']==original
