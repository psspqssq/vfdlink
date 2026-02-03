# WEG Drive Gateway - Yaskawa to WEG CFW11 Modbus Translator

A Modbus RTU gateway that translates Yaskawa VFD commands to WEG CFW11 drive format with a real-time web interface.

> **🔧 PLC Programmer?** Need to implement Modbus without libraries? → **[FOR_PLC_PROGRAMMERS.md](FOR_PLC_PROGRAMMERS.md)** (Start here!)

## 🎯 What It Does

This gateway acts as a "man-in-the-middle" that:
1. Emulates a Yaskawa VFD on one serial port (connects to your PLC/Controller)
2. Translates incoming Modbus commands to WEG CFW11 format
3. Forwards translated commands to the actual WEG drive on another serial port
4. Provides a beautiful web interface for configuration and monitoring

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Hardware Setup

- Connect Controller/PLC to **COM3** (or your chosen port)
- Connect WEG CFW11 drive to **COM4** (or your chosen port)
- Ensure both devices are configured for Modbus RTU at 9600 baud

### 3. Run the Web Interface

```bash
python webserver.py
```

Then open your browser to: **http://localhost:5000**

### 4. Configure and Start

1. Update port settings in the web interface if needed
2. Click "Start Server"
3. Monitor real-time activity in the log window

## 🎨 Web Interface Features

- **Live Configuration**: Change ports, baud rate, and parameters on the fly
- **Real-Time Logs**: See all Modbus transactions as they happen
- **Color-Coded Messages**: INFO, SUCCESS, ERROR, WARNING, COMMAND types
- **Statistics Dashboard**: Track total messages, commands sent, and errors
- **Auto-Scroll Logs**: Automatically follow the latest activity
- **Modern UI**: Beautiful, responsive design that works on any device
- **🧪 Test Mode**: Send direct commands to WEG for testing (NEW!)
  - Preset quick commands (start, stop, set frequency)
  - Custom register read/write
  - Built-in frequency calculator
  - Real-time response feedback

## 🔧 Configuration Options

| Setting | Default | Description | WEG Parameter |
|---------|---------|-------------|---------------|
| Controller Port | COM3 | Serial port for PLC/Controller | - |
| WEG Port | COM4 | Serial port for WEG drive | - |
| Baud Rate | 9600 | Communication speed | P0312 |
| Parity | None | Error checking (N/E/O) | P0313 |
| Stop Bits | 1 | Stop bits (1 or 2) | P0314 |
| Data Bits | 8 | Data bits (7 or 8) | - |
| Slave ID | 6 | Modbus slave address | P0315 |
| Max Frequency | 6000 | Yaskawa max freq (0-60Hz = 0-6000) | - |

### WEG CFW11 Serial Communication Parameters

According to WEG CFW11 manual, configure these parameters on the drive:
- **P0312** - Serial Baud Rate: 1200, 2400, 4800, 9600, 19200, 38400, 57600, 115200
- **P0313** - Serial Parity: 0=None, 1=Even, 2=Odd (Default: 0)
- **P0314** - Serial Stop Bits: 0=1 bit, 1=2 bits (Default: 0)
- **P0315** - Serial Address: 1-247 (Default: 1)
- **P0316** - Serial Protocol: 4=Modbus RTU
- **P0317** - Serial Timeout: 0.1-25.5 seconds (Default: 1.0s)

## 📡 Modbus Register Mapping

### Yaskawa → WEG Translation

| Yaskawa Reg | Function | WEG Reg | Notes |
|-------------|----------|---------|-------|
| 0x0001 | RUN/STOP | P0682 | Direct bit mapping |
| 0x0002 | Frequency | P0683 | Scaled: 0-6000 → 0-8192 |

## 🐛 Python Logic Improvements Made

1. **Connection Management**: WEG client stays connected instead of reconnecting each time
2. **Error Handling**: Comprehensive try/except blocks for all serial operations
3. **Thread Safety**: Added locks to prevent concurrent writes
4. **Proper Logging**: Replaced print() with structured logging system
5. **Connection Recovery**: Automatic reconnection on failure
6. **Message Buffer**: Stores recent messages for web interface

## 📝 Running Without Web Interface

If you want to run just the gateway (no web interface):

```bash
python vfdserver.py
```

Press `Ctrl+C` to stop.

## 🔍 Troubleshooting

### "Port already in use"
- Close any other applications using the COM ports
- Check Device Manager to confirm port numbers

### "Permission denied"
- Run as Administrator on Windows
- Check that you have permission to access serial ports

### Web interface not loading
- Ensure Flask and dependencies are installed
- Check that port 5000 is not in use by another application
- Try accessing http://127.0.0.1:5000 instead

## 📊 Message Types

- **INFO**: General system information
- **SUCCESS**: Successful operations
- **ERROR**: Failed operations or exceptions
- **WARNING**: Non-critical issues
- **COMMAND**: Modbus commands received/sent
- **DEBUG**: Detailed debugging information

## 🛠️ Advanced Usage

### Changing Web Server Port

Edit `webserver.py` line:
```python
socketio.run(app, debug=True, host='0.0.0.0', port=5000)
```

### Adding More Register Mappings

Edit the `YaskawaCallback.setValues()` method in `vfdserver.py`:
```python
elif reg_address == 0x0003:  # New register
    # Your translation logic here
    self._write_to_weg(YOUR_WEG_REG, value, "DESCRIPTION")
```

## 📚 Learning Resources

New to this project or want to understand how it works? We've got you covered!

### Complete Learning Path

1. **[STUDY_GUIDE.md](STUDY_GUIDE.md)** - Start here! 📖
   - What problem this solves and why
   - Core concepts explained (Modbus, VFD, serial communication)
   - Line-by-line code walkthrough
   - Theory: design patterns, threading, callbacks
   - Why specific design decisions were made
   - Exercises to test your understanding

2. **[SYSTEM_DIAGRAMS.md](SYSTEM_DIAGRAMS.md)** - Visual learner? 📊
   - System architecture diagrams
   - Data flow visualization
   - Thread execution timeline
   - Modbus frame anatomy
   - WebSocket vs HTTP comparison
   - Error propagation examples

3. **[HANDS_ON_TUTORIAL.md](HANDS_ON_TUTORIAL.md)** - Learn by doing! 🛠️
   - Practical experiments you can run
   - Modify code and see results
   - Test translation math
   - Thread safety demonstrations
   - Add new features step-by-step
   - Debugging techniques
   - Challenge projects

4. **[QUICK_REFERENCE.md](QUICK_REFERENCE.md)** - Quick lookup 📖
   - Command cheat sheet
   - Configuration reference
   - Code snippets
   - Common errors and solutions
   - API endpoint reference
   - Conversion calculators

### Recommended Learning Order

**Total Beginner?** → Start with STUDY_GUIDE.md sections 1-3

**Visual Learner?** → Look at SYSTEM_DIAGRAMS.md first, then STUDY_GUIDE.md

**Want to Experiment?** → Jump to HANDS_ON_TUTORIAL.md Lab 1

**Need Quick Info?** → Use QUICK_REFERENCE.md

**Understanding the Code?** → Read STUDY_GUIDE.md sections 4-6

**Ready to Extend?** → Complete HANDS_ON_TUTORIAL.md challenges

## 📄 License

Free to use and modify for your projects.

## 🤝 Support

For issues or questions:
1. Check the web interface logs for detailed error messages
2. Review the **QUICK_REFERENCE.md** for common issues
3. See **HANDS_ON_TUTORIAL.md** debugging section
4. Study the error handling in **STUDY_GUIDE.md**

