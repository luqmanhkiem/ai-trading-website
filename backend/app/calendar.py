"""Forex Factory's official weekly export; cached, attributed and never inferred."""
import asyncio
from datetime import datetime, timezone, timedelta
import hashlib
import time
import httpx

URL='https://nfs.faireconomy.media/ff_calendar_thisweek.json'
SOURCE='Forex Factory weekly export'
SOURCE_URL='https://www.forexfactory.com/calendar'

class CalendarError(Exception):pass

def parse_events(payload):
    if not isinstance(payload,list) or len(payload)>3000:
        raise CalendarError('Invalid calendar document.')
    result=[]
    seen=set()
    for raw in payload:
        try:
            if not isinstance(raw,dict):raise ValueError()
            title=raw['title'].strip()
            currency=raw['country'].strip()
            impact=raw['impact']
            if not title or len(title)>300 or currency not in ('USD','EUR','GBP','JPY','CHF','CAD','AUD','NZD','CNY','All'):
                raise ValueError()
            if impact not in ('High','Medium','Low','Holiday','Non-Economic'):raise ValueError()
            moment=datetime.fromisoformat(raw['date'].replace('Z','+00:00'))
            if moment.tzinfo is None:raise ValueError()
            timestamp=int(moment.timestamp())
            key=hashlib.sha256(f'{title}|{currency}|{timestamp}'.encode()).hexdigest()[:24]
            if key in seen:continue
            seen.add(key)
            def text(field):
                value=raw.get(field)
                return str(value)[:100] if value not in ('',None) else None
            result.append(dict(id=key,title=title,currency=currency,impact=impact,time=timestamp,
                time_precision='date' if impact=='Holiday' else 'scheduled',
                forecast=text('forecast'),previous=text('previous'),actual=text('actual'),source=SOURCE))
        except (KeyError,ValueError,TypeError,AttributeError,OverflowError):
            # Reject the whole document rather than silently hiding scheduled risks.
            raise CalendarError('Calendar format changed or an event is invalid. Last valid data retained.') from None
    return sorted(result,key=lambda e:(e['time'],e['id']))

class CalendarService:
    def __init__(self,settings,store):
        self.settings,self.store=settings,store
        cached=store.load_cache('calendar:forex_factory') or {}
        self.events=cached.get('events',[])
        self.updated_at=cached.get('updated_at',0)
        self.last_attempt=0
        self.error=None
        self.lock=None
        self.refreshing=False

    @property
    def enabled(self):return self.settings.calendar_provider=='forex_factory'

    async def refresh(self,force=False):
        if not self.enabled:return
        if self.lock is None:self.lock=asyncio.Lock()
        async with self.lock:
            # UI refresh cannot bypass the shared source rate limit.
            if time.time()-self.last_attempt<self.settings.calendar_refresh_seconds:return
            self.last_attempt=time.time()
            self.refreshing=True
            try:
                async with httpx.AsyncClient(timeout=15,follow_redirects=False) as client:
                    response=await client.get(URL,headers={'Accept':'application/json','User-Agent':'Aurum-Research/0.1'})
                if response.status_code!=200:
                    raise CalendarError(f'Calendar source returned HTTP {response.status_code}. Retaining last valid data.')
                if len(response.content)>2_000_000:raise CalendarError('Calendar document exceeds size limit.')
                try:events=parse_events(response.json())
                except ValueError:raise CalendarError('Invalid calendar JSON.') from None
                now=time.time()
                self.store.save_cache('calendar:forex_factory',dict(events=events,updated_at=now))
                self.events,self.updated_at,self.error=events,now,None
            except CalendarError as e:self.error=str(e)
            except Exception:self.error='Calendar source unavailable. Retaining last valid data; retrying on the next refresh.'
            finally:self.refreshing=False

    async def run(self):
        if self.settings.calendar_provider not in ('none','forex_factory'):
            self.error='Unknown calendar provider. Set CALENDAR_PROVIDER=forex_factory or none.'
            return
        while True:
            if self.enabled and time.time()-self.updated_at>=self.settings.calendar_refresh_seconds:
                await self.refresh()
            await asyncio.sleep(30)

    def snapshot(self):
        now=time.time()
        stale=bool(self.error) or not self.updated_at or now-self.updated_at>self.settings.calendar_refresh_seconds*2
        # Cached exports from a previous week must never imply a current complete schedule.
        today=datetime.now(timezone.utc).replace(hour=0,minute=0,second=0,microsecond=0)
        week_start=(today-timedelta(days=(today.weekday()+1)%7)).timestamp()
        in_period=any(week_start<=e['time']<week_start+7*86400 for e in self.events)
        if self.events and not in_period:stale=True
        if not self.enabled:message='Calendar disabled. Set CALENDAR_PROVIDER=forex_factory to connect.'
        elif self.error:message=self.error
        elif not self.updated_at:message='Loading the official weekly export…'
        elif stale:message='Cached calendar is stale or outside the current period. Check the source.'
        else:message='Weekly schedule loaded. Event times can change; actual values may be unavailable in this export.'
        return dict(configured=self.enabled,source=SOURCE,source_url=SOURCE_URL,events=self.events if self.enabled else [],
            updated_at=self.updated_at,stale=stale,refreshing=self.refreshing,
            next_refresh_at=(self.last_attempt+self.settings.calendar_refresh_seconds if self.last_attempt else now) if self.enabled else None,
            message=message,scope='This week only',signal_filter_enabled=False)
