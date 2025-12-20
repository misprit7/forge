#!/usr/bin/env python3
"""
Utility script to kill lingering Forge processes.

Use this if Forge processes aren't being cleaned up properly after training.
"""

import subprocess
import os
import signal
import sys

def kill_forge_processes():
    """Kill all Forge Java processes"""
    print("Searching for Forge processes...")
    
    try:
        # Find Java processes with "forge" in command line
        result = subprocess.run(['pgrep', '-f', 'forge.view.Main'], 
                              capture_output=True, text=True)
        
        if result.returncode == 0:
            pids = result.stdout.strip().split('\n')
            killed_count = 0
            
            for pid in pids:
                if pid:
                    try:
                        pid_int = int(pid)
                        print(f"Killing Forge process {pid_int}")
                        os.kill(pid_int, signal.SIGKILL)
                        killed_count += 1
                    except (ProcessLookupError, ValueError) as e:
                        print(f"Could not kill process {pid}: {e}")
            
            if killed_count > 0:
                print(f"Killed {killed_count} Forge processes")
            else:
                print("Found Forge processes but couldn't kill any")
        else:
            print("No Forge processes found")
            
    except Exception as e:
        print(f"Error searching for processes: {e}")
    
    # Also try to find Maven processes that might be running Forge
    try:
        result = subprocess.run(['pgrep', '-f', 'mvn.*forge'], 
                              capture_output=True, text=True)
        
        if result.returncode == 0:
            pids = result.stdout.strip().split('\n')
            for pid in pids:
                if pid:
                    try:
                        pid_int = int(pid)
                        print(f"Killing Maven process {pid_int}")
                        os.kill(pid_int, signal.SIGKILL)
                    except (ProcessLookupError, ValueError) as e:
                        print(f"Could not kill Maven process {pid}: {e}")
    except Exception as e:
        print(f"Error searching for Maven processes: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--list":
        # Just list processes
        try:
            result = subprocess.run(['pgrep', '-f', '-l', 'forge'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                print("Found processes:")
                print(result.stdout)
            else:
                print("No Forge-related processes found")
        except Exception as e:
            print(f"Error listing processes: {e}")
    else:
        kill_forge_processes()