from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, emit
import threading
import time
import vfdserver

app = Flask(__name__)
app.config['SECRET_KEY'] = 'wegdrive-secret-key'
# Use threading mode instead of eventlet for Python 3.14 compatibility
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Thread for broadcasting messages
broadcast_thread = None
last_message_count = 0

def broadcast_messages():
    """Broadcast new messages to all connected clients"""
    global last_message_count
    while True:
        time.sleep(0.5)  # Check every 500ms
        current_count = len(vfdserver.recent_messages)
        if current_count > last_message_count:
            # Send new messages
            new_messages = vfdserver.recent_messages[last_message_count:]
            socketio.emit('new_messages', {'messages': new_messages})
            last_message_count = current_count
        elif current_count < last_message_count:
            # Messages were cleared
            last_message_count = current_count

@app.route('/')
def index():
    """Serve the main page"""
    return render_template('index.html')

@app.route('/api/config', methods=['GET'])
def get_config():
    """Get current configuration"""
    return jsonify({
        'success': True,
        'config': vfdserver.config,
        'server_running': vfdserver.server_running
    })

@app.route('/api/config', methods=['POST'])
def update_config():
    """Update configuration"""
    try:
        data = request.json
        
        # Update config - Serial settings
        if 'PORT_CONTROLADOR' in data:
            vfdserver.config['PORT_CONTROLADOR'] = data['PORT_CONTROLADOR']
        if 'PORT_WEG' in data:
            vfdserver.config['PORT_WEG'] = data['PORT_WEG']
        if 'BAUD_RATE' in data:
            vfdserver.config['BAUD_RATE'] = int(data['BAUD_RATE'])
        if 'PARITY' in data:
            vfdserver.config['PARITY'] = data['PARITY']
        if 'STOPBITS' in data:
            vfdserver.config['STOPBITS'] = int(data['STOPBITS'])
        if 'BYTESIZE' in data:
            vfdserver.config['BYTESIZE'] = int(data['BYTESIZE'])
        
        # Slave IDs
        if 'SLAVE_ID' in data:
            vfdserver.config['SLAVE_ID'] = int(data['SLAVE_ID'])
        if 'YASKAWA_SLAVE_ID' in data:
            vfdserver.config['YASKAWA_SLAVE_ID'] = int(data['YASKAWA_SLAVE_ID'])
        
        # Frequency settings
        if 'MAX_FREQ' in data:
            vfdserver.config['MAX_FREQ'] = int(data['MAX_FREQ'])
        
        # Bus mode settings
        if 'SINGLE_BUS_MODE' in data:
            vfdserver.config['SINGLE_BUS_MODE'] = bool(data['SINGLE_BUS_MODE'])
        if 'RESPOND_TO_ANY_ID' in data:
            vfdserver.config['RESPOND_TO_ANY_ID'] = bool(data['RESPOND_TO_ANY_ID'])
        if 'HEARTBEAT_INTERVAL' in data:
            vfdserver.config['HEARTBEAT_INTERVAL'] = float(data['HEARTBEAT_INTERVAL'])
        if 'WEG_MAX_FREQ_HZ' in data:
            vfdserver.config['WEG_MAX_FREQ_HZ'] = float(data['WEG_MAX_FREQ_HZ'])
        
        vfdserver.add_message('INFO', 'Configuration updated')
        
        return jsonify({
            'success': True,
            'message': 'Configuration updated successfully'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 400

@app.route('/api/messages', methods=['GET'])
def get_messages():
    """Get all recent messages"""
    return jsonify({
        'success': True,
        'messages': vfdserver.recent_messages
    })

@app.route('/api/messages/clear', methods=['POST'])
def clear_messages():
    """Clear all messages"""
    global last_message_count
    vfdserver.recent_messages.clear()
    last_message_count = 0
    return jsonify({
        'success': True,
        'message': 'Messages cleared'
    })

@app.route('/api/server/start', methods=['POST'])
def start_server():
    """Start the Modbus server"""
    try:
        if vfdserver.server_running:
            return jsonify({
                'success': False,
                'message': 'Server is already running'
            })
        
        success = vfdserver.start_server_thread()
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Server started successfully'
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Failed to start server'
            })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@app.route('/api/server/stop', methods=['POST'])
def stop_server():
    """Stop the Modbus server"""
    try:
        vfdserver.stop_server()
        return jsonify({
            'success': True,
            'message': 'Server stop signal sent'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@app.route('/api/status', methods=['GET'])
def get_status():
    """Get server status"""
    return jsonify({
        'success': True,
        'server_running': vfdserver.server_running,
        'message_count': len(vfdserver.recent_messages),
        'current_mode': vfdserver.get_mode()
    })

@app.route('/api/mode', methods=['GET'])
def get_mode():
    """Get current application mode"""
    return jsonify({
        'success': True,
        'mode': vfdserver.get_mode()
    })

@app.route('/api/mode', methods=['POST'])
def set_mode():
    """Set application mode: redirect, listen, or command"""
    try:
        data = request.json
        mode = data.get('mode', '').lower()
        
        if mode not in ['redirect', 'listen', 'command']:
            return jsonify({
                'success': False,
                'message': 'Invalid mode. Must be: redirect, listen, or command'
            }), 400
        
        if vfdserver.set_mode(mode):
            return jsonify({
                'success': True,
                'message': f'Mode set to {mode.upper()}',
                'mode': mode
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Failed to set mode'
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@app.route('/api/decoded', methods=['GET'])
def get_decoded():
    """Get decoded Yaskawa messages (for listen mode)"""
    return jsonify({
        'success': True,
        'decoded': vfdserver.decoded_messages
    })

@app.route('/api/decoded/clear', methods=['POST'])
def clear_decoded():
    """Clear decoded messages"""
    vfdserver.decoded_messages.clear()
    return jsonify({
        'success': True,
        'message': 'Decoded messages cleared'
    })

@app.route('/api/yaskawa/registers', methods=['GET'])
def get_yaskawa_registers():
    """Get Yaskawa register definitions for reference"""
    return jsonify({
        'success': True,
        'registers': {f'0x{k:04X}': v for k, v in vfdserver.YASKAWA_REGISTERS.items()},
        'command_bits': vfdserver.YASKAWA_COMMAND_BITS,
        'status_bits': vfdserver.YASKAWA_STATUS_BITS
    })

@app.route('/api/test/write', methods=['POST'])
def test_write():
    """Send a test write command directly to WEG"""
    try:
        data = request.json
        register = int(data.get('register'))
        value = int(data.get('value'))
        
        # Use WEG client to write directly
        if not vfdserver.weg_client or not vfdserver.weg_client.connected:
            if not vfdserver.init_weg_client():
                return jsonify({
                    'success': False,
                    'message': 'WEG client not connected'
                }), 400
        
        with vfdserver.weg_lock:
            result = vfdserver.weg_client.write_register(
                register, 
                value, 
                slave=vfdserver.config['SLAVE_ID']
            )
            
            if result.isError():
                vfdserver.add_message('ERROR', f'Test write failed: Register {register} = {value}')
                return jsonify({
                    'success': False,
                    'message': f'Modbus error: {result}'
                }), 400
            else:
                vfdserver.add_message('SUCCESS', f'Test write: P{register:04d} = {value}')
                return jsonify({
                    'success': True,
                    'message': f'Successfully wrote {value} to P{register:04d}'
                })
                
    except Exception as e:
        vfdserver.add_message('ERROR', f'Test write exception: {str(e)}')
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@app.route('/api/test/read', methods=['POST'])
def test_read():
    """Send a test read command to WEG"""
    try:
        data = request.json
        register = int(data.get('register'))
        func_code = data.get('func_code', 3)  # 3=holding, 4=input registers
        
        # Use WEG client to read directly
        if not vfdserver.weg_client or not vfdserver.weg_client.connected:
            if not vfdserver.init_weg_client():
                return jsonify({
                    'success': False,
                    'message': 'WEG client not connected'
                }), 400
        
        with vfdserver.weg_lock:
            if func_code == 4:
                # Read input registers (function code 04)
                result = vfdserver.weg_client.read_input_registers(
                    register, 
                    1, 
                    slave=vfdserver.config['SLAVE_ID']
                )
                reg_type = "Input"
            else:
                # Read holding registers (function code 03)
                result = vfdserver.weg_client.read_holding_registers(
                    register, 
                    1, 
                    slave=vfdserver.config['SLAVE_ID']
                )
                reg_type = "Holding"
            
            if result.isError():
                vfdserver.add_message('ERROR', f'Test read failed: {reg_type} Register {register} - {result}')
                return jsonify({
                    'success': False,
                    'message': f'Modbus error (FC{func_code}): {result}'
                }), 400
            else:
                value = result.registers[0]
                vfdserver.add_message('INFO', f'Test read: P{register:04d} = {value} ({reg_type} FC{func_code})')
                return jsonify({
                    'success': True,
                    'message': f'Read P{register:04d} = {value} (FC{func_code})',
                    'value': value,
                    'func_code': func_code
                })
                
    except Exception as e:
        vfdserver.add_message('ERROR', f'Test read exception: {str(e)}')
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@app.route('/api/reconnect', methods=['POST'])
def reconnect():
    """Force reconnect to WEG with current settings"""
    try:
        if vfdserver.reconnect_weg_client():
            return jsonify({
                'success': True,
                'message': 'Reconnected to WEG successfully'
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Failed to reconnect'
            }), 400
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@app.route('/api/raw_monitor/start', methods=['POST'])
def start_raw_monitor():
    """Start raw serial monitor for debugging"""
    try:
        if vfdserver.start_raw_monitor():
            return jsonify({
                'success': True,
                'message': 'Raw serial monitor started'
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Monitor already running or failed to start'
            }), 400
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@app.route('/api/raw_monitor/stop', methods=['POST'])
def stop_raw_monitor():
    """Stop raw serial monitor"""
    try:
        vfdserver.stop_raw_monitor()
        return jsonify({
            'success': True,
            'message': 'Raw serial monitor stopped'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@app.route('/api/raw_monitor/status', methods=['GET'])
def raw_monitor_status():
    """Get raw monitor status"""
    return jsonify({
        'success': True,
        'running': vfdserver.raw_monitor_running
    })

@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    print('Client connected')
    emit('connection_response', {'status': 'connected'})

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    print('Client disconnected')

if __name__ == '__main__':
    # Start broadcast thread
    broadcast_thread = threading.Thread(target=broadcast_messages, daemon=True)
    broadcast_thread.start()
    
    print("Starting Web Interface on http://localhost:5000")
    socketio.run(app, debug=True, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)

