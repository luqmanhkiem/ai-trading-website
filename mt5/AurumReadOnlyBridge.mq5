// Read-only quote and candle exporter. Contains no trading library or order calls.
#property strict
#property version "1.01"
#property description "Exports Valetax XAUUSD quotes/candles to your local Aurum API. Never trades."
input string Endpoint = "http://127.0.0.1:8000/api/mt5/ingest";
input string BridgeToken = "";
input int PollSeconds = 1;
// Recent history only; receiver accepts up to 600 completed M5 bars plus current.
input int HistoryBars = 600;
// 9999 = detect from TimeTradeServer minus TimeGMT, rounded to 15 minutes.
input int BrokerUtcOffsetMinutes = 9999;
long last_sent = 0;
string EscapeJson(string value)
{
   StringReplace(value,"\\","\\\\");
   StringReplace(value,"\"","\\\"");
   StringReplace(value,"\r"," ");
   StringReplace(value,"\n"," ");
   StringReplace(value,"\t"," ");
   return value;
}
int OnInit()
{
   if(StringLen(BridgeToken)<32 || PollSeconds<1 || PollSeconds>10 || HistoryBars<90 || HistoryBars>600)
   {
      Print("Aurum: set the local bridge token (32+ characters) PollSeconds 1–10, and HistoryBars 90–600.");
      return INIT_PARAMETERS_INCORRECT;
   }
   if(StringFind(_Symbol,"XAUUSD")!=0)
   {
      Print("Aurum: attach to the exact Valetax XAUUSD chart, including its suffix.");
      return INIT_PARAMETERS_INCORRECT;
   }
   if(!EventSetTimer(PollSeconds)) return INIT_FAILED;
   Print("Aurum read-only bridge started. No order execution is implemented.");
   return INIT_SUCCEEDED;
}
void OnDeinit(const int reason) { EventKillTimer(); Comment(""); }
void OnTimer()
{
   if(!TerminalInfoInteger(TERMINAL_CONNECTED))
   { Comment("Aurum: terminal disconnected; no data sent."); return; }
   MqlTick tick;
   if(!SymbolInfoTick(_Symbol,tick) || tick.bid<=0 || tick.ask<tick.bid) return;
   long offset = BrokerUtcOffsetMinutes==9999 ? (long)MathRound((double)(TimeTradeServer()-TimeGMT())/900.0)*900 : (long)BrokerUtcOffsetMinutes*60;
   long utc_ms = tick.time_msc-offset*1000;
   if(utc_ms<=last_sent) return;
   MqlRates rates[];
   ArraySetAsSeries(rates,false);
   int copied = CopyRates(_Symbol,PERIOD_M5,0,HistoryBars+1,rates);
   if(copied<91) { Comment("Aurum: waiting for M5 history to load."); return; }
   int digits=(int)SymbolInfoInteger(_Symbol,SYMBOL_DIGITS);
   string payload="{\"symbol\":\""+EscapeJson(_Symbol)+"\",\"broker\":\""+EscapeJson(AccountInfoString(ACCOUNT_COMPANY))+"\",";
   payload+=StringFormat("\"tick_time_ms\":%I64d,\"server_utc_offset_seconds\":%I64d,",utc_ms,offset);
   payload+="\"bid\":"+DoubleToString(tick.bid,digits)+",\"ask\":"+DoubleToString(tick.ask,digits)+",";
   payload+="\"contract_size\":"+DoubleToString(SymbolInfoDouble(_Symbol,SYMBOL_TRADE_CONTRACT_SIZE),8)+",";
   payload+="\"lot_step\":"+DoubleToString(SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_STEP),8)+",";
   payload+="\"min_lot\":"+DoubleToString(SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN),8)+",";
   payload+="\"max_lot\":"+DoubleToString(SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MAX),8)+",\"bars\":[";
   for(int i=0;i<copied;i++)
   {
      if(i>0) payload+=",";
      payload+=StringFormat("{\"time\":%I64d,",(long)rates[i].time-offset);
      payload+="\"open\":"+DoubleToString(rates[i].open,digits)+",\"high\":"+DoubleToString(rates[i].high,digits)+",";
      payload+="\"low\":"+DoubleToString(rates[i].low,digits)+",\"close\":"+DoubleToString(rates[i].close,digits)+"}";
   }
   payload+="]}";
   char body[],result[];
   StringToCharArray(payload,body,0,WHOLE_ARRAY,CP_UTF8);
   ArrayResize(body,ArraySize(body)-1); // Exclude terminating NUL from the HTTP body.
   string headers="Content-Type: application/json\r\nAuthorization: Bearer "+BridgeToken+"\r\n";
   string response_headers;
   ResetLastError();
   int code=WebRequest("POST",Endpoint,headers,3000,body,result,response_headers);
   if(code==200)
   {
      last_sent=utc_ms;
      Comment("Aurum: Valetax ",_Symbol," exported (read-only). M5 bars: ",copied-1,". UTC offset minutes: ",offset/60);
   }
   else
   {
      Comment("Aurum: bridge HTTP ",code," / MT5 error ",GetLastError(),". Check URL allowlist, local token, symbol and UTC offset.");
      // Never log credentials or request headers.
   }
}
