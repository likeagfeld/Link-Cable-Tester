#!/usr/bin/env python3
"""
Dreamcast Serial Cable Tester
Simple tool to verify cable is receiving data from Dreamcast
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import subprocess
import threading
import time
import json
from pathlib import Path

# Try to import paramiko for SSH
PARAMIKO_AVAILABLE = False
try:
    import paramiko
    PARAMIKO_AVAILABLE = True
except ImportError:
    pass

class CableTesterGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Dreamcast Cable Tester")
        self.root.geometry("900x650")
        
        self.config_file = Path.home() / ".dreamcast_cable_tester.json"
        
        self.ssh_client = None
        self.monitor_process = None
        self.stop_flag = threading.Event()
        
        self.test_running = False
        self.scixb_detected = False
        
        self.create_widgets()
        self.load_config()
        
    def create_widgets(self):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(4, weight=1)
        
        # Connection Settings
        conn_frame = ttk.LabelFrame(main_frame, text="Raspberry Pi Connection", padding="10")
        conn_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=5)
        conn_frame.columnconfigure(1, weight=1)
        
        ttk.Label(conn_frame, text="Pi IP Address:").grid(row=0, column=0, sticky=tk.W, padx=5)
        self.ip_entry = ttk.Entry(conn_frame, width=30)
        self.ip_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5)
        
        ttk.Label(conn_frame, text="SSH Port:").grid(row=1, column=0, sticky=tk.W, padx=5)
        self.ssh_port_entry = ttk.Entry(conn_frame, width=30)
        self.ssh_port_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=5)
        self.ssh_port_entry.insert(0, "22")
        
        ttk.Label(conn_frame, text="Username:").grid(row=2, column=0, sticky=tk.W, padx=5)
        self.user_entry = ttk.Entry(conn_frame, width=30)
        self.user_entry.grid(row=2, column=1, sticky=(tk.W, tk.E), padx=5)
        self.user_entry.insert(0, "pi")
        
        ttk.Label(conn_frame, text="Password:").grid(row=3, column=0, sticky=tk.W, padx=5)
        self.pass_entry = ttk.Entry(conn_frame, width=30, show="*")
        self.pass_entry.grid(row=3, column=1, sticky=(tk.W, tk.E), padx=5)
        
        # Cable Settings
        cable_frame = ttk.LabelFrame(main_frame, text="Cable Settings", padding="10")
        cable_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=5)
        cable_frame.columnconfigure(1, weight=1)
        
        ttk.Label(cable_frame, text="Serial Port:").grid(row=0, column=0, sticky=tk.W, padx=5)
        self.port_entry = ttk.Entry(cable_frame, width=30)
        self.port_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5)
        self.port_entry.insert(0, "/dev/ttyUSB0")
        
        ttk.Label(cable_frame, text="Baud Rate:").grid(row=1, column=0, sticky=tk.W, padx=5)
        self.baud_entry = ttk.Entry(cable_frame, width=30)
        self.baud_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=5)
        self.baud_entry.insert(0, "260416")
        
        # Control Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=2, column=0, pady=10)
        
        self.start_button = ttk.Button(button_frame, text="Start Test", command=self.start_test, width=15)
        self.start_button.grid(row=0, column=0, padx=5)
        
        self.stop_button = ttk.Button(button_frame, text="Stop Test", command=self.stop_test, state=tk.DISABLED, width=15)
        self.stop_button.grid(row=0, column=1, padx=5)
        
        ttk.Button(button_frame, text="Clear Log", command=self.clear_log, width=15).grid(row=0, column=2, padx=5)
        
        ttk.Button(button_frame, text="Save Config", command=self.save_config, width=15).grid(row=0, column=3, padx=5)
        
        # Status
        status_frame = ttk.LabelFrame(main_frame, text="Test Status", padding="10")
        status_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=5)
        
        self.status_label = ttk.Label(status_frame, text="Ready to test", foreground="gray")
        self.status_label.pack()
        
        # Output Log
        log_frame = ttk.LabelFrame(main_frame, text="Test Output", padding="10")
        log_frame.grid(row=4, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, height=15, width=80)
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        self.log_text.tag_config("success", foreground="green", font=("TkDefaultFont", 10, "bold"))
        self.log_text.tag_config("error", foreground="red", font=("TkDefaultFont", 10, "bold"))
        self.log_text.tag_config("warning", foreground="orange")
        self.log_text.tag_config("info", foreground="blue")
        self.log_text.tag_config("scixb", foreground="green", background="yellow", font=("TkDefaultFont", 11, "bold"))
        
    def log_message(self, message, tag=None):
        timestamp = time.strftime("%H:%M:%S")
        formatted_msg = f"[{timestamp}] {message}\n"
        self.log_text.insert(tk.END, formatted_msg, tag)
        self.log_text.see(tk.END)
        
    def update_status(self, message, color="gray"):
        self.status_label.config(text=message, foreground=color)
            
    def start_test(self):
        if self.test_running:
            return
            
        if not self.ip_entry.get() or not self.user_entry.get():
            messagebox.showerror("Error", "Please enter Pi IP address and username")
            return
            
        self.test_running = True
        self.scixb_detected = False
        self.stop_flag.clear()
        
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        
        self.log_message("=" * 60, "info")
        self.log_message("Starting cable test...", "info")
        self.log_message("=" * 60, "info")
        
        test_thread = threading.Thread(target=self.run_test, daemon=True)
        test_thread.start()
        
    def stop_test(self):
        self.log_message("Stopping test...", "warning")
        self.stop_flag.set()
        
        if self.ssh_client:
            try:
                self.ssh_client.close()
            except:
                pass
        
        self.ssh_client = None
        self.test_running = False
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.update_status("Test stopped", "gray")
        
    def connect_ssh(self, host, user, password, port):
        try:
            if PARAMIKO_AVAILABLE:
                self.ssh_client = paramiko.SSHClient()
                self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                
                if password:
                    self.ssh_client.connect(host, port=port, username=user, password=password, timeout=10)
                else:
                    self.ssh_client.connect(host, port=port, username=user, timeout=10)
                return True
            else:
                self.log_message("Paramiko not available - install with: pip install paramiko", "error")
                return False
        except Exception as e:
            self.log_message(f"Connection error: {str(e)}", "error")
            return False
            
    def run_test(self):
        try:
            pi_ip = self.ip_entry.get()
            pi_user = self.user_entry.get()
            pi_pass = self.pass_entry.get()
            ssh_port = int(self.ssh_port_entry.get())
            port = self.port_entry.get()
            baud = self.baud_entry.get()
            
            self.log_message(f"Connecting to {pi_user}@{pi_ip}:{ssh_port}...", "info")
            
            if not self.connect_ssh(pi_ip, pi_user, pi_pass, ssh_port):
                self.stop_test()
                return
                
            self.log_message("Connected!", "success")
            
            # Cleanup
            self.log_message("Cleaning up...", "info")
            stdin, stdout, stderr = self.ssh_client.exec_command(
                f'sudo pkill -9 cat; sudo pkill -9 -f link_cable; sudo fuser -k {port} 2>/dev/null; '
                f'rm -f /tmp/serial_data.txt /tmp/link_output.log; sleep 2'
            )
            stdout.channel.recv_exit_status()
            
            # Just start both - don't verify, trust they'll work
            # Create a Python script that opens port NON-exclusively (like minicom does)
            self.log_message("Creating non-exclusive serial monitor...", "info")
            
            monitor_script = f'''import serial
import sys
import time

try:
    # Open WITHOUT exclusive - allows link_cable to also open it
    ser = serial.Serial('{port}', {baud}, timeout=0.5, exclusive=False)
    sys.stderr.write("Monitor opened port\\n")
    sys.stderr.flush()
    
    with open('/tmp/serial_data.txt', 'w') as f:
        while True:
            data = ser.read(100)
            if data:
                text = data.decode('utf-8', errors='ignore')
                f.write(text)
                f.flush()
                sys.stdout.write(text)
                sys.stdout.flush()
            time.sleep(0.01)
except Exception as e:
    sys.stderr.write(str(e) + "\\n")
    sys.exit(1)
'''
            
            stdin, stdout, stderr = self.ssh_client.exec_command('cat > /tmp/monitor.py')
            stdin.write(monitor_script)
            stdin.channel.shutdown_write()
            stdout.channel.recv_exit_status()
            
            self.log_message("Starting non-exclusive monitor...", "info")
            stdin, stdout, stderr = self.ssh_client.exec_command('nohup python /tmp/monitor.py > /dev/null 2>&1 &')
            stdout.channel.recv_exit_status()
            time.sleep(2)
            
            self.log_message("Starting link_cable.py...", "info")
            stdin, stdout, stderr = self.ssh_client.exec_command(
                f'cd /opt/dreampi-linkcable && nohup python link_cable.py com={port} game=5 matching=1 > /tmp/link_output.log 2>&1 &'
            )
            stdout.channel.recv_exit_status()
            time.sleep(3)
            
            # Check what actually started
            stdin, stdout, stderr = self.ssh_client.exec_command('ps aux | grep -E "(cat /dev/tty|link_cable)" | grep -v grep')
            processes = stdout.read().decode().strip()
            
            if processes:
                self.log_message("Running processes:", "success")
                for line in processes.split('\n'):
                    self.log_message(f"  {line[:100]}", "info")
            else:
                self.log_message("Warning: No processes detected, but continuing anyway...", "warning")
            
            # Check link script output
            time.sleep(2)
            stdin, stdout, stderr = self.ssh_client.exec_command('tail -10 /tmp/link_output.log 2>/dev/null')
            link_out = stdout.read().decode().strip()
            if link_out:
                self.log_message("Link script output:", "info")
                for line in link_out.split('\n'):
                    self.log_message(f"  {line}", "info")
            
            self.log_message("", "info")
            self.log_message("=" * 60, "success")
            self.log_message("MONITORING FOR DATA", "success")
            self.log_message("=" * 60, "success")
            self.log_message("", "info")
            self.log_message("Initiate connection from Dreamcast NOW", "warning")
            self.log_message("", "info")
            
            # Monitor BOTH files
            start_time = time.time()
            timeout = 120
            serial_pos = 0
            link_pos = 0
            
            while not self.stop_flag.is_set() and (time.time() - start_time) < timeout:
                # Check serial data file
                stdin, stdout, stderr = self.ssh_client.exec_command(f'tail -c +{serial_pos + 1} /tmp/serial_data.txt 2>/dev/null')
                serial_data = stdout.read().decode('utf-8', errors='ignore')
                
                if serial_data:
                    serial_pos += len(serial_data.encode('utf-8'))
                    for line in serial_data.split('\n'):
                        line = line.strip()
                        if line:
                            self.log_message(f"[SERIAL] {line}", "info")
                            if "SCIXB START" in line:
                                self.scixb_detected = True
                
                # Check link output file
                stdin, stdout, stderr = self.ssh_client.exec_command(f'tail -c +{link_pos + 1} /tmp/link_output.log 2>/dev/null')
                link_data = stdout.read().decode('utf-8', errors='ignore')
                
                if link_data:
                    link_pos += len(link_data.encode('utf-8'))
                    for line in link_data.split('\n'):
                        line = line.strip()
                        if line:
                            self.log_message(f"[LINK] {line}", "info")
                            if "SCIXB" in line or "VOOT" in line or "Connection established" in line:
                                self.scixb_detected = True
                
                if self.scixb_detected:
                    self.log_message("", "scixb")
                    self.log_message("=" * 60, "scixb")
                    self.log_message(">>> CONNECTION DETECTED! <<<", "scixb")
                    self.log_message(">>> CABLE WORKS! <<<", "scixb")
                    self.log_message("=" * 60, "scixb")
                    
                    self.root.after(0, lambda: messagebox.showinfo("SUCCESS!", "Cable is working!"))
                    time.sleep(2)
                    self.stop_test()
                    return
                
                time.sleep(0.5)
            
            if not self.scixb_detected:
                self.log_message("", "error")
                self.log_message("TIMEOUT - No data detected", "error")
                
        except Exception as e:
            self.log_message(f"Error: {str(e)}", "error")
        finally:
            if not self.stop_flag.is_set():
                self.stop_test()
                
    def clear_log(self):
        self.log_text.delete(1.0, tk.END)
        
    def save_config(self):
        config = {
            "pi_ip": self.ip_entry.get(),
            "ssh_port": self.ssh_port_entry.get(),
            "pi_user": self.user_entry.get(),
            "port": self.port_entry.get(),
            "baud": self.baud_entry.get()
        }
        
        try:
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2)
            messagebox.showinfo("Success", "Configuration saved!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save config: {str(e)}")
            
    def load_config(self):
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    
                self.ip_entry.insert(0, config.get("pi_ip", ""))
                self.ssh_port_entry.delete(0, tk.END)
                self.ssh_port_entry.insert(0, config.get("ssh_port", "22"))
                self.user_entry.delete(0, tk.END)
                self.user_entry.insert(0, config.get("pi_user", "pi"))
                self.port_entry.delete(0, tk.END)
                self.port_entry.insert(0, config.get("port", "/dev/ttyUSB0"))
                self.baud_entry.delete(0, tk.END)
                self.baud_entry.insert(0, config.get("baud", "260416"))
            except:
                pass

def main():
    root = tk.Tk()
    app = CableTesterGUI(root)
    
    def on_closing():
        if app.test_running:
            if messagebox.askokcancel("Quit", "Test is running. Stop and quit?"):
                app.stop_test()
                root.destroy()
        else:
            root.destroy()
            
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()

if __name__ == "__main__":
    main()
