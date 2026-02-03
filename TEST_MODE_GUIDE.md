# 🧪 Test Mode Guide - Direct WEG Control

## What is Test Mode?

Test Mode lets you send **direct Modbus commands** to your WEG drive from the web interface, bypassing the normal gateway translation. Perfect for:

- ✅ Testing WEG connectivity
- ✅ Learning Modbus commands
- ✅ Debugging issues
- ✅ Manual motor control
- ✅ Experimenting with parameters

---

## ⚠️ Important Warning

**Test Mode sends commands DIRECTLY to the WEG drive!**

- Commands bypass the gateway translation logic
- Motor will respond immediately
- Use caution with motor running
- Have emergency stop ready

---

## 🚀 How to Use Test Mode

### 1. Start the System

```bash
python webserver.py
```

Open browser: `http://localhost:5000`

### 2. Scroll to Test Mode Panel

Look for the "🧪 Test Mode - Direct WEG Commands" section at the bottom of the page.

---

## 🎮 Quick Commands

### Start/Stop Motor

**▶️ Start Motor** - Writes `1` to P0682 (Control Word)
- Sets bit 0 = run
- Motor starts at current frequency setpoint

**⏹️ Stop Motor** - Writes `0` to P0682
- Clears bit 0 = stop
- Motor decelerates to stop

### Set Frequency

**Set 15 Hz** - Writes `2048` to P0683 (Speed Reference)
- 2048 = 25% of 8192
- Approximately 15 Hz if max is 60 Hz

**Set 30 Hz** - Writes `4096` to P0683
- 4096 = 50% of 8192
- Approximately 30 Hz

**Set 45 Hz** - Writes `6144` to P0683
- 6144 = 75% of 8192
- Approximately 45 Hz

### Direction Control

**Forward** - Writes `0` to P0685 (Direction)
**Reverse** - Writes `1` to P0685

### Read Commands

**📖 Read Actual Speed (P0681)** - Reads current motor speed
- Returns 0-8192 (0-100% of max)

**📖 Read Control Word (P0682)** - Reads control status
- Bit 0 = run/stop state

**📖 Read Speed Ref (P0683)** - Reads speed setpoint
- Current frequency reference

---

## 🔧 Custom Command

Send any register/value combination:

### To Write:
1. Enter **Register (P-number)**: e.g., `683`
2. Enter **Value**: e.g., `4096`
3. Click **📤 Send Custom**

### To Read:
1. Enter **Register (P-number)**: e.g., `681`
2. Click **📥 Read Custom Register**

### Common Registers:

| Register | Function | Write Values | Read Values |
|----------|----------|--------------|-------------|
| P0682 (682) | Control Word | 0=Stop, 1=Run | Current state |
| P0683 (683) | Speed Reference | 0-8192 (0-100%) | Setpoint |
| P0685 (685) | Direction | 0=Fwd, 1=Rev | Current dir |
| P0681 (681) | Actual Speed | (read only) | 0-8192 |
| P0312 (312) | Baud Rate | 9600, 19200, etc | Current baud |
| P0315 (315) | Slave ID | 1-247 | Current ID |

---

## 🧮 Frequency Calculator

### Interactive Hz to WEG Value Conversion

1. Enter **Desired Frequency (Hz)**: e.g., `37.5`
2. **WEG Value** auto-calculates: e.g., `5120`
3. Click **Send** to apply

### How It Works:

```
Formula: WEG_Value = (Hz × 100 / 6000) × 8192

Example: 37.5 Hz
  = (37.5 × 100 / 6000) × 8192
  = (3750 / 6000) × 8192
  = 0.625 × 8192
  = 5120
```

### Quick Reference:

| Hz | WEG Value | Percentage |
|----|-----------|------------|
| 0 | 0 | 0% |
| 15 | 2048 | 25% |
| 30 | 4096 | 50% |
| 45 | 6144 | 75% |
| 60 | 8192 | 100% |

---

## 📊 Understanding Responses

### Success Response (Green)

```
[10:30:15 AM] Successfully wrote 4096 to P0683
```

Means:
- ✅ Modbus command sent successfully
- ✅ WEG acknowledged the write
- ✅ Value has been set

### Error Response (Red)

```
[10:30:15 AM] Modbus error: Illegal address
```

Common errors:
- **Illegal address**: Register doesn't exist
- **Illegal value**: Value out of range for that register
- **Gateway not connected**: WEG client not connected (check wiring)
- **Timeout**: No response from WEG (check slave ID, baud rate)

---

## 🎯 Common Test Scenarios

### Scenario 1: First-Time Connection Test

**Goal:** Verify you can talk to the WEG

1. Click **📖 Read Actual Speed (P0681)**
2. **Success?** Connection is working!
3. **Error?** Check:
   - WEG powered on
   - Wiring (A-to-A, B-to-B)
   - Slave ID matches (P0315)
   - Baud rate matches (P0312)

### Scenario 2: Basic Motor Operation

**Goal:** Start motor at specific speed

1. Enter `25.0` in Frequency Calculator
2. Click **Send** (sets to 25 Hz)
3. Click **▶️ Start Motor**
4. Motor should start and run at 25 Hz
5. Click **⏹️ Stop Motor** when done

### Scenario 3: Test Direction Change

**Goal:** Change motor direction

1. Click **⏹️ Stop Motor** (must be stopped first!)
2. Click **Direction: Reverse**
3. Click **▶️ Start Motor**
4. Motor runs in reverse
5. Stop, change back to Forward, restart

### Scenario 4: Speed Ramping

**Goal:** Gradually increase speed

1. Click **Set 15 Hz**
2. Click **▶️ Start Motor**
3. Wait 3 seconds
4. Click **Set 30 Hz**
5. Wait 3 seconds
6. Click **Set 45 Hz**
7. Observe motor accelerating

### Scenario 5: Read All Status

**Goal:** Get complete motor status

1. Click **📖 Read Control Word** - Check if running
2. Click **📖 Read Speed Ref** - Check setpoint
3. Click **📖 Read Actual Speed** - Check actual speed

Compare setpoint vs actual to verify motor is following commands.

---

## 🐛 Troubleshooting

### Issue: "WEG client not connected"

**Solutions:**
1. Check Configuration section - is COM4 correct?
2. Click **Start Server** button
3. Check terminals/wiring
4. Verify WEG is powered on

### Issue: "Modbus error: Gateway not connected"

**Check:**
- [ ] WEG drive powered on
- [ ] RS-485 wiring correct (A-to-A, B-to-B, GND-to-GND)
- [ ] Termination resistor installed (120Ω)
- [ ] Slave ID matches: Config Slave ID = WEG P0315
- [ ] Baud rate matches: Config = WEG P0312

### Issue: "Illegal address" Error

**Cause:** Register doesn't exist or isn't accessible

**Check:**
- Parameter number is valid (0000-9999)
- Parameter is accessible via Modbus (check WEG manual)
- Using correct function code (write=6, read=3)

### Issue: Motor Doesn't Respond

**Check:**
1. WEG in remote mode: P0220 = 2 or 3
2. No faults on WEG display
3. Emergency stop not pressed
4. Frequency > 0 (motor won't start at 0 Hz)
5. Control word bit 0 set (P0682 = 1)

---

## 💡 Pro Tips

### 1. Use Test Mode for Learning

Before building your application, use test mode to:
- Understand how each register works
- See actual Modbus frames in real-time log
- Learn correct values for your application

### 2. Monitor the Log

The real-time log shows every command:
```
[SUCCESS] Test write: P0683 = 4096
```

Watch for:
- Command confirmation
- Error messages
- Response timing

### 3. Save Working Commands

When you find a command that works, note:
- Register number
- Value
- Expected behavior

Use these in your application code.

### 4. Test Incrementally

Don't change multiple things at once:
1. ✅ Test one command
2. ✅ Verify it works
3. ✅ Move to next command

### 5. Safety First

Always have:
- Emergency stop button ready
- Motor uncoupled from load (for testing)
- Clear area around motor
- Knowledge of how to stop motor

---

## 📝 Example Testing Session

### Complete Workflow

```
1. [10:00:00] Click "Read Actual Speed"
   Response: P0681 = 0 (motor stopped)

2. [10:00:05] Enter 30.0 Hz in calculator
   WEG Value: 4096 (calculated automatically)

3. [10:00:08] Click "Send" (from calculator)
   Response: Successfully wrote 4096 to P0683

4. [10:00:12] Click "Start Motor"
   Response: Successfully wrote 1 to P0682
   (Motor starts running!)

5. [10:00:30] Click "Read Actual Speed"
   Response: P0681 = 4096 (running at setpoint)

6. [10:01:00] Enter 45.0 Hz in calculator
   WEG Value: 6144

7. [10:01:03] Click "Send"
   Response: Successfully wrote 6144 to P0683
   (Motor accelerates to 45 Hz)

8. [10:01:30] Click "Stop Motor"
   Response: Successfully wrote 0 to P0682
   (Motor decelerates to stop)

9. [10:01:45] Click "Read Actual Speed"
   Response: P0681 = 0 (confirmed stopped)
```

---

## 🎓 Learning Exercises

### Exercise 1: Find Your Motor's Speed

1. Start motor at 30 Hz
2. Use multimeter or tachometer
3. Measure actual RPM
4. Calculate: RPM = (Hz × 60) / (poles / 2)
5. Compare calculated vs measured

### Exercise 2: Test Acceleration Time

1. Set motor to 15 Hz
2. Start motor
3. Change to 45 Hz
4. Time how long it takes
5. Compare to WEG P0100 (accel time parameter)

### Exercise 3: Map All Parameters

1. Try reading P0100, P0101, P0102...
2. Note which ones work
3. Note which give "illegal address"
4. Build your own parameter list

### Exercise 4: Calculate Custom Frequencies

Use calculator to find WEG values for:
- 12.5 Hz → ?
- 22.3 Hz → ?
- 48.7 Hz → ?
- 55.0 Hz → ?

Verify by sending and reading back.

---

## 🔒 Safety Notes

### Before Testing:

- [ ] Motor uncoupled from machinery
- [ ] Emergency stop accessible
- [ ] Clear area around motor
- [ ] Know how to stop immediately
- [ ] WEG parameters configured safely

### Never:

- ❌ Test with motor under load (first time)
- ❌ Exceed motor nameplate ratings
- ❌ Run motor without cooling (if required)
- ❌ Leave motor running unattended (testing)
- ❌ Touch rotating parts

### Always:

- ✅ Use emergency stop when needed
- ✅ Monitor motor temperature
- ✅ Stop immediately if something sounds wrong
- ✅ Follow motor manufacturer's guidelines
- ✅ Have qualified person present

---

## 📚 Related Documents

- **README.md** - System overview
- **QUICK_REFERENCE.md** - Register reference
- **WEG_CONFIG_NOTES.md** - WEG parameter details
- **MODBUS_PLC_GUIDE.md** - Modbus protocol details

---

## 🎯 Summary

**Test Mode gives you:**
- ✅ Direct control over WEG parameters
- ✅ Real-time command testing
- ✅ Learning tool for Modbus
- ✅ Debugging capability
- ✅ Calculator for frequency conversion

**Perfect for:**
- Initial setup and testing
- Learning how the system works
- Debugging connection issues
- Experimenting safely

**Remember:**
- Commands go directly to WEG (bypass gateway)
- Motor responds immediately
- Monitor real-time log for feedback
- Use responsibly!

---

**Happy testing! 🚀**


