import logging
import threading
import time
import serial
from datetime import datetime
from pymodbus.server import StartSerialServer
from pymodbus.device import ModbusDeviceIdentification
from pymodbus.datastore import ModbusSequentialDataBlock, ModbusSlaveContext, ModbusServerContext
from pymodbus.client import ModbusSerialClient as ModbusClient

# --- CONFIGURACIÓN ---
config = {
    'PORT_CONTROLADOR': 'COM4',  # Port for listening to Sullair HMI
    'PORT_WEG': 'COM4',          # Port for WEG VFD (can be same as controller for single-bus)
    'BAUD_RATE': 38400,
    'PARITY': 'N',               # Parity: 'N'=None, 'E'=Even, 'O'=Odd
    'STOPBITS': 2,               # Stop bits: 1 or 2
    'BYTESIZE': 8,               # Data bits: 7 or 8
    'SLAVE_ID': 5,               # WEG slave ID (target drive)
    'YASKAWA_SLAVE_ID': 6,       # Slave ID the emulator responds to (what Sullair expects)
    'MAX_FREQ': 6000,            # Max frequency Yaskawa (0-60.00Hz)
    'RESPOND_TO_ANY_ID': False,  # Respond to any slave ID (for debugging)
    'SINGLE_BUS_MODE': True,     # Set True if WEG and controller on same RS-485 bus
    'HEARTBEAT_INTERVAL': 0.5,   # Seconds between WEG heartbeat polls (must be < P0314!)
    'WEG_MAX_FREQ_HZ': 60.0,     # WEG motor max frequency (8192 = this value)
}

# --- APPLICATION MODE ---
# 'redirect' = Forward Yaskawa commands to WEG (production)
# 'listen'   = Listen and decode Yaskawa commands without forwarding (debug)
# 'command'  = Direct WEG testing mode (testing)
current_mode = 'redirect'

# --- YASKAWA A1000 EMULATION ---
# Emulator targets Yaskawa A1000 MEMOBUS/Modbus (Technical Manual SIEP C710616, Appendix C).
# Register map: 0x0000=Status, 0x0001=Command, 0x0002=Freq Ref, etc. Same across A1000/V1000 series.
#
# MEMOBUS "special rules" some controllers use to know they're talking to an A1000:
# - Same wire format as Modbus RTU (FC 03/04/06/10, CRC-16). Many HMIs treat MEMOBUS = Modbus for A1000.
# - Optional: drive type/model/option register (see A1000 manual C.9 Data Table). If your controller
#   reads a specific register to identify A1000, add it below and set a valid value so the HMI accepts the drive.
# - Timing: inter-frame delay and response time; we use short fixed delays. Can be made configurable if needed.
# - Broadcast (slave 0): we only respond to Yaskawa Emulator ID (e.g. 6), not broadcast.
# Identification registers (0x00F0-0x00F2) are set so controllers that read "drive type" get A1000.
# --- YASKAWA COMMAND DECODER ---
# Yaskawa common register definitions for decoding
YASKAWA_REGISTERS = {
    # Status and Control (0x0000-0x000F)
    0x0000: {'name': 'STATUS', 'description': 'Drive Status Word'},
    0x0001: {'name': 'COMMAND', 'description': 'Run/Stop Command Word'},
    0x0002: {'name': 'FREQ_REF', 'description': 'Frequency Reference (x0.01 Hz)'},
    0x0003: {'name': 'OUTPUT_FREQ', 'description': 'Output Frequency (x0.01 Hz)'},
    0x0004: {'name': 'OUTPUT_CURRENT', 'description': 'Output Current (x0.01 A)'},
    0x0005: {'name': 'OUTPUT_VOLTAGE', 'description': 'Output Voltage (V)'},
    0x0006: {'name': 'DC_BUS_VOLTAGE', 'description': 'DC Bus Voltage (V)'},
    0x0007: {'name': 'OUTPUT_POWER', 'description': 'Output Power (x0.1 kW)'},
    0x0008: {'name': 'OUTPUT_TORQUE', 'description': 'Output Torque (x0.1 %)'},
    0x0009: {'name': 'MOTOR_SPEED', 'description': 'Motor Speed (RPM)'},
    0x000A: {'name': 'THERMAL_LOAD', 'description': 'Motor Thermal Load (%)'},
    0x000B: {'name': 'INPUT_STATUS', 'description': 'Digital Input Status'},
    0x000C: {'name': 'OUTPUT_STATUS', 'description': 'Digital Output Status'},
    0x000D: {'name': 'FAULT_CODE', 'description': 'Active Fault Code'},
    0x000E: {'name': 'ALARM_CODE', 'description': 'Active Alarm Code'},
    0x000F: {'name': 'DRIVE_TEMP', 'description': 'Drive Temperature (C)'},
    
    # Ramp Times (0x0010-0x001F)
    0x0010: {'name': 'ACCEL_TIME', 'description': 'Acceleration Time (x0.1 s)'},
    0x0011: {'name': 'DECEL_TIME', 'description': 'Deceleration Time (x0.1 s)'},
    0x0012: {'name': 'ACCEL_TIME_2', 'description': 'Acceleration Time 2'},
    0x0013: {'name': 'DECEL_TIME_2', 'description': 'Deceleration Time 2'},
    0x0014: {'name': 'JOG_FREQ', 'description': 'Jog Frequency'},
    0x0015: {'name': 'JOG_ACCEL', 'description': 'Jog Acceleration'},
    0x0016: {'name': 'JOG_DECEL', 'description': 'Jog Deceleration'},
    
    # Frequency Limits (0x0020-0x002F)
    0x0020: {'name': 'FREQ_UPPER_LIMIT', 'description': 'Frequency Upper Limit'},
    0x0021: {'name': 'FREQ_LOWER_LIMIT', 'description': 'Frequency Lower Limit'},
    0x0022: {'name': 'RTC_YEAR', 'description': 'Real Time Clock - Year'},
    0x0023: {'name': 'RTC_MONTH', 'description': 'Real Time Clock - Month'},
    0x0024: {'name': 'RTC_DAY', 'description': 'Real Time Clock - Day'},
    0x0025: {'name': 'RTC_HOUR', 'description': 'Real Time Clock - Hour'},
    0x0026: {'name': 'RTC_MINUTE', 'description': 'Real Time Clock - Minute'},
    0x0027: {'name': 'RTC_SECOND', 'description': 'Real Time Clock - Second'},
    0x0028: {'name': 'RUN_HOURS_HI', 'description': 'Run Hours (High Word)'},
    0x0029: {'name': 'RUN_HOURS_LO', 'description': 'Run Hours (Low Word)'},
    0x002A: {'name': 'POWER_ON_HOURS_HI', 'description': 'Power On Hours (High)'},
    0x002B: {'name': 'POWER_ON_HOURS_LO', 'description': 'Power On Hours (Low)'},
    
    # PID Control (0x0030-0x003F)
    0x0030: {'name': 'PID_SETPOINT', 'description': 'PID Setpoint'},
    0x0031: {'name': 'PID_FEEDBACK', 'description': 'PID Feedback'},
    0x0032: {'name': 'PID_OUTPUT', 'description': 'PID Output'},
    0x0033: {'name': 'PID_ERROR', 'description': 'PID Error'},
    0x0034: {'name': 'PID_P_GAIN', 'description': 'PID Proportional Gain'},
    0x0035: {'name': 'PID_I_TIME', 'description': 'PID Integral Time'},
    0x0036: {'name': 'PID_D_TIME', 'description': 'PID Derivative Time'},
    
    # Multi-speed References (0x0040-0x004F)
    0x0040: {'name': 'MULTISPEED_1', 'description': 'Multi-speed Reference 1'},
    0x0041: {'name': 'MULTISPEED_2', 'description': 'Multi-speed Reference 2'},
    0x0042: {'name': 'MULTISPEED_3', 'description': 'Multi-speed Reference 3'},
    0x0043: {'name': 'MULTISPEED_4', 'description': 'Multi-speed Reference 4'},
    
    # Analog I/O (0x0050-0x005F)
    0x0050: {'name': 'ANALOG_IN_1', 'description': 'Analog Input 1 (%)'},
    0x0051: {'name': 'ANALOG_IN_2', 'description': 'Analog Input 2 (%)'},
    0x0052: {'name': 'ANALOG_OUT_1', 'description': 'Analog Output 1 (%)'},
    0x0053: {'name': 'ANALOG_OUT_2', 'description': 'Analog Output 2 (%)'},
    # Sullair WS Controller reads these A1000 registers (per Sullair Modbus spec 02250162-949)
    0x0020: {'name': 'YASK_STATUS_WORD', 'description': 'Status Word for Sullair (read)'},
    0x0021: {'name': 'YASK_GENL_STATUS', 'description': 'General Status Word for Sullair'},
    0x0023: {'name': 'YASK_ACTUAL_PCT', 'description': 'Actual Speed % (0.01%)'},
    0x0024: {'name': 'YASK_ACTUAL_FREQ', 'description': 'Actual Frequency (0.01 Hz)'},
    0x0026: {'name': 'YASK_MOTOR_CURRENT', 'description': 'Motor Current (0.1 A)'},
    0x0027: {'name': 'YASK_POWER_OUT', 'description': 'Output Power (0.1 kW)'},
    0x0031: {'name': 'YASK_DC_VOLTAGE', 'description': 'DC Link Voltage (V)'},
    0x0068: {'name': 'YASK_UNIT_TEMP', 'description': 'Unit Temperature (deg)'},
    0x007F: {'name': 'YASK_ALARM_FAULT', 'description': 'Alarm / Active Fault (0=none)'},
    0x07D8: {'name': 'YASK_MOTOR_TEMP', 'description': 'Motor Temperature (0.1%)'},
}

# Yaskawa command word bit definitions
YASKAWA_COMMAND_BITS = {
    0: 'RUN/STOP',
    1: 'DIRECTION (0=FWD, 1=REV)',
    2: 'EXTERNAL FAULT',
    3: 'FAULT RESET',
    4: 'JOG',
    5: 'ACCEL/DECEL INHIBIT',
    6: 'RAMP HOLD',
    7: 'DC BRAKING',
    8: 'MULTISPEED 1',
    9: 'MULTISPEED 2',
    10: 'MULTISPEED 3',
    11: 'MULTISPEED 4',
}

# Yaskawa status word bit definitions  
YASKAWA_STATUS_BITS = {
    0: 'DRIVE READY',
    1: 'RUNNING',
    2: 'DIRECTION (0=FWD, 1=REV)',
    3: 'FAULT ACTIVE',
    4: 'REFERENCE FROM KEYPAD',
    5: 'AT FREQUENCY',
    6: 'BELOW BASE SPEED',
    7: 'RUNNING AT ZERO SPEED',
    8: 'DC INJECTION',
    9: 'OVERLOAD WARNING',
    10: 'UNDERVOLTAGE WARNING',
    11: 'TORQUE LIMITED',
}
# Status values for emulator - HMI shows "faulted" if bit 3 set or fault code != 0
YASKAWA_STATUS_READY = 0x0021   # Bit 0 = Drive Ready, Bit 5 = At Frequency (bit 3 = FAULT must be 0)
YASKAWA_STATUS_FAULT_BIT = 0x0008  # Bit 3 = FAULT ACTIVE - never set this in emulator

def decode_yaskawa_command(register, value, is_write=True):
    """Decode Yaskawa register and provide human-readable description"""
    result = {
        'register': register,
        'register_hex': f'0x{register:04X}',
        'value': value,
        'value_hex': f'0x{value:04X}',
        'value_binary': f'{value:016b}',
        'operation': 'WRITE' if is_write else 'READ',
        'description': '',
        'decoded_bits': [],
        'calculated_value': None
    }
    
    # Get register info
    reg_info = YASKAWA_REGISTERS.get(register, {'name': 'UNKNOWN', 'description': f'Unknown Register {register}'})
    result['register_name'] = reg_info['name']
    result['description'] = reg_info['description']
    
    # Decode specific registers
    if register == 0x0001:  # Command Word
        result['decoded_bits'] = decode_bits(value, YASKAWA_COMMAND_BITS)
        if value & 0x01:
            result['calculated_value'] = 'RUN COMMAND ACTIVE'
        else:
            result['calculated_value'] = 'STOP COMMAND'
        if value & 0x02:
            result['calculated_value'] += ' (REVERSE)'
        else:
            result['calculated_value'] += ' (FORWARD)'
            
    elif register == 0x0000:  # Status Word
        result['decoded_bits'] = decode_bits(value, YASKAWA_STATUS_BITS)
        
    elif register == 0x0002:  # Frequency Reference
        freq_hz = value / 100.0
        result['calculated_value'] = f'{freq_hz:.2f} Hz ({value/60:.0f} RPM at 2-pole)'
        
    elif register == 0x0003:  # Output Frequency
        freq_hz = value / 100.0
        result['calculated_value'] = f'{freq_hz:.2f} Hz'
        
    elif register == 0x0004:  # Output Current
        current_a = value / 100.0
        result['calculated_value'] = f'{current_a:.2f} A'
        
    elif register == 0x0005:  # Output Voltage
        result['calculated_value'] = f'{value} V'
        
    elif register == 0x0009:  # Motor Speed
        result['calculated_value'] = f'{value} RPM'
        
    elif register in [0x0010, 0x0011]:  # Accel/Decel time
        result['calculated_value'] = f'{value / 10.0:.1f} seconds'
    
    return result

def decode_bits(value, bit_definitions):
    """Decode individual bits based on definitions"""
    active_bits = []
    for bit_num, description in bit_definitions.items():
        if value & (1 << bit_num):
            active_bits.append({'bit': bit_num, 'description': description, 'state': 'ON'})
        else:
            active_bits.append({'bit': bit_num, 'description': description, 'state': 'OFF'})
    return active_bits

def format_decoded_command(decoded):
    """Format decoded command for display"""
    lines = []
    lines.append(f"[{decoded['operation']}] Register {decoded['register_hex']} ({decoded['register_name']})")
    lines.append(f"  Description: {decoded['description']}")
    lines.append(f"  Value: {decoded['value']} (0x{decoded['value']:04X}, binary: {decoded['value_binary']})")
    
    if decoded['calculated_value']:
        lines.append(f"  Interpreted: {decoded['calculated_value']}")
    
    # Show active bits for command/status words
    if decoded['decoded_bits']:
        active = [b for b in decoded['decoded_bits'] if b['state'] == 'ON']
        if active:
            bit_strs = [f"Bit{b['bit']}:{b['description']}" for b in active]
            lines.append(f"  Active Bits: {', '.join(bit_strs)}")
    
    return '\n'.join(lines)

# Logger and message storage
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Store recent messages for web interface
recent_messages = []
MAX_MESSAGES = 100

def add_message(msg_type, message):
    """Add message to the buffer with timestamp"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
    recent_messages.append({
        'timestamp': timestamp,
        'type': msg_type,
        'message': message
    })
    if len(recent_messages) > MAX_MESSAGES:
        recent_messages.pop(0)
    logger.info(f"[{msg_type}] {message}")

# Cliente para hablar con el WEG
weg_client = None
weg_lock = threading.Lock()

def init_weg_client():
    """Initialize WEG client with error handling"""
    global weg_client
    try:
        # Close existing connection if any
        if weg_client:
            try:
                weg_client.close()
            except:
                pass
        
        weg_client = ModbusClient(
            port=config['PORT_WEG'], 
            baudrate=config['BAUD_RATE'], 
            parity=config['PARITY'], 
            stopbits=config['STOPBITS'], 
            bytesize=config['BYTESIZE'], 
            timeout=3  # Increased timeout for slower devices
        )
        if weg_client.connect():
            add_message('INFO', f"WEG client connected on {config['PORT_WEG']} @ {config['BAUD_RATE']} baud, {config['BYTESIZE']}{config['PARITY']}{config['STOPBITS']}")
            return True
        else:
            add_message('ERROR', f"Failed to connect WEG client on {config['PORT_WEG']}")
            return False
    except Exception as e:
        add_message('ERROR', f"Error initializing WEG client: {str(e)}")
        return False

def reconnect_weg_client():
    """Force reconnection with current config"""
    global weg_client
    if weg_client:
        try:
            weg_client.close()
            add_message('INFO', 'Closed existing WEG connection')
        except:
            pass
        weg_client = None
    return init_weg_client()

# --- LÓGICA DE TRADUCCIÓN ---
class YaskawaCallback(ModbusSequentialDataBlock):
    """
    Esta clase intercepta las escrituras que el PLC hace al 'Yaskawa'
    y las traduce inmediatamente al formato del WEG CFW11.
    Supports multiple modes: redirect, listen, command
    """
    def setValues(self, address, values):
        global current_mode
        
        # Primero guardamos el valor en la memoria local (para que el PLC lo lea si quiere)
        super().setValues(address, values)
        
        reg_address = address 
        val = values[0] if values else 0

        # LISTEN MODE: Just decode and display, no forwarding
        if current_mode == 'listen':
            decoded = decode_yaskawa_command(reg_address, val, is_write=True)
            add_message('YASKAWA', format_decoded_command(decoded))
            
            # Store decoded data for web interface
            add_decoded_message(decoded)
            
            # Update status register to simulate drive response
            # This makes the controller think commands are being executed
            if reg_address == 0x0001:  # Command word
                # Echo command to status - never set fault bit or HMI shows "faulted"
                status = 0x0001  # Drive Ready
                if val & 0x01:
                    status |= 0x0002  # Running
                if val & 0x02:
                    status |= 0x0004  # Reverse
                status |= 0x0020  # At frequency
                super().setValues(0x0000, [status & ~YASKAWA_STATUS_FAULT_BIT])
                # Sullair WS Controller reads register 0x0020 for status (not 0x0000)
                super().setValues(0x0020, [status & ~YASKAWA_STATUS_FAULT_BIT])
                add_message('DEBUG', f'Simulated status response: 0x{status & ~YASKAWA_STATUS_FAULT_BIT:04X}')
            
            return
        
        # COMMAND MODE: No translation, ignore incoming commands
        if current_mode == 'command':
            add_message('DEBUG', f"Command mode - ignoring write to {reg_address:#06x}: {val}")
            return
        
        # REDIRECT MODE: Translate and forward to WEG
        yaskawa_id = config.get('YASKAWA_SLAVE_ID', 6)
        weg_id = config.get('SLAVE_ID', 5)
        
        # Log received message
        decoded = decode_yaskawa_command(reg_address, val, is_write=True)
        add_message('RECV', f"[Node {yaskawa_id}] WRITE Reg 0x{reg_address:04X} = {val} (0x{val:04X})")
        add_message('DECODE', f"  -> {decoded.get('register_name', 'UNKNOWN')}: {decoded.get('calculated_value', decoded.get('description', 'N/A'))}")
        
        # 1. TRADUCIR COMANDO DE MARCHA (Yaskawa Reg 0x0001)
        if reg_address == 0x0001:
            # Mapeo: Bit 0 en WEG P0682 es General Enable/Run
            add_message('SEND', f"[Node {weg_id}] WRITE P0682 = {val} (RUN/STOP)")
            self._write_to_weg(682, val, "RUN/STOP")

        # 2. TRADUCIR FRECUENCIA (Yaskawa Reg 0x0002)
        elif reg_address == 0x0002:
            # Yaskawa suele usar 0-6000 para 0-60.00Hz
            # WEG CFW11 usa 0-8192 para 0-100% de la velocidad
            freq_hz = val / 100.0
            val_weg = int((val / config['MAX_FREQ']) * 8192)
            add_message('SEND', f"[Node {weg_id}] WRITE P0683 = {val_weg} (FREQ {freq_hz:.2f}Hz)")
            
            # Enviamos al registro 683 del WEG (Referencia de Velocidad)
            self._write_to_weg(683, val_weg, "FREQUENCY")
        
        else:
            add_message('DEBUG', f"No translation rule for register 0x{reg_address:04X}")

    def getValues(self, address, count=1):
        """Intercept read requests for logging"""
        global current_mode
        
        values = super().getValues(address, count)
        yaskawa_id = config.get('YASKAWA_SLAVE_ID', 6)
        
        if current_mode == 'listen':
            for i, val in enumerate(values):
                decoded = decode_yaskawa_command(address + i, val, is_write=False)
                add_message('RECV', f"[Node {yaskawa_id}] READ Reg 0x{address+i:04X} -> {val} (0x{val:04X})")
                add_message('DECODE', f"  -> {decoded.get('register_name', 'UNKNOWN')}: {decoded.get('calculated_value', decoded.get('description', 'N/A'))}")
                add_decoded_message(decoded)
        elif current_mode == 'redirect':
            # Log reads in redirect mode too
            for i, val in enumerate(values):
                decoded = decode_yaskawa_command(address + i, val, is_write=False)
                add_message('RECV', f"[Node {yaskawa_id}] READ Reg 0x{address+i:04X} -> {val} (0x{val:04X})")
        
        return values

    def _write_to_weg(self, register, value, command_name):
        """Thread-safe write to WEG with error handling"""
        weg_id = config.get('SLAVE_ID', 5)
        single_bus = config.get('SINGLE_BUS_MODE', False) or (config['PORT_CONTROLADOR'] == config['PORT_WEG'])
        
        if single_bus:
            # In single bus mode, queue the command for later transmission
            # The server and WEG share the same RS-485 bus
            queue_weg_command(register, value, command_name)
            return
        
        # Dual port mode - use separate WEG client
        with weg_lock:
            try:
                if weg_client is None or not weg_client.connected:
                    if not init_weg_client():
                        add_message('ERROR', f"[Node {weg_id}] Cannot write {command_name}: WEG not connected")
                        return
                
                result = weg_client.write_register(register, value, slave=config['SLAVE_ID'])
                
                if result.isError():
                    add_message('ERROR', f"[Node {weg_id}] Write FAILED P{register:04d}={value}: {result}")
                else:
                    add_message('SUCCESS', f"[Node {weg_id}] Write OK P{register:04d}={value} ({command_name})")
                    
            except Exception as e:
                add_message('ERROR', f"[Node {weg_id}] Exception: {str(e)}")
                # Try to reconnect on next attempt
                if weg_client:
                    try:
                        weg_client.close()
                    except:
                        pass

# Store decoded messages for web interface
decoded_messages = []
MAX_DECODED = 50

def add_decoded_message(decoded):
    """Add decoded message to buffer for web interface"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
    decoded['timestamp'] = timestamp
    decoded_messages.append(decoded)
    if len(decoded_messages) > MAX_DECODED:
        decoded_messages.pop(0)

def set_mode(mode):
    """Set the application mode"""
    global current_mode
    if mode in ['redirect', 'listen', 'command']:
        current_mode = mode
        add_message('INFO', f'Mode changed to: {mode.upper()}')
        return True
    return False

def get_mode():
    """Get current mode"""
    return current_mode

# --- SINGLE BUS MODE: Command Queue ---
weg_command_queue = []
weg_queue_lock = threading.Lock()

def queue_weg_command(register, value, command_name):
    """Queue a command to be sent to WEG on single bus"""
    weg_id = config.get('SLAVE_ID', 5)
    with weg_queue_lock:
        weg_command_queue.append({
            'register': register,
            'value': value,
            'name': command_name,
            'timestamp': datetime.now()
        })
        add_message('QUEUE', f"[Node {weg_id}] Queued: P{register:04d}={value} ({command_name})")

def build_modbus_write_frame(slave_id, register, value):
    """Build a Modbus RTU write single register frame (FC 0x06)"""
    # Function code 06 = Write Single Register
    frame = bytes([
        slave_id,           # Slave address
        0x06,               # Function code
        (register >> 8) & 0xFF,   # Register address high byte
        register & 0xFF,          # Register address low byte
        (value >> 8) & 0xFF,      # Value high byte
        value & 0xFF              # Value low byte
    ])
    # Calculate CRC-16
    crc = calculate_crc(frame)
    frame += bytes([crc & 0xFF, (crc >> 8) & 0xFF])
    return frame

def build_modbus_read_frame(slave_id, register, count):
    """Build a Modbus RTU read holding registers frame (FC 0x03)"""
    frame = bytes([
        slave_id,           # Slave address
        0x03,               # Function code (Read Holding Registers)
        (register >> 8) & 0xFF,   # Register address high byte
        register & 0xFF,          # Register address low byte
        (count >> 8) & 0xFF,      # Count high byte
        count & 0xFF              # Count low byte
    ])
    # Calculate CRC-16
    crc = calculate_crc(frame)
    frame += bytes([crc & 0xFF, (crc >> 8) & 0xFF])
    return frame

def calculate_crc(data):
    """Calculate Modbus CRC-16"""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc

def get_modbus_request_frame_length(data):
    """Return length of first Modbus request frame in data, or None if incomplete/unknown.
    Used to scan a buffer containing multiple concatenated frames."""
    if len(data) < 4:
        return None
    fc = data[1]
    if fc in (0x03, 0x04):  # Read Holding/Input Registers - 8 bytes
        return 8 if len(data) >= 8 else None
    if fc == 0x06:  # Write Single Register - 8 bytes
        return 8 if len(data) >= 8 else None
    if fc == 0x10:  # Write Multiple Registers
        if len(data) < 7:
            return None
        byte_count = data[6]
        total = 9 + byte_count
        return total if len(data) >= total else None
    # Unknown function code - caller can skip 1 byte to resync
    return None

def get_modbus_response_frame_length(data):
    """Return length of a Modbus response frame (from slave e.g. WEG), or None."""
    if len(data) < 5:
        return None
    fc = data[1]
    if fc in (0x03, 0x04):  # Read response: slave, fc, byte_count, data..., crc, crc
        byte_count = data[2]
        total = 3 + byte_count + 2
        return total if len(data) >= total else None
    if fc == 0x06 or fc == 0x10:  # Write response: 8 bytes
        return 8 if len(data) >= 8 else None
    return None

def run_single_bus_gateway():
    """Custom single-bus handler for redirect mode - both slave and master on same port.

    HMI shows 'faulted' when: (1) No valid Modbus response = communication timeout - ensure
    Node 6 frames are processed (buffer scan); (2) Status word bit 3 (FAULT ACTIVE) set -
    we never set it; (3) Fault code register 0x000D non-zero - we init to 0."""
    global server_running
    
    yaskawa_id = config.get('YASKAWA_SLAVE_ID', 6)
    weg_id = config.get('SLAVE_ID', 5)
    
    # Initialize register values (simulated Yaskawa A1000 state)
    # Sullair WS Controller (spec 02250162-949) reads specific registers to verify A1000 is present.
    # Register space extended to 0x1000 so reads to high addresses (e.g. 0x07D8) don't index out.
    REGISTER_SIZE = 0x1000
    registers = [0] * REGISTER_SIZE
    
    # Standard MEMOBUS registers (0x0000-0x000F)
    registers[0x0000] = YASKAWA_STATUS_READY   # Status: Ready + At Frequency, NO fault bit
    registers[0x0001] = 0       # Command word (written by controller)
    registers[0x0002] = 0       # Frequency reference (written by controller)
    registers[0x0003] = 0       # Output frequency
    registers[0x0004] = 0       # Output current
    registers[0x0008] = 0       # Pressure reference (Sullair writes here)
    registers[0x000A] = 0       # General control word (Sullair writes here)
    registers[0x000D] = 0       # Fault code - must be 0 or HMI shows faulted
    registers[0x000E] = 0       # Alarm code - 0 = no alarm
    
    # SULLAIR-SPECIFIC A1000 REGISTERS (per Sullair Modbus spec 02250162-949)
    # These are the registers Sullair WS Controller reads to detect and monitor Yaskawa A1000
    registers[0x0020] = YASKAWA_STATUS_READY  # Status Word: Bit 0=Ready, Bit 5=At Freq (Sullair reads this!)
    registers[0x0021] = 0x0000  # General Status Word
    registers[0x0023] = 0       # Actual speed % (0.01%)
    registers[0x0024] = 0       # Actual frequency (0.01 Hz)
    registers[0x0026] = 0       # Motor current (0.1 A)
    registers[0x0027] = 0       # Output power (0.1 kW)
    registers[0x0031] = 540     # DC link voltage (~540V typical for 400V drive)
    registers[0x0068] = 25      # Unit temperature (25 deg)
    registers[0x007F] = 0       # Alarm / Active Fault - MUST be 0 for "no fault"
    registers[0x07D8] = 0       # Motor temperature (0.1%)
    
    # Frequency limit (at a non-conflicting address)
    registers[0x0010] = 6000       # Freq upper limit (60.00 Hz)
    
    try:
        ser = serial.Serial(
            port=config['PORT_CONTROLADOR'],
            baudrate=config['BAUD_RATE'],
            parity=config['PARITY'],
            stopbits=config['STOPBITS'],
            bytesize=config['BYTESIZE'],
            timeout=0.05
        )
        add_message('INFO', f"Single bus gateway started on {config['PORT_CONTROLADOR']}")
        add_message('INFO', f"  Yaskawa ID: {yaskawa_id}, WEG ID: {weg_id}")
        
        buffer = bytearray()
        last_rx_time = time.time()
        
        while server_running:
            # Read incoming data
            data = ser.read(64)
            if data:
                buffer.extend(data)
                last_rx_time = time.time()
                hex_data = ' '.join([f'{b:02X}' for b in data])
                add_message('RAW', f"RX: {hex_data}")
            
            # If we have data and there's been a gap (end of frame), scan for Node 6 frames
            if len(buffer) >= 8 and (time.time() - last_rx_time) > 0.005:
                # SCAN buffer for Node 6 frames with valid CRC (handles mixed protocol traffic)
                found_frame = False
                for i in range(len(buffer) - 7):  # Need at least 8 bytes for shortest frame
                    if buffer[i] == yaskawa_id:
                        fc = buffer[i + 1]
                        frame_len = None
                        
                        # Calculate expected frame length based on function code
                        if fc == 0x03 or fc == 0x04:  # Read Holding/Input Registers
                            frame_len = 8
                        elif fc == 0x06:  # Write Single Register
                            frame_len = 8
                        elif fc == 0x10:  # Write Multiple Registers
                            if i + 7 <= len(buffer):
                                byte_count = buffer[i + 6]
                                frame_len = 9 + byte_count
                        
                        if frame_len and i + frame_len <= len(buffer):
                            frame = buffer[i:i + frame_len]
                            # Verify CRC
                            if verify_crc(frame):
                                hex_frame = ' '.join([f'{b:02X}' for b in frame])
                                add_message('RECV', f"[Node {yaskawa_id}] Valid frame at offset {i}: {hex_frame}")
                                
                                # Process as Yaskawa slave
                                _, response, registers = process_yaskawa_request(frame, registers, yaskawa_id, weg_id, ser)
                                if response:
                                    time.sleep(0.002)  # Small delay before responding
                                    bytes_written = ser.write(response)
                                    ser.flush()
                                    hex_resp = ' '.join([f'{b:02X}' for b in response])
                                    add_message('TX', f"[Node {yaskawa_id}] Response ({bytes_written}B): {hex_resp}")
                                
                                # Remove processed data up to and including this frame
                                buffer = buffer[i + frame_len:]
                                found_frame = True
                                break
                
                # If no valid Node 6 frame found, clear old data to prevent buffer growth
                if not found_frame and len(buffer) > 256:
                    add_message('DEBUG', f"Clearing {len(buffer) - 64} bytes of unprocessed data")
                    buffer = buffer[-64:]  # Keep last 64 bytes in case frame spans reads
            
            # Clear stale buffer
            if len(buffer) > 0 and (time.time() - last_rx_time) > 0.5:
                buffer.clear()
            
            # Process any queued WEG commands (only when bus is idle)
            if len(buffer) == 0 and (time.time() - last_rx_time) > 0.05:
                process_weg_queue_on_bus(ser, weg_id)
            
            time.sleep(0.001)
        
        ser.close()
        add_message('INFO', 'Single bus gateway stopped')
        
    except Exception as e:
        add_message('ERROR', f"Single bus gateway error: {str(e)}")
        import traceback
        add_message('ERROR', traceback.format_exc())
        server_running = False

def verify_crc(data):
    """Verify CRC of a Modbus frame"""
    if len(data) < 4:
        return False
    message = data[:-2]
    received_crc = data[-2] | (data[-1] << 8)
    calculated_crc = calculate_crc(message)
    return received_crc == calculated_crc

def process_yaskawa_request(buffer, registers, yaskawa_id, weg_id, ser):
    """Process incoming Modbus request as Yaskawa slave"""
    if len(buffer) < 4:
        return None, None, registers
    
    slave_id = buffer[0]
    func_code = buffer[1]
    
    if slave_id != yaskawa_id:
        return None, None, registers
    
    response = None
    frame_len = 0
    
    if func_code == 0x03 or func_code == 0x04:  # Read Holding/Input Registers
        if len(buffer) >= 8:
            frame_len = 8
            
            # Verify CRC
            if not verify_crc(buffer[:frame_len]):
                add_message('ERROR', f"CRC error on received frame")
                return buffer[:frame_len], None, registers
            
            start_addr = (buffer[2] << 8) | buffer[3]
            count = (buffer[4] << 8) | buffer[5]
            
            hex_frame = ' '.join([f'{b:02X}' for b in buffer[:frame_len]])
            fc_name = "READ HOLD" if func_code == 0x03 else "READ INPUT"
            add_message('RECV', f"[Node {yaskawa_id}] {fc_name} Reg 0x{start_addr:04X} x{count}")
            
            # Build response
            resp = bytearray([slave_id, func_code, count * 2])
            values_log = []
            for i in range(count):
                addr = start_addr + i
                val = registers[addr] if addr < len(registers) else 0
                values_log.append(f"0x{addr:04X}={val}")
                resp.extend([(val >> 8) & 0xFF, val & 0xFF])
            
            # Log ALL values being returned (critical for debugging Sullair communication)
            add_message('SEND', f"[Node {yaskawa_id}] Response: {', '.join(values_log)}")
            
            crc = calculate_crc(resp)
            resp.extend([crc & 0xFF, (crc >> 8) & 0xFF])
            response = bytes(resp)
            
            # Log decoded values (only first few to avoid spam)
            for i in range(min(count, 3)):
                addr = start_addr + i
                val = registers[addr] if addr < len(registers) else 0
                decoded = decode_yaskawa_command(addr, val, is_write=False)
                add_message('DECODE', f"  0x{addr:04X}={val} ({decoded.get('register_name', 'UNK')})")
            if count > 3:
                add_message('DECODE', f"  ... and {count-3} more registers")
            
    elif func_code == 0x06:  # Write Single Register
        if len(buffer) >= 8:
            frame_len = 8
            
            # Verify CRC
            if not verify_crc(buffer[:frame_len]):
                add_message('ERROR', f"CRC error on received frame")
                return buffer[:frame_len], None, registers
            
            reg_addr = (buffer[2] << 8) | buffer[3]
            value = (buffer[4] << 8) | buffer[5]
            
            add_message('RECV', f"[Node {yaskawa_id}] WRITE Reg 0x{reg_addr:04X} = {value}")
            
            # Store value (never allow fault bit in status reg 0; never overwrite A1000 identification)
            A1000_ID_REGISTERS = (0x00F0, 0x00F1, 0x00F2)  # read-only: drive type, software version, option
            if reg_addr == 0:
                value = value & ~YASKAWA_STATUS_FAULT_BIT
            if reg_addr < len(registers) and reg_addr not in A1000_ID_REGISTERS:
                registers[reg_addr] = value
            
            # Update status if command word (never set fault bit - HMI shows faulted if bit 3 set)
            if reg_addr == 0x0001:
                status = 0x0001  # Drive Ready
                if value & 0x01:
                    status |= 0x0002  # Running
                if value & 0x02:
                    status |= 0x0004  # Reverse
                status |= 0x0020  # At frequency
                registers[0x0000] = status & ~YASKAWA_STATUS_FAULT_BIT  # Standard MEMOBUS status
                # Sullair WS Controller reads 0x0020 for status (not 0x0000)
                registers[0x0020] = status & ~YASKAWA_STATUS_FAULT_BIT  # Sullair-specific status
            
            # Decode and log
            decoded = decode_yaskawa_command(reg_addr, value, is_write=True)
            add_message('DECODE', f"  -> {decoded.get('register_name', 'UNK')}: {decoded.get('calculated_value', decoded.get('description', 'N/A'))}")
            
            # Redirect: translate Yaskawa A1000 commands to WEG CFW-11 and queue
            translate_to_weg(reg_addr, value, weg_id)
            
            # Build echo response (same as request)
            resp = bytearray([slave_id, func_code])
            resp.extend(buffer[2:6])  # Echo register and value
            crc = calculate_crc(resp)
            resp.extend([crc & 0xFF, (crc >> 8) & 0xFF])
            response = bytes(resp)
            
    elif func_code == 0x10:  # Write Multiple Registers
        if len(buffer) >= 7:
            byte_count = buffer[6]
            frame_len = 9 + byte_count
            if len(buffer) >= frame_len:
                # Verify CRC
                if not verify_crc(buffer[:frame_len]):
                    add_message('ERROR', f"CRC error on received frame")
                    return buffer[:frame_len], None, registers
                
                start_addr = (buffer[2] << 8) | buffer[3]
                count = (buffer[4] << 8) | buffer[5]
                
                add_message('RECV', f"[Node {yaskawa_id}] WRITE MULT Reg 0x{start_addr:04X} x{count}")
                
                # Store values (never allow fault bit in status; never overwrite A1000 identification)
                A1000_ID_REGISTERS = (0x00F0, 0x00F1, 0x00F2)
                for i in range(count):
                    addr = start_addr + i
                    val = (buffer[7 + i*2] << 8) | buffer[8 + i*2]
                    if addr == 0:
                        val = val & ~YASKAWA_STATUS_FAULT_BIT  # Status: clear fault bit
                    if addr < len(registers) and addr not in A1000_ID_REGISTERS:
                        registers[addr] = val
                    
                    # Update Sullair-specific status register if command word is written
                    if addr == 0x0001:
                        status = 0x0001  # Drive Ready
                        if val & 0x01:
                            status |= 0x0002  # Running
                        if val & 0x02:
                            status |= 0x0004  # Reverse
                        status |= 0x0020  # At frequency
                        registers[0x0000] = status & ~YASKAWA_STATUS_FAULT_BIT
                        registers[0x0020] = status & ~YASKAWA_STATUS_FAULT_BIT  # Sullair reads 0x0020
                    
                    decoded = decode_yaskawa_command(addr, val, is_write=True)
                    add_message('DECODE', f"  0x{addr:04X}={val} ({decoded.get('register_name', 'UNK')})")
                    
                    # Redirect: translate each Yaskawa register to WEG CFW-11 (skip read-only id regs)
                    if addr not in A1000_ID_REGISTERS:
                        translate_to_weg(addr, val, weg_id)
                
                # Build response (echo address and count only)
                resp = bytearray([slave_id, func_code])
                resp.extend(buffer[2:6])  # Echo start addr and count
                crc = calculate_crc(resp)
                resp.extend([crc & 0xFF, (crc >> 8) & 0xFF])
                response = bytes(resp)
    else:
        # Unsupported function code
        add_message('WARNING', f"[Node {yaskawa_id}] Unsupported FC 0x{func_code:02X}")
        # Return exception response
        resp = bytearray([slave_id, func_code | 0x80, 0x01])  # Exception: Illegal Function
        crc = calculate_crc(resp)
        resp.extend([crc & 0xFF, (crc >> 8) & 0xFF])
        response = bytes(resp)
        frame_len = len(buffer)  # Clear whole buffer
    
    return buffer[:frame_len] if frame_len > 0 else None, response, registers

def translate_to_weg(yaskawa_reg, value, weg_id):
    """Translate Yaskawa register write to WEG command
    
    WEG CFW-11 P0682 Control Word bits:
        Bit 0: Start/Stop (0=stop with ramp, 1=run)
        Bit 1: General Enable (0=disable inverter, 1=enable)
        Bit 2: Direction (0=reverse, 1=forward)
        Bit 3: JOG
        Bit 4: LOC/REM (0=local, 1=remote) - MUST be 1 for serial control!
        Bit 5: Second Ramp
        Bit 6: Quick Stop
        Bit 7: Fault Reset
    
    Yaskawa command word bits:
        Bit 0: RUN/STOP
        Bit 1: Direction (0=FWD, 1=REV)
        
    Common Yaskawa frequency register variations:
        0x0002: Frequency Reference (standard)
        0x0009: Motor Speed (some controllers)
        0x0102: Frequency Command (alternate)
    """
    # Log ALL incoming writes for debugging
    add_message('DEBUG', f"translate_to_weg: Reg=0x{yaskawa_reg:04X}, Value={value} (0x{value:04X})")
    
    if yaskawa_reg == 0x0001:  # Command word -> P0682
        # Translate Yaskawa command bits to WEG control word
        weg_control = 0x0010  # Always set bit 4 (Remote mode) for serial control
        
        # Yaskawa Bit 0 (RUN) -> WEG Bit 0 (Start/Stop) + Bit 1 (General Enable)
        if value & 0x01:  # RUN command
            weg_control |= 0x0003  # Set Start/Stop (bit 0) + General Enable (bit 1)
        
        # Yaskawa Bit 1 (Direction: 0=FWD, 1=REV) -> WEG Bit 2 (Direction: 0=REV, 1=FWD)
        # Note: WEG direction is inverted from Yaskawa!
        if not (value & 0x02):  # Yaskawa FWD (bit1=0) -> WEG FWD (bit2=1)
            weg_control |= 0x0004
        # else: Yaskawa REV (bit1=1) -> WEG REV (bit2=0) - already 0
        
        # Yaskawa Bit 3 (Fault Reset) -> WEG Bit 7 (Fault Reset)
        if value & 0x08:
            weg_control |= 0x0080
        
        add_message('TRANSLATE', f"Yaskawa CMD 0x{value:04X} -> WEG P0682 = 0x{weg_control:04X}")
        add_message('DECODE', f"  WEG: {'RUN' if weg_control & 0x01 else 'STOP'}, {'GEN_EN' if weg_control & 0x02 else 'DIS'}, {'FWD' if weg_control & 0x04 else 'REV'}, {'REMOTE' if weg_control & 0x10 else 'LOCAL'}")
        queue_weg_command(682, weg_control, "CONTROL")
        
    elif yaskawa_reg == 0x0002:  # Frequency Reference -> P0683
        # Yaskawa: 0-6000 = 0-60.00Hz (value / 100 = Hz)
        # WEG P0683: 13-bit scale where 8192 = motor sync frequency (WEG_MAX_FREQ_HZ)
        yaskawa_max = config.get('MAX_FREQ', 6000)  # Yaskawa scale (6000 = 60.00 Hz)
        weg_max_hz = config.get('WEG_MAX_FREQ_HZ', 60.0)  # WEG motor max freq
        
        # Convert Yaskawa value to Hz
        freq_hz = value / 100.0
        
        # Convert Hz to WEG 13-bit scale (8192 = weg_max_hz)
        val_weg = int((freq_hz / weg_max_hz) * 8192)
        
        add_message('TRANSLATE', f"Yaskawa 0x0002={value} -> {freq_hz:.2f}Hz -> WEG P0683={val_weg} (max={weg_max_hz}Hz)")
        queue_weg_command(683, val_weg, f"SPEED {freq_hz:.1f}Hz")
        
    elif yaskawa_reg == 0x0009:  # Motor Speed (RPM) - some controllers use this
        # If sending RPM directly, convert: assuming 1800 RPM = 8192
        sync_rpm = 1800  # 4-pole 60Hz motor
        val_weg = int((value / sync_rpm) * 8192)
        add_message('TRANSLATE', f"Yaskawa SPEED 0x0009={value}RPM -> WEG P0683={val_weg}")
        queue_weg_command(683, val_weg, f"SPEED {value}RPM")
        
    elif yaskawa_reg == 0x0102 or yaskawa_reg == 0x0202:  # Alternate frequency registers
        # Some controllers use 0x0102 or 0x0202 for frequency
        freq_hz = value / 100.0
        val_weg = int((value / config['MAX_FREQ']) * 8192)
        add_message('TRANSLATE', f"Yaskawa ALT_FREQ 0x{yaskawa_reg:04X}={value} ({freq_hz:.2f}Hz) -> WEG P0683={val_weg}")
        queue_weg_command(683, val_weg, f"SPEED {freq_hz:.1f}Hz")
        
    elif yaskawa_reg >= 0x0020 and yaskawa_reg <= 0x002F:
        # Multi-speed presets or frequency limits - log but don't translate
        add_message('DEBUG', f"Freq limit/preset reg 0x{yaskawa_reg:04X}={value} (not translated)")
        
    else:
        add_message('DEBUG', f"No WEG translation for Yaskawa reg 0x{yaskawa_reg:04X}={value}")

_last_weg_poll_time = [0]  # Use list to avoid global declaration issues
_weg_heartbeat_count = [0]
_weg_heartbeat_ok = [0]
_weg_heartbeat_fail = [0]

def process_weg_queue_on_bus(ser, weg_id):
    """Process queued WEG commands on the shared serial bus.
    
    WEG CFW-11 A128 timeout occurs when P0314 (Serial Watchdog) is set and no valid
    Modbus frames are received within that time. Heartbeat reads P0680; interval must be < P0314.
    """
    global weg_command_queue
    
    # Heartbeat: Poll WEG regularly to prevent A128 timeout
    heartbeat_interval = config.get('HEARTBEAT_INTERVAL', 0.5)
    current_time = time.time()
    if current_time - _last_weg_poll_time[0] > heartbeat_interval:
        _last_weg_poll_time[0] = current_time
        _weg_heartbeat_count[0] += 1
        try:
            heartbeat_frame = build_modbus_read_frame(weg_id, 680, 1)
            hex_hb = ' '.join([f'{b:02X}' for b in heartbeat_frame])
            time.sleep(0.004)
            ser.reset_input_buffer()
            ser.write(heartbeat_frame)
            ser.flush()
            time.sleep(0.05)
            response = ser.read(32)
            if response and len(response) >= 5:
                _weg_heartbeat_ok[0] += 1
                if _weg_heartbeat_count[0] % 10 == 0 and response[0] == weg_id and response[1] == 0x03:
                    status = (response[3] << 8) | response[4]
                    status_str = []
                    if status & 0x0100: status_str.append("RUN")
                    if status & 0x0200: status_str.append("GEN_EN")
                    if status & 0x1000: status_str.append("REMOTE")
                    if status & 0x8000: status_str.append("FAULT")
                    if status & 0x0080: status_str.append("ALARM")
                    add_message('DEBUG', f"[WEG] Heartbeat #{_weg_heartbeat_count[0]}: P0680=0x{status:04X} ({', '.join(status_str) if status_str else 'STOPPED'})")
            else:
                _weg_heartbeat_fail[0] += 1
                if _weg_heartbeat_fail[0] <= 5 or _weg_heartbeat_fail[0] % 10 == 0:
                    add_message('WARNING', f"[WEG] Heartbeat #{_weg_heartbeat_count[0]} NO RESPONSE (fail {_weg_heartbeat_fail[0]}/{_weg_heartbeat_count[0]})")
                    add_message('DEBUG', f"[WEG] TX: {hex_hb}")
        except Exception as e:
            _weg_heartbeat_fail[0] += 1
            add_message('ERROR', f"[WEG] Heartbeat error: {str(e)}")
    
    with weg_queue_lock:
        if not weg_command_queue:
            return
        queue_len = len(weg_command_queue)
        cmd = weg_command_queue.pop(0)
    
    add_message('INFO', f"[Node {weg_id}] Processing queue ({queue_len} commands)")
    try:
        frame = build_modbus_write_frame(weg_id, cmd['register'], cmd['value'])
        hex_frame = ' '.join([f'{b:02X}' for b in frame])
        add_message('SEND', f"[Node {weg_id}] TX P{cmd['register']:04d}={cmd['value']}: {hex_frame}")
        ser.reset_input_buffer()
        bytes_sent = ser.write(frame)
        ser.flush()
        add_message('DEBUG', f"[Node {weg_id}] Sent {bytes_sent} bytes")
        time.sleep(0.15)
        response = ser.read(8)
        if response:
            hex_resp = ' '.join([f'{b:02X}' for b in response])
            if len(response) >= 2 and response[1] == 0x06:
                add_message('SUCCESS', f"[Node {weg_id}] RX OK: {hex_resp}")
            elif len(response) >= 2 and response[1] & 0x80:
                error_code = response[2] if len(response) > 2 else 0
                add_message('ERROR', f"[Node {weg_id}] Exception {error_code}: {hex_resp}")
            else:
                add_message('DEBUG', f"[Node {weg_id}] RX: {hex_resp}")
        else:
            add_message('WARNING', f"[Node {weg_id}] No response (check wiring/ID)")
            
    except Exception as e:
        add_message('ERROR', f"WEG TX error: {str(e)}")
        import traceback
        add_message('ERROR', traceback.format_exc())

# --- RAW SERIAL MONITOR ---
raw_monitor_running = False
raw_monitor_thread = None

def start_raw_monitor():
    """Start raw serial monitor to see any incoming data"""
    global raw_monitor_running, raw_monitor_thread
    
    if raw_monitor_running:
        add_message('WARNING', 'Raw monitor already running')
        return False
    
    raw_monitor_running = True
    raw_monitor_thread = threading.Thread(target=_raw_monitor_loop, daemon=True)
    raw_monitor_thread.start()
    return True

def stop_raw_monitor():
    """Stop the raw serial monitor"""
    global raw_monitor_running
    raw_monitor_running = False
    add_message('INFO', 'Raw monitor stopped')

def _raw_monitor_loop():
    """Monitor loop that reads raw serial data"""
    global raw_monitor_running
    
    try:
        # Open serial port directly
        ser = serial.Serial(
            port=config['PORT_CONTROLADOR'],
            baudrate=config['BAUD_RATE'],
            parity=config['PARITY'],
            stopbits=config['STOPBITS'],
            bytesize=config['BYTESIZE'],
            timeout=0.1
        )
        add_message('INFO', f"RAW MONITOR: Listening on {config['PORT_CONTROLADOR']} @ {config['BAUD_RATE']} baud")
        add_message('INFO', f"RAW MONITOR: Settings: {config['BYTESIZE']}{config['PARITY']}{config['STOPBITS']}")
        
        bytes_received = 0
        
        while raw_monitor_running:
            data = ser.read(256)  # Read up to 256 bytes
            if data:
                bytes_received += len(data)
                hex_data = ' '.join([f'{b:02X}' for b in data])
                
                # Try to decode as Modbus RTU
                modbus_info = decode_raw_modbus(data)
                
                add_message('RAW', f"Received {len(data)} bytes: {hex_data}")
                if modbus_info:
                    add_message('RAW', f"  -> {modbus_info}")
            
            time.sleep(0.01)
        
        ser.close()
        add_message('INFO', f"RAW MONITOR: Closed. Total bytes received: {bytes_received}")
        
    except Exception as e:
        add_message('ERROR', f"RAW MONITOR error: {str(e)}")
        raw_monitor_running = False

def decode_raw_modbus(data):
    """Try to decode raw bytes as Modbus RTU"""
    if len(data) < 4:
        return None
    
    slave_id = data[0]
    func_code = data[1]
    
    func_names = {
        1: 'Read Coils',
        2: 'Read Discrete Inputs',
        3: 'Read Holding Registers',
        4: 'Read Input Registers',
        5: 'Write Single Coil',
        6: 'Write Single Register',
        15: 'Write Multiple Coils',
        16: 'Write Multiple Registers',
    }
    
    func_name = func_names.get(func_code, f'Unknown FC{func_code}')
    
    if func_code in [3, 4] and len(data) >= 8:
        # Read request: Slave, FC, AddrHi, AddrLo, CountHi, CountLo, CRC, CRC
        addr = (data[2] << 8) | data[3]
        count = (data[4] << 8) | data[5]
        return f"Slave {slave_id}, {func_name}, Addr: {addr} (0x{addr:04X}), Count: {count}"
    
    elif func_code == 6 and len(data) >= 8:
        # Write single register: Slave, FC, AddrHi, AddrLo, ValueHi, ValueLo, CRC, CRC
        addr = (data[2] << 8) | data[3]
        value = (data[4] << 8) | data[5]
        return f"Slave {slave_id}, {func_name}, Addr: {addr} (0x{addr:04X}), Value: {value}"
    
    elif func_code == 16 and len(data) >= 9:
        # Write multiple registers
        addr = (data[2] << 8) | data[3]
        count = (data[4] << 8) | data[5]
        return f"Slave {slave_id}, {func_name}, Addr: {addr} (0x{addr:04X}), Count: {count}"
    
    return f"Slave {slave_id}, {func_name}"

# --- INICIALIZACIÓN DEL SERVIDOR (EL ENGAÑO) ---
server_thread = None
server_running = False

def run_gateway():
    """Start the Modbus gateway server"""
    global server_running, current_mode
    server_running = True
    
    single_bus = config.get('SINGLE_BUS_MODE', False) or (config['PORT_CONTROLADOR'] == config['PORT_WEG'])
    
    # In listen mode, we don't need WEG connection
    if current_mode == 'listen':
        add_message('INFO', f"LISTEN MODE: Starting Yaskawa listener on {config['PORT_CONTROLADOR']}")
        add_message('INFO', 'No WEG connection will be established - decode only')
        add_message('INFO', 'Simulating Yaskawa "Ready" status for controller')
    elif current_mode == 'command':
        add_message('INFO', f"COMMAND MODE: Direct WEG testing on {config['PORT_WEG']}")
        # Initialize WEG client for command mode
        if not init_weg_client():
            add_message('WARNING', 'WEG connection failed, will retry on first command')
    else:
        # REDIRECT MODE
        if single_bus:
            add_message('INFO', f"REDIRECT MODE (Single Bus): {config['PORT_CONTROLADOR']}")
            add_message('INFO', f"  Emulating Yaskawa at Node {config.get('YASKAWA_SLAVE_ID', 6)}")
            add_message('INFO', f"  Forwarding to WEG at Node {config.get('SLAVE_ID', 5)}")
            add_message('INFO', 'Using custom single-bus handler')
            # Use custom single bus handler instead of pymodbus server
            run_single_bus_gateway()
            return
        else:
            add_message('INFO', f"REDIRECT MODE (Dual Port)")
            add_message('INFO', f"  Listening on {config['PORT_CONTROLADOR']}")
            add_message('INFO', f"  Forwarding to WEG on {config['PORT_WEG']}")
            if not init_weg_client():
                add_message('WARNING', 'Starting anyway, will retry WEG connection on first command')
    
    # Pre-populate registers with simulated Yaskawa "ready" status
    # This makes the controller think a real drive is connected
    initial_values = [0] * 100
    
    # Register 0x0000 (Status Word) - Set bits to indicate drive is ready
    # Bit 0: Drive Ready = 1
    # Bit 5: At Frequency = 1 (not moving, at target)
    initial_values[0] = 0x0021  # Drive Ready + At Frequency
    
    # Register 0x0001 (Command Echo) - Start with stop command
    initial_values[1] = 0x0000
    
    # Register 0x0002 (Frequency Reference) - 0 Hz
    initial_values[2] = 0
    
    # Register 0x0003 (Output Frequency) - 0 Hz  
    initial_values[3] = 0
    
    # Register 0x0004 (Output Current) - 0 A
    initial_values[4] = 0
    
    # Register 0x0005 (Output Voltage) - Typical value
    initial_values[5] = 480
    
    # Register 0x0006 (DC Bus Voltage) - Typical value
    initial_values[6] = 650
    
    # Register 0x0009 (Motor Speed) - 0 RPM
    initial_values[9] = 0
    
    # Register 0x000F (Drive Temp) - 25 C
    initial_values[15] = 25
    
    # Ramp times (0x0010-0x0011) - 10.0 seconds
    initial_values[16] = 100  # Accel time x0.1s
    initial_values[17] = 100  # Decel time x0.1s
    
    # Frequency limits (0x0020-0x0021)
    initial_values[32] = 6000  # Upper limit 60.00 Hz
    initial_values[33] = 0     # Lower limit 0 Hz
    
    # Real Time Clock (0x0022-0x0027) - Current date/time
    from datetime import datetime as dt
    now = dt.now()
    initial_values[34] = now.year   # 0x0022 - Year
    initial_values[35] = now.month  # 0x0023 - Month
    initial_values[36] = now.day    # 0x0024 - Day
    initial_values[37] = now.hour   # 0x0025 - Hour
    initial_values[38] = now.minute # 0x0026 - Minute
    initial_values[39] = now.second # 0x0027 - Second
    
    # PID values (0x0030-0x0031)
    initial_values[48] = 0  # PID Setpoint
    initial_values[49] = 0  # PID Feedback
    
    # Creamos un bloque de registros de tipo Holding (4x)
    # El PLC escribirá en las direcciones 1 y 2
    store = ModbusSlaveContext(
        hr=YaskawaCallback(0x0000, initial_values),
        zero_mode=True
    )
    
    # If RESPOND_TO_ANY_ID is True, respond to all slave addresses (1-247)
    # This is useful for debugging when you don't know the expected slave ID
    if config.get('RESPOND_TO_ANY_ID', False):
        slaves_dict = {i: store for i in range(1, 248)}
        context = ModbusServerContext(slaves=slaves_dict, single=False)
        add_message('INFO', 'Server will respond to ANY slave ID (1-247) - Debug mode')
    else:
        context = ModbusServerContext(slaves={config['SLAVE_ID']: store}, single=False)
        add_message('INFO', f"Server responding to slave ID {config['SLAVE_ID']} only")

    try:
        # Arranca el puerto que escucha al PLC
        StartSerialServer(
            context=context, 
            port=config['PORT_CONTROLADOR'], 
            baudrate=config['BAUD_RATE'],
            parity=config['PARITY'],
            stopbits=config['STOPBITS'],
            bytesize=config['BYTESIZE'],
            framer='rtu'
        )
    except Exception as e:
        add_message('ERROR', f"Server error: {str(e)}")
        server_running = False

def start_server_thread():
    """Start server in a separate thread"""
    global server_thread
    if server_thread is None or not server_thread.is_alive():
        server_thread = threading.Thread(target=run_gateway, daemon=True)
        server_thread.start()
        return True
    return False

def stop_server():
    """Stop the server"""
    global server_running, weg_client
    server_running = False
    if weg_client:
        try:
            weg_client.close()
            add_message('INFO', 'WEG client closed')
        except:
            pass
    add_message('INFO', 'Server stopped')

if __name__ == "__main__":
    try:
        run_gateway()
    except KeyboardInterrupt:
        add_message('INFO', 'Shutting down...')
        stop_server()
