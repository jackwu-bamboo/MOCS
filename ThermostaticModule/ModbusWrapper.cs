using System;
using System.Runtime.InteropServices;

namespace ModbusWrapper
{
    public enum RegisterType
    {
        Invalid = 0,
        DiscreteInputs,
        Coils,
        InputRegisters,
        HoldingRegisters
    }
    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Ansi)]
    public struct Parameter
    {
        public ushort ServerAddr;
        public ushort CheckAddress;
        public ushort CheckValue;
    }


    public class Modbus
    {
        private const string DllName = "IH_CS_Modbus.dll";

        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        private static extern IntPtr createModbus(Parameter parameter);

        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        private static extern void destroyModbus(IntPtr instance);

        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        private static extern int connectState(IntPtr instance);

        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        private static extern IntPtr portName(IntPtr instance);

        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        private static extern int read(
            IntPtr instance,
            RegisterType registerType,
            ushort startAddr,
            ushort num,
            [Out] short[] data,
            int timeOut = 3500);

        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        private static extern int write(
            IntPtr instance,
            RegisterType registerType,
            ushort startAddr,
            short[] data,
            ushort num,
            int timeOut = 3500);

        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        private static extern int readSensor(
            IntPtr instance,
            ushort startAddr,
            [Out] short[] data,
            int timeOut = 3500);

        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        private static extern int readSensorArray(
            IntPtr instance,
            ushort startAddr,
            ushort num,
            [Out] short[] data,
            int timeOut = 3500);

        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        private static extern int readSensorRange(
            IntPtr instance,
            ushort startAddr,
            ushort endAddr,
            ushort num,
            [Out] short[] data,
            int timeOut = 3500);

        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        private static extern int readSwitch(
            IntPtr instance,
            ushort startAddr,
            [Out] short[] data,
            int timeOut = 3500);

        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        private static extern int readSwitchArray(
            IntPtr instance,
            ushort startAddr,
            ushort num,
            [Out] short[] data,
            int timeOut = 3500);

        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        private static extern int writeSwitch(
            IntPtr instance,
            ushort startAddr,
            short[] data,
            int timeOut = 3500);

        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        private static extern int writeSwitchArray(
            IntPtr instance,
            ushort startAddr,
            short[] data,
            ushort num,
            int timeOut = 3500);

        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        private static extern int writeSwitchCheck(
            IntPtr instance,
            ushort startAddr,
            short[] data,
            int timeOut = 3500);

        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        private static extern int readRegister(
            IntPtr instance,
            ushort startAddr,
            [Out] short[] data,
            int timeOut = 3500);

        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        private static extern int readRegisterArray(
            IntPtr instance,
            ushort startAddr,
            ushort num,
            [Out] short[] data,
            int timeOut = 3500);

        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        private static extern int writeRegister(
            IntPtr instance,
            ushort startAddr,
            short[] data,
            int timeOut = 3500);

        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        private static extern int writeRegisterArray(
            IntPtr instance,
            ushort startAddr,
            short[] data,
            ushort num,
            int timeOut = 3500);

        [DllImport(DllName, CallingConvention = CallingConvention.Cdecl)]
        private static extern int writeRegisterCheck(
            IntPtr instance,
            ushort startAddr,
            short[] data,
            int timeOut = 3500);
        

        private IntPtr _instance;

        public Modbus(Parameter parameter)
        {
            _instance = createModbus(parameter);
            if (_instance == IntPtr.Zero)
            {
                throw new Exception("Failed to create Modbus instance.");
            }
            else
            {
                Console.WriteLine("Create Modbus finished");
            }
        }

        ~Modbus()
        {
            if (_instance != IntPtr.Zero)
            {
                destroyModbus(_instance);
                _instance = IntPtr.Zero;
            }
        }

        public int ConnectState()
        {
            if (_instance == IntPtr.Zero) throw new ObjectDisposedException(nameof(Modbus));
            return connectState(_instance);
        }

        public string PortName()
        {
            if (_instance == IntPtr.Zero) throw new ObjectDisposedException(nameof(Modbus));
            IntPtr portNamePtr = portName(_instance);
            return Marshal.PtrToStringAnsi(portNamePtr);
        }

        public int Read(RegisterType registerType, ushort startAddr, ushort num, out short[] data, int timeOut = 3500)
        {
            if (_instance == IntPtr.Zero) throw new ObjectDisposedException(nameof(Modbus));
            data = new short[num];
            return read(_instance, registerType, startAddr, num, data, timeOut);
        }

        public int Write(RegisterType registerType, ushort startAddr, short[] data, ushort num, int timeOut = 3500)
        {
            if (_instance == IntPtr.Zero) throw new ObjectDisposedException(nameof(Modbus));
            return write(_instance, registerType, startAddr, data, num, timeOut);
        }
        public int readSensor(ushort startAddr, out short[] data, int timeOut = 3500)
        {
            if (_instance == IntPtr.Zero) throw new ObjectDisposedException(nameof(Modbus));
            data = new short[1];
            return readSensor(_instance, startAddr, data, timeOut);
        }
        public int readSensorArray(ushort startAddr, ushort num, out short[] data, int timeOut = 3500)
        {
            if (_instance == IntPtr.Zero) throw new ObjectDisposedException(nameof(Modbus));
            data = new short[num];
            return readSensorArray(_instance, startAddr, num, data, timeOut);
        }
        public int readSensorRange( ushort startAddr, ushort endAddr, ushort num, out short[] data, int timeOut = 3500)
        {
            if (_instance == IntPtr.Zero) throw new ObjectDisposedException(nameof(Modbus));
            data = new short[num];
            return readSensorRange(_instance, startAddr, endAddr, num, data, timeOut);
        }

        public int readSwitch(ushort startAddr, out short[] data, int timeOut = 3500)
        {
            if (_instance == IntPtr.Zero) throw new ObjectDisposedException(nameof(Modbus));
            data = new short[1];
            return readSwitch(_instance, startAddr, data, timeOut);
        }
        public int readSwitchArray(ushort startAddr, ushort num, out short[] data, int timeOut = 3500)
        {
            if (_instance == IntPtr.Zero) throw new ObjectDisposedException(nameof(Modbus));
            data = new short[num];
            return readSwitchArray(_instance, startAddr, num, data, timeOut);
        }

        public int writeSwitch(ushort startAddr, short[] data, int timeOut = 3500)
        {
            if (_instance == IntPtr.Zero) throw new ObjectDisposedException(nameof(Modbus));
            return writeSwitch(_instance, startAddr, data, timeOut);
        }

        public int writeSwitchArray(ushort startAddr, short[] data, ushort num, int timeOut = 3500)
        {
            if (_instance == IntPtr.Zero) throw new ObjectDisposedException(nameof(Modbus));
            return writeSwitchArray(_instance, startAddr, data, num, timeOut);
        }

        public int writeSwitchCheck(ushort startAddr, short[] data, int timeOut = 3500)
        {
            if (_instance == IntPtr.Zero) throw new ObjectDisposedException(nameof(Modbus));
            return writeSwitchCheck(_instance, startAddr, data, timeOut);
        }
        public int readRegister(ushort startAddr, out short[] data, int timeOut = 3500)
        {
            if (_instance == IntPtr.Zero) throw new ObjectDisposedException(nameof(Modbus));
            data = new short[1];
            return readRegister(_instance, startAddr, data, timeOut);
        }
        public int readRegisterArray(ushort startAddr, ushort num, out short[] data, int timeOut = 3500)
        {
            if (_instance == IntPtr.Zero) throw new ObjectDisposedException(nameof(Modbus));
            data = new short[num];
            return readRegisterArray(_instance, startAddr, num, data, timeOut);
        }

        public int writeRegister(ushort startAddr, short[] data, int timeOut = 3500)
        {
            if (_instance == IntPtr.Zero) throw new ObjectDisposedException(nameof(Modbus));
            return writeRegister(_instance, startAddr, data, timeOut);
        }

        public int writeRegisterArray(ushort startAddr, short[] data, ushort num, int timeOut = 3500)
        {
            if (_instance == IntPtr.Zero) throw new ObjectDisposedException(nameof(Modbus));
            return writeRegisterArray(_instance, startAddr, data, num, timeOut);
        }

        public int writeRegisterCheck(ushort startAddr, short[] data, int timeOut = 3500)
        {
            if (_instance == IntPtr.Zero) throw new ObjectDisposedException(nameof(Modbus));
            return writeRegisterCheck(_instance, startAddr, data, timeOut);
        }
    }
}
