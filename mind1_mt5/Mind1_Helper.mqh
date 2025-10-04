//+------------------------------------------------------------------+
//|                                             Mind1_Helper.mqh     |
//|   Helper functions: Logging + JoinFeeds (ใช้ FILE_BIN)           |
//+------------------------------------------------------------------+
#property strict

//----------------------
// Write log to file (per day)
//----------------------
void WriteLogToFile(string text)
{
   string day = TimeToString(TimeCurrent(), TIME_DATE);
   string log_file = "mind1_log_" + StringReplace(day,".","-") + ".txt";
   string ts = TimeToString(TimeCurrent(), TIME_DATE|TIME_SECONDS);

   string line = ts + " " + text + "\r\n";

   // เปิดไฟล์แบบ FILE_BIN + append
   int handle = FileOpen(log_file, FILE_READ|FILE_WRITE|FILE_BIN|FILE_COMMON);
   if(handle != INVALID_HANDLE)
   {
      FileSeek(handle, 0, SEEK_END);  // append ต่อท้าย
      FileWriteString(handle, line, StringLen(line));
      FileClose(handle);
   }
   else
   {
      Print("❌ Error: cannot open log file " + log_file);
   }
}

//----------------------
// Join JSON feeds array
//----------------------
string JoinFeeds(string &feeds[])
{
   string json = "[";
   for(int i=0; i<ArraySize(feeds); i++)
   {
      json += feeds[i];
      if(i < ArraySize(feeds)-1)
         json += ",";
   }
   json += "]";
   return json;
}
