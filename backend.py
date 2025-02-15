import flet as ft
from datetime import datetime
import threading
import time
from receiver import SerialCommunicator
import folium
import tempfile
import os
from geopy.geocoders import Nominatim
import webbrowser

def main(page: ft.Page):
    page.title = "Wireless E-commerce Chat"
    page.theme_mode = "light"
    page.padding = 0
    page.window_width = 400
    page.window_height = 800
    page.bgcolor = ft.colors.WHITE

    # Initialize SerialCommunicator
    comm = SerialCommunicator()
    comm.start()

    messages = []
    current_user = "user1"  # Local user
    remote_user = "user2"   # Remote user

    # Catalog of products
    catalog = [
        {"name": "Potato", "price": 40, "image": r"C:\Users\Divyansh\Downloads\potato.png"},
        {"name": "", "price": 15.99, "image": r"C:\Users\Divyansh\Downloads\detergen.jpg"},
        {"name": "Product 3", "price": 20.99, "image": r"C:\Users\Divyansh\Downloads\flour.jpg"},
    ]

    class Message:
        def __init__(self, user_id: str, text: str = None, image_path: str = None, 
                     timestamp: datetime = None, location: dict = None, order: dict = None):
            self.user_id = user_id
            self.text = text
            self.image_path = image_path
            self.timestamp = timestamp or datetime.now()
            self.location = location
            self.order = order

    def create_location_map(latitude, longitude, save_path):
        """Create a map with the given location marked and save it as HTML"""
        m = folium.Map(location=[latitude, longitude], zoom_start=15)
        folium.Marker(
            [latitude, longitude],
            popup="Location",
            icon=folium.Icon(color='red', icon='info-sign')
        ).add_to(m)
        m.save(save_path)

    def create_message_bubble(message: Message):
        is_current_user = message.user_id == current_user
        
        message_content = []
        
        if message.text:
            message_content.append(
                ft.Text(
                    message.text,
                    color=ft.colors.WHITE if is_current_user else ft.colors.BLACK,
                    size=16,
                    weight=ft.FontWeight.W_400,
                )
            )
        
        if message.image_path:
            message_content.append(
                ft.Image(
                    src=message.image_path,
                    width=200,
                    height=200,
                    fit=ft.ImageFit.CONTAIN,
                    border_radius=ft.border_radius.all(8),
            )
            )
        if message.location:
            location_button = ft.ElevatedButton(
                text="View Location 📍",
                on_click=lambda _: webbrowser.open(message.location['map_path']),
                bgcolor=ft.colors.BLUE_100 if is_current_user else ft.colors.GREY_300,
            )
            message_content.append(location_button)
            
            message_content.append(
                ft.Text(
                    f"📍 {message.location['address']}",
                    color=ft.colors.WHITE70 if is_current_user else ft.colors.BLACK45,
                    size=12,
                    italic=True,
                )
            )
        
        if message.order:
            order_details = message.order
            message_content.append(
                ft.Text(
                    "Order Details:",
                    color=ft.colors.WHITE if is_current_user else ft.colors.BLACK,
                    size=16,
                    weight=ft.FontWeight.W_600,
                )
            )
            message_content.append(
                ft.Text(
                    f"Product: {order_details['product']}",
                    color=ft.colors.WHITE70 if is_current_user else ft.colors.BLACK45,
                    size=14,
                )
            )
            message_content.append(
                ft.Text(
                    f"Quantity: {order_details['quantity']}",
                    color=ft.colors.WHITE70 if is_current_user else ft.colors.BLACK45,
                    size=14,
                )
            )
            message_content.append(
                ft.Text(
                    f"Price: ₹{order_details['price']}",
                    color=ft.colors.WHITE70 if is_current_user else ft.colors.BLACK45,
                    size=14,
                )
            )
        
        message_content.append(
            ft.Text(
                message.timestamp.strftime("%H:%M"),
                color=ft.colors.WHITE70 if is_current_user else ft.colors.BLACK45,
                size=12,
            )
        )
        
        return ft.Container(
            content=ft.Column(
                controls=message_content,
                tight=True,
            ),
            bgcolor=ft.colors.BLUE if is_current_user else ft.colors.GREY_200,
            border_radius=ft.border_radius.BorderRadius(
                10,
                10,
                0 if is_current_user else 10,
                10 if is_current_user else 0,
            ),
            padding=ft.padding.all(12),
            margin=ft.margin.only(
                left=50 if is_current_user else 10,
                right=10 if is_current_user else 50,
                top=5,
                bottom=5,
            ),
        )

    chat_list = ft.ListView(
        expand=True,
        spacing=10,
        padding=20,
        auto_scroll=True,
    )

    message_input = ft.TextField(
        hint_text="Type a message...",
        color=ft.colors.BLACK,
        border_radius=30,
        filled=True,
        expand=True,
        border_color=ft.colors.TRANSPARENT,
        bgcolor=ft.colors.GREY_200,
    )

    def send_message(e):
        if not message_input.value:
            return

        try:
            message_text = message_input.value.strip()
            if message_text:
                comm.send_message(message_text)

                new_message = Message(
                    current_user,
                    text=message_text,
                )
                messages.append(new_message)
                chat_list.controls.append(create_message_bubble(new_message))
                
                message_input.value = ""
                page.update()
        except Exception as ex:
            print(f"Error sending message: {ex}")

    message_input.on_submit = send_message

    def share_location(e):
        try:
            
            latitude = 31.481166698721232
            longitude = 76.19067937116364

            geolocator = Nominatim(user_agent="wireless_chat")
            location = geolocator.reverse(f"{latitude}, {longitude}")
            
            temp_dir = tempfile.gettempdir()
            map_path = os.path.join(temp_dir, f"location_map_{int(time.time())}.html")
            create_location_map(latitude, longitude, map_path)

            location_data = {
                'latitude': latitude,
                'longitude': longitude,
                'address': location.address,
                'map_path': map_path
            }

            comm.send_location(location_data)

            new_message = Message(
                current_user,
                text="Shared a location:",
                location=location_data
            )
            messages.append(new_message)
            chat_list.controls.append(create_message_bubble(new_message))
            page.update()

        except Exception as ex:
            print(f"Error sharing location: {ex}")

    def pick_files_result(e: ft.FilePickerResultEvent):
        if e.files:
            try:
                comm.send_image(e.files[0].path)
                
                new_message = Message(
                    current_user,
                    image_path=e.files[0].path,
                )
                messages.append(new_message)
                chat_list.controls.append(create_message_bubble(new_message))
                page.update()
            except Exception as ex:
                print(f"Error sending image: {ex}")

    file_picker = ft.FilePicker(
        on_result=pick_files_result
    )
    page.overlay.append(file_picker)

    def place_order(product_name, price, quantity=1):
        try:
            order_details = {
                'product': product_name,
                'quantity': quantity,
                'price': price
            }

            comm.send_order(order_details)

            new_message = Message(
                current_user,
                text="Placed an order:",
                order=order_details
            )
            messages.append(new_message)
            chat_list.controls.append(create_message_bubble(new_message))
            page.update()
        except Exception as ex:
            print(f"Error placing order: {ex}")

    def show_catalog(e):
        catalog_items = []
        for product in catalog:
            catalog_items.append(
                ft.Card(
                    content=ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Image(
                                    src=product["image"],
                                    width=150,
                                    height=150,
                                    fit=ft.ImageFit.COVER,
                                ),
                                ft.Text(product["name"], size=16, weight=ft.FontWeight.BOLD),
                                ft.Text(f"Price: ₹{product['price']}", size=14),
                                ft.ElevatedButton(
                                    text="Order Now",
                                    on_click=lambda e, p=product: place_order(p["name"], p["price"]),
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.CENTER,
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        padding=10,
                    ),
                )
            )

        catalog_view = ft.Column(
            controls=catalog_items,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )

        # Create a message for the catalog
        catalog_message = Message(
            current_user,
            text="Product Catalog:",
        )

        # Add the catalog message to the chat list
        chat_list.controls.append(create_message_bubble(catalog_message))
        chat_list.controls.append(catalog_view)
        page.update()
    def check_received_messages():
        while True:
            try:
                message = comm.get_message()
                if message:
                    if message.type == 'message':
                        new_message = Message(
                            remote_user,
                            text=message.content,
                            timestamp=message.timestamp
                        )
                    elif message.type == 'image':
                        new_message = Message(
                            remote_user,
                            image_path=message.path,
                            timestamp=message.timestamp
                        )
                    elif message.type == 'location':
                        location_data = message.content
                        map_path = os.path.join(
                            tempfile.gettempdir(),
                            f"location_map_received_{int(time.time())}.html"
                        )
                        create_location_map(
                            location_data['latitude'],
                            location_data['longitude'],
                            map_path
                        )
                        location_data['map_path'] = map_path
                        
                        new_message = Message(
                            remote_user,
                            text="Shared a location:",
                            location=location_data,
                            timestamp=message.timestamp
                        )
                    elif message.type == 'order':
                        new_message = Message(
                            remote_user,
                            text="Received an order:",
                            order=message.content,
                            timestamp=message.timestamp
                        )
                    elif message.type == 'error':
                        print(f"Communication error: {message.content}")
                        continue

                    messages.append(new_message)
                    chat_list.controls.append(create_message_bubble(new_message))
                    page.update()
                time.sleep(0.1)
            except Exception as ex:
                print(f"Error in message checking: {ex}")
                time.sleep(1)

    receiver_thread = threading.Thread(target=check_received_messages)
    receiver_thread.daemon = True
    receiver_thread.start()

    image_button = ft.IconButton(
        icon=ft.icons.IMAGE,
        icon_color=ft.colors.BLUE,
        tooltip="Upload Image",
        on_click=lambda _: file_picker.pick_files(
            allow_multiple=False,
            allowed_extensions=["png", "jpg", "jpeg", "gif"]
        ),
    )

    location_button = ft.IconButton(
        icon=ft.icons.LOCATION_ON,
        icon_color=ft.colors.BLUE,
        tooltip="Share Location",
        on_click=share_location,
    )

    catalog_button = ft.IconButton(
        icon=ft.icons.SHOPPING_BAG,
        icon_color=ft.colors.BLUE,
        tooltip="View Catalog",
        on_click=show_catalog,
    )

    send_button = ft.IconButton(
        icon=ft.icons.SEND_ROUNDED,
        icon_color=ft.colors.BLUE,
        on_click=send_message,
    )

    app_bar = ft.Container(
        content=ft.Row(
            controls=[
                ft.Image(
                    src="https://media.tenor.com/EQ1eDjBvEwsAAAAe/champak-champaklal.png",
                    width=40,
                    height=40,
                    fit=ft.ImageFit.COVER,
                    border_radius=ft.border_radius.all(20),
                ),
                ft.Text(
                    "Vendor",
                    color=ft.colors.BLACK,
                    size=20,
                    weight=ft.FontWeight.BOLD,
                ),
            ],
            spacing=10,
        ),
        padding=10,
        bgcolor=ft.colors.WHITE,
        border=ft.border.only(
            bottom=ft.border.BorderSide(1, ft.colors.GREY_300)
        ),
    )

    input_container = ft.Container(
        content=ft.Row(
            controls=[
                message_input,
                image_button,
                location_button,
                #catalog_button,
                send_button,
            ],
            spacing=10,
        ),
        padding=ft.padding.all(10),
        bgcolor=ft.colors.WHITE,
        border=ft.border.only(
            top=ft.border.BorderSide(1, ft.colors.TRANSPARENT)
        ),
    )

    def on_window_event(e):
        if e.data == "close":
            comm.stop()
            page.window_close()
            
    page.window_prevent_close = True
    page.on_window_event = on_window_event

    page.add(
        ft.Column(
            controls=[
                app_bar,
                chat_list,
                input_container,
            ],
            spacing=0,
            expand=True,
        )
    )

if __name__ == "__main__":
    ft.app(target=main, view=ft.FLET_APP)