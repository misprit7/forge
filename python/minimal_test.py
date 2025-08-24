#!/usr/bin/env python3

import socket
import json
import threading
import time

def handle_server():
    """Simple test server that responds to decision requests"""
    try:
        # Create server socket
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(('localhost', 12345))
        server.listen(1)
        print("Test server listening on port 12345...")
        
        # Accept connection
        client, addr = server.accept()
        print(f"Client connected from {addr}")
        
        buffer = ""
        while True:
            data = client.recv(1024).decode()
            if not data:
                break
                
            buffer += data
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                if line.strip():
                    print(f"Received: {line.strip()}")
                    
                    try:
                        message = json.loads(line)
                        if message.get("type") == "decision_request":
                            print("Sending response for decision request...")
                            response = {
                                "type": "decision_response", 
                                "success": True,
                                "decision": {"chosenIndices": [0], "additionalData": {}}
                            }
                            response_str = json.dumps(response) + "\n"
                            client.send(response_str.encode())
                            print(f"Sent: {response}")
                    except Exception as e:
                        print(f"Error processing message: {e}")
        
        client.close()
        server.close()
        
    except Exception as e:
        print(f"Server error: {e}")

if __name__ == "__main__":
    handle_server()