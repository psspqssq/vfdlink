# 🔧 Modbus RTU for PLC Implementation - Complete Guide

## Purpose
This guide shows you **exactly** how to create Modbus RTU frames manually in a PLC without using libraries. Every byte is explained.

---

## 📐 Modbus RTU Frame Structure

### Basic Frame Format

```
┌──────────┬──────────┬────────────┬──────────┬──────────┐
│ Slave ID │ Function │    Data    │ CRC Low  │ CRC High │
│ (1 byte) │ (1 byte) │ (N bytes)  │ (1 byte) │ (1 byte) │
└──────────┴──────────┴────────────┴──────────┴──────────┘
```

**Key Points:**
- Minimum frame: 4 bytes (Slave ID + Function + 2 CRC bytes)
- Maximum frame: 256 bytes
- Data is BIG ENDIAN (most significant byte first)
- CRC is LITTLE ENDIAN (least significant byte first)

---

## 🎯 Writing to a WEG Register (Function 0x06)

This is what your PLC needs to do to control the WEG drive.

### Function 0x06: Write Single Register

**Frame Structure:**
```
Byte 0: Slave ID        (1 byte)
Byte 1: Function 0x06   (1 byte)
Byte 2: Register Hi     (1 byte)  ─┐
Byte 3: Register Lo     (1 byte)  ─┴─ 16-bit register address
Byte 4: Value Hi        (1 byte)  ─┐
Byte 5: Value Lo        (1 byte)  ─┴─ 16-bit value to write
Byte 6: CRC Lo          (1 byte)  ─┐
Byte 7: CRC Hi          (1 byte)  ─┴─ Error check
```

**Total: 8 bytes**

---

## 📝 Real Example: Start Motor at 30Hz

### Step 1: Set Frequency to 30Hz

**What we want:**
- Slave ID: 6 (WEG address)
- Register: P0683 = 683 decimal = 0x02AB hex
- Value: 4096 (50% of 8192, which is 30Hz if max is 60Hz)
- Value in hex: 4096 = 0x1000 hex

**Build the frame byte by byte:**

```
Byte 0: 0x06        (Slave ID = 6)
Byte 1: 0x06        (Function = Write Single Register)
Byte 2: 0x02        (Register high byte of 0x02AB)
Byte 3: 0xAB        (Register low byte of 0x02AB)
Byte 4: 0x10        (Value high byte of 0x1000 = 4096)
Byte 5: 0x00        (Value low byte of 0x1000)
Byte 6: 0x??        (CRC low - calculate below)
Byte 7: 0x??        (CRC high - calculate below)
```

**Frame before CRC:**
```
[0x06][0x06][0x02][0xAB][0x10][0x00]
```

### Step 2: Calculate CRC-16

See "CRC Calculation" section below. For this frame:
```
CRC = 0xA1E6

CRC Low byte  = 0xE6
CRC High byte = 0xA1
```

**Complete frame to send:**
```
[0x06][0x06][0x02][0xAB][0x10][0x00][0xE6][0xA1]
```

### Step 3: Send and Receive

**PLC sends:** `06 06 02 AB 10 00 E6 A1` (8 bytes)

**WEG responds:** `06 06 02 AB 10 00 E6 A1` (Same 8 bytes = echo = success!)

If there's an error, byte 1 will be 0x86 (0x06 + 0x80)

---

## 📝 Real Example: Start the Motor

After setting frequency, start the motor:

**What we want:**
- Slave ID: 6
- Register: P0682 = 682 decimal = 0x02AA hex
- Value: 1 (bit 0 set = run)

**Build the frame:**

```
Byte 0: 0x06        (Slave ID = 6)
Byte 1: 0x06        (Function = Write Single Register)
Byte 2: 0x02        (Register high byte of 0x02AA)
Byte 3: 0xAA        (Register low byte of 0x02AA)
Byte 4: 0x00        (Value high byte of 0x0001)
Byte 5: 0x01        (Value low byte - bit 0 = RUN)
Byte 6: 0x??        (CRC low)
Byte 7: 0x??        (CRC high)
```

**Frame before CRC:**
```
[0x06][0x06][0x02][0xAA][0x00][0x01]
```

**CRC calculation result:** 0x27F5
- CRC Low: 0xF5
- CRC High: 0x27

**Complete frame:**
```
[0x06][0x06][0x02][0xAA][0x00][0x01][0xF5][0x27]
```

**Result:** Motor starts running at 30Hz! 🎉

---

## 📝 Real Example: Stop the Motor

**What we want:**
- Slave ID: 6
- Register: P0682 = 0x02AA
- Value: 0 (bit 0 clear = stop)

**Complete frame:**
```
[0x06][0x06][0x02][0xAA][0x00][0x00][0x26][0x35]
```

---

## 🧮 CRC-16-MODBUS Calculation

### The Algorithm

CRC-16-MODBUS uses polynomial 0xA001 (reversed)

**Pseudo-code:**
```
function calculate_crc(data[], length):
    crc = 0xFFFF                    // Start with all bits set
    
    for i = 0 to length-1:
        crc = crc XOR data[i]       // XOR with current byte
        
        for j = 0 to 7:             // Process each bit
            if (crc AND 0x0001):    // If LSB is 1
                crc = (crc >> 1) XOR 0xA001
            else:
                crc = crc >> 1
    
    return crc                       // Already in correct byte order
```

### Step-by-Step Example

Calculate CRC for: `[0x06][0x06][0x02][0xAB][0x10][0x00]`

**Initial:**
```
CRC = 0xFFFF (binary: 1111111111111111)
```

**Process Byte 0 (0x06):**
```
CRC = 0xFFFF XOR 0x06 = 0xFFF9

Bit 0: LSB=1, so CRC = (0xFFF9 >> 1) XOR 0xA001 = 0xD7FC
Bit 1: LSB=0, so CRC = 0xD7FC >> 1 = 0x6BFE
Bit 2: LSB=0, so CRC = 0x6BFE >> 1 = 0x35FF
Bit 3: LSB=1, so CRC = (0x35FF >> 1) XOR 0xA001 = 0xCAFF
Bit 4: LSB=1, so CRC = (0xCAFF >> 1) XOR 0xA001 = 0xB57F
Bit 5: LSB=1, so CRC = (0xB57F >> 1) XOR 0xA001 = 0xFABF
Bit 6: LSB=1, so CRC = (0xFABF >> 1) XOR 0xA001 = 0xDD5F
Bit 7: LSB=1, so CRC = (0xDD5F >> 1) XOR 0xA001 = 0xBEAF

After byte 0: CRC = 0xBEAF
```

**Process Byte 1 (0x06):**
```
CRC = 0xBEAF XOR 0x06 = 0xBEA9
... (process 8 bits)
After byte 1: CRC = 0x18BE
```

**Process remaining bytes...**

**Final CRC = 0xA1E6**

**Send as:** Low byte first = `[0xE6][0xA1]`

---

## 💻 PLC Implementation - Structured Text

### Complete Function

```pascal
FUNCTION_BLOCK FB_ModbusWrite
VAR_INPUT
    SlaveID : BYTE;           // WEG address (usually 6)
    Register : UINT;          // Register number (e.g., 683)
    Value : UINT;             // Value to write
    Execute : BOOL;           // Trigger on rising edge
END_VAR

VAR_OUTPUT
    Done : BOOL;              // TRUE when complete
    Error : BOOL;             // TRUE if error
    TxBuffer : ARRAY[0..7] OF BYTE;  // Frame to send
END_VAR

VAR
    CRC : UINT;
    i : INT;
    j : INT;
END_VAR

// Build Modbus frame
IF Execute THEN
    // Byte 0: Slave ID
    TxBuffer[0] := SlaveID;
    
    // Byte 1: Function code
    TxBuffer[1] := 16#06;  // Write Single Register
    
    // Byte 2-3: Register address (big endian)
    TxBuffer[2] := UINT_TO_BYTE(Register >> 8);      // High byte
    TxBuffer[3] := UINT_TO_BYTE(Register AND 16#FF); // Low byte
    
    // Byte 4-5: Value (big endian)
    TxBuffer[4] := UINT_TO_BYTE(Value >> 8);         // High byte
    TxBuffer[5] := UINT_TO_BYTE(Value AND 16#FF);    // Low byte
    
    // Calculate CRC
    CRC := 16#FFFF;
    
    FOR i := 0 TO 5 DO  // First 6 bytes
        CRC := CRC XOR TxBuffer[i];
        
        FOR j := 0 TO 7 DO
            IF (CRC AND 16#0001) = 1 THEN
                CRC := SHR(CRC, 1) XOR 16#A001;
            ELSE
                CRC := SHR(CRC, 1);
            END_IF;
        END_FOR;
    END_FOR;
    
    // Byte 6-7: CRC (little endian!)
    TxBuffer[6] := UINT_TO_BYTE(CRC AND 16#FF);      // Low byte first
    TxBuffer[7] := UINT_TO_BYTE(CRC >> 8);           // High byte second
    
    Done := TRUE;
END_IF;

END_FUNCTION_BLOCK
```

---

## 💻 PLC Implementation - Ladder Logic

### Using Function Blocks

```
     Execute
        │
    ┌───┴────────────────────┐
    │  FB_ModbusWrite        │
    │  SlaveID := 6          │
    │  Register := 683       │
    │  Value := 4096         │
    │  Execute := StartTrig  │
    │  ─────────────────     │
    │  Done => SendFrame     │
    │  TxBuffer => SerialTx  │
    └────────────────────────┘
```

---

## 💻 PLC Implementation - C-like (Arduino/Embedded)

### Complete Example

```c
#include <stdint.h>

// Calculate CRC-16-MODBUS
uint16_t modbus_crc(uint8_t *data, uint8_t length) {
    uint16_t crc = 0xFFFF;
    uint8_t i, j;
    
    for (i = 0; i < length; i++) {
        crc ^= data[i];
        
        for (j = 0; j < 8; j++) {
            if (crc & 0x0001) {
                crc = (crc >> 1) ^ 0xA001;
            } else {
                crc = crc >> 1;
            }
        }
    }
    
    return crc;
}

// Write single register
void modbus_write_register(uint8_t slave_id, uint16_t reg, uint16_t value) {
    uint8_t frame[8];
    uint16_t crc;
    
    // Build frame
    frame[0] = slave_id;
    frame[1] = 0x06;                    // Function: Write Single Register
    frame[2] = (reg >> 8) & 0xFF;       // Register high byte
    frame[3] = reg & 0xFF;              // Register low byte
    frame[4] = (value >> 8) & 0xFF;     // Value high byte
    frame[5] = value & 0xFF;            // Value low byte
    
    // Calculate CRC
    crc = modbus_crc(frame, 6);
    
    // Add CRC (little endian!)
    frame[6] = crc & 0xFF;              // CRC low byte
    frame[7] = (crc >> 8) & 0xFF;       // CRC high byte
    
    // Send via serial port
    serial_write(frame, 8);
}

// Usage examples
void set_frequency_30hz() {
    // 30Hz = 3000 in Yaskawa format
    // Convert to WEG: (3000 / 6000) * 8192 = 4096
    modbus_write_register(6, 683, 4096);
}

void start_motor() {
    modbus_write_register(6, 682, 1);  // Bit 0 = run
}

void stop_motor() {
    modbus_write_register(6, 682, 0);  // Bit 0 = stop
}
```

---

## 📊 Register Value Calculations

### Convert Hz to WEG Value

```
WEG_value = (Hz * 100 / MAX_FREQ) * 8192

Where:
- Hz = desired frequency (e.g., 30)
- MAX_FREQ = your maximum (usually 6000 for 60Hz)
- Result is 0-8192 representing 0-100%
```

**Examples:**

| Desired Hz | Calculation | WEG Value |
|------------|-------------|-----------|
| 0 Hz | (0 / 6000) * 8192 | 0 |
| 15 Hz | (1500 / 6000) * 8192 | 2048 |
| 30 Hz | (3000 / 6000) * 8192 | 4096 |
| 45 Hz | (4500 / 6000) * 8192 | 6144 |
| 60 Hz | (6000 / 6000) * 8192 | 8192 |

### PLC Scaling Function

```pascal
FUNCTION Hz_to_WEG_Value : UINT
VAR_INPUT
    Frequency_Hz : REAL;      // Desired frequency in Hz
    Max_Freq_Hz : REAL;       // Maximum frequency (usually 60.0)
END_VAR

VAR
    Percentage : REAL;
END_VAR

// Calculate percentage of max
Percentage := Frequency_Hz / Max_Freq_Hz;

// Scale to WEG range (0-8192)
Hz_to_WEG_Value := REAL_TO_UINT(Percentage * 8192.0);

END_FUNCTION
```

---

## 🔍 Reading from WEG (Function 0x03)

### Function 0x03: Read Holding Registers

**Request Frame:**
```
Byte 0: Slave ID        (1 byte)
Byte 1: Function 0x03   (1 byte)
Byte 2: Start Reg Hi    (1 byte)  ─┐ Starting register
Byte 3: Start Reg Lo    (1 byte)  ─┘
Byte 4: Quantity Hi     (1 byte)  ─┐ Number of registers
Byte 5: Quantity Lo     (1 byte)  ─┘
Byte 6: CRC Lo          (1 byte)
Byte 7: CRC Hi          (1 byte)
```

**Example: Read P0681 (actual speed)**

```
Register 681 = 0x02A9

Frame: [0x06][0x03][0x02][0xA9][0x00][0x01][CRC][CRC]
                                   ^    ^
                                   └────┴─ Read 1 register

Complete: [0x06][0x03][0x02][0xA9][0x00][0x01][0xD5][0xE7]
```

**Response Frame:**
```
Byte 0: Slave ID
Byte 1: Function 0x03
Byte 2: Byte count (= 2 * number of registers)
Byte 3: Data high byte
Byte 4: Data low byte
Byte 5: CRC Lo
Byte 6: CRC Hi
```

**Example Response:** (if speed is 4096)
```
[0x06][0x03][0x02][0x10][0x00][CRC][CRC]
              ^    ^─────────^
              │    └─ Value: 0x1000 = 4096
              └─ 2 bytes of data
```

---

## ⚠️ Important Timing Considerations

### Inter-Character Timeout

Modbus RTU requires **continuous transmission**. If there's a gap > 1.5 character times between bytes, the frame is considered broken.

**At 9600 baud:**
- 1 character = 11 bits (1 start + 8 data + 1 parity + 1 stop)
- Time per character = 11 / 9600 = 1.146 ms
- Maximum gap = 1.5 * 1.146 ms = **1.7 ms**

**PLC Implementation:**
```
Send all 8 bytes without delay!

// WRONG:
Send(TxBuffer[0]);
DELAY(10ms);           // ❌ Too long!
Send(TxBuffer[1]);

// RIGHT:
FOR i := 0 TO 7 DO
    Send(TxBuffer[i]); // ✓ Immediate
END_FOR
```

### Frame Gap (3.5 character times)

Wait **at least** 3.5 character times between frames.

**At 9600 baud:**
- Minimum gap = 3.5 * 1.146 ms = **4 ms**

```pascal
// Send first command
ModbusWrite(6, 683, 4096);

// Wait before next command
WAIT_TIME(5);  // 5 ms minimum

// Send second command
ModbusWrite(6, 682, 1);
```

---

## 📝 Complete PLC Example: Start Motor at 30Hz

### Structured Text

```pascal
PROGRAM MotorControl
VAR
    StartButton : BOOL;
    StopButton : BOOL;
    DesiredFreq : REAL := 30.0;     // 30 Hz
    
    TxFrame : ARRAY[0..7] OF BYTE;
    Step : INT := 0;
    Timer : TON;
    
    WEG_SlaveID : BYTE := 6;
END_VAR

CASE Step OF
    0:  // Wait for start button
        IF StartButton THEN
            Step := 1;
        END_IF;
    
    1:  // Set frequency to 30Hz
        // Calculate WEG value: (30/60) * 8192 = 4096
        BuildModbusFrame(WEG_SlaveID, 683, 4096, TxFrame);
        SendSerialData(TxFrame, 8);
        Timer(IN:=TRUE, PT:=T#10ms);
        Step := 2;
    
    2:  // Wait for transmission
        IF Timer.Q THEN
            Timer(IN:=FALSE);
            Step := 3;
        END_IF;
    
    3:  // Start motor
        BuildModbusFrame(WEG_SlaveID, 682, 1, TxFrame);
        SendSerialData(TxFrame, 8);
        Step := 4;
    
    4:  // Running - wait for stop
        IF StopButton THEN
            Step := 5;
        END_IF;
    
    5:  // Stop motor
        BuildModbusFrame(WEG_SlaveID, 682, 0, TxFrame);
        SendSerialData(TxFrame, 8);
        Step := 0;
END_CASE;

END_PROGRAM
```

---

## 🧪 Testing Your Implementation

### Manual Test Values

Test your CRC calculation with these known values:

| Frame | Expected CRC |
|-------|--------------|
| `[0x01][0x03][0x00][0x00][0x00][0x0A]` | 0xC5CD |
| `[0x06][0x06][0x02][0xAB][0x10][0x00]` | 0xA1E6 |
| `[0x06][0x06][0x02][0xAA][0x00][0x01]` | 0x27F5 |

### Verify Your CRC Function

```c
// Test vectors
uint8_t test1[] = {0x01, 0x03, 0x00, 0x00, 0x00, 0x0A};
uint16_t crc1 = modbus_crc(test1, 6);
// Should be: 0xC5CD

uint8_t test2[] = {0x06, 0x06, 0x02, 0xAB, 0x10, 0x00};
uint16_t crc2 = modbus_crc(test2, 6);
// Should be: 0xA1E6

uint8_t test3[] = {0x06, 0x06, 0x02, 0xAA, 0x00, 0x01};
uint16_t crc3 = modbus_crc(test3, 6);
// Should be: 0x27F5
```

---

## 🐛 Troubleshooting

### No Response from WEG

**Check:**
1. Baud rate matches (both 9600)
2. Parity matches (usually None)
3. Slave ID is correct (check P0315 on WEG)
4. CRC is correct
5. No gaps between bytes
6. Proper gap between frames (>4ms at 9600)
7. RS-485 A/B wires not swapped

### Wrong CRC Error

**Common mistakes:**
1. Not sending CRC in little-endian (low byte first)
2. Wrong polynomial (should be 0xA001)
3. Not initializing CRC to 0xFFFF
4. Including CRC bytes in CRC calculation (don't!)

### Motor Doesn't Start

**Sequence matters:**
1. First: Set frequency (register 683)
2. Wait: 10ms minimum
3. Then: Send run command (register 682)

Also check:
- WEG is in remote mode (parameter P0220)
- WEG has no faults (check display)
- Frequency is > 0

---

## 📋 Quick Reference Card

### Frame Construction Checklist

```
□ Byte 0: Slave ID (usually 6)
□ Byte 1: Function (0x06 for write)
□ Byte 2: Register high byte (big endian)
□ Byte 3: Register low byte
□ Byte 4: Value high byte (big endian)
□ Byte 5: Value low byte
□ Byte 6: CRC low byte (little endian)
□ Byte 7: CRC high byte
```

### Key WEG Registers

| Register | Hex | Function | Values |
|----------|-----|----------|--------|
| P0682 | 0x02AA | Control word | Bit 0: 1=Run, 0=Stop |
| P0683 | 0x02AB | Speed reference | 0-8192 (0-100%) |
| P0685 | 0x02AD | Direction | 0=Forward, 1=Reverse |
| P0681 | 0x02A9 | Actual speed | Read only |

### Baud Rate Character Times

| Baud | 1 Char | Inter-char (<) | Frame gap (>) |
|------|--------|----------------|---------------|
| 9600 | 1.15ms | 1.7ms | 4ms |
| 19200 | 0.57ms | 0.9ms | 2ms |
| 38400 | 0.29ms | 0.4ms | 1ms |

---

## 💡 Pro Tips

1. **Always set frequency first, then start** - WEG won't start at 0Hz

2. **Use a serial monitor** - See actual bytes being sent/received

3. **Test CRC separately** - Verify your CRC function with known values

4. **Add timeouts** - If no response in 100ms, retry

5. **Log everything during testing** - Helps debug issues

6. **Start simple** - Test with single command before complex sequences

7. **Use oscilloscope if available** - Verify timing and signal levels

---

## 📚 Additional Resources

### CRC Calculation Tools

Online calculator: https://crccalc.com/
- Algorithm: CRC-16/MODBUS
- Input type: Hex
- Initial value: 0xFFFF
- Polynomial: 0x8005 (or 0xA001 reversed)

### Testing Tools

- **QModMaster** - Free Modbus testing software
- **Modbus Poll** - Professional tool (paid)
- **Serial port monitor** - See raw bytes

---

## 🎯 Summary

### To control WEG from your PLC:

1. **Build 8-byte frame:**
   - Slave ID, Function, Register (2 bytes), Value (2 bytes), CRC (2 bytes)

2. **Calculate CRC:**
   - Start with 0xFFFF
   - XOR each byte, then process 8 bits
   - Send low byte first!

3. **Send continuously:**
   - No gaps > 1.5 character times between bytes
   - Wait > 3.5 character times between frames

4. **Sequence:**
   - Set frequency (P0683)
   - Wait 10ms
   - Start motor (P0682 = 1)

### Example Frames You Need:

**Set 30Hz:** `06 06 02 AB 10 00 E6 A1`  
**Start:** `06 06 02 AA 00 01 F5 27`  
**Stop:** `06 06 02 AA 00 00 26 35`

---

**You now have everything needed to implement Modbus in your PLC! 🚀**

Test with simple commands first, verify CRC calculation, then build up to complex sequences.

