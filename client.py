import socket
import threading
import json
import tkinter as tk
import tkinter.font as tkFont
import tkinter.messagebox as mb

class ChatClientGUI:
    def __init__(self, master):
        self.master = master
        self.master.title("Chat - Cliente")
        self.master.geometry("800x500")
        self.socket = None
        self.username = None
        self.current_lat = None
        self.current_lon = None
        self.create_login_frame()

    def create_login_frame(self):
        self.login_frame = tk.Frame(self.master, padx=20, pady=20)
        self.login_frame.pack(expand=True)
        
        title = tk.Label(self.login_frame, text="Login no Chat", font=tkFont.Font(size=16, weight="bold"))
        title.grid(row=0, column=0, columnspan=2, pady=10)

        tk.Label(self.login_frame, text="Nome:").grid(row=1, column=0, sticky="e", pady=5)
        self.entry_username = tk.Entry(self.login_frame, width=30)
        self.entry_username.grid(row=1, column=1, pady=5)

        tk.Label(self.login_frame, text="Latitude:").grid(row=2, column=0, sticky="e", pady=5)
        self.entry_lat = tk.Entry(self.login_frame, width=30)
        self.entry_lat.grid(row=2, column=1, pady=5)

        tk.Label(self.login_frame, text="Longitude:").grid(row=3, column=0, sticky="e", pady=5)
        self.entry_lon = tk.Entry(self.login_frame, width=30)
        self.entry_lon.grid(row=3, column=1, pady=5)

        tk.Button(self.login_frame, text="Entrar", width=20, command=self.register).grid(row=4, column=0, columnspan=2, pady=15)

    def register(self):
        self.username = self.entry_username.get().strip()
        lat = self.entry_lat.get().strip()
        lon = self.entry_lon.get().strip()
        if not self.username or not lat or not lon:
            mb.showerror("Erro", "Todos os campos são obrigatórios!")
            return
        try:
            lat = float(lat)
            lon = float(lon)
        except ValueError:
            mb.showerror("Erro", "Latitude e Longitude devem ser números.")
            return

        self.current_lat = lat
        self.current_lon = lon

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.socket.connect(("127.0.0.1", 5000))
        except Exception as e:
            mb.showerror("Erro", f"Não foi possível conectar ao servidor: {e}")
            return

        register_msg = {"action": "register", "username": self.username, "lat": lat, "lon": lon}
        self.send_message(register_msg)

        self.login_frame.destroy()
        self.create_main_interface()

        threading.Thread(target=self.listen_server, daemon=True).start()
        self.master.after(120000, self.refresh_users)

    def create_main_interface(self):
        self.main_pane = tk.PanedWindow(self.master, orient=tk.HORIZONTAL)
        self.main_pane.pack(fill=tk.BOTH, expand=True)

        self.chat_frame = tk.Frame(self.main_pane, padx=10, pady=10)
        self.main_pane.add(self.chat_frame, stretch="always")

        self.chat_text = tk.Text(self.chat_frame, state=tk.DISABLED, wrap=tk.WORD, font=("Helvetica", 12))
        self.chat_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, pady=5)
        chat_scrollbar = tk.Scrollbar(self.chat_frame, command=self.chat_text.yview)
        chat_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.chat_text.config(yscrollcommand=chat_scrollbar.set)

        self.control_frame = tk.Frame(self.main_pane, padx=10, pady=10)
        self.main_pane.add(self.control_frame)

        title_control = tk.Label(self.control_frame, text="Contatos Próximos", font=tkFont.Font(size=14, weight="bold"))
        title_control.pack(pady=5)

        self.users_listbox = tk.Listbox(self.control_frame, width=30, height=10, font=("Helvetica", 12))
        self.users_listbox.pack(pady=5)

        tk.Button(self.control_frame, text="Refresh", width=20, command=self.refresh_users).pack(pady=5)

        self.position_label = tk.Label(self.control_frame, 
                                       text=f"Sua Posição: Lat: {self.current_lat} | Lon: {self.current_lon}",
                                       font=tkFont.Font(size=8))
        self.position_label.pack(pady=10)

        separator = tk.Label(self.control_frame, text="Atualizar Posição", font=tkFont.Font(size=12, weight="bold"))
        separator.pack(pady=(20,5))

        tk.Label(self.control_frame, text="Latitude:").pack(pady=2)
        self.entry_new_lat = tk.Entry(self.control_frame, width=25)
        self.entry_new_lat.pack(pady=2)

        tk.Label(self.control_frame, text="Longitude:").pack(pady=2)
        self.entry_new_lon = tk.Entry(self.control_frame, width=25)
        self.entry_new_lon.pack(pady=2)

        tk.Button(self.control_frame, text="Atualizar", width=20, command=self.update_location).pack(pady=10)

        self.msg_frame = tk.Frame(self.master, padx=10, pady=10)
        self.msg_frame.pack(fill=tk.X)

        self.entry_message = tk.Entry(self.msg_frame, font=("Helvetica", 12))
        self.entry_message.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        tk.Button(self.msg_frame, text="Enviar", width=15, command=self.send_chat_message).pack(side=tk.LEFT)

    def send_chat_message(self):
        selected_indices = self.users_listbox.curselection()
        if not selected_indices:
            mb.showerror("Erro", "Selecione um usuário para enviar a mensagem.")
            return
        receiver_item = self.users_listbox.get(selected_indices[0])
        receiver = receiver_item.split(" (")[0]
        text = self.entry_message.get().strip()
        if not text:
            return
        message_msg = {"action": "message", "sender": self.username, "receiver": receiver, "text": text}
        self.send_message(message_msg)
        self.append_text(f"Você -> {receiver}: {text}")
        self.entry_message.delete(0, tk.END)

    def update_location(self):
        lat = self.entry_new_lat.get().strip()
        lon = self.entry_new_lon.get().strip()
        if not lat or not lon:
            mb.showerror("Erro", "Informe ambos os valores de latitude e longitude.")
            return
        try:
            lat = float(lat)
            lon = float(lon)
        except ValueError:
            mb.showerror("Erro", "Latitude e Longitude devem ser números.")
            return
        update_msg = {"action": "update_location", "username": self.username, "lat": lat, "lon": lon}
        self.send_message(update_msg)

        self.current_lat = lat
        self.current_lon = lon
        self.position_label.config(text=f"Sua Posição: Lat: {self.current_lat} | Lon: {self.current_lon}")

        self.entry_new_lat.delete(0, tk.END)
        self.entry_new_lon.delete(0, tk.END)

    def refresh_users(self):
        refresh_msg = {"action": "refresh", "username": self.username}
        self.send_message(refresh_msg)
        self.master.after(120000, self.refresh_users)

    def listen_server(self):
        while True:
            try:
                data = self.socket.recv(1024)
                if not data:
                    break
                messages = data.decode().split("\n")
                for msg in messages:
                    if msg.strip() == "":
                        continue
                    try:
                        data_json = json.loads(msg)
                        self.handle_server_message(data_json)
                    except Exception as e:
                        print("Erro ao processar mensagem:", e)
            except Exception as e:
                print("Erro na conexão:", e)
                break

    def handle_server_message(self, data):
        action = data.get("action")
        if action == "register_ack":
            self.append_text(data.get("message"))
        elif action == "refresh_ack":
            visible_users = data.get("visible_users", [])
            self.users_listbox.delete(0, tk.END)
            for item in visible_users:
                if isinstance(item, dict):
                    display_text = f"{item['username']} ({item['distance']}m)"
                else:
                    display_text = item
                if display_text.split(" ")[0] != self.username:
                    self.users_listbox.insert(tk.END, display_text)
        elif action == "message":
            sender = data.get("sender")
            text = data.get("text")
            self.append_text(f"{sender}: {text}")

    def send_message(self, msg):
        try:
            self.socket.sendall((json.dumps(msg) + "\n").encode())
        except Exception as e:
            print("Erro ao enviar mensagem:", e)

    def append_text(self, message):
        self.chat_text.config(state=tk.NORMAL)
        self.chat_text.insert(tk.END, message + "\n")
        self.chat_text.config(state=tk.DISABLED)
        self.chat_text.see(tk.END)

if __name__ == "__main__":
    root = tk.Tk()
    app = ChatClientGUI(root)
    root.mainloop()
