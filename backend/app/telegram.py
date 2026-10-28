"""Server-only Telegram configuration; tokens never enter browser payloads or errors."""
import asyncio
import time
import httpx

class TelegramError(Exception):pass

async def call_bot(token,method,payload=None):
    # Only fixed Telegram methods; no user-supplied URL or redirect destination.
    if method not in ('getMe','getWebhookInfo','getUpdates','sendMessage'):raise TelegramError('Unsupported bot method.')
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            response=await client.post(f'https://api.telegram.org/bot{token}/{method}',json=payload or {})
        data=response.json()
        if response.is_success and data.get('ok'):return data.get('result')
        if response.status_code==429:raise TelegramError('Telegram rate limit reached; try again later.')
        if response.status_code in (401,404):raise TelegramError('Telegram token is invalid or revoked.')
        if response.status_code==403:raise TelegramError('Telegram access denied. Start the bot chat or check channel permissions.')
        raise TelegramError('Telegram rejected the request. Verify the chat destination and bot permissions.')
    except TelegramError:raise
    except Exception:raise TelegramError('Telegram network or response error. No credentials were logged.') from None

class TelegramService:
    def __init__(self,settings):
        self.settings=settings
        self.status='Disabled' if not settings.telegram_enabled else 'Configured; awaiting new signal' if self.configured else 'Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID'
        self.last_sent_at=None
        self.last_test_at=0
        self.test_lock=None

    @property
    def configured(self):return bool(self.settings.telegram_bot_token and self.settings.telegram_chat_id)

    def snapshot(self):
        return dict(enabled=self.settings.telegram_enabled,configured=self.configured,status=self.status,
                    last_sent_at=self.last_sent_at,alerts=['New paper signals'],destination='Configured privately' if self.configured else 'Not configured')

    async def send_text(self,text):
        if not self.settings.telegram_enabled:
            self.status='Disabled';return False
        if not self.configured:
            self.status='Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID';return False
        try:
            await call_bot(self.settings.telegram_bot_token,'sendMessage',{
                'chat_id':self.settings.telegram_chat_id,'text':text,'link_preview_options':{'is_disabled':True}})
            self.status='Last alert delivered';self.last_sent_at=time.time()
            return True
        except TelegramError as e:
            self.status=str(e);return False

    async def send_signal(self,signal,mode,source):
        if not self.settings.telegram_enabled:return False
        label='SIMULATED' if mode=='simulated' else source.upper()+' • PAPER'
        targets=' | '.join(f'TP{i+1} {p:.2f}' for i,p in enumerate(signal['targets']))
        return await self.send_text(f"{label} • XAUUSD {signal['side']} {signal['timeframe']} • {signal.get('profile', 'legacy').title()}\n"
            f"Strategy: {signal.get('strategy', 'legacy')}\nRisk: {signal.get('risk_label','Legacy')} (relative grade, not win probability)\nEntry zone {signal['entry_low']:.2f}–{signal['entry_high']:.2f}\nSL {signal['stop']:.2f}\n{targets}\n"
            + (' / '.join(f'TP{i+1}={r:g}R' for i,r in enumerate(signal['rr_targets']))+'. Prices use midpoint until entry; rebase to observed fill-to-stop risk.\n' if signal.get('rr_targets') else '')
            + (f"TP3 method: {signal.get('target_method','market structure')}. TP3 stays fixed; TP1/TP2 use reference midpoint until filled.\n" if signal.get('structural_targets') else '')
            + ('TPs 30/35/40 pips ($3/$3.50/$4) from actual entry; prices above use reference midpoint until filled.\n' if signal.get('target_pips') else '')
            + ('TP3 is the recent high/low; minimum entry reward/risk 2.5:1.\n' if signal.get('minimum_rr') else '')+'Paper setup, not an executed trade. TP1/TP2 are milestones; full exit at TP3 or stop.')

    async def test_message(self,source):
        if self.test_lock is None:self.test_lock=asyncio.Lock()
        async with self.test_lock:
            if not self.settings.telegram_enabled or not self.configured:
                raise TelegramError('Telegram is not enabled/configured. Run the private setup helper first.')
            if time.time()-self.last_test_at<15:raise TelegramError('Wait 15 seconds before sending another test.')
            self.last_test_at=time.time()
            return await self.send_text(f'Aurum connection test\nSource: {source}\nPaper-signal notifications are connected. No trade was placed.')
