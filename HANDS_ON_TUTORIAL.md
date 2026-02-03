# 🛠️ Hands-On Tutorial: Learning by Doing

## Introduction

This tutorial will help you understand the system through **practical experiments**. You'll modify code, observe results, and build intuition about how everything works together.

**Prerequisites:**
- You've read the STUDY_GUIDE.md
- You've looked at SYSTEM_DIAGRAMS.md
- You have the system running (or can run it in test mode)

---

## Lab 1: Understanding the Translation Math

### Experiment 1A: Trace a Single Command

Let's trace what happens when the PLC sends `3000` for frequency.

**Step 1:** Add detailed logging to `vfdserver.py`

Find this code (around line 88):

```python
elif reg_address == 0x0002:
    freq_hz = val / 100.0
    val_weg = int((val / config['MAX_FREQ']) * 8192)
```

**Step 2:** Modify it to add more logging:

```python
elif reg_address == 0x0002:
    # Calculate Hz
    freq_hz = val / 100.0
    add_message('DEBUG', f"Step 1: Yaskawa value = {val}")
    add_message('DEBUG', f"Step 2: Frequency = {freq_hz:.2f} Hz")
    
    # Calculate percentage
    percentage = val / config['MAX_FREQ']
    add_message('DEBUG', f"Step 3: Percentage = {percentage:.4f} ({percentage*100:.2f}%)")
    
    # Calculate WEG value
    val_weg = int(percentage * 8192)
    add_message('DEBUG', f"Step 4: WEG value = {val_weg} (out of 8192)")
    
    # Original log
    add_message('COMMAND', f"Frequency: {freq_hz:.2f}Hz (raw: {val}) -> WEG value: {val_weg}")
    
    self._write_to_weg(683, val_weg, "FREQUENCY")
```

**Step 3:** Test it!

Create a test file `test_translation.py`:

```python
"""Test the translation logic without hardware"""
import vfdserver

# Create callback instance
callback = vfdserver.YaskawaCallback(0x0000, [0]*100)

# Simulate PLC writing different frequencies
test_values = [0, 1500, 3000, 4500, 6000]

for val in test_values:
    print(f"\n{'='*50}")
    print(f"Testing Yaskawa value: {val}")
    print('='*50)
    callback.setValues(0x0002, [val])
    print("\nMessages generated:")
    # Print last 5 messages
    for msg in vfdserver.recent_messages[-5:]:
        print(f"  [{msg['type']}] {msg['message']}")
```

**Step 4:** Run it:

```bash
python test_translation.py
```

**Expected Output:**

```
==================================================
Testing Yaskawa value: 3000
==================================================
  [DEBUG] Step 1: Yaskawa value = 3000
  [DEBUG] Step 2: Frequency = 30.00 Hz
  [DEBUG] Step 3: Percentage = 0.5000 (50.00%)
  [DEBUG] Step 4: WEG value = 4096 (out of 8192)
  [COMMAND] Frequency: 30.00Hz (raw: 3000) -> WEG value: 4096
```

**Questions to Answer:**

1. What WEG value do you get for Yaskawa `1500`?
2. What percentage is `4500` of `6000`?
3. If you change `MAX_FREQ` to `5000`, what happens to the WEG value for input `3000`?

---

### Experiment 1B: Reverse Engineering

**Task:** Write a function that converts WEG values back to Yaskawa values.

Add to `vfdserver.py`:

```python
def weg_to_yaskawa(weg_value):
    """
    Convert WEG speed reference back to Yaskawa format
    
    WEG: 0-8192 represents 0-100%
    Yaskawa: 0-6000 represents 0-60.00Hz
    
    Example:
        weg_to_yaskawa(4096) → 3000
        (4096/8192 = 0.5, 0.5 * 6000 = 3000)
    """
    percentage = weg_value / 8192
    yaskawa_value = int(percentage * config['MAX_FREQ'])
    return yaskawa_value

# Test it
def test_reverse_conversion():
    test_cases = [
        (0, 0),
        (2048, 1500),
        (4096, 3000),
        (6144, 4500),
        (8192, 6000),
    ]
    
    print("\nReverse Conversion Test:")
    print("WEG Value → Yaskawa Value (Expected)")
    print("-" * 40)
    
    for weg_val, expected in test_cases:
        result = weg_to_yaskawa(weg_val)
        status = "✓" if result == expected else "✗"
        print(f"{status} {weg_val:5d} → {result:5d} (expected {expected:5d})")
        
        # Also check round-trip
        freq_hz = result / 100.0
        val_weg_roundtrip = int((result / config['MAX_FREQ']) * 8192)
        print(f"   Round-trip: {result} → {val_weg_roundtrip} (diff: {abs(weg_val - val_weg_roundtrip)})")
```

**Run the test:**

```python
if __name__ == "__main__":
    test_reverse_conversion()
```

---

## Lab 2: Thread Safety Experiments

### Experiment 2A: See What Happens Without Locks

**⚠️ Warning:** This will break things temporarily - that's the point!

**Step 1:** Make a backup of `vfdserver.py`:

```bash
copy vfdserver.py vfdserver.py.backup
```

**Step 2:** Comment out the lock in `_write_to_weg`:

```python
def _write_to_weg(self, register, value, command_name):
    """Thread-safe write to WEG with error handling"""
    # with weg_lock:  ← COMMENTED OUT!
    try:
        if weg_client is None or not weg_client.connected:
            # ... rest of code
```

**Step 3:** Create a stress test:

`stress_test.py`:

```python
"""Stress test: Send many commands quickly"""
import threading
import time
import vfdserver

def send_commands(thread_id):
    """Simulate multiple PLC commands"""
    callback = vfdserver.YaskawaCallback(0x0000, [0]*100)
    
    for i in range(10):
        # Send frequency command
        freq_val = 1000 + (thread_id * 100) + (i * 10)
        callback.setValues(0x0002, [freq_val])
        time.sleep(0.05)  # 50ms between commands

# Start multiple threads
threads = []
for i in range(3):
    t = threading.Thread(target=send_commands, args=(i,))
    t.start()
    threads.append(t)

# Wait for all to finish
for t in threads:
    t.join()

print("\nCheck the logs for errors or weird behavior!")
```

**Step 4:** Run and observe:

```bash
python stress_test.py
```

**What to look for:**
- Error messages about serial port failures
- Corrupted data
- Messages being logged out of order
- Possible crashes

**Step 5:** Restore the lock:

```bash
copy vfdserver.py.backup vfdserver.py
```

**Step 6:** Run the stress test again with the lock restored.

**Questions:**

1. What errors did you see without the lock?
2. How did the lock fix it?
3. Is there any performance difference?

---

## Lab 3: Adding a New Register

### Experiment 3A: Add a "Motor Direction" Register

**Scenario:** The PLC wants to control motor direction using register `0x0003`:
- Value `0` = Forward
- Value `1` = Reverse

**Step 1:** Find the WEG register for direction

Look in the WEG manual (or these common registers):
- `P0685` - Logic direction (0=forward, 1=reverse)

**Step 2:** Add to `YaskawaCallback.setValues()`:

```python
# Add this after the frequency translation (around line 96)

# 3. TRANSLATE DIRECTION (Yaskawa Reg 0x0003)
elif reg_address == 0x0003:
    direction_text = "REVERSE" if val == 1 else "FORWARD"
    add_message('COMMAND', f"Direction command: {val} ({direction_text})")
    
    # WEG P0685: 0=Forward, 1=Reverse (same as Yaskawa!)
    self._write_to_weg(685, val, "DIRECTION")
```

**Step 3:** Test it:

```python
# In test_translation.py, add:
print("\n" + "="*50)
print("Testing Direction Commands")
print("="*50)

callback.setValues(0x0003, [0])  # Forward
time.sleep(0.5)
callback.setValues(0x0003, [1])  # Reverse
```

**Step 4:** Check the web interface logs to verify!

---

### Experiment 3B: Add Read Support

So far, we only WRITE to the WEG. Let's READ status back!

**Step 1:** Override `getValues` in `YaskawaCallback`:

```python
def getValues(self, address, count=1):
    """
    Called when PLC READS a register.
    We'll read from WEG and translate back.
    """
    reg_address = address
    
    # Example: Read motor speed from WEG
    if reg_address == 0x0100:  # New "status" register
        try:
            with weg_lock:
                if weg_client and weg_client.connected:
                    # Read actual speed from WEG P0681
                    result = weg_client.read_holding_registers(
                        681, 1, slave=config['SLAVE_ID']
                    )
                    
                    if not result.isError():
                        weg_speed = result.registers[0]
                        
                        # Translate WEG → Yaskawa
                        percentage = weg_speed / 8192
                        yaskawa_speed = int(percentage * config['MAX_FREQ'])
                        
                        add_message('INFO', 
                            f"Read speed: WEG={weg_speed} → Yaskawa={yaskawa_speed}")
                        
                        # Update our memory with this value
                        super().setValues(address, [yaskawa_speed])
                        
        except Exception as e:
            add_message('ERROR', f"Error reading from WEG: {e}")
    
    # Return value from memory
    return super().getValues(address, count)
```

**Step 2:** Test reading:

```python
# Test read
print("\nTesting READ from register 0x0100:")
result = callback.getValues(0x0100)
print(f"Result: {result}")
```

---

## Lab 4: Web Interface Experiments

### Experiment 4A: Add a Statistics Graph

Let's add a live graph showing command frequency.

**Step 1:** Add statistics tracking to `vfdserver.py`:

```python
# Add after recent_messages definition
command_stats = {
    'last_minute': [],  # List of (timestamp, frequency_hz)
    'max_freq': 0,
    'min_freq': 0,
    'avg_freq': 0,
}

# In YaskawaCallback.setValues(), for frequency:
elif reg_address == 0x0002:
    freq_hz = val / 100.0
    
    # Track statistics
    from datetime import datetime
    command_stats['last_minute'].append((datetime.now(), freq_hz))
    
    # Keep only last 60 seconds
    cutoff = datetime.now().timestamp() - 60
    command_stats['last_minute'] = [
        (ts, freq) for ts, freq in command_stats['last_minute']
        if ts.timestamp() > cutoff
    ]
    
    # Calculate stats
    if command_stats['last_minute']:
        freqs = [f for _, f in command_stats['last_minute']]
        command_stats['max_freq'] = max(freqs)
        command_stats['min_freq'] = min(freqs)
        command_stats['avg_freq'] = sum(freqs) / len(freqs)
    
    # ... rest of code
```

**Step 2:** Add API endpoint in `webserver.py`:

```python
@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get command statistics"""
    return jsonify({
        'success': True,
        'stats': vfdserver.command_stats
    })
```

**Step 3:** Update `index.html` to display:

Add to the stats section:

```html
<div class="stat-card">
    <div class="stat-value" id="avgFreq">0.0</div>
    <div class="stat-label">Avg Frequency (Hz)</div>
</div>
```

Add JavaScript to fetch:

```javascript
// Poll statistics
setInterval(async () => {
    const response = await fetch('/api/stats');
    const data = await response.json();
    if (data.success) {
        document.getElementById('avgFreq').textContent = 
            data.stats.avg_freq.toFixed(2);
    }
}, 2000);
```

---

### Experiment 4B: Add a "Test Command" Button

Add a button to send test commands without needing a PLC!

**Step 1:** Add API endpoint:

```python
@app.route('/api/test/frequency', methods=['POST'])
def test_frequency():
    """Send a test frequency command"""
    try:
        data = request.json
        freq_hz = float(data.get('frequency', 30.0))
        
        # Convert Hz to Yaskawa value
        yaskawa_val = int(freq_hz * 100)
        
        # Simulate PLC write
        if vfdserver.server_thread and vfdserver.server_running:
            # Get the datastore and write to it
            # This will trigger YaskawaCallback.setValues()
            add_message('INFO', f'Test command: {freq_hz} Hz')
            
            return jsonify({
                'success': True,
                'message': f'Sent test command: {freq_hz} Hz'
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Server not running'
            })
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        })
```

**Step 2:** Add button in HTML:

```html
<div class="card">
    <h2>🧪 Test Commands</h2>
    <div class="form-group">
        <label for="testFreq">Test Frequency (Hz):</label>
        <input type="number" id="testFreq" value="30.0" step="0.1" min="0" max="60">
    </div>
    <button onclick="sendTestCommand()" class="btn-primary">
        Send Test Command
    </button>
</div>

<script>
async function sendTestCommand() {
    const freq = parseFloat(document.getElementById('testFreq').value);
    
    const response = await fetch('/api/test/frequency', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ frequency: freq })
    });
    
    const data = await response.json();
    showNotification(data.message, data.success ? 'success' : 'error');
}
</script>
```

Now you can test without a PLC!

---

## Lab 5: Debugging Techniques

### Experiment 5A: Packet Sniffer

Let's see the actual Modbus frames being sent!

**Create `modbus_sniffer.py`:**

```python
"""Sniff Modbus RTU traffic on serial port"""
import serial
import sys

def parse_modbus_frame(data):
    """Parse and display Modbus RTU frame"""
    if len(data) < 4:
        return "Frame too short"
    
    slave_id = data[0]
    function = data[1]
    
    functions = {
        0x03: "Read Holding Registers",
        0x06: "Write Single Register",
        0x10: "Write Multiple Registers",
    }
    
    func_name = functions.get(function, f"Unknown (0x{function:02X})")
    
    if function == 0x06 and len(data) >= 6:
        reg_addr = (data[2] << 8) | data[3]
        value = (data[4] << 8) | data[5]
        return f"Slave {slave_id}: {func_name} - Reg {reg_addr} = {value}"
    
    return f"Slave {slave_id}: {func_name}"

def sniff_port(port, baudrate=9600):
    """Sniff traffic on a serial port"""
    print(f"Sniffing on {port} at {baudrate} baud...")
    print("Press Ctrl+C to stop\n")
    
    ser = serial.Serial(port, baudrate, timeout=0.1)
    buffer = []
    
    try:
        while True:
            # Read available bytes
            if ser.in_waiting:
                byte = ser.read(1)
                buffer.append(byte[0])
                
                # Look for frame end (timeout or CRC)
                if len(buffer) >= 8:
                    frame = bytes(buffer)
                    print(f"[{len(buffer)} bytes] {frame.hex(' ')}")
                    print(f"  → {parse_modbus_frame(buffer)}\n")
                    buffer = []
            
            # Timeout - assume frame ended
            elif buffer:
                frame = bytes(buffer)
                print(f"[{len(buffer)} bytes] {frame.hex(' ')}")
                print(f"  → {parse_modbus_frame(buffer)}\n")
                buffer = []
                
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        ser.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python modbus_sniffer.py COM4")
        sys.exit(1)
    
    port = sys.argv[1]
    sniff_port(port)
```

**Usage:**

```bash
# Sniff traffic to WEG drive
python modbus_sniffer.py COM4
```

Then send commands and watch the actual bytes!

---

### Experiment 5B: Simulated WEG Drive

Test your gateway without real hardware!

**Create `fake_weg.py`:**

```python
"""Simulated WEG CFW11 drive for testing"""
from pymodbus.server import StartSerialServer
from pymodbus.datastore import ModbusSlaveContext, ModbusServerContext
from pymodbus.datastore import ModbusSequentialDataBlock

class WEGSimulator(ModbusSequentialDataBlock):
    """Simulates WEG CFW11 behavior"""
    
    def __init__(self):
        # Initialize with zeros
        super().__init__(0x0000, [0]*1000)
        
        # Set some default values
        self.setValues(312, [9600])   # P0312: Baud rate
        self.setValues(313, [0])      # P0313: Parity (None)
        self.setValues(315, [6])      # P0315: Slave ID
        
        # Motor parameters
        self.motor_running = False
        self.current_speed = 0
    
    def setValues(self, address, values):
        """Handle writes to WEG parameters"""
        super().setValues(address, values)
        
        val = values[0] if values else 0
        
        # P0682: Run/Stop
        if address == 682:
            self.motor_running = (val & 0x01) != 0
            status = "RUNNING" if self.motor_running else "STOPPED"
            print(f"[WEG] Motor command: {status} (value: {val:#04x})")
        
        # P0683: Speed reference
        elif address == 683:
            self.current_speed = val
            percentage = (val / 8192) * 100
            print(f"[WEG] Speed set to: {val} ({percentage:.1f}%)")
            
            # Simulate: Update actual speed (P0681)
            self.setValues(681, [val])
        
        # P0685: Direction
        elif address == 685:
            direction = "REVERSE" if val == 1 else "FORWARD"
            print(f"[WEG] Direction: {direction}")

def run_simulator(port='COM4', baudrate=9600):
    """Run the WEG simulator"""
    print("="*50)
    print("WEG CFW11 Simulator")
    print("="*50)
    print(f"Port: {port}")
    print(f"Baud: {baudrate}")
    print(f"Slave ID: 6")
    print("\nListening for commands...\n")
    
    # Create datastore
    store = ModbusSlaveContext(
        hr=WEGSimulator(),
        zero_mode=True
    )
    context = ModbusServerContext(slaves=store, single=True)
    
    # Start server
    StartSerialServer(
        context=context,
        port=port,
        baudrate=baudrate,
        parity='N',
        stopbits=1,
        bytesize=8,
        framer='rtu'
    )

if __name__ == "__main__":
    import sys
    port = sys.argv[1] if len(sys.argv) > 1 else 'COM4'
    run_simulator(port)
```

**Usage:**

1. Run the simulator: `python fake_weg.py COM4`
2. Run your gateway: `python webserver.py`
3. Send commands and watch both console outputs!

---

## Lab 6: Performance Testing

### Experiment 6A: Measure Response Time

How fast can the gateway translate commands?

**Create `benchmark.py`:**

```python
"""Benchmark the gateway performance"""
import time
import vfdserver

def benchmark_translation(iterations=1000):
    """Measure translation speed"""
    callback = vfdserver.YaskawaCallback(0x0000, [0]*100)
    
    # Disable WEG writing for pure translation test
    original_write = callback._write_to_weg
    callback._write_to_weg = lambda r, v, n: None
    
    print(f"Running {iterations} translations...")
    
    start = time.time()
    
    for i in range(iterations):
        # Alternate between commands
        callback.setValues(0x0001, [1])  # Run
        callback.setValues(0x0002, [3000 + i % 1000])  # Frequency
    
    elapsed = time.time() - start
    
    callback._write_to_weg = original_write
    
    print(f"\nResults:")
    print(f"  Total time: {elapsed:.3f} seconds")
    print(f"  Commands/second: {(iterations * 2) / elapsed:.0f}")
    print(f"  Average latency: {(elapsed / (iterations * 2)) * 1000:.3f} ms")

if __name__ == "__main__":
    benchmark_translation()
```

**Run it:**

```bash
python benchmark.py
```

**Questions:**

1. How many commands per second can it handle?
2. Is this fast enough for your application?
3. What's the bottleneck? (Translation logic vs. serial communication)

---

## Lab 7: Error Handling

### Experiment 7A: Simulate Failures

**Create `error_test.py`:**

```python
"""Test error handling"""
import vfdserver

# Test 1: Invalid register
print("Test 1: Writing to unexpected register")
callback = vfdserver.YaskawaCallback(0x0000, [0]*100)
callback.setValues(0x9999, [12345])  # Random register
print("→ Should just log it\n")

# Test 2: Out of range frequency
print("Test 2: Frequency beyond max")
callback.setValues(0x0002, [10000])  # Way over 6000!
print("→ What happens? Check logs\n")

# Test 3: Negative value (wraps in unsigned int)
print("Test 3: 'Negative' value")
callback.setValues(0x0002, [-100])  # Actually large positive in unsigned!
print("→ Interesting behavior\n")

print("\nCheck recent_messages for results:")
for msg in vfdserver.recent_messages[-10:]:
    print(f"[{msg['type']}] {msg['message']}")
```

**Add validation to prevent issues:**

In `vfdserver.py`, add to frequency translation:

```python
elif reg_address == 0x0002:
    # Validate input
    if val < 0:
        add_message('ERROR', f'Invalid frequency: {val} (negative not allowed)')
        return
    
    if val > config['MAX_FREQ']:
        add_message('WARNING', 
            f'Frequency {val} exceeds MAX_FREQ {config["MAX_FREQ"]}, capping')
        val = config['MAX_FREQ']
    
    # ... rest of translation
```

---

## Challenge Projects

### Challenge 1: Add Acceleration Ramping

**Goal:** Smoothly ramp frequency changes instead of instant jumps.

**Hints:**
- Create a background thread that gradually changes frequency
- Store target frequency vs. current frequency
- Update every 100ms

### Challenge 2: Create a Dashboard

**Goal:** Build a visual dashboard showing:
- Current motor speed (gauge)
- Command history (graph)
- Error log (table)
- System status (indicators)

**Technologies:** Use Chart.js or similar library

### Challenge 3: Add Data Logging to CSV

**Goal:** Log all commands to a file for later analysis.

**Format:**
```csv
timestamp,register,value_yaskawa,value_weg,status
2026-02-01 10:30:00.123,0x0002,3000,4096,SUCCESS
```

### Challenge 4: Implement Modbus TCP

**Goal:** Instead of serial, use Modbus TCP/IP.

**Hints:**
- Use `ModbusTcpServer` instead of `StartSerialServer`
- Use `ModbusTcpClient` for WEG connection
- Test on localhost first (127.0.0.1)

---

## Debugging Checklist

When something doesn't work:

### 1. Check Serial Ports

```python
# List available ports
import serial.tools.list_ports
ports = serial.tools.list_ports.comports()
for port in ports:
    print(f"{port.device}: {port.description}")
```

### 2. Verify Configuration

```python
# Print effective config
print(vfdserver.config)
```

### 3. Check Connections

```python
# Test WEG connection
if vfdserver.weg_client:
    print(f"WEG connected: {vfdserver.weg_client.connected}")
else:
    print("WEG client not initialized")
```

### 4. Monitor Logs

Watch the web interface real-time log for errors.

### 5. Check Thread Status

```python
# Are threads running?
print(f"Server thread alive: {vfdserver.server_thread.is_alive() if vfdserver.server_thread else False}")
print(f"Server running flag: {vfdserver.server_running}")
```

---

## Learning Path Summary

You've now:

1. ✅ Understood the translation math
2. ✅ Seen thread safety in action
3. ✅ Added new register mappings
4. ✅ Extended the web interface
5. ✅ Used debugging tools
6. ✅ Tested error handling
7. ✅ Measured performance

## Next Steps

1. **Read the actual WEG manual** - understand all available parameters
2. **Study Modbus protocol in depth** - read the official spec
3. **Learn about PLC programming** - understand the other side
4. **Explore industrial protocols** - Profibus, EtherCAT, etc.
5. **Build your own project** - apply these concepts elsewhere!

---

## Resources

### Python Libraries
- **pymodbus**: Modbus protocol implementation
- **pyserial**: Serial port communication
- **Flask**: Web framework
- **Flask-SocketIO**: WebSocket support

### Documentation
- Modbus Protocol Specification: https://modbus.org/specs.php
- WEG CFW11 Manual: (check your PDF)
- Python Threading: https://docs.python.org/3/library/threading.html

### Tools
- **Serial Port Monitor**: Windows apps to monitor COM ports
- **Modbus Poll**: Test tool for Modbus (paid)
- **QModMaster**: Free Modbus testing tool

---

## Final Words

Remember: **The best way to learn is by breaking things!**

Don't be afraid to:
- Modify the code
- Try extreme values
- Introduce bugs intentionally
- Read error messages carefully
- Fix things yourself

Every error is a learning opportunity. 

**Happy coding! 🚀**


