#!/usr/bin/env python3
from flask import Flask, jsonify, request, render_template_string
import subprocess
import json
import os
import time
import random
from datetime import datetime

app = Flask(__name__)

# Configuration
UNITY_SERVER_HOST = "localhost"
UNITY_SERVER_PORT = 7777

# File paths for communication with Unity - FIXED FOR WSL
STATUS_FILE_PATH = "/tmp/unity-traffic/traffic_system_status.json"
COMMANDS_DIR = "/tmp/unity-traffic/commands/"

# Create directories if they don't exist
os.makedirs(os.path.dirname(STATUS_FILE_PATH), exist_ok=True)
os.makedirs(COMMANDS_DIR, exist_ok=True)

def send_unity_command(light_id, action, **kwargs):
    """Send a command to Unity traffic light via JSON file"""
    try:
        command = {
            "action": action,
            "timestamp": int(time.time() * 1000),
            **kwargs
        }
        
        command_file = os.path.join(COMMANDS_DIR, f"{light_id}_command.json")
        with open(command_file, 'w') as f:
            json.dump(command, f)
        
        print(f"Command sent to Unity: {light_id} - {action}")
        return True
    except Exception as e:
        print(f"Error sending command to Unity: {e}")
        return False

def get_traffic_system_status():
    """Get current traffic system status from Unity manager"""
    try:
        if os.path.exists(STATUS_FILE_PATH):
            with open(STATUS_FILE_PATH, 'r') as f:
                return json.load(f)
        return None
    except Exception as e:
        print(f"Error reading traffic system status: {e}")
        return None

def get_all_light_ids():
    """Get all available traffic light IDs"""
    try:
        system_data = get_traffic_system_status()
        if system_data and 'lights' in system_data:
            return [light['id'] for light in system_data['lights']]
        return []
    except Exception as e:
        print(f"Error getting light IDs: {e}")
        return []

# ==================== API ENDPOINTS ====================

@app.route('/api/status', methods=['GET'])
def get_status():
    """Get Unity traffic system status"""
    try:
        result = subprocess.run(['pgrep', '-f', 'server.x86_64'], 
                              capture_output=True, text=True)
        is_running = len(result.stdout.strip()) > 0
        
        system_data = get_traffic_system_status()
        
        return jsonify({
            "status": "running" if is_running else "stopped",
            "server": "local",
            "timestamp": datetime.now().isoformat(),
            "unity_host": UNITY_SERVER_HOST,
            "unity_port": UNITY_SERVER_PORT,
            "traffic_system_connected": system_data is not None,
            "total_lights": system_data.get('totalLights', 0) if system_data else 0,
            "detection_method": "pgrep"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/traffic/lights', methods=['GET'])
def get_traffic_lights():
    """Get all traffic lights status from Unity Manager"""
    try:
        system_data = get_traffic_system_status()
        
        if system_data:
            return jsonify({
                "lights": system_data.get('lights', []),
                "source": "unity_manager",
                "file_path": STATUS_FILE_PATH,
                "timestamp": system_data.get('timestamp', datetime.now().isoformat()),
                "total_lights": system_data.get('totalLights', 0),
                "system_active": system_data.get('systemActive', False),
                "integration_status": "connected"
            })
        else:
            return jsonify({
                "error": "Unity traffic system not found",
                "expected_file": STATUS_FILE_PATH,
                "unity_running": False,
                "integration_status": "disconnected"
            })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/traffic/lights/list', methods=['GET'])
def list_all_lights():
    """Get list of all available light IDs"""
    try:
        light_ids = get_all_light_ids()
        return jsonify({
            "light_ids": light_ids,
            "total_lights": len(light_ids),
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/traffic/lights/<light_id>/set', methods=['POST'])
def set_traffic_light(light_id):
    """Set traffic light status"""
    try:
        data = request.get_json()
        new_status = data.get('status', 'green').lower()
        
        if new_status not in ['red', 'yellow', 'green']:
            return jsonify({"error": "Invalid status. Use: red, yellow, green"}), 400
        
        success = send_unity_command(light_id, "set_status", status=new_status)
        
        if success:
            return jsonify({
                "message": f"Traffic light {light_id} set to {new_status}",
                "light_id": light_id,
                "status": new_status,
                "success": True,
                "method": "unity_command_file",
                "timestamp": datetime.now().isoformat()
            })
        else:
            return jsonify({"error": "Failed to send command to Unity"}), 500
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/traffic/lights/<light_id>/mode', methods=['POST'])
def set_traffic_light_mode(light_id):
    """Set traffic light control mode"""
    try:
        data = request.get_json()
        mode = data.get('mode', 'automatic').lower()
        
        if mode not in ['automatic', 'manual', 'api_controlled']:
            return jsonify({"error": "Invalid mode. Use: automatic, manual, api_controlled"}), 400
        
        success = send_unity_command(light_id, "set_mode", mode=mode)
        
        if success:
            return jsonify({
                "message": f"Traffic light {light_id} mode set to {mode}",
                "light_id": light_id,
                "mode": mode,
                "success": True,
                "timestamp": datetime.now().isoformat()
            })
        else:
            return jsonify({"error": "Failed to send command to Unity"}), 500
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/traffic/lights/bulk/mode', methods=['POST'])
def set_all_lights_mode():
    """Set all traffic lights to a specific mode"""
    try:
        data = request.get_json()
        mode = data.get('mode', 'manual').lower()
        
        if mode not in ['automatic', 'manual', 'api_controlled']:
            return jsonify({"error": "Invalid mode. Use: automatic, manual, api_controlled"}), 400
        
        light_ids = get_all_light_ids()
        if not light_ids:
            return jsonify({"error": "No traffic lights found"}), 404
        
        successful_lights = []
        failed_lights = []
        
        for light_id in light_ids:
            if send_unity_command(light_id, "set_mode", mode=mode):
                successful_lights.append(light_id)
            else:
                failed_lights.append(light_id)
        
        return jsonify({
            "message": f"Bulk mode change to {mode}",
            "mode": mode,
            "total_lights": len(light_ids),
            "successful_lights": successful_lights,
            "failed_lights": failed_lights,
            "success_count": len(successful_lights),
            "success": len(failed_lights) == 0,
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/traffic/attack/chaos', methods=['POST'])
def chaos_attack():
    """CYBERSECURITY DEMO: Simulate a traffic light hacking attack"""
    try:
        data = request.get_json()
        attack_type = data.get('type', 'random_lights')
        duration = data.get('duration', 10)
        
        light_ids = get_all_light_ids()
        if not light_ids:
            return jsonify({"error": "No traffic lights found"}), 404
        
        print(f"CHAOS ATTACK INITIATED: {attack_type} for {duration}s on {len(light_ids)} lights")
        
        if attack_type == 'random_lights':
            affected_lights = []
            statuses = ['red', 'yellow', 'green']
            
            for light_id in light_ids:
                random_status = random.choice(statuses)
                if send_unity_command(light_id, "set_mode", mode="api_controlled"):
                    if send_unity_command(light_id, "set_status", status=random_status):
                        affected_lights.append(light_id)
            
            return jsonify({
                "message": f"CHAOS ATTACK INITIATED: {attack_type}",
                "attack_type": attack_type,
                "target_lights": affected_lights,
                "total_lights_affected": len(affected_lights),
                "duration": duration,
                "warning": "This is a cybersecurity demonstration",
                "success": True,
                "attack_id": int(time.time())
            })
            
        elif attack_type == 'all_red':
            affected_lights = []
            for light_id in light_ids:
                if send_unity_command(light_id, "set_mode", mode="api_controlled"):
                    if send_unity_command(light_id, "set_status", status="red"):
                        affected_lights.append(light_id)
            
            return jsonify({
                "message": "TRAFFIC JAM ATTACK: All lights set to RED",
                "attack_type": attack_type,
                "affected_lights": affected_lights,
                "total_lights_affected": len(affected_lights),
                "success": True
            })
            
        elif attack_type == 'all_green':
            affected_lights = []
            for light_id in light_ids:
                if send_unity_command(light_id, "set_mode", mode="api_controlled"):
                    if send_unity_command(light_id, "set_status", status="green"):
                        affected_lights.append(light_id)
            
            return jsonify({
                "message": "DANGEROUS INTERSECTION ATTACK: All lights set to GREEN",
                "attack_type": attack_type,
                "affected_lights": affected_lights,
                "total_lights_affected": len(affected_lights),
                "success": True,
                "warning": "EXTREMELY DANGEROUS: This would cause accidents in real traffic"
            })
            
        else:
            return jsonify({"error": "Unknown attack type. Use: random_lights, all_red, all_green"}), 400
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/traffic/restore', methods=['POST'])
def restore_normal_operation():
    """Restore normal traffic light operation after attack"""
    try:
        light_ids = get_all_light_ids()
        if not light_ids:
            return jsonify({"error": "No traffic lights found"}), 404
        
        restored_lights = []
        for light_id in light_ids:
            if send_unity_command(light_id, "set_mode", mode="automatic"):
                restored_lights.append(light_id)
        
        print(f"SYSTEM RESTORED: {len(restored_lights)} lights restored to automatic mode")
        
        return jsonify({
            "message": "Traffic system restored to normal operation",
            "restored_lights": restored_lights,
            "total_lights_restored": len(restored_lights),
            "mode": "automatic",
            "success": True,
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/dashboard', methods=['GET'])
def dashboard():
    """Web-based traffic control dashboard"""
    dashboard_html = """
<!DOCTYPE html>
<html>
<head>
    <title>Traffic System Control Dashboard</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #1a1a1a; color: #fff; }
        .container { max-width: 1400px; margin: 0 auto; }
        .header { text-align: center; margin-bottom: 30px; }
        .header h1 { color: #ff6b35; }
        .status-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 15px; margin-bottom: 30px; }
        .light-card { background: #2d2d2d; border: 2px solid #444; border-radius: 8px; padding: 15px; }
        .light-status { font-weight: bold; font-size: 18px; }
        .status-red { color: #ff4444; }
        .status-yellow { color: #ffaa00; }
        .status-green { color: #44ff44; }
        .controls { background: #333; padding: 20px; border-radius: 8px; margin-bottom: 20px; }
        .control-group { margin-bottom: 15px; }
        .button { background: #ff6b35; color: white; border: none; padding: 10px 20px; margin: 5px; border-radius: 5px; cursor: pointer; }
        .button:hover { background: #ff8555; }
        .danger-button { background: #dc2626; }
        .danger-button:hover { background: #ef4444; }
        .success-button { background: #16a34a; }
        .success-button:hover { background: #22c55e; }
        select, input { padding: 8px; margin: 5px; border-radius: 4px; border: 1px solid #555; background: #444; color: #fff; }
        .status-indicator { font-size: 14px; margin-top: 10px; padding: 5px; border-radius: 3px; }
        .connected { background: #16a34a; }
        .disconnected { background: #dc2626; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Traffic System Control Dashboard</h1>
            <h2>Cybersecurity Demo</h2>
            <p id="connectionStatus">Checking connection...</p>
        </div>
        
        <div class="controls">
            <h3>Quick Actions</h3>
            <div class="control-group">
                <button class="button success-button" onclick="setAllMode('manual')">Set All to Manual Mode</button>
                <button class="button success-button" onclick="setAllMode('automatic')">Set All to Automatic Mode</button>
                <button class="button" onclick="updateStatus()">Refresh Status</button>
            </div>
            
            <h3>Cyber Attack Simulations</h3>
            <div class="control-group">
                <button class="button danger-button" onclick="chaosAttack()">Chaos Attack (Random Lights)</button>
                <button class="button danger-button" onclick="jamAttack()">Traffic Jam Attack (All Red)</button>
                <button class="button danger-button" onclick="dangerousAttack()">Dangerous Attack (All Green)</button>
                <button class="button success-button" onclick="restore()">Restore Normal Operation</button>
            </div>
            
            <h3>Individual Light Control</h3>
            <div class="control-group">
                <select id="lightSelector">
                    <option value="">Select Light...</option>
                </select>
                <button class="button" onclick="setLight('red')">Set RED</button>
                <button class="button" onclick="setLight('yellow')">Set YELLOW</button>
                <button class="button" onclick="setLight('green')">Set GREEN</button>
            </div>
        </div>
        
        <h3>System Status</h3>
        <div id="systemStatus" class="status-grid">
            Loading...
        </div>
    </div>

    <script>
        async function updateStatus() {
            try {
                const response = await fetch('/api/traffic/lights');
                const data = await response.json();
                
                document.getElementById('connectionStatus').innerHTML = 
                    `<div class="status-indicator connected">Connected - ${data.total_lights} lights found</div>`;
                
                const statusDiv = document.getElementById('systemStatus');
                const lightSelector = document.getElementById('lightSelector');
                
                if (data.lights && data.lights.length > 0) {
                    statusDiv.innerHTML = data.lights.map(light => `
                        <div class="light-card">
                            <div class="light-status status-${light.status}">${light.id}</div>
                            <div>Status: <span class="status-${light.status}">${light.status.toUpperCase()}</span></div>
                            <div>Mode: ${light.controlMode}</div>
                            <div>Position: (${light.position.x.toFixed(1)}, ${light.position.y.toFixed(1)}, ${light.position.z.toFixed(1)})</div>
                            <div>Intersection: ${light.intersection}</div>
                            <div>Duration: ${light.greenDuration}s</div>
                        </div>
                    `).join('');
                    
                    lightSelector.innerHTML = '<option value="">Select Light...</option>' +
                        data.lights.map(light => `<option value="${light.id}">${light.id}</option>`).join('');
                } else {
                    statusDiv.innerHTML = '<div class="light-card">No traffic lights found</div>';
                }
            } catch (error) {
                document.getElementById('connectionStatus').innerHTML = 
                    `<div class="status-indicator disconnected">Connection Failed</div>`;
                document.getElementById('systemStatus').innerHTML = 
                    `<div class="light-card">Error: ${error.message}</div>`;
            }
        }
        
        async function setAllMode(mode) {
            try {
                const response = await fetch('/api/traffic/lights/bulk/mode', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({mode: mode})
                });
                
                const data = await response.json();
                if (data.success) {
                    alert(`All lights set to ${mode.toUpperCase()} mode (${data.success_count}/${data.total_lights})`);
                    updateStatus();
                } else {
                    alert(`Partial success: ${data.success_count}/${data.total_lights} lights updated`);
                }
            } catch (error) {
                alert('Connection error: ' + error.message);
            }
        }
        
        async function setLight(status) {
            const selectedLight = document.getElementById('lightSelector').value;
            if (!selectedLight) {
                alert('Please select a light first');
                return;
            }
            
            try {
                const response = await fetch(`/api/traffic/lights/${selectedLight}/set`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({status: status})
                });
                
                const data = await response.json();
                if (data.success) {
                    alert(`Traffic light ${selectedLight} set to ${status.toUpperCase()}`);
                    // Immediately refresh to show change
                    setTimeout(updateStatus, 500);
                } else {
                    alert('Error: ' + data.error);
                }
            } catch (error) {
                alert('Connection error: ' + error.message);
            }
        }
        
        async function chaosAttack() {
            if (!confirm('This will cause chaotic traffic light behavior! Continue?')) return;
            
            try {
                const response = await fetch('/api/traffic/attack/chaos', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({type: 'random_lights', duration: 30})
                });
                
                const data = await response.json();
                if (data.success) {
                    alert(`CHAOS ATTACK INITIATED! ${data.total_lights_affected} lights randomized.`);
                    setTimeout(updateStatus, 1000);
                } else {
                    alert('Attack failed: ' + data.error);
                }
            } catch (error) {
                alert('Connection error: ' + error.message);
            }
        }
        
        async function jamAttack() {
            if (!confirm('This will cause a traffic jam! Continue?')) return;
            
            try {
                const response = await fetch('/api/traffic/attack/chaos', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({type: 'all_red', duration: 30})
                });
                
                const data = await response.json();
                if (data.success) {
                    alert(`TRAFFIC JAM ATTACK! ${data.total_lights_affected} lights stuck on RED.`);
                    setTimeout(updateStatus, 1000);
                } else {
                    alert('Attack failed: ' + data.error);
                }
            } catch (error) {
                alert('Connection error: ' + error.message);
            }
        }
        
        async function dangerousAttack() {
            if (!confirm('DANGER: This simulates a potentially deadly attack! Continue?')) return;
            
            try {
                const response = await fetch('/api/traffic/attack/chaos', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({type: 'all_green', duration: 30})
                });
                
                const data = await response.json();
                if (data.success) {
                    alert(`DANGEROUS ATTACK! ${data.total_lights_affected} lights set to GREEN - would cause accidents!`);
                    setTimeout(updateStatus, 1000);
                } else {
                    alert('Attack failed: ' + data.error);
                }
            } catch (error) {
                alert('Connection error: ' + error.message);
            }
        }
        
        async function restore() {
            try {
                const response = await fetch('/api/traffic/restore', {method: 'POST'});
                const data = await response.json();
                
                if (data.success) {
                    alert(`Traffic system restored! ${data.total_lights_restored} lights back to automatic mode.`);
                    setTimeout(updateStatus, 1000);
                } else {
                    alert('Restore failed: ' + data.error);
                }
            } catch (error) {
                alert('Connection error: ' + error.message);
            }
        }
        
        // Update status every 2 seconds
        setInterval(updateStatus, 2000);
        updateStatus(); // Initial load
    </script>
</body>
</html>
    """
    return render_template_string(dashboard_html)

@app.route('/', methods=['GET'])
def index():
    """API documentation"""
    return jsonify({
        "api": "Unity Traffic System Control API",
        "version": "2.0",
        "description": "Cybersecurity-focused traffic system with attack simulation capabilities",
        "dashboard": "http://localhost:5000/dashboard",
        "endpoints": [
            "GET /api/status - Get system status",
            "GET /api/traffic/lights - Get all traffic lights status",
            "GET /api/traffic/lights/list - Get light IDs only",
            "POST /api/traffic/lights/<id>/set - Set traffic light status",
            "POST /api/traffic/lights/<id>/mode - Set control mode",
            "POST /api/traffic/lights/bulk/mode - Set all lights mode",
            "POST /api/traffic/attack/chaos - Simulate cyber attacks",
            "POST /api/traffic/restore - Restore normal operation",
            "GET /dashboard - Web control interface"
        ]
    })

if __name__ == '__main__':
    print("Starting Unity Traffic System API...")
    print(f"API Documentation: http://localhost:5000/")
    print(f"Control Dashboard: http://localhost:5000/dashboard")
    print(f"Status File: {STATUS_FILE_PATH}")
    print(f"Command Directory: {COMMANDS_DIR}")
    print("Ready for cybersecurity demonstrations!")
    print("")
    app.run(host='0.0.0.0', port=5000, debug=True)