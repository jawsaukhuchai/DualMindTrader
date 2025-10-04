//+------------------------------------------------------------------+
//|                                                Mind1_HO.mq5      |
//|   EA ส่งออก feed JSON ให้ Mind2 (ใช้ FILE_BIN)                   |
//+------------------------------------------------------------------+
#property strict

#include <stderror.mqh>
#include <stdlib.mqh>
#include <string.mqh>
#include "Mind1_Helper.mqh"   // ใช้ WriteLogToFile, JoinFeeds

//----------------------
// Input parameters
//----------------------
input int ExportIntervalMinutes = 5;   // Export feed ทุก ๆ กี่นาที
input double SpreadLimit = 2000;       // spread limit

datetime last_export = 0;

//----------------------
// Helper: Build timeframe indicators
//----------------------
string BuildTimeframeJSON(string sym, ENUM_TIMEFRAMES tf, datetime now)
{
   int h_ema_fast = iMA(sym, tf, 12, 0, MODE_EMA, PRICE_CLOSE);
   int h_ema_slow = iMA(sym, tf, 26, 0, MODE_EMA, PRICE_CLOSE);
   int h_rsi      = iRSI(sym, tf, 14, PRICE_CLOSE);
   int h_atr      = iATR(sym, tf, 14);
   int h_macd     = iMACD(sym, tf, 12, 26, 9, PRICE_CLOSE);

   double ema_fast_arr[], ema_slow_arr[], rsi_arr[], atr_arr[];
   double macd_main[], macd_signal[];

   ArraySetAsSeries(ema_fast_arr,true);
   ArraySetAsSeries(ema_slow_arr,true);
   ArraySetAsSeries(rsi_arr,true);
   ArraySetAsSeries(atr_arr,true);
   ArraySetAsSeries(macd_main,true);
   ArraySetAsSeries(macd_signal,true);

   CopyBuffer(h_ema_fast,0,0,1,ema_fast_arr);
   CopyBuffer(h_ema_slow,0,0,1,ema_slow_arr);
   CopyBuffer(h_rsi,0,0,1,rsi_arr);
   CopyBuffer(h_atr,0,0,1,atr_arr);
   CopyBuffer(h_macd,0,0,1,macd_main);
   CopyBuffer(h_macd,1,0,1,macd_signal);

   double ema_fast = ema_fast_arr[0];
   double ema_slow = ema_slow_arr[0];
   double rsi      = rsi_arr[0];
   double atr      = atr_arr[0];
   double macd_val = macd_main[0];
   double macd_sig = macd_signal[0];

   string json = "{"
      +"\"ema_fast\":"+DoubleToString(ema_fast,5)+","
      +"\"ema_slow\":"+DoubleToString(ema_slow,5)+","
      +"\"rsi\":"+DoubleToString(rsi,2)+","
      +"\"atr\":"+DoubleToString(atr,5)+","
      +"\"macd_main\":"+DoubleToString(macd_val,5)+","
      +"\"macd_signal\":"+DoubleToString(macd_sig,5)
      +"}";

   return json;
}

//----------------------
// OnTick
//----------------------
void OnTick()
{
   datetime now = TimeCurrent();
   if(now - last_export < ExportIntervalMinutes*60) return;
   last_export = now;

   string symbols[] = {"BTCUSDc","XAUUSDc","EURUSDc","AUDUSDc","NZDUSDc","GBPUSDc"};
   string feeds[];
   ArrayResize(feeds,0);

   for(int i=0; i<ArraySize(symbols); i++)
   {
      string sym = symbols[i];
      if(!SymbolSelect(sym,true))
      {
         string warn = "⚠ Symbol data unavailable for " + sym;
         Print(warn);
         WriteLogToFile(warn);
         continue;
      }

      double bid = SymbolInfoDouble(sym,SYMBOL_BID);
      double ask = SymbolInfoDouble(sym,SYMBOL_ASK);
      double spread = (ask - bid)/_Point;

      // ---------------- Filters ----------------
      bool spread_pass = (spread <= SpreadLimit);
      string filters = "{"
         +"\"spread\":{\"value\":"+DoubleToString(spread,_Digits)+",\"limit\":"+DoubleToString(SpreadLimit,0)+",\"pass\":"+(spread_pass?"true":"false")+"},"
         +"\"news\":{\"impact\":\"NONE\",\"pass\":true},"
         +"\"sideway\":{\"state\":false,\"pass\":true}"
         +"}";

      // ---------------- Timeframes ----------------
      string tf_m5 = BuildTimeframeJSON(sym, PERIOD_M5, now);
      string tf_h1 = BuildTimeframeJSON(sym, PERIOD_H1, now);
      string tf_h4 = BuildTimeframeJSON(sym, PERIOD_H4, now);

      string timeframes = "{"
         +"\"M5\":"+tf_m5+","
         +"\"H1\":"+tf_h1+","
         +"\"H4\":"+tf_h4
         +"}";

      // ---------------- Build feed JSON ----------------
      string feed = "{"
         +"\"symbol\":\""+sym+"\","
         +"\"bid\":"+DoubleToString(bid,_Digits)+","
         +"\"ask\":"+DoubleToString(ask,_Digits)+","
         +"\"spread\":"+DoubleToString(spread,_Digits)+","
         +"\"filters\":"+filters+","
         +"\"timeframes\":"+timeframes+","
         +"\"timestamp\":\""+TimeToString(now,TIME_DATE|TIME_SECONDS)+"\""
         +"}";

      int sz = ArraySize(feeds);
      ArrayResize(feeds,sz+1);
      feeds[sz] = feed;
   }

   // ✅ รวม feeds เป็น JSON array
   string json = JoinFeeds(feeds);

   // ✅ เขียนไฟล์ mind1_feed.json ด้วย FILE_BIN
   int fh = FileOpen("mind1_feed.json", FILE_WRITE|FILE_BIN|FILE_COMMON);
   if(fh != INVALID_HANDLE)
   {
      FileWriteString(fh, json, StringLen(json));
      FileClose(fh);
      WriteLogToFile("[EXPORT] mind1_feed.json updated with "+IntegerToString(ArraySize(feeds))+" symbols at "+TimeToString(now,TIME_DATE|TIME_SECONDS));
   }
   else
   {
      Print("❌ Error: cannot open mind1_feed.json");
      WriteLogToFile("❌ Error: cannot open mind1_feed.json");
   }
}
