#!/usr/bin/env python3
"""Interactive private Telegram setup. Never pass a token in command arguments."""
import asyncio
import getpass
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from app.config import Settings
from app.telegram import call_bot,TelegramError


def save_settings(values):
    path=ROOT/'backend/.env'
    text=path.read_text() if path.exists() else (ROOT/'backend/.env.example').read_text()
    for key,value in values.items():
        if '\n' in value or '\r' in value:raise ValueError('Configuration values must be single-line.')
        # JSON-compatible quoting is accepted by python-dotenv and preserves # characters.
        import json
        line=key+'='+json.dumps(value)
        pattern=r'^'+key+r'=.*$'
        text=re.sub(pattern,lambda _:line,text,flags=re.M) if re.search(pattern,text,re.M) else text+'\n'+line+'\n'
    path.write_text(text);path.chmod(0o600)


async def main():
    cfg=Settings(_env_file=ROOT/'backend/.env')
    print('Create a bot with @BotFather (/newbot), then open your new bot chat and send /start.')
    print('Enter its token here privately. It is hidden and will not be printed or sent anywhere except Telegram.')
    token=getpass.getpass('Bot token (blank keeps an existing local token): ').strip() or cfg.telegram_bot_token
    if not token or not re.fullmatch(r'\d+:[A-Za-z0-9_-]+',token):
        raise TelegramError('No valid bot token entered. Nothing saved.')
    bot=await call_bot(token,'getMe')
    print('Verified bot: @'+bot.get('username','unknown'))
    chat_id=input('Chat ID or @channel username (blank to discover your bot chats): ').strip()
    if not chat_id:
        hook=await call_bot(token,'getWebhookInfo')
        if hook.get('url'):
            raise TelegramError('This bot already has a webhook. Enter a known destination manually or create a separate bot; Aurum will not change its webhook.')
        updates=await call_bot(token,'getUpdates',{'timeout':0,'limit':100})
        chats={}
        for update in updates:
            message=update.get('message') or update.get('channel_post') or {}
            chat=message.get('chat')
            if chat:
                label=chat.get('title') or chat.get('first_name') or chat.get('username') or chat.get('type','chat')
                chats[str(chat['id'])]=str(label).replace('\n',' ')[:80]
        if not chats:
            raise TelegramError('No bot chats found. Open your bot in Telegram, press Start/send /start, then run this helper again. Nothing saved.')
        print('Available destinations (message contents are not displayed):')
        choices=list(chats)
        for i,key in enumerate(choices,1):print(f'{i}. {chats[key]} ({key})')
        selection=input('Choose the destination number: ').strip()
        if not selection.isdigit() or not 1<=int(selection)<=len(choices):
            raise TelegramError('No valid destination selected. Nothing saved.')
        chat_id=choices[int(selection)-1]
    if not re.fullmatch(r'-?\d+|@[A-Za-z0-9_]{5,}',chat_id):
        raise TelegramError('Invalid chat ID/channel username. Nothing saved.')
    save_settings({'TELEGRAM_BOT_TOKEN':token,'TELEGRAM_CHAT_ID':chat_id,'TELEGRAM_ENABLED':'true'})
    print('Saved privately to backend/.env. No message has been sent.')
    print('Restart Aurum, open Connections, then click Send test message to verify delivery.')

if __name__=='__main__':
    try:asyncio.run(main())
    except (TelegramError,ValueError) as e:print(str(e));sys.exit(1)
    except (EOFError,KeyboardInterrupt):print('\nSetup cancelled.');sys.exit(1)
    except Exception:print('Setup failed. Check connectivity and dependencies; credentials were not printed.');sys.exit(1)
