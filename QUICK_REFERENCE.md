# 📖 Quick Reference Guide

A condensed reference for quick lookups while working with the system.

---

## Common Commands

### Start the System

```bash
# Start web interface (recommended)
python webserver.py

# Start gateway only (no web interface)
python vfdserver.py
```

### Access Web Interface

```
http://localhost:5000
```

---

## Key File Overview

| File | Purpose | Key Components |
|------|---------|----------------|
| `vfdserver.py` | Gateway core | `YaskawaCallback`, `init_weg_client()`, `run_gateway()` |
| `webserver.py` | Web interface | Flask routes, SocketIO, broadcast thread |
| `templates/index.html` | UI | Configuration form, real-time log, controls |
| `requirements.txt` | Dependencies | Python packages needed |

---

## Configuration Reference

### Serial Parameters

| Parameter | Default | Options | WEG Parameter |
|-----------|---------|---------|---------------|
| PORT_CONTROLADOR | COM3 | Any COM port | - |
| PORT_WEG | COM4 | Any COM port | - |
| BAUD_RATE | 9600 | 1200-115200 | P0312 |
| PARITY | 'N' | 'N', 'E', 'O' | P0313 |
| STOPBITS | 1 | 1, 2 | P0314 |
| BYTESIZE | 8 | 7, 8 | - |
| SLAVE_ID | 6 | 1-247 | P0315 |
| MAX_FREQ | 6000 | 0-10000 | - |

### WEG CFW11 Parameters

| Parameter | Function | Values |
|-----------|----------|--------|
| P0312 | Baud rate | 1200, 2400, 4800, 9600, 19200, 38400, 57600, 115200 |
| P0313 | Parity | 0=None, 1=Even, 2=Odd |
| P0314 | Stop bits | 0=1 bit, 1=2 bits |
| P0315 | Slave address | 1-247 |
| P0316 | Protocol | 4=Modbus RTU |
| P0682 | Control word | Bit 0: Run/Stop |
| P0683 | Speed reference | 0-8192 (0-100%) |
| P0685 | Direction | 0=Forward, 1=Reverse |

---

## Register Mapping

### Yaskawa → WEG Translation

| Yaskawa Reg | Function | Yaskawa Format | WEG Reg | WEG Format |
|-------------|----------|----------------|---------|------------|
| 0x0001 | Run/Stop | Bit 0: Run | P0682 | Bit 0: Run |
| 0x0002 | Frequency | 0-6000 (0-60Hz) | P0683 | 0-8192 (0-100%) |

### Scaling Formulas

```python
# Yaskawa → Hz
freq_hz = yaskawa_value / 100.0

# Yaskawa → WEG
weg_value = (yaskawa_value / MAX_FREQ) * 8192

# WEG → Percentage
percentage = (weg_value / 8192) * 100

# WEG → Yaskawa (reverse)
yaskawa_value = (weg_value / 8192) * MAX_FREQ
```

### Quick Conversion Table (MAX_FREQ = 6000)

| Hz | Yaskawa | WEG | Percentage |
|----|---------|-----|------------|
| 0 | 0 | 0 | 0% |
| 15 | 1500 | 2048 | 25% |
| 30 | 3000 | 4096 | 50% |
| 45 | 4500 | 6144 | 75% |
| 60 | 6000 | 8192 | 100% |

---

## Code Snippets

### Adding a New Register

```python
# In YaskawaCallback.setValues()
elif reg_address == 0x00XX:  # Your register
    add_message('COMMAND', f"New command: {val}")
    # Translate if needed
    translated_val = your_translation_logic(val)
    # Write to WEG
    self._write_to_weg(WEG_REG_NUMBER, translated_val, "DESCRIPTION")
```

### Adding an API Endpoint

```python
# In webserver.py
@app.route('/api/your-endpoint', methods=['GET', 'POST'])
def your_function():
    try:
        # Your logic here
        return jsonify({
            'success': True,
            'data': your_data
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 400
```

### Reading from WEG

```python
# Thread-safe read
with weg_lock:
    if weg_client and weg_client.connected:
        result = weg_client.read_holding_registers(
            address=REG_NUMBER,
            count=1,
            slave=config['SLAVE_ID']
        )
        if not result.isError():
            value = result.registers[0]
            # Use value...
```

### Writing to WEG

```python
# Thread-safe write
with weg_lock:
    if weg_client and weg_client.connected:
        result = weg_client.write_register(
            address=REG_NUMBER,
            value=YOUR_VALUE,
            slave=config['SLAVE_ID']
        )
        if result.isError():
            # Handle error...
```

---

## Modbus RTU Quick Reference

### Function Codes

| Code | Function | Description |
|------|----------|-------------|
| 0x03 | Read Holding Registers | Read values from registers |
| 0x06 | Write Single Register | Write one register |
| 0x10 | Write Multiple Registers | Write many registers |
| 0x01 | Read Coils | Read output bits |
| 0x02 | Read Discrete Inputs | Read input bits |

### Frame Format

```
[Slave ID][Function][Data...][CRC Low][CRC High]
```

### Example: Write Register

```
Slave 6, Write Reg 683, Value 4096:
[0x06][0x06][0x02][0xAB][0x10][0x00][CRC][CRC]
  │     │     │            │
  │     │     └── Register 683 (0x02AB)
  │     └── Function: Write Single Register
  └── Slave ID: 6
       Value: 4096 (0x1000)
```

---

## Common Error Messages

| Error | Cause | Solution |
|-------|-------|----------|
| `Serial exception: could not open port` | Port in use or doesn't exist | Check Device Manager, close other programs |
| `Modbus Error: [Invalid CRC]` | Communication error | Check cables, baud rate, interference |
| `Permission denied` | Insufficient privileges | Run as Administrator |
| `WEG client not connected` | Connection lost | Check COM4 cable, WEG power |
| `Server is already running` | Tried to start twice | Stop first, then start |

---

## Debugging Commands

### List Serial Ports

```python
import serial.tools.list_ports
ports = serial.tools.list_ports.comports()
for port in ports:
    print(f"{port.device}: {port.description}")
```

### Test Modbus Connection

```python
from pymodbus.client import ModbusSerialClient

client = ModbusSerialClient(
    port='COM4',
    baudrate=9600,
    parity='N',
    stopbits=1,
    bytesize=8,
    timeout=1
)

if client.connect():
    print("Connected!")
    result = client.read_holding_registers(681, 1, slave=6)
    print(f"Result: {result.registers if not result.isError() else 'Error'}")
    client.close()
else:
    print("Connection failed")
```

### Check Thread Status

```python
import vfdserver

print(f"Server running: {vfdserver.server_running}")
print(f"Thread alive: {vfdserver.server_thread.is_alive() if vfdserver.server_thread else False}")
print(f"WEG connected: {vfdserver.weg_client.connected if vfdserver.weg_client else False}")
```

---

## Web API Endpoints

| Endpoint | Method | Purpose | Parameters |
|----------|--------|---------|------------|
| `/` | GET | Main page | - |
| `/api/config` | GET | Get configuration | - |
| `/api/config` | POST | Update configuration | JSON: config object |
| `/api/messages` | GET | Get all messages | - |
| `/api/messages/clear` | POST | Clear messages | - |
| `/api/server/start` | POST | Start gateway | - |
| `/api/server/stop` | POST | Stop gateway | - |
| `/api/status` | GET | Get server status | - |

### Example API Call

```javascript
// Get configuration
const response = await fetch('/api/config');
const data = await response.json();
console.log(data.config);

// Update configuration
await fetch('/api/config', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
        BAUD_RATE: 19200,
        SLAVE_ID: 1
    })
});
```

---

## WebSocket Events

| Event | Direction | Data | Purpose |
|-------|-----------|------|---------|
| `connect` | Browser → Server | - | Initial connection |
| `connection_response` | Server → Browser | `{status: 'connected'}` | Confirm connection |
| `new_messages` | Server → Browser | `{messages: [...]}` | Push new log messages |
| `disconnect` | Browser → Server | - | Connection closed |

### Example WebSocket Usage

```javascript
const socket = io();

socket.on('connect', () => {
    console.log('Connected to server');
});

socket.on('new_messages', (data) => {
    data.messages.forEach(msg => {
        console.log(`[${msg.type}] ${msg.message}`);
    });
});
```

---

## Threading Overview

```
Main Thread (Flask)
  ├─ Handles HTTP requests
  ├─ Manages configuration
  └─ Returns API responses

Gateway Thread (daemon)
  ├─ Runs Modbus server (COM3)
  ├─ Receives PLC commands
  ├─ Translates Yaskawa → WEG
  └─ Sends to WEG (COM4)

Broadcast Thread (daemon)
  ├─ Polls recent_messages
  └─ Pushes updates via WebSocket
```

### Thread Safety Rules

1. **Always use `weg_lock`** when accessing `weg_client`
2. **Use `with weg_lock:`** for automatic lock management
3. **Keep locked sections short** to avoid blocking
4. **Never nest locks** to avoid deadlock

---

## Performance Metrics

### Typical Benchmarks

| Metric | Value |
|--------|-------|
| Translation latency | < 1 ms |
| Serial write time | 10-50 ms (depends on baud rate) |
| WebSocket push delay | < 500 ms |
| Commands per second | 50-100 (serial limited) |

### Optimization Tips

1. **Increase baud rate** (if both devices support it)
2. **Reduce logging** in production
3. **Batch multiple writes** if possible
4. **Use faster computer** (minimal impact)

---

## Keyboard Shortcuts (Web Interface)

Browser shortcuts work as normal:

- **Ctrl + R**: Refresh page (reload config)
- **Ctrl + Shift + I**: Open DevTools (see console)
- **Ctrl + +/-**: Zoom in/out

---

## Project Structure

```
wegdrive/
├── vfdserver.py          # Gateway core logic
├── webserver.py          # Flask web server
├── requirements.txt      # Python dependencies
├── start.bat             # Windows startup script
├── templates/
│   └── index.html        # Web interface
├── STUDY_GUIDE.md        # Comprehensive learning guide
├── SYSTEM_DIAGRAMS.md    # Visual diagrams
├── HANDS_ON_TUTORIAL.md  # Practical exercises
├── QUICK_REFERENCE.md    # This file
├── README.md             # Project overview
└── WEG_CONFIG_NOTES.md   # WEG-specific notes
```

---

## Useful Python One-Liners

```python
# View recent messages
print('\n'.join([f"[{m['type']}] {m['message']}" for m in vfdserver.recent_messages[-10:]]))

# Get current config
import json; print(json.dumps(vfdserver.config, indent=2))

# Count messages by type
from collections import Counter; Counter(m['type'] for m in vfdserver.recent_messages)

# Find errors
[m for m in vfdserver.recent_messages if m['type'] == 'ERROR']

# Clear all messages
vfdserver.recent_messages.clear()
```

---

## Conversion Calculators

### Python Functions

```python
def yaskawa_to_hz(val, max_freq=6000):
    """Yaskawa value to Hz"""
    return val / 100.0

def yaskawa_to_weg(val, max_freq=6000):
    """Yaskawa value to WEG value"""
    return int((val / max_freq) * 8192)

def weg_to_percentage(val):
    """WEG value to percentage"""
    return (val / 8192) * 100

def hz_to_yaskawa(hz):
    """Hz to Yaskawa value"""
    return int(hz * 100)

# Examples
print(yaskawa_to_hz(3000))      # → 30.0
print(yaskawa_to_weg(3000))     # → 4096
print(weg_to_percentage(4096))  # → 50.0
print(hz_to_yaskawa(45.5))      # → 4550
```

---

## Safety Considerations

### ⚠️ Important Warnings

1. **Always test without motor first** - use simulated WEG
2. **Emergency stop** - have physical E-stop button
3. **Validate inputs** - check frequency limits
4. **Monitor errors** - watch for communication failures
5. **Backup working config** - save before changes
6. **Never force operations** - respect device limits

### Production Checklist

- [ ] Test with simulated devices first
- [ ] Verify all register mappings
- [ ] Test error handling (disconnect cables)
- [ ] Check emergency stop works
- [ ] Document all custom changes
- [ ] Set appropriate max frequency
- [ ] Configure timeout values
- [ ] Test under load
- [ ] Monitor for several hours
- [ ] Have rollback plan

---

## Getting Help

### In Order of Preference

1. **Check logs** - Web interface real-time log
2. **Read error messages** - Usually tell you what's wrong
3. **Review this guide** - Common issues covered
4. **Check wiring** - 90% of issues are hardware
5. **Test components separately** - Isolate the problem
6. **Check WEG manual** - Device-specific details

### Information to Gather

When troubleshooting, note:
- Error message (exact text)
- Configuration settings
- What you were trying to do
- Recent changes made
- Hardware setup (ports, cables)
- Log messages before error

---

## Glossary

| Term | Meaning |
|------|---------|
| **VFD** | Variable Frequency Drive - controls motor speed |
| **Modbus RTU** | Serial communication protocol for industrial devices |
| **PLC** | Programmable Logic Controller - industrial computer |
| **Gateway** | Device that translates between protocols |
| **Register** | Memory location in Modbus device |
| **Slave ID** | Address of Modbus device (1-247) |
| **Baud Rate** | Speed of serial communication (bits/second) |
| **CRC** | Cyclic Redundancy Check - error detection |
| **Holding Register** | Read/write register in Modbus |
| **WebSocket** | Persistent two-way connection for real-time updates |

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-02-01 | Initial system creation |

---

## License

Free to use and modify for your projects.

---

**📌 Bookmark this page for quick reference while working!**

For in-depth explanations, see:
- **STUDY_GUIDE.md** - Comprehensive learning
- **SYSTEM_DIAGRAMS.md** - Visual explanations
- **HANDS_ON_TUTORIAL.md** - Practical exercises


