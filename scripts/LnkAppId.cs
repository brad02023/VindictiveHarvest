using System;
using System.Runtime.InteropServices;
using System.Runtime.InteropServices.ComTypes;
using System.Text;

namespace ShortcutProps
{
    [StructLayout(LayoutKind.Sequential, Pack = 4)]
    public struct PROPERTYKEY
    {
        public Guid fmtid;
        public uint pid;
    }

    [StructLayout(LayoutKind.Sequential)]
    public struct PROPVARIANT
    {
        public ushort vt;
        public ushort wReserved1;
        public ushort wReserved2;
        public ushort wReserved3;
        public IntPtr p;
        public long pad;

        public static PROPVARIANT FromString(string s)
        {
            return new PROPVARIANT
            {
                vt = 31,
                p = Marshal.StringToCoTaskMemUni(s)
            };
        }

        public void Clear()
        {
            PropVariantClear(ref this);
        }

        [DllImport("ole32.dll")]
        private static extern int PropVariantClear(ref PROPVARIANT pvar);
    }

    [ComImport, Guid("886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    interface IPropertyStore
    {
        [PreserveSig] int GetCount(out uint cProps);
        [PreserveSig] int GetAt(uint iProp, out PROPERTYKEY pkey);
        [PreserveSig] int GetValue(ref PROPERTYKEY key, out PROPVARIANT pv);
        [PreserveSig] int SetValue(ref PROPERTYKEY key, ref PROPVARIANT pv);
        [PreserveSig] int Commit();
    }

    [ComImport, Guid("00021401-0000-0000-C000-000000000046")]
    class CShellLink {}

    [ComImport, Guid("000214F9-0000-0000-C000-000000000046"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    interface IShellLinkW
    {
        void GetPath([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder pszFile, int cch, IntPtr pfd, int fFlags);
        void GetIDList(out IntPtr ppidl);
        void SetIDList(IntPtr pidl);
        void GetDescription([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder pszName, int cch);
        void SetDescription([MarshalAs(UnmanagedType.LPWStr)] string pszName);
        void GetWorkingDirectory([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder pszDir, int cch);
        void SetWorkingDirectory([MarshalAs(UnmanagedType.LPWStr)] string pszDir);
        void GetArguments([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder pszArgs, int cch);
        void SetArguments([MarshalAs(UnmanagedType.LPWStr)] string pszArgs);
        void GetHotkey(out short pwHotkey);
        void SetHotkey(short wHotkey);
        void GetShowCmd(out int piShowCmd);
        void SetShowCmd(int iShowCmd);
        void GetIconLocation([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder pszIconPath, int cch, out int piIcon);
        void SetIconLocation([MarshalAs(UnmanagedType.LPWStr)] string pszIconPath, int iIcon);
        void SetRelativePath([MarshalAs(UnmanagedType.LPWStr)] string pszPathRel, int dwReserved);
        void Resolve(IntPtr hwnd, int fFlags);
        void SetPath([MarshalAs(UnmanagedType.LPWStr)] string pszFile);
    }

    [ComImport, Guid("0000010b-0000-0000-C000-000000000046"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    interface IPersistFile
    {
        void GetClassID(out Guid pClassID);
        [PreserveSig] int IsDirty();
        void Load([MarshalAs(UnmanagedType.LPWStr)] string pszFileName, int dwMode);
        void Save([MarshalAs(UnmanagedType.LPWStr)] string pszFileName, [MarshalAs(UnmanagedType.Bool)] bool fRemember);
        void SaveCompleted([MarshalAs(UnmanagedType.LPWStr)] string pszFileName);
        void GetCurFile([MarshalAs(UnmanagedType.LPWStr)] out string ppszFileName);
    }

    public static class Writer
    {
        static readonly PROPERTYKEY IdKey = Key(5);
        static readonly PROPERTYKEY RelaunchCommandKey = Key(2);
        static readonly PROPERTYKEY RelaunchIconKey = Key(3);
        static readonly PROPERTYKEY RelaunchNameKey = Key(4);

        static PROPERTYKEY Key(uint pid)
        {
            return new PROPERTYKEY
            {
                fmtid = new Guid("9F4C2855-9F79-4B39-A8D0-E1D42DE1D5F3"),
                pid = pid
            };
        }

        public static void Apply(string lnk, string appId, string relaunch, string display, string icon)
        {
            var sl = (IShellLinkW)new CShellLink();
            var pf = (IPersistFile)sl;
            pf.Load(lnk, 0x00000012);
            var store = (IPropertyStore)sl;
            Set(store, IdKey, appId);
            if (!string.IsNullOrEmpty(relaunch))
                Set(store, RelaunchCommandKey, relaunch);
            if (!string.IsNullOrEmpty(display))
                Set(store, RelaunchNameKey, display);
            if (!string.IsNullOrEmpty(icon))
                Set(store, RelaunchIconKey, icon);
            int hr = store.Commit();
            if (hr < 0) Marshal.ThrowExceptionForHR(hr);
            pf.Save(lnk, true);
            Marshal.ReleaseComObject(store);
            Marshal.ReleaseComObject(pf);
            Marshal.ReleaseComObject(sl);
        }

        static void Set(IPropertyStore store, PROPERTYKEY key, string value)
        {
            var pv = PROPVARIANT.FromString(value);
            try
            {
                int hr = store.SetValue(ref key, ref pv);
                if (hr < 0) Marshal.ThrowExceptionForHR(hr);
            }
            finally
            {
                pv.Clear();
            }
        }
    }
}
