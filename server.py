import socket
import threading
import json
import math
from mom import RabbitMQHandler
from config import USER, PASSWORD

class User:
    def __init__(self, username, lat, lon, conn):
        self.username = username
        self.lat = lat
        self.lon = lon
        self.conn = conn

class ChatServer:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)
        print(f"Servidor iniciado em {self.host}:{self.port}")
        self.users = {} 
        self.lock = threading.Lock()

    def start(self):
        while True:
            conn, addr = self.server_socket.accept()
            print(f"Conexão estabelecida com {addr}")
            threading.Thread(target=self.handle_client, args=(conn, addr), daemon=True).start()

    def handle_client(self, conn, addr):
        try:
            while True:
                data = conn.recv(1024)
                if not data:
                    break
                messages = data.decode().split("\n")
                for msg in messages:
                    if msg.strip() == "":
                        continue
                    self.process_message(conn, msg)
        except Exception as e:
            print("Erro com o cliente", addr, ":", e)
        finally:
            self.remove_connection(conn)
            conn.close()

    def process_message(self, conn, msg):
        try:
            data = json.loads(msg)
        except json.JSONDecodeError:
            return

        action = data.get("action")
        if action == "register":
            username = data.get("username")
            lat = float(data.get("lat"))
            lon = float(data.get("lon"))
            with self.lock:
                self.users[username] = User(username, lat, lon, conn)
            response = {"action": "register_ack", "message": "Registrado com sucesso"}
            conn.sendall((json.dumps(response) + "\n").encode())
        elif action == "update_location":
            username = data.get("username")
            lat = float(data.get("lat"))
            lon = float(data.get("lon"))
            with self.lock:
                if username in self.users:
                    self.users[username].lat = lat
                    self.users[username].lon = lon
            self.check_pending(username)
        elif action == "refresh":
            username = data.get("username")
            visible_users = self.get_visible_users(username)
            response = {"action": "refresh_ack", "visible_users": visible_users}
            conn.sendall((json.dumps(response) + "\n").encode())
            self.check_pending(username)
        elif action == "message":
            sender = data.get("sender")
            receiver = data.get("receiver")
            text = data.get("text")
            self.handle_message(sender, receiver, text)

    def get_visible_users(self, username):
        with self.lock:
            if username not in self.users:
                return []
            current_user = self.users[username]
            visible = []
            for uname, user in self.users.items():
                if uname == username:
                    continue
                d = self.distance(current_user.lat, current_user.lon, user.lat, user.lon)
                if d <= 200:
                    visible.append({"username": uname, "distance": int(d)})
            return visible

    def distance(self, lat1, lon1, lat2, lon2):
        return math.sqrt((lat1 - lat2)**2 + (lon1 - lon2)**2)

    def handle_message(self, sender, receiver, text):
        with self.lock:
            if sender not in self.users or receiver not in self.users:
                return
            sender_user = self.users[sender]
            receiver_user = self.users[receiver]
            if self.distance(sender_user.lat, sender_user.lon, receiver_user.lat, receiver_user.lon) <= 200:
                response = {"action": "message", "sender": sender, "text": text}
                try:
                    receiver_user.conn.sendall((json.dumps(response) + "\n").encode())
                except Exception as e:
                    print("Erro ao enviar mensagem:", e)
            else:
                amqp_url = f"amqps://{USER}:{PASSWORD}@jackal.rmq.cloudamqp.com/{USER}"
                mq_handler = RabbitMQHandler(amqp_url)
                mq_handler.publish_message(receiver, sender, text)
                print(f"Mensagem de {sender} para {receiver} armazenada no CloudAMQP.")

    def check_pending(self, username):
        with self.lock:
            if username not in self.users:
                return
            user = self.users[username]
        amqp_url = f"amqps://{USER}:{PASSWORD}@jackal.rmq.cloudamqp.com/{USER}"
        mq_handler = RabbitMQHandler(amqp_url)
        
        def deliver(message):
            sender = message["sender"]
            with self.lock:
                if sender not in self.users:
                    # Se o remetente não estiver conectado, entrega mesmo assim.
                    response = {"action": "message", "sender": sender, "text": message["text"]}
                    try:
                        user.conn.sendall((json.dumps(response) + "\n").encode())
                        print(f"Entregando mensagem pendente de {sender} para {username} (remetente desconectado)")
                        return True
                    except Exception as e:
                        print("Erro ao entregar mensagem pendente:", e)
                        return False
                sender_user = self.users[sender]
                if self.distance(user.lat, user.lon, sender_user.lat, sender_user.lon) <= 200:
                    response = {"action": "message", "sender": sender, "text": message["text"]}
                    try:
                        user.conn.sendall((json.dumps(response) + "\n").encode())
                        print(f"Entregando mensagem pendente de {sender} para {username}")
                        return True
                    except Exception as e:
                        print("Erro ao entregar mensagem pendente:", e)
                        return False
                else:
                    return False
        
        mq_handler.consume_messages(username, deliver)
        
        # Agendar nova verificação em 5 segundos, para tentar entregar mensagens que ainda estejam pendentes.
        threading.Timer(5, lambda: self.check_pending(username)).start()


    def remove_connection(self, conn):
        with self.lock:
            to_remove = None
            for username, user in list(self.users.items()):
                if user.conn == conn:
                    to_remove = username
                    break
            if to_remove:
                print(f"Usuário {to_remove} desconectado.")
                del self.users[to_remove]

if __name__ == "__main__":
    server = ChatServer("127.0.0.1", 5000)
    server.start()
