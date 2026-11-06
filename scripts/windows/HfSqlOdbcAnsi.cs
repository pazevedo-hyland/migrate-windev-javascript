// ANSI ODBC adapter for the HFSQL ODBC driver (tested: HFSQL 28, 32-bit). The driver's Unicode entry points
// (SQLDriverConnectW and friends, which pyodbc and .NET's System.Data.Odbc call) crashed the host process; the ANSI
// entry points work. Loaded by hfsql-export.ps1 in a 32-bit Windows PowerShell host, against a scratch copy of the data.
// Output: one <table>.jsonl per table: a header line {table, count, columns, encoding}, then one JSON array per row
// (text as strings, NULL as null, binary as {"base64": ...}); the export fails unless rows read = COUNT(*) before and after.
using System;
using System.IO;
using System.Text;
using System.Collections.Generic;
using System.Globalization;
using System.Runtime.InteropServices;
using System.Web.Script.Serialization;

public sealed class HfSqlOdbcAnsi : IDisposable {
    [DllImport("odbc32.dll")] static extern short SQLAllocHandle(short t, IntPtr p, out IntPtr h);
    [DllImport("odbc32.dll")] static extern short SQLSetEnvAttr(IntPtr e, int a, IntPtr v, int n);
    [DllImport("odbc32.dll", CharSet=CharSet.Ansi)] static extern short SQLDriverConnectA(IntPtr h, IntPtr w, string input, short n, StringBuilder output, short max, out short length, ushort completion);
    [DllImport("odbc32.dll", CharSet=CharSet.Ansi)] static extern short SQLExecDirectA(IntPtr h, string sql, int n);
    [DllImport("odbc32.dll")] static extern short SQLFetch(IntPtr h);
    [DllImport("odbc32.dll")] static extern short SQLGetData(IntPtr h, ushort col, short type, byte[] data, int max, out int length);
    [DllImport("odbc32.dll")] static extern short SQLNumResultCols(IntPtr h, out short count);
    [DllImport("odbc32.dll", CharSet=CharSet.Ansi)] static extern short SQLDescribeColA(IntPtr h, ushort col, StringBuilder name, short max, out short length, out short type, out uint size, out short scale, out short nullable);
    [DllImport("odbc32.dll", CharSet=CharSet.Ansi)] static extern short SQLGetDiagRecA(short type, IntPtr h, short rec, StringBuilder state, out int native, StringBuilder text, short max, out short length);
    [DllImport("odbc32.dll")] static extern short SQLFreeHandle(short t, IntPtr h);
    [DllImport("odbc32.dll")] static extern short SQLDisconnect(IntPtr h);
    IntPtr env, dbc;
    readonly Encoding Ansi;
    static readonly CultureInfo Invariant = CultureInfo.InvariantCulture;
    static void CheckData(short rc, IntPtr h, bool allowTruncation) {
        if (rc != 1) { Check(rc,3,h,"read column"); return; }
        for (short record=1;;record++) {
            var state=new StringBuilder(6); var message=new StringBuilder(4096); int native; short length;
            short diagnostic=SQLGetDiagRecA(3,h,record,state,out native,message,4096,out length);
            if(diagnostic==100) break;
            Check(diagnostic,3,h,"read data diagnostic");
            if(!allowTruncation || state.ToString()!="01004")
                throw new InvalidOperationException("ODBC conversion warning rejected: "+state+" "+message);
        }
    }
    static void Check(short rc, short type, IntPtr h, string operation) {
        if (rc == 0 || rc == 1) return;
        var state = new StringBuilder(6); var message = new StringBuilder(4096); int native; short length;
        SQLGetDiagRecA(type,h,1,state,out native,message,4096,out length);
        throw new InvalidOperationException(operation+": ODBC "+rc+" "+state+" "+message);
    }
    public HfSqlOdbcAnsi(string dsn) : this(dsn, 1252) { }
    /// <param name="codePage">ANSI code page the driver returns text in (the Windows ANSI code page, 1252 for Western European).</param>
    public HfSqlOdbcAnsi(string dsn, int codePage) {
        if (IntPtr.Size != 4) throw new InvalidOperationException("This adapter requires a 32-bit host.");
        Ansi = Encoding.GetEncoding(codePage, EncoderFallback.ExceptionFallback, DecoderFallback.ExceptionFallback);
        Check(SQLAllocHandle(1,IntPtr.Zero,out env),1,env,"allocate env");
        Check(SQLSetEnvAttr(env,200,new IntPtr(3),0),1,env,"ODBC3");
        Check(SQLAllocHandle(2,env,out dbc),1,env,"allocate connection");
        short n; var output = new StringBuilder(2048);
        Check(SQLDriverConnectA(dbc,IntPtr.Zero,"DSN="+dsn,-3,output,2048,out n,0),2,dbc,"connect ANSI");
    }
    IntPtr Query(string sql) {
        IntPtr statement;
        Check(SQLAllocHandle(3,dbc,out statement),2,dbc,"allocate statement");
        try { Check(SQLExecDirectA(statement,sql,-3),3,statement,"execute SELECT"); return statement; }
        catch { SQLFreeHandle(3,statement); throw; }
    }
    public static int CharacterCount(byte[] buffer, int reported, short rc) {
        int capacity=buffer.Length-1;
        int terminator=Array.IndexOf(buffer,(byte)0);
        if(terminator<0 || terminator>capacity) throw new InvalidOperationException("Missing ANSI terminator.");
        if(rc==1 && terminator!=capacity) throw new InvalidOperationException("Early terminator in truncated ANSI data.");
        if(rc==0 && (reported<0 || reported<terminator)) throw new InvalidOperationException("Inconsistent ANSI data length.");
        if(rc==0 && reported!=terminator && !(reported==1 && terminator==0))
            throw new InvalidOperationException("Unexpected embedded ANSI terminator; refusing data loss.");
        // HFSQL 28 reports length 1 for an empty SQL_C_CHAR result. The byte is
        // the C terminator, not a character. Nonempty results exclude it normally.
        return terminator;
    }
    object Value(IntPtr s, ushort col, short sqlType) {
        int indicator;
        if (sqlType == 6 || sqlType == 8 || sqlType == 7) {
            bool single = sqlType == 7;
            byte[] raw = new byte[single ? 4 : 8];
            CheckData(SQLGetData(s,col,(short)(single ? 7 : 8),raw,raw.Length,out indicator),s,false);
            if (indicator == -1) return null;
            return single ? BitConverter.ToSingle(raw,0).ToString("R",Invariant) : BitConverter.ToDouble(raw,0).ToString("R",Invariant);
        }
        bool binary = sqlType == -2 || sqlType == -3 || sqlType == -4;
        using (var stream = new MemoryStream()) {
            while (true) {
                byte[] buffer = new byte[65536];
                short rc = SQLGetData(s,col,(short)(binary ? -2 : 1),buffer,buffer.Length,out indicator);
                if (rc == 100) break;
                CheckData(rc,s,true);
                if (indicator == -1) return null;
                int capacity = binary ? buffer.Length : buffer.Length-1;
                if(rc==1 && indicator>=0 && indicator<=capacity) throw new InvalidOperationException("Inconsistent truncation length.");
                int take = rc == 1 ? capacity : Math.Min(Math.Max(indicator,0),capacity);
                if (indicator == -4 && rc == 0) throw new InvalidOperationException("Unknown final column length.");
                if (!binary) take=CharacterCount(buffer,indicator,rc);
                stream.Write(buffer,0,take);
                if (rc == 0) break;
            }
            byte[] bytes = stream.ToArray();
            return binary ? (object)new Dictionary<string,object>{{"base64",Convert.ToBase64String(bytes)}} : Ansi.GetString(bytes);
        }
    }
    long Count(string name) {
        IntPtr s=Query("SELECT COUNT(*) FROM \""+name.Replace("\"","\"\"")+"\"");
        try { Check(SQLFetch(s),3,s,"fetch count"); return long.Parse((string)Value(s,1,3),Invariant); }
        finally { SQLFreeHandle(3,s); }
    }
    public void Export(string[] names, string outDirectory) {
        if (Directory.Exists(outDirectory)) throw new IOException("Export directory must be new.");
        Directory.CreateDirectory(outDirectory);
        var json=new JavaScriptSerializer();
        foreach (string name in names) {
            long expected=Count(name), rows=0;
            IntPtr s=Query("SELECT * FROM \""+name.Replace("\"","\"\"")+"\"");
            try {
                short columns; Check(SQLNumResultCols(s,out columns),3,s,"column count");
                short[] types=new short[columns];
                var metadata=new List<object>();
                for (ushort c=1;c<=columns;c++) {
                    var label=new StringBuilder(512); short n,type,scale,nullable; uint size;
                    Check(SQLDescribeColA(s,c,label,512,out n,out type,out size,out scale,out nullable),3,s,"column description");
                    types[c-1]=type;
                    metadata.Add(new Dictionary<string,object>{{"name",label.ToString()},{"odbc_sql_type",type},{"size",size},{"scale",scale},{"nullable",nullable==1},{"type",type==-2||type==-3||type==-4 ? "bytes" : "str"}});
                }
                using (var writer=new StreamWriter(Path.Combine(outDirectory,name+".jsonl"),false,new UTF8Encoding(false))) {
                    writer.WriteLine(json.Serialize(new Dictionary<string,object>{{"table",name},{"count",expected},{"columns",metadata},{"encoding","code page "+Ansi.CodePage+" ("+Ansi.WebName+") via SQL_C_CHAR; floating point via native SQL_C_FLOAT/DOUBLE"}}));
                    while (true) {
                        short rc=SQLFetch(s); if(rc==100) break; Check(rc,3,s,"fetch row");
                        object[] values=new object[columns];
                        for(ushort c=1;c<=columns;c++) values[c-1]=Value(s,c,types[c-1]);
                        writer.WriteLine(json.Serialize(values)); rows++;
                    }
                }
                long after=Count(name);
                if(rows!=expected || after!=expected) throw new InvalidOperationException(name+": row count mismatch "+rows+" vs "+expected+" / "+after);
                Console.WriteLine(name+": "+rows+" rows (source counts agree before and after)");
            } finally { SQLFreeHandle(3,s); }
        }
    }
    public void Dispose() {
        if(dbc!=IntPtr.Zero) { SQLDisconnect(dbc); SQLFreeHandle(2,dbc); dbc=IntPtr.Zero; }
        if(env!=IntPtr.Zero) { SQLFreeHandle(1,env); env=IntPtr.Zero; }
    }
}
