import serial
import struct
import io
import cv2
import numpy as np
import threading
import time
import json
import base64
from PIL import Image
from PIL import ImageFile
from queue import Queue
from dataclasses import dataclass
from typing import Optional
from datetime import datetime
from queue import Empty

ImageFile.LOAD_TRUNCATED_IMAGES = True

@dataclass
class Communication:
    type: str  # 'message', 'image', 'location', or 'order'
    content: str  # For messages, locations, or orders
    timestamp: datetime
    status: str = 'received'
    path: Optional[str] = None  # For images

class SerialCommunicator:
    def __init__(self, port="COM5", baudrate=460800):
        self.ser = serial.Serial(port, baudrate, timeout=1)
        self.received_chunks = {}
        self.running = True
        self.send_queue = Queue()
        self.message_queue = Queue()
        self.image_save_path = "received_images/"
        
        import os
        os.makedirs(self.image_save_path, exist_ok=True)

    def image_to_chunks(self, image_path, chunk_size=30):
        try:
            with Image.open(image_path) as img:
                new_width = 100 
                aspect_ratio = img.height / img.width
                new_height = int(new_width * aspect_ratio)  
                img = img.resize((new_width, new_height))
                img_byte_array = io.BytesIO()
                img.save(img_byte_array, format="PNG")
                binary_data = img_byte_array.getvalue()

            chunks = []
            for i in range(0, len(binary_data), chunk_size):
                chunk_data = binary_data[i:i + chunk_size]
                chunk_index = struct.pack("H", i // chunk_size)
                chunk_data = chunk_data.ljust(chunk_size, b'\x00')
                chunks.append(chunk_index + chunk_data)

            return len(chunks), chunks
        except Exception as e:
            print(f"Error in image_to_chunks: {e}")
            return 0, []

    def send_message(self, message):
        self.send_queue.put(('message', message))

    def send_image(self, image_path):
        self.send_queue.put(('image', image_path))

    def send_location(self, location_data):
        """Send location data through serial communication"""
        # Remove map_path from location data before sending
        location_data_copy = location_data.copy()
        if 'map_path' in location_data_copy:
            del location_data_copy['map_path']
            
        self.send_queue.put(('location', location_data_copy))

    def send_order(self, order_data):
        """Send order data through serial communication"""
        self.send_queue.put(('order', order_data))

    def _send_message_data(self, message):
        try:
            self.ser.write(b'MT')
            self.ser.write(message.encode('utf-8'))
            self.ser.write(b'\n')
            self.ser.flush()
            self.ser.write(b'MEN')
            self.ser.flush()
        except Exception as e:
            print(f"Error in _send_message_data: {e}")

    def _send_location_data(self, location_data):
        try:
            # Convert location data to JSON string with a special end marker
            location_json = json.dumps(location_data) + "<<END>>"
            
            self.ser.write(b'LT')
            self.ser.write(location_json.encode('utf-8'))
            self.ser.flush()
            self.ser.write(b'LEN')
            self.ser.flush()
        except Exception as e:
            print(f"Error in _send_location_data: {e}")

    def _send_image_data(self, image_path):
        try:
            total_chunks, chunks = self.image_to_chunks(image_path)
            if total_chunks == 0:
                return

            self.ser.write(b'ST')
            self.ser.write(struct.pack("H", total_chunks))
            self.ser.flush()

            for chunk in chunks:
                self.ser.write(chunk)
                self.ser.flush()
                time.sleep(0.03)

            self.ser.write(b'EN')
            self.ser.flush()
        except Exception as e:
            print(f"Error in _send_image_data: {e}")

    def _send_order_data(self, order_data):
        try:
            # Convert order data to JSON string with a special end marker
            order_json = json.dumps(order_data) + "<<END>>"
            
            self.ser.write(b'OT')
            self.ser.write(order_json.encode('utf-8'))
            self.ser.flush()
            self.ser.write(b'OEN')
            self.ser.flush()
        except Exception as e:
            print(f"Error in _send_order_data: {e}")

    def sender_thread(self):
        while self.running:
            try:
                if not self.send_queue.empty():
                    data_type, data = self.send_queue.get()
                    if data_type == 'message':
                        self._send_message_data(data)
                    elif data_type == 'image':
                        self._send_image_data(data)
                    elif data_type == 'location':
                        self._send_location_data(data)
                    elif data_type == 'order':
                        self._send_order_data(data)
                time.sleep(0.01)
            except Exception as e:
                print(f"Error in sender_thread: {e}")
                self.message_queue.put(Communication(
                    type='error',
                    content=f"Send error: {str(e)}",
                    timestamp=datetime.now()
                ))

    def save_image(self, received_chunks):
        try:
            sorted_chunks = [received_chunks[i] for i in sorted(received_chunks.keys())]
            image_data = b"".join(sorted_chunks).rstrip(b'\x00')

            buffer = io.BytesIO(image_data)
            img = Image.open(buffer)
            

            # Generate unique filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            image_path = f"{self.image_save_path}received_image_{timestamp}.png"
            
        
            img.save(image_path)
            
            # Store image information in queue
            self.message_queue.put(Communication(
                type='image',
                content='Image received',
                timestamp=datetime.now(),
                path=image_path
            ))
            
            return image_path

        except Exception as e:
            self.message_queue.put(Communication(
                type='error',
                content=f"Image reconstruction error: {str(e)}",
                timestamp=datetime.now()
            ))
            return None

    def receiver_thread(self):
        buffer = ""
        while self.running:
            try:
                header = self.ser.read(2)
                
                if header == b'MT':
                    message = self.ser.read_until(b'\n').strip().decode('utf-8')
                    self.message_queue.put(Communication(
                        type='message',
                        content=message,
                        timestamp=datetime.now()
                    ))

                elif header == b'LT':
                    # Read until we find the end marker
                    buffer = ""
                    while True:
                        char = self.ser.read(1).decode('utf-8', errors='ignore')
                        if not char:
                            break
                        buffer += char
                        if "<<END>>" in buffer:
                            # Remove the end marker and parse the JSON
                            json_str = buffer.split("<<END>>")[0]
                            try:
                                location_data = json.loads(json_str)
                                self.message_queue.put(Communication(
                                    type='location',
                                    content=location_data,
                                    timestamp=datetime.now()
                                ))
                            except json.JSONDecodeError as e:
                                print(f"JSON decode error: {e}, Data: {json_str}")
                            break

                elif header == b'OT':
                    # Read until we find the end marker
                    buffer = ""
                    while True:
                        char = self.ser.read(1).decode('utf-8', errors='ignore')
                        if not char:
                            break
                        buffer += char
                        if "<<END>>" in buffer:
                            # Remove the end marker and parse the JSON
                            json_str = buffer.split("<<END>>")[0]
                            try:
                                order_data = json.loads(json_str)
                                self.message_queue.put(Communication(
                                    type='order',
                                    content=order_data,
                                    timestamp=datetime.now()
                                ))
                            except json.JSONDecodeError as e:
                                print(f"JSON decode error: {e}, Data: {json_str}")
                            break

                elif header == b'ST':
                    total_chunks = struct.unpack("H", self.ser.read(2))[0]
                    self.received_chunks.clear()

                    for _ in range(total_chunks):
                        chunk = self.ser.read(32)
                        if len(chunk) == 32:
                            chunk_index = struct.unpack("H", chunk[:2])[0]
                            chunk_data = chunk[2:]
                            self.received_chunks[chunk_index] = chunk_data

                elif header == b'EN':
                    self.save_image(self.received_chunks)

            except Exception as e:
                print(f"Error in receiver_thread: {e}")
                self.message_queue.put(Communication(
                    type='error',
                    content=f"Receive error: {str(e)}",
                    timestamp=datetime.now()
                ))

    def get_message(self):
        try:
            return self.message_queue.get_nowait()
        except Empty:
            return None

    def get_message_blocking(self):
        return self.message_queue.get()

    def start(self):
        self.send_thread = threading.Thread(target=self.sender_thread)
        self.recv_thread = threading.Thread(target=self.receiver_thread)
        
        self.send_thread.start()
        self.recv_thread.start()

    def stop(self):
        self.running = False
        self.send_thread.join()
        self.recv_thread.join()
        self.ser.close()