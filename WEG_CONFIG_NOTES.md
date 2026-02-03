# WEG CFW11 Configuration Guide

## Serial Communication Setup (Modbus RTU)

### Required Parameters on WEG Drive

Configure these parameters on your WEG CFW11 drive using the keypad or via HMI:

| Parameter | Description | Value | Notes |
|-----------|-------------|-------|-------|
| **P0312** | Baud Rate | 9600 | Match with gateway config |
| **P0313** | Parity | 0 (None) | 0=None, 1=Even, 2=Odd |
| **P0314** | Stop Bits | 0 (1 bit) | 0=1 bit, 1=2 bits |
| **P0315** | Slave Address | 6 | Must match gateway SLAVE_ID |
| **P0316** | Protocol | 4 | 4=Modbus RTU (Required!) |
| **P0317** | Timeout | 1.0s | Serial timeout period |

### Important Control Registers

The gateway automatically translates Yaskawa commands to these WEG registers:

#### Write Registers (Commands to WEG)

| Register | Parameter | Function | Format |
|----------|-----------|----------|--------|
| **P0682** | Digital Inputs | RUN/STOP commands | Bit field |
| **P0683** | Speed Reference | Frequency setpoint | 0-8192 = 0-100% |

#### Read Registers (Status from WEG)

| Register | Parameter | Function | Format |
|----------|-----------|----------|--------|
| **P0001** | Operating State | Drive status | Status code |
| **P0002** | Output Frequency | Current frequency | 0.01 Hz units |
| **P0003** | Output Current | Motor current | 0.01 A units |
| **P0004** | Output Voltage | Motor voltage | 0.1 V units |
| **P0005** | DC Bus Voltage | Bus voltage | 0.1 V units |

### Digital Input Mapping (P0682)

When writing to P0682, bit meanings:

| Bit | Function | Value |
|-----|----------|-------|
| 0 | General Enable / Run | 1=Enable, 0=Disable |
| 1 | Forward/Reverse | 1=Forward, 0=Reverse |
| 2 | JOG | 1=JOG mode |
| 3 | Local/Remote | 1=Remote control |
| 4-15 | Reserved | - |

### Speed Reference (P0683)

Format: **0 to 8192** represents **0% to 100%** of maximum configured frequency

Example:
- If P0134 (Max Frequency) = 60.00 Hz
- Value 4096 = 50% = 30.00 Hz
- Value 8192 = 100% = 60.00 Hz

### Common WEG Parameters to Check

| Parameter | Description | Typical Value |
|-----------|-------------|---------------|
| **P0133** | Motor Rated Voltage | 220V / 380V / 440V |
| **P0134** | Max Frequency | 60.00 Hz |
| **P0220** | Source Selector | 7 (Serial/Modbus) |
| **P0221** | Speed Reference Source | 7 (Serial/Modbus) |
| **P0296** | Write Enable | 1 (Allow writes) |

## Quick Setup Procedure

### 1. Configure WEG Drive
```
P0312 = 9600        (Baud rate)
P0313 = 0           (No parity)
P0314 = 0           (1 stop bit)
P0315 = 6           (Address 6)
P0316 = 4           (Modbus RTU)
P0220 = 7           (Serial control)
P0221 = 7           (Serial speed ref)
P0296 = 1           (Enable writes)
```

### 2. Wire Connections
- **WEG RS485 A** → FT232 A/D+
- **WEG RS485 B** → FT232 B/D-
- **WEG GND** → FT232 GND

### 3. Gateway Configuration
Set these in the web interface to match your WEG:
- Baud Rate: 9600
- Parity: None
- Stop Bits: 1
- Slave ID: 6

### 4. Test Communication
1. Start the gateway
2. Send a test command from PLC/Controller
3. Check web interface logs for successful communication

## Troubleshooting

### No Communication
1. Check P0316 is set to 4 (Modbus RTU)
2. Verify P0315 matches gateway SLAVE_ID
3. Check serial parameters match exactly
4. Verify RS485 wiring (A to A, B to B)
5. Check for proper 120Ω termination resistors

### Commands Not Working
1. Set P0220 = 7 (Serial control source)
2. Set P0221 = 7 (Serial speed reference)
3. Set P0296 = 1 (Write enable)
4. Check for active fault codes (P0048)

### Reading Values
If you need to read drive status, use Modbus function code 03 (Read Holding Registers) on these:
- P0001 (State)
- P0002 (Frequency)
- P0003 (Current)

## References

- WEG CFW11 User Manual - Chapter 8 (Serial Communications)
- Modbus RTU Protocol Specification
- WEG Parameter Table (Complete list in manual)



