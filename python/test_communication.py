#!/usr/bin/env python3
"""
Test script to isolate the Java-Python communication issue
"""

import socket
import json
import threading
import time

def test_python_client():
    """Test Python acting as client connecting to Java server"""
    print("Python: Attempting to connect to Java server on localhost:12345...")
    
    try:
        # Connect to Java server
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(('localhost', 12345))
        print("Python: Connected successfully!")
        
        # Start message receiving thread
        def receive_messages():
            buffer = ""
            while True:
                try:
                    data = sock.recv(1024).decode()
                    if not data:
                        break
                    
                    buffer += data
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        if line.strip():
                            print(f"Python: Received: {line.strip()}")
                            
                            try:
                                message = json.loads(line)
                                if message.get("type") == "decision_request":
                                    print("Python: Received decision request, sending response...")
                                    
                                    # Send response
                                    response = {
                                        "type": "decision_response",
                                        "success": True,
                                        "decision": {
                                            "chosenIndices": [0],
                                            "additionalData": {}
                                        }
                                    }
                                    response_json = json.dumps(response) + "\n"
                                    sock.sendall(response_json.encode())
                                    print(f"Python: Sent response: {response}")
                                    
                            except json.JSONDecodeError as e:
                                print(f"Python: JSON decode error: {e}")
                                
                except Exception as e:
                    print(f"Python: Receive error: {e}")
                    break
        
        # Start receiver thread
        receiver = threading.Thread(target=receive_messages, daemon=True)
        receiver.start()
        
        # Keep connection alive
        print("Python: Listening for messages... (waiting 30 seconds)")
        time.sleep(30)
        
        sock.close()
        print("Python: Disconnected")
        
    except Exception as e:
        print(f"Python: Connection error: {e}")

if __name__ == "__main__":
    test_python_client()