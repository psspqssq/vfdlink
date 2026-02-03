# 🔧 Quick Start for PLC Programmers

## You Asked: "How do Modbus instructions work without libraries?"

**This document is your answer!** ✅

---

## 🎯 What You Need

You need to send **8 bytes** to control the WEG drive. Here's exactly how:

### The 8-Byte Frame

```
[SlaveID][0x06][Reg_Hi][Reg_Lo][Val_Hi][Val_Lo][CRC_Lo][CRC_Hi]
```

### Example: Start motor at 30Hz

**Step 1: Set frequency to 30Hz**
```
Send: [06][06][02][AB][10][00][E6][A1]
       │   │   │       │       │
       │   │   │       │       └─ CRC = 0xA1E6 (calculate or look up)
       │   │   │       └─ Value = 0x1000 = 4096 (30Hz)
       │   │   └─ Register = 0x02AB = 683 (P0683 speed reference)
       │   └─ Function = 0x06 (write single register)
       └─ Slave ID = 6
```

**Step 2: Wait 10ms**

**Step 3: Start motor**
```
Send: [06][06][02][AA][00][01][F5][27]
       │   │   │       │       └─ CRC = 0x27F5
       │   │   │       └─ Value = 1 (bit 0 = run)
       │   │   └─ Register = 0x02AA = 682 (P0682 control)
       │   └─ Function = 0x06
       └─ Slave ID = 6
```

**Done!** Motor runs at 30Hz 🎉

---

## 📋 Your To-Do List

1. **Print this:** [MODBUS_CHEAT_SHEET.txt](MODBUS_CHEAT_SHEET.txt) - Keep it at your desk!

2. **Read this:** [MODBUS_PLC_GUIDE.md](MODBUS_PLC_GUIDE.md) - Complete guide

3. **Copy code:** The guide has ready-to-use PLC code in:
   - Structured Text (IEC 61131-3)
   - Ladder Logic function blocks
   - C (for embedded/Arduino)

4. **Test with these frames:**
   - **Set 30Hz:** `[06][06][02][AB][10][00][E6][A1]`
   - **Start:** `[06][06][02][AA][00][01][F5][27]`
   - **Stop:** `[06][06][02][AA][00][00][26][35]`

---

## 🧮 The CRC-16 Algorithm

You need this to calculate the last 2 bytes (CRC).

### Simple Algorithm

```
CRC = 0xFFFF

FOR each byte in frame (except last 2):
    CRC = CRC XOR byte
    
    FOR bit = 0 to 7:
        IF (CRC AND 1) = 1:
            CRC = (CRC >> 1) XOR 0xA001
        ELSE:
            CRC = CRC >> 1

Send CRC LOW byte first, then HIGH byte
```

### Test Your CRC Function

If you calculate CRC for `[06][06][02][AB][10][00]`, you should get:
- **CRC = 0xA1E6**
- **Send as:** `[E6][A1]` (low byte first!)

---

## 📊 Frequency Conversion

### Formula

```
Hz → Yaskawa:  value = Hz * 100
Yaskawa → WEG: value = (Yaskawa / 6000) * 8192
```

### Quick Table

| Hz  | WEG Value | Hex Value | Byte 4 | Byte 5 |
|-----|-----------|-----------|--------|--------|
| 15  | 2048      | 0x0800    | 0x08   | 0x00   |
| 30  | 4096      | 0x1000    | 0x10   | 0x00   |
| 45  | 6144      | 0x1800    | 0x18   | 0x00   |
| 60  | 8192      | 0x2000    | 0x20   | 0x00   |

---

## ⏱️ Timing Critical!

### Between Bytes in Same Frame
**Maximum gap:** 1.7 ms @ 9600 baud

**This means:** Send all 8 bytes continuously, no delays!

```
// WRONG in PLC
Send(Byte0)
WAIT 10ms     ← ❌ Frame will break!
Send(Byte1)

// RIGHT in PLC
FOR i := 0 TO 7:
    Send(TxBuffer[i])   ← ✅ No delay between
END_FOR
```

### Between Different Frames
**Minimum gap:** 4 ms @ 9600 baud

```
// Send first command
SendFrame([06][06][02][AB][10][00][E6][A1])

// Wait!
WAIT 5ms      ← ✅ Give time for WEG to process

// Send second command
SendFrame([06][06][02][AA][00][01][F5][27])
```

---

## 🔍 WEG Register Quick Reference

| P Number | Hex    | What It Does         | Values                    |
|----------|--------|----------------------|---------------------------|
| P0682    | 0x02AA | Control (Run/Stop)   | Bit 0: 1=Run, 0=Stop      |
| P0683    | 0x02AB | Speed Reference      | 0-8192 = 0-100%           |
| P0685    | 0x02AD | Direction            | 0=Forward, 1=Reverse      |
| P0681    | 0x02A9 | Actual Speed (Read)  | 0-8192                    |

---

## 📝 Complete PLC Example (Structured Text)

```pascal
PROGRAM StartMotor
VAR
    Step : INT := 0;
    Timer : TON;
    TxFrame : ARRAY[0..7] OF BYTE;
END_VAR

CASE Step OF
    0:  // Set frequency to 30Hz (4096)
        TxFrame[0] := 16#06;  // Slave ID
        TxFrame[1] := 16#06;  // Function
        TxFrame[2] := 16#02;  // Register high (P0683)
        TxFrame[3] := 16#AB;  // Register low
        TxFrame[4] := 16#10;  // Value high (4096)
        TxFrame[5] := 16#00;  // Value low
        TxFrame[6] := 16#E6;  // CRC low
        TxFrame[7] := 16#A1;  // CRC high
        
        SendSerialData(TxFrame, 8);
        Timer(IN:=TRUE, PT:=T#10ms);
        Step := 1;
    
    1:  // Wait for timer
        IF Timer.Q THEN
            Timer(IN:=FALSE);
            Step := 2;
        END_IF;
    
    2:  // Start motor
        TxFrame[0] := 16#06;
        TxFrame[1] := 16#06;
        TxFrame[2] := 16#02;
        TxFrame[3] := 16#AA;  // Register P0682
        TxFrame[4] := 16#00;
        TxFrame[5] := 16#01;  // Value = 1 (run)
        TxFrame[6] := 16#F5;  // CRC low
        TxFrame[7] := 16#27;  // CRC high
        
        SendSerialData(TxFrame, 8);
        Step := 3;
    
    3:  // Running!
        // Motor is now running at 30Hz
        ;
END_CASE;
END_PROGRAM
```

---

## ✅ Pre-Flight Checklist

Before you start programming:

- [ ] WEG parameter P0315 (Slave ID) = 6
- [ ] WEG parameter P0312 (Baud Rate) = 9600
- [ ] WEG parameter P0313 (Parity) = 0 (None)
- [ ] WEG parameter P0314 (Stop Bits) = 0 (1 bit)
- [ ] WEG parameter P0316 (Protocol) = 4 (Modbus RTU)
- [ ] WEG parameter P0220 (Control) = Remote via serial
- [ ] PLC serial port configured: 9600, 8N1
- [ ] RS-485 wiring: A-to-A, B-to-B
- [ ] Termination resistor (120Ω) if needed

---

## 🎯 Next Steps

### 1. Print the Cheat Sheet
```
MODBUS_CHEAT_SHEET.txt
```
Has all the frames, conversion tables, and CRC test values.

### 2. Read the Full Guide
```
MODBUS_PLC_GUIDE.md
```
Complete explanation with:
- Detailed CRC calculation steps
- More code examples
- Reading from WEG (Function 0x03)
- Troubleshooting guide
- Testing procedures

### 3. Understand Why It Works (Optional)
If you want to learn the theory:
```
STUDY_GUIDE.md - Section 2: Modbus Protocol
SYSTEM_DIAGRAMS.md - Modbus Frame Anatomy
```

---

## 🐛 Common Mistakes

### 1. CRC Byte Order
**Wrong:** `frame[6] = CRC_High; frame[7] = CRC_Low;`  
**Right:** `frame[6] = CRC_Low; frame[7] = CRC_High;`  

CRC is sent **LITTLE ENDIAN** (low byte first)!

### 2. Register Byte Order
**Wrong:** `frame[2] = RegisterLow; frame[3] = RegisterHigh;`  
**Right:** `frame[2] = RegisterHigh; frame[3] = RegisterLow;`  

Registers are sent **BIG ENDIAN** (high byte first)!

### 3. Timing Between Bytes
**Wrong:** Adding delays between bytes in same frame  
**Right:** Send all 8 bytes continuously  

### 4. Not Waiting Between Frames
**Wrong:** Sending next command immediately  
**Right:** Wait at least 4ms before next frame  

---

## 📞 Need Help?

### Quick Questions
- See: [MODBUS_CHEAT_SHEET.txt](MODBUS_CHEAT_SHEET.txt)

### Detailed Explanation
- See: [MODBUS_PLC_GUIDE.md](MODBUS_PLC_GUIDE.md)

### Understanding the Protocol
- See: [STUDY_GUIDE.md](STUDY_GUIDE.md) Section 2
- See: [SYSTEM_DIAGRAMS.md](SYSTEM_DIAGRAMS.md) Modbus sections

### CRC Calculation Issues
- [MODBUS_PLC_GUIDE.md](MODBUS_PLC_GUIDE.md) has test vectors
- [MODBUS_CHEAT_SHEET.txt](MODBUS_CHEAT_SHEET.txt) has quick test values

---

## 🚀 Summary

**To control WEG from your PLC:**

1. Build 8-byte frame with correct values
2. Calculate CRC (or use lookup table)
3. Send continuously (no gaps > 1.7ms)
4. Wait 4ms+ before next frame
5. First set frequency, then start motor

**Example frames you can use right now:**
- Set 30Hz: `06 06 02 AB 10 00 E6 A1`
- Start: `06 06 02 AA 00 01 F5 27`
- Stop: `06 06 02 AA 00 00 26 35`

**That's it!** No libraries needed. Pure byte manipulation.

---

**Ready to implement? Open [MODBUS_PLC_GUIDE.md](MODBUS_PLC_GUIDE.md) for the complete guide!**

🎉 **Good luck with your PLC programming!** 🎉


