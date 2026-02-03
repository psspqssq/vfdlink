import logging
import threading
import time
from datetime import datetime
from pymodbus.server import StartSerialServer
from pymodbus.device import ModbusDeviceIdentification
from pymodbus.datastore import ModbusSequentialDataBlock, ModbusSlaveContext, ModbusServerContext
from pymodbus.client import ModbusSerialClient as ModbusClient

# --- CONFIGURACIÓN ---
config = {
    'PORT_CONTROLADOR': 'COM3',  # Adaptador FT232 conectado al Controlador
    'PORT_WEG': 'COM4',          # Adaptador FT232 conectado al WEG
    'BAUD_RATE': 9600,
    'PARITY': 'N',               # Parity: 'N'=None, 'E'=Even, 'O'=Odd (WEG default: None)
    'STOPBITS': 1,               # Stop bits: 1 or 2 (WEG default: 1)
    'BYTESIZE': 8,               # Data bits: 7 or 8 (WEG default: 8)
    'SLAVE_ID': 6,
    'MAX_FREQ': 6000,  # Máximo valor de frecuencia Yaskawa (0-60.00Hz)
}

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
        weg_client = ModbusClient(
            port=config['PORT_WEG'], 
            baudrate=config['BAUD_RATE'], 
            parity=config['PARITY'], 
            stopbits=config['STOPBITS'], 
            bytesize=config['BYTESIZE'], 
            timeout=1
        )
        if weg_client.connect():
            add_message('INFO', f"WEG client connected on {config['PORT_WEG']}")
            return True
        else:
            add_message('ERROR', f"Failed to connect WEG client on {config['PORT_WEG']}")
            return False
    except Exception as e:
        add_message('ERROR', f"Error initializing WEG client: {str(e)}")
        return False

# --- LÓGICA DE TRADUCCIÓN ---
class YaskawaCallback(ModbusSequentialDataBlock):
    """
    Esta clase intercepta las escrituras que el PLC hace al 'Yaskawa'
    y las traduce inmediatamente al formato del WEG CFW11.
    """
    def setValues(self, address, values):
        # Primero guardamos el valor en la memoria local (para que el PLC lo lea si quiere)
        super().setValues(address, values)
        
        reg_address = address 
        val = values[0] if values else 0

        # 1. TRADUCIR COMANDO DE MARCHA (Yaskawa Reg 0x0001)
        if reg_address == 0x0001:
            add_message('COMMAND', f"RUN/STOP command received: {val:#06x} ({val})")
            # Mapeo: Bit 0 en WEG P0682 es General Enable/Run
            self._write_to_weg(682, val, "RUN/STOP")

        # 2. TRADUCIR FRECUENCIA (Yaskawa Reg 0x0002)
        elif reg_address == 0x0002:
            # Yaskawa suele usar 0-6000 para 0-60.00Hz
            # WEG CFW11 usa 0-8192 para 0-100% de la velocidad
            freq_hz = val / 100.0
            val_weg = int((val / config['MAX_FREQ']) * 8192)
            add_message('COMMAND', f"Frequency: {freq_hz:.2f}Hz (raw: {val}) -> WEG value: {val_weg}")
            
            # Enviamos al registro 683 del WEG (Referencia de Velocidad)
            self._write_to_weg(683, val_weg, "FREQUENCY")
        
        else:
            add_message('DEBUG', f"Write to register {reg_address:#06x}: {val}")

    def _write_to_weg(self, register, value, command_name):
        """Thread-safe write to WEG with error handling"""
        with weg_lock:
            try:
                if weg_client is None or not weg_client.connected:
                    if not init_weg_client():
                        add_message('ERROR', f"Cannot write {command_name}: WEG client not connected")
                        return
                
                result = weg_client.write_register(register, value, slave=config['SLAVE_ID'])
                
                if result.isError():
                    add_message('ERROR', f"Failed to write {command_name} to WEG register {register}: {result}")
                else:
                    add_message('SUCCESS', f"Written to WEG P{register:04d}: {value} ({command_name})")
                    
            except Exception as e:
                add_message('ERROR', f"Exception writing {command_name} to WEG: {str(e)}")
                # Try to reconnect on next attempt
                if weg_client:
                    try:
                        weg_client.close()
                    except:
                        pass

# --- INICIALIZACIÓN DEL SERVIDOR (EL ENGAÑO) ---
server_thread = None
server_running = False

def run_gateway():
    """Start the Modbus gateway server"""
    global server_running
    server_running = True
    
    # Initialize WEG client
    if not init_weg_client():
        add_message('WARNING', 'Starting anyway, will retry WEG connection on first command')
    
    # Creamos un bloque de registros de tipo Holding (4x)
    # El PLC escribirá en las direcciones 1 y 2
    store = ModbusSlaveContext(
        hr=YaskawaCallback(0x0000, [0]*100), # Memoria de 100 registros
        zero_mode=True
    )
    context = ModbusServerContext(slaves=store, single=True)

    add_message('INFO', f"Starting Yaskawa emulator on {config['PORT_CONTROLADOR']}")
    add_message('INFO', f"Forwarding to WEG on {config['PORT_WEG']}")

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
