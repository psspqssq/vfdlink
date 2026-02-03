# 📡 Serial Communication Parameters Guide

## Why Serial Parameters Matter

**ALL devices on the same RS-485 bus MUST have identical settings!**

If even ONE parameter is different between devices, communication will fail.

---

## 🔧 The 5 Critical Parameters

### 1. Baud Rate (Speed)

**What it is:** Bits per second transmitted

**Common values:**
- 9600 (most common, default)
- 19200 (2× faster)
- 38400 (4× faster)

**WEG Parameter:** P0312

**Rule:** Lower is more reliable, higher is faster

**Tip:** Start with 9600, only increase if you need faster response

---

### 2. Parity (Error Detection) ⭐ **IMPORTANT**

**What it is:** Extra bit added for error checking

**Options:**
- **None (N)** - No error checking (most common)
- **Even (E)** - Even parity bit
- **Odd (O)** - Odd parity bit

**WEG Parameter:** P0313
- 0 = None
- 1 = Even
- 2 = Odd

**Default:** None (most reliable)

#### How Parity Works

```
Example with data byte: 10110101

Even Parity:
  Count 1's: 5 (odd number)
  Add parity bit: 1 (to make total even)
  Sent: 10110101 + 1

Odd Parity:
  Count 1's: 5 (odd number)
  Add parity bit: 0 (to keep total odd)
  Sent: 10110101 + 0

None:
  No parity bit added
  Sent: 10110101
```

**Why None is Common:**
- Modbus RTU has CRC error checking (better than parity)
- Parity bit = wasted bandwidth
- One less thing to configure wrong

**When to Use Even/Odd:**
- Legacy systems that require it
- Extra noisy environments
- Specific device requirements

---

### 3. Stop Bits (Frame End Marker)

**What it is:** Bits marking end of each byte

**Options:**
- **1** - Standard (most common)
- **2** - Extra stop bit (slower but more reliable)

**WEG Parameter:** P0314
- 0 = 1 stop bit
- 1 = 2 stop bits

**Default:** 1 stop bit

**When to use 2:**
- Very noisy environment
- Long cable runs (>500m)
- Older equipment that requires it

---

### 4. Data Bits (Byte Size)

**What it is:** Number of bits per character

**Options:**
- **7** - ASCII text only (rare in Modbus)
- **8** - Binary data (standard for Modbus)

**Default:** 8 bits

**Rule:** Always use 8 for Modbus RTU

---

### 5. Slave ID (Device Address)

**What it is:** Unique identifier for each device on the bus

**Range:** 1-247

**WEG Parameter:** P0315

**Common values:**
- 1 (default WEG)
- 6 (common for VFDs)

**Rule:** Each device needs a unique ID!

---

## 📊 Common Configurations

### Standard Modbus RTU (Recommended)

```
Baud Rate:  9600
Parity:     None (N)
Stop Bits:  1
Data Bits:  8
```

**Notation:** `9600,8,N,1` or `9600 8N1`

**WEG Settings:**
```
P0312 = 9600
P0313 = 0 (None)
P0314 = 0 (1 bit)
```

---

### High Speed Configuration

```
Baud Rate:  38400
Parity:     None (N)
Stop Bits:  1
Data Bits:  8
```

**Notation:** `38400 8N1`

**Use when:** Need faster response, short cables

---

### Legacy/Noisy Environment

```
Baud Rate:  9600
Parity:     Even (E)
Stop Bits:  2
Data Bits:  8
```

**Notation:** `9600 8E2`

**Use when:** 
- Old equipment requires it
- Electrical interference
- Long cable runs

---

## ⚠️ Configuration Mistakes

### Mistake 1: Parity Mismatch ❌

```
PLC Settings:    9600 8N1
WEG Settings:    9600 8E1  ← Different parity!
Result: No communication!
```

**Symptom:** Timeout errors, no response

**Fix:** Make parity match on all devices

---

### Mistake 2: Baud Rate Mismatch ❌

```
PLC:    19200 baud
WEG:    9600 baud   ← Different speed!
Result: Garbage data or no communication
```

**Symptom:** CRC errors, random failures

**Fix:** Set same baud rate everywhere

---

### Mistake 3: Wrong Data Bits ❌

```
Settings:   9600 7N1  ← 7 data bits
Modbus RTU needs: 8 data bits
Result: Data corruption
```

**Symptom:** Values are wrong, CRC errors

**Fix:** Always use 8 data bits for Modbus

---

## 🔍 How to Verify Settings

### On WEG CFW11:

Press `P` button on keypad:

```
P0312 → Shows baud rate (9600, 19200, etc.)
P0313 → Shows parity (0=None, 1=Even, 2=Odd)
P0314 → Shows stop bits (0=1 bit, 1=2 bits)
P0315 → Shows slave ID (1-247)
```

### In Web Interface:

1. Open `http://localhost:5000`
2. Check Configuration section:
   - Baud Rate: dropdown
   - Parity: dropdown
   - Stop Bits: dropdown
   - Data Bits: dropdown
   - Slave ID: input field

### In Click PLC:

Setup → Serial Ports → Port 2/3:
- Check all parameters match

---

## 🧪 Testing Configuration

### Test 1: Read a Register

Use Test Mode to read P0681 (actual speed):

**Success:** You get a value (e.g., "P0681 = 0")
→ Configuration is correct! ✅

**Failure:** Timeout or error
→ Check settings ❌

### Test 2: Send CRC-sensitive Command

Write to P0683:

**Success:** Motor speed changes
→ CRC is working (parity correct) ✅

**Failure:** CRC errors
→ Parity or baud rate mismatch ❌

---

## 📐 Frame Format Examples

### With No Parity (8N1)

```
┌───────┬────────┬────────┬────────┬─────────┐
│ Start │ Data   │ Data   │ Stop   │ Idle    │
│ Bit   │ (8bits)│ (8bits)│ Bit    │         │
└───────┴────────┴────────┴────────┴─────────┘
  1 bit   8 bits   8 bits   1 bit
  
Total: 11 bits per byte
At 9600 baud: 1.146 ms per byte
```

### With Even Parity (8E1)

```
┌───────┬────────┬────────┬────────┬────────┬─────────┐
│ Start │ Data   │ Data   │ Parity │ Stop   │ Idle    │
│ Bit   │ (8bits)│ (8bits)│ Bit    │ Bit    │         │
└───────┴────────┴────────┴────────┴────────┴─────────┘
  1 bit   8 bits   8 bits   1 bit    1 bit
  
Total: 12 bits per byte
At 9600 baud: 1.250 ms per byte (slower!)
```

---

## 💡 Best Practices

### 1. Use Standard Settings

**Default:** `9600 8N1`

Most compatible, most reliable, easiest to troubleshoot

### 2. Document Your Settings

Write down what you use:
```
System: WEG Drive Control
Baud: 9600
Parity: None
Stop: 1
Data: 8
Slave ID: 6
Date: ________
```

### 3. Set Everything Before Connecting

**Wrong order:**
1. Connect cables
2. Try to communicate
3. Fiddle with settings while troubleshooting ❌

**Right order:**
1. Set WEG parameters (P0312-P0315)
2. Set gateway/PLC parameters
3. Verify all match
4. Connect cables
5. Test communication ✅

### 4. When in Doubt, Use Default

Most Modbus devices default to `9600 8N1`

### 5. Higher Baud = More Noise Sensitive

```
9600:   Works up to 1000m cable
19200:  Works up to 500m cable
38400:  Works up to 200m cable
```

---

## 🔧 Troubleshooting by Symptom

### Symptom: "Timeout" Errors

**Possible causes:**
- [ ] Baud rate mismatch
- [ ] Wrong slave ID
- [ ] Cable not connected
- [ ] Wrong COM port

**Test:** Try reading a register in Test Mode

---

### Symptom: "CRC Error"

**Possible causes:**
- [ ] Parity mismatch (most common!)
- [ ] Stop bits mismatch
- [ ] Electrical noise
- [ ] Cable too long

**Test:** Change parity setting, try again

---

### Symptom: Random Failures

**Possible causes:**
- [ ] Intermittent connection
- [ ] Baud rate too high for cable length
- [ ] Missing termination resistor
- [ ] Electrical interference

**Test:** Lower baud rate, check cables

---

### Symptom: Wrong Values

**Possible causes:**
- [ ] Wrong data bits (7 instead of 8)
- [ ] Byte order issues (unrelated to serial params)

**Test:** Verify 8 data bits everywhere

---

## 📊 Quick Reference Table

| Parameter | Default | Common Alt | WEG Param | PLC Setting |
|-----------|---------|------------|-----------|-------------|
| **Baud Rate** | 9600 | 19200, 38400 | P0312 | Port config |
| **Parity** | None | Even | P0313 (0) | Port config |
| **Stop Bits** | 1 | 2 | P0314 (0) | Port config |
| **Data Bits** | 8 | - | - | Port config |
| **Slave ID** | 6 | 1 | P0315 | Per command |

---

## 🎯 Configuration Checklist

### Before Starting:

- [ ] Know what baud rate to use (usually 9600)
- [ ] Know what parity to use (usually None)
- [ ] Know what slave ID WEG has (check P0315)
- [ ] Have WEG manual handy

### On WEG:

- [ ] Set P0312 (baud rate)
- [ ] Set P0313 (parity: 0=None, 1=Even, 2=Odd)
- [ ] Set P0314 (stop bits: 0=1, 1=2)
- [ ] Set P0315 (slave ID: 6 recommended)
- [ ] Set P0316 (protocol: 4=Modbus RTU)
- [ ] Write down these values!

### In Gateway/PLC:

- [ ] Set baud rate (match WEG P0312)
- [ ] Set parity (match WEG P0313)
- [ ] Set stop bits (match WEG P0314)
- [ ] Set data bits (8)
- [ ] Set slave ID (match WEG P0315)
- [ ] Save configuration

### Test:

- [ ] Try reading a register (Test Mode)
- [ ] Try writing a value
- [ ] Verify motor responds
- [ ] No CRC errors in log

---

## 🚀 Summary

### The 3 Rules:

1. **ALL devices must match** - Every parameter, no exceptions
2. **Use standard settings** - `9600 8N1` unless you have a reason not to
3. **Test before assuming** - Use Test Mode to verify

### The Notation:

**9600 8N1** means:
- **9600** - Baud rate
- **8** - Data bits
- **N** - No parity
- **1** - 1 stop bit

### Most Common Config:

```
Baud Rate:  9600
Parity:     None (N)
Stop Bits:  1
Data Bits:  8

In short: 9600 8N1
```

This works 95% of the time!

---

## 📚 Related Documents

- **QUICK_REFERENCE.md** - Serial settings table
- **WEG_CONFIG_NOTES.md** - WEG-specific parameters
- **CLICK_PLC_IMPLEMENTATION.md** - Click PLC port setup
- **MODBUS_PLC_GUIDE.md** - Modbus protocol details

---

**Match your settings and you'll have reliable communication! 🎉**


