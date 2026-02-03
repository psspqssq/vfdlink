# 🔧 Click PLC Implementation Guide - WEG VFD Control

## AutomationDirect Click PLC - Step-by-Step Implementation

---

## ⚠️ IMPORTANT: Which Guide Do You Need?

### This Guide: Direct Control (1 RS-485 Channel) ⭐ **Simple Setup**
```
┌─────────────┐      RS-485      ┌──────────────┐
│  Click PLC  ├──────────────────┤  WEG CFW11   │
│  (Master)   │    1 Channel     │   (Slave)    │
└─────────────┘                  └──────────────┘
```
**Use this guide if:**
- ✅ Click PLC is your ONLY controller
- ✅ You're writing the control program in Click
- ✅ No other PLC involved
- ✅ Need: 1 RS-485 channel

### Alternative: Gateway Mode (2 RS-485 Channels)
```
┌──────────┐   RS-485   ┌─────────┐   RS-485   ┌─────────┐
│Existing  ├───Chan 1───┤ Click   ├───Chan 2───┤   WEG   │
│   PLC    │  (Yaskawa) │Gateway  │   (WEG)    │  CFW11  │
└──────────┘            └─────────┘            └─────────┘
```
**Use [CLICK_PLC_GATEWAY.md](CLICK_PLC_GATEWAY.md) instead if:**
- ✅ You have an existing PLC that speaks Yaskawa
- ✅ You need Click to translate between protocols
- ✅ You're replacing the Python gateway with Click PLC
- ✅ Need: 2 RS-485 channels

> **📄 2-Channel Gateway Setup: [CLICK_PLC_GATEWAY.md](CLICK_PLC_GATEWAY.md)**

---

## 🎯 Good News!

Click PLCs have **built-in Modbus instructions** that handle CRC and framing automatically! You don't need to calculate CRC manually.

---

## 📋 Hardware Setup

### Required Click PLC Model

You need a Click PLC with a **serial port** (RS-485 or RS-232):

- **Click PLUS CPU** (C2-01CPU or C2-02CPU) - Has RS-485 port
- **Click BASIC** with **C0-01AC** (RS-232/485 module)

### Wiring

**For RS-485 (recommended):**
```
Click PLC          WEG CFW11
Port 2 (RS-485)
  A  ────────────── A (Terminal 10)
  B  ────────────── B (Terminal 11)
  C  ────────────── GND (Terminal 9)
```

**Important:** Add 120Ω termination resistor at WEG end between A and B

---

## ⚙️ Click Programming Software Setup

### 1. Configure Serial Port

**In Click Programming Software:**

1. Go to **Setup** → **Serial Ports** → **Port 2 (RS-485)**
2. Set parameters:
   - **Protocol:** Modbus RTU Master
   - **Baud Rate:** 9600
   - **Data Bits:** 8
   - **Parity:** None
   - **Stop Bits:** 1
   - **Transmit Delay:** 10 ms (between frames)

![Port Configuration]
```
┌─────────────────────────────────────┐
│ Port 2 Configuration                │
├─────────────────────────────────────┤
│ Protocol:     [Modbus RTU Master]   │
│ Baud Rate:    [9600]                │
│ Data Bits:    [8]                   │
│ Parity:       [None]                │
│ Stop Bits:    [1]                   │
│ TX Delay:     [10] ms               │
└─────────────────────────────────────┘
```

---

## 📊 Click PLC Memory Allocation

### Data Registers (DS) - Use these

```
DS1     - Motor frequency setpoint (Hz × 10, e.g., 300 = 30.0Hz)
DS2     - WEG speed reference value (0-8192)
DS3     - Control word (bit 0 = run/stop)
DS4     - Modbus function status
DS5     - Scratch register for calculations

DF1     - Frequency in Hz (floating point, optional)
DF2     - Max frequency constant (60.0)
```

### Control Bits (C) - Use these

```
C1      - Start button (input)
C2      - Stop button (input)
C3      - Motor running status
C4      - Modbus write complete flag
C5      - Modbus error flag
C10     - System enable
```

---

## 🔢 Click PLC Ladder Logic Implementation

### Network 1: System Initialization

```
     C10                         
─────] [──────────────────────(L)── (Load DS1 with 300 = 30Hz)
                               │
                               └── MOV 300 DS1
                               
     C10                         
─────] [──────────────────────(L)── (Load max freq)
                               │
                               └── MOV 6000 DS5
```

### Network 2: Calculate WEG Speed Value

**Formula:** `DS2 = (DS1 × 8192) ÷ 6000`

```
     C10                                    
─────] [──────────────────────────────(L)── MUL DS1, 8192, DS2
                                       │
                                       └── DIV DS2, 6000, DS2
```

**Explanation:**
- DS1 = 300 (30.0 Hz)
- 300 × 8192 = 2,457,600
- 2,457,600 ÷ 6000 = 4096
- DS2 = 4096 (50% of 8192)

### Network 3: Write Frequency to WEG

**Using MODBUS WRITE instruction:**

```
     C10          C4
─────] [─────────]/[────────────────(L)── Modbus Write
                                      │
                                      └── MWX (Modbus Write Extended)
                                          Port: 2
                                          Slave: 6
                                          Function: 6 (Write Single Reg)
                                          Register: 683
                                          Data Source: DS2
                                          Status: C4
                                          Error: C5
```

**Click Instruction Parameters:**
- **Port:** 2 (RS-485 port)
- **Slave ID:** 6 (WEG address from P0315)
- **Function:** 6 (Write Single Register)
- **Register:** 683 (P0683 - Speed Reference)
- **Data:** DS2 (calculated WEG value)
- **Done Bit:** C4 (goes high when write completes)
- **Error Bit:** C5 (goes high on error)

### Network 4: Start Motor Command

```
     C1           C2           C3           C4
─────] [─────────]/[─────────]/[──────────] [───(L)── MOV 1 DS3
                                               │
     C4                                        └── MWX
─────] [──────────────────────────────(L)──       Port: 2
                                       │          Slave: 6
                                       └──        Function: 6
                                                  Register: 682
                                                  Data Source: DS3
                                                  Status: C4
                                                  Error: C5
                                                  
──────────────────────────────────────(S)── C3 (Set running status)
```

**Explanation:**
- C1 = Start button pressed
- C2 = Stop button NOT pressed
- C3 = Motor NOT already running
- C4 = Previous Modbus write completed
- Then: Write 1 to DS3, send to P0682 (control word)
- Set C3 to indicate motor running

### Network 5: Stop Motor Command

```
     C2           C3           C4
─────] [─────────] [──────────] [───────(L)── MOV 0 DS3
                                         │
     C4                                  └── MWX
─────] [──────────────────────────(L)──     Port: 2
                                   │        Slave: 6
                                   └──      Function: 6
                                            Register: 682
                                            Data Source: DS3
                                            Status: C4
                                            Error: C5
                                            
──────────────────────────────────(R)── C3 (Reset running status)
```

### Network 6: Frequency Adjustment (Optional)

```
     C10          X1                    
─────] [─────────] [──────────────(L)── INC DS1  (Increase freq)
                                   │
                                   └── (limit check)
                                       IF DS1 > 600 THEN DS1 = 600
     
     C10          X2
─────] [─────────] [──────────────(L)── DEC DS1  (Decrease freq)
                                   │
                                   └── (limit check)
                                       IF DS1 < 0 THEN DS1 = 0
```

---

## 📝 Complete Click PLC Program (Text View)

### Using Click Programming Software Ladder Editor

```
Network 1: Initialize
├─ Rung 1: MOV 300 → DS1          // 30.0 Hz setpoint
├─ Rung 2: MOV 6000 → DS5         // Max frequency reference
└─ Rung 3: (S) C10                // Enable system

Network 2: Scale Frequency to WEG Format
├─ Rung 1: MUL DS1, 8192 → DS2    // Multiply by 8192
└─ Rung 2: DIV DS2, 6000 → DS2    // Divide by max freq

Network 3: Write Speed to WEG
└─ Rung 1: MWX
           ├─ Port 2
           ├─ Slave 6
           ├─ Function 6
           ├─ Register 683
           ├─ Data DS2
           ├─ Done C4
           └─ Error C5

Network 4: Start Motor
├─ Rung 1: MOV 1 → DS3            // Run command
└─ Rung 2: MWX
           ├─ Port 2
           ├─ Slave 6
           ├─ Function 6
           ├─ Register 682
           ├─ Data DS3
           ├─ Done C4
           └─ Error C5

Network 5: Stop Motor
├─ Rung 1: MOV 0 → DS3            // Stop command
└─ Rung 2: MWX
           ├─ Port 2
           ├─ Slave 6
           ├─ Function 6
           ├─ Register 682
           ├─ Data DS3
           ├─ Done C4
           └─ Error C5
```

---

## 🎯 Click Structured Text (Optional)

If you prefer Structured Text in Click PLUS:

```pascal
PROGRAM VFD_Control

VAR
    FreqSetpoint : INT := 300;      // 30.0 Hz
    WEG_SpeedRef : INT;             // 0-8192
    ControlWord : INT;              // Run/Stop
    StartButton : BOOL;
    StopButton : BOOL;
    MotorRunning : BOOL;
END_VAR

// Scale frequency to WEG format
WEG_SpeedRef := (FreqSetpoint * 8192) / 6000;

// Write speed reference to WEG
MODBUS_WRITE(
    Port := 2,
    SlaveID := 6,
    FunctionCode := 6,
    RegisterAddr := 683,
    Data := WEG_SpeedRef,
    Done => ModbusDone,
    Error => ModbusError
);

// Start motor
IF StartButton AND NOT StopButton AND NOT MotorRunning THEN
    ControlWord := 1;
    MODBUS_WRITE(
        Port := 2,
        SlaveID := 6,
        FunctionCode := 6,
        RegisterAddr := 682,
        Data := ControlWord,
        Done => ModbusDone,
        Error => ModbusError
    );
    MotorRunning := TRUE;
END_IF;

// Stop motor
IF StopButton AND MotorRunning THEN
    ControlWord := 0;
    MODBUS_WRITE(
        Port := 2,
        SlaveID := 6,
        FunctionCode := 6,
        RegisterAddr := 682,
        Data := ControlWord,
        Done => ModbusDone,
        Error => ModbusError
    );
    MotorRunning := FALSE;
END_IF;

END_PROGRAM
```

---

## 🔍 Using Click's Built-in Modbus Instructions

### MWX - Modbus Write Extended (Recommended)

**Instruction Box:**
```
┌─────────────────────────────┐
│        MWX                  │
│                             │
│ Port:      [2]              │ ← RS-485 port
│ Slave:     [6]              │ ← WEG address
│ Function:  [6]              │ ← Write Single Register
│ Register:  [683]            │ ← P0683 Speed Reference
│ Data:      [DS2]            │ ← Source register
│ Done:      [C4]             │ ← Completion bit
│ Error:     [C5]             │ ← Error bit
└─────────────────────────────┘
```

**What Click Handles Automatically:**
- ✅ CRC calculation (you don't code this!)
- ✅ Frame construction
- ✅ Byte ordering (endianness)
- ✅ Timing between bytes
- ✅ Response handling
- ✅ Error detection

**You just provide:**
- Slave ID
- Register number
- Value to write

---

## 📊 HMI Integration (Click View)

### Using C-More or Click View HMI

**Screen Layout:**

```
┌─────────────────────────────────────────┐
│  WEG Motor Control                      │
├─────────────────────────────────────────┤
│                                         │
│  Frequency Setpoint: [ 30.0 ] Hz       │ ← Numeric input (DS1 ÷ 10)
│                                         │
│  ┌─────────┐  ┌─────────┐              │
│  │  START  │  │  STOP   │              │ ← Momentary buttons
│  └─────────┘  └─────────┘              │
│                                         │
│  Motor Status: [RUNNING]                │ ← Status indicator (C3)
│                                         │
│  Actual Speed: 30.0 Hz                  │ ← Read from P0681
│                                         │
│  [=================    ] 75%            │ ← Bar graph
│                                         │
└─────────────────────────────────────────┘
```

**HMI Tag Assignments:**

| Screen Element | Type | Address | Description |
|----------------|------|---------|-------------|
| Freq Setpoint | Numeric Entry | DS1 | User enters 0-600 (×10) |
| Start Button | Momentary | C1 | Sets C1 on press |
| Stop Button | Momentary | C2 | Sets C2 on press |
| Motor Status | Indicator | C3 | Shows run/stop |
| Actual Speed | Numeric Display | DS10 | Read from WEG |
| Speed Bar | Bar Graph | DS10 | Visual feedback |

---

## 🔁 Reading Motor Status from WEG

### Add Modbus Read Instruction

**Network: Read Actual Speed**

```
     C10          Timer1
─────] [─────────] [────────────(L)── MRX (Modbus Read Extended)
                                 │
                                 └── MRX
                                     Port: 2
                                     Slave: 6
                                     Function: 3 (Read Holding Reg)
                                     Register: 681  (P0681 Actual Speed)
                                     Quantity: 1
                                     Destination: DS10
                                     Done: C6
                                     Error: C7
                                     
─────────────────────────────────(TON)── Timer1: 100ms (read every 100ms)
```

**Convert WEG value to Hz for display:**

```
Network: Convert to Hz
     C6
─────] [──────────────────────(L)── MUL DS10, 6000 → DS11
                               │
                               └── DIV DS11, 8192 → DS11
                                   (DS11 now in Hz × 10)
```

---

## ⚙️ WEG CFW11 Parameter Setup

**Before programming, configure WEG:**

| Parameter | Setting | Description |
|-----------|---------|-------------|
| P0220 | 2 or 3 | Serial/Remote control mode |
| P0312 | 9600 | Baud rate |
| P0313 | 0 | Parity = None |
| P0314 | 0 | Stop bits = 1 |
| P0315 | 6 | Slave address |
| P0316 | 4 | Protocol = Modbus RTU |
| P0317 | 1.0 | Communication timeout (1 sec) |

**How to set:**
1. Press **P** button on WEG display
2. Enter parameter number (e.g., 0315)
3. Press **P** again
4. Use arrows to set value (e.g., 6)
5. Press **P** to save
6. Repeat for all parameters

---

## 🧪 Testing Procedure

### Step 1: Test Communication

**Simple test program:**

```
Network 1: Write Test Value
     C1
─────] [──────────────────(L)── MOV 100 → DS2
                           │
                           └── MWX
                               Port: 2
                               Slave: 6
                               Function: 6
                               Register: 683
                               Data: DS2
                               Done: C4
                               Error: C5
```

**Expected:**
- C4 should turn ON (write successful)
- C5 should stay OFF (no errors)

**If C5 turns ON:**
- Check wiring (A, B, GND)
- Verify WEG slave ID (P0315)
- Verify baud rate matches (P0312)

### Step 2: Test Motor Start

**Prerequisites:**
- WEG must be powered
- No faults on WEG display
- Emergency stop not pressed

**Program:**
1. Set DS1 = 300 (30 Hz)
2. Press Start button (C1)
3. Monitor C3 (should go high)
4. Motor should start spinning

### Step 3: Test Frequency Changes

**Gradually increase frequency:**
```
DS1 = 100  → 10 Hz  (motor slow)
DS1 = 300  → 30 Hz  (medium)
DS1 = 500  → 50 Hz  (fast)
```

Motor speed should change accordingly.

---

## 🐛 Troubleshooting Click PLC

### Issue 1: C5 (Error Bit) Always On

**Possible causes:**

1. **Wrong Slave ID**
   - Check: P0315 on WEG = Slave ID in MWX instruction
   
2. **Wrong Baud Rate**
   - Check: P0312 on WEG = Click port 2 baud rate setting
   
3. **Wiring Issue**
   - Check: A-to-A, B-to-B
   - Check: Ground connection
   - Check: Termination resistor (120Ω)

4. **WEG Not in Remote Mode**
   - Check: P0220 should be 2 or 3

### Issue 2: Motor Doesn't Start

**Check sequence:**

1. **Frequency set first?**
   - Must write to register 683 BEFORE 682
   - Add 100ms timer between writes

2. **WEG ready?**
   - Check WEG display for fault codes
   - Reset WEG if needed

3. **Control word correct?**
   - DS3 should be 1 (bit 0 set)
   - Monitor DS3 value in Click software

### Issue 3: Intermittent Communication

**Possible causes:**

1. **Electrical Noise**
   - Use shielded cable
   - Keep away from power wires
   - Add ferrite beads

2. **Missing Termination**
   - Add 120Ω resistor at WEG end

3. **Wrong Timing**
   - Increase TX Delay in Click port settings
   - Try 20ms or 50ms

---

## 📋 Complete Programming Checklist

### Before Starting

- [ ] Click PLC has RS-485 port (or module)
- [ ] WEG CFW11 powered on
- [ ] RS-485 cable connected (A-to-A, B-to-B)
- [ ] Termination resistor installed (120Ω)
- [ ] WEG parameters configured (P0312-P0317)
- [ ] Click Programming Software installed

### Programming Steps

- [ ] Configure Click Port 2 for Modbus RTU Master, 9600, 8N1
- [ ] Create data registers (DS1-DS5)
- [ ] Create control bits (C1-C5)
- [ ] Program Network 1: Initialize
- [ ] Program Network 2: Calculate WEG value
- [ ] Program Network 3: Write frequency
- [ ] Program Network 4: Start motor
- [ ] Program Network 5: Stop motor
- [ ] Download program to Click PLC
- [ ] Test communication (check C4/C5)
- [ ] Test motor start/stop
- [ ] Test frequency changes

### After Testing

- [ ] Add HMI screens (if using Click View)
- [ ] Add error handling
- [ ] Add status monitoring
- [ ] Add data logging (optional)
- [ ] Document settings
- [ ] Train operators

---

## 💡 Pro Tips for Click PLC

### 1. Use Timers for Sequencing

```
     C1           TMR1
─────] [─────────]/[──────(TON)── TMR1: 100ms
                           │
     TMR1.Q               └── (write frequency)
─────] [──────────(TON)── TMR2: 100ms
                   │
     TMR2.Q       └── (start motor)
─────] [──────────(S)── C3
```

### 2. Add Safety Interlocks

```
     C1           EmergencyStop      VFD_Fault
─────] [─────────]/[───────────────]/[──────(start logic)
```

### 3. Monitor Communication Health

```
Network: Communication Watchdog
     C4
─────]/[──────────(TON)── TMR_Watchdog: 1000ms (1 sec)
                   │
     TMR_Watchdog.Q
─────] [──────────(S)── C_CommFault (Set comm fault)
```

If no successful write in 1 second → flag fault

---

## 📊 Memory Usage Estimate

**Typical Click PLC program:**

- **Data Registers:** 10-15 (DS1-DS15)
- **Control Bits:** 10-20 (C1-C20)
- **Timers:** 5-10
- **Program Size:** ~50-100 rungs
- **Scan Time:** < 5ms

**Well within Click PLC capabilities!**

---

## 🎓 Next Steps

### Beginner Level
1. Start with simple test (write single value)
2. Add start/stop commands
3. Test thoroughly before production

### Intermediate Level
4. Add HMI for operator interface
5. Implement error handling
6. Add status monitoring

### Advanced Level
7. Multi-motor control
8. Recipe management
9. Data logging
10. Remote monitoring

---

## 📚 Additional Resources

### AutomationDirect Resources
- Click PLC User Manual (Chapter on Modbus)
- Click Programming Software Help (F1 key)
- AutomationDirect Technical Support: 1-800-633-0405

### WEG Resources
- CFW11 Manual (Modbus section)
- Parameter reference guide

### This Project's Resources
- [MODBUS_PLC_GUIDE.md](MODBUS_PLC_GUIDE.md) - General Modbus theory
- [MODBUS_CHEAT_SHEET.txt](MODBUS_CHEAT_SHEET.txt) - Quick reference
- [FOR_PLC_PROGRAMMERS.md](FOR_PLC_PROGRAMMERS.md) - General PLC guide

---

## 🎯 Summary

**Click PLC makes it EASY!**

✅ **No CRC calculation needed** - Click handles it  
✅ **No frame construction** - Click handles it  
✅ **No timing worries** - Click handles it  
✅ **Just use MWX instruction** - Give it register & value  

**Basic program is ~5 networks, ~20 rungs!**

**You can have a working motor control in 1-2 hours!**

---

## 🚀 Ready to Program?

1. **Configure Port 2** (Modbus RTU Master, 9600, 8N1)
2. **Use MWX instruction** (Port 2, Slave 6, Function 6)
3. **Write to Register 683** (frequency) then **Register 682** (start)
4. **Done!**

**That's literally all you need for Click PLC!** 🎉

---

*Good luck with your Click PLC programming!*

