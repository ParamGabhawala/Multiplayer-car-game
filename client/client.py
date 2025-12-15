import socket
import threading
import json
import pygame
import time

DISCOVERY_PORT = 50001
TCP_PORT = 50000

# Discover rooms
def discover_rooms(timeout=1.5):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.settimeout(0.4)

    found = []
    start = time.time()

    while time.time() - start < timeout:
        try:
            sock.sendto(b"DISCOVER_ROOM", ("<broadcast>", DISCOVERY_PORT))
            data, addr = sock.recvfrom(1024)
            info = json.loads(data.decode())
            found.append(info)
        except (socket.timeout, json.JSONDecodeError, OSError):
            pass

    sock.close()
    return found


class Client:
    def __init__(self):
        self.sock = None
        self.players = []
        self.running = True
        self.id = None
        self.lock = threading.Lock()

    def connect(self, host):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((host, TCP_PORT))
        threading.Thread(target=self.recv_loop, daemon=True).start()

    def recv_loop(self):
        buf = b""
        while self.running:
            try:
                data = self.sock.recv(4096)
                if not data:
                    self.running = False
                    break

                buf += data
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    msg = json.loads(line.decode())

                    if msg["type"] == "welcome":
                        self.id = msg["id"]

                    elif msg["type"] == "state":
                        with self.lock:
                            self.players = msg["players"]

            except (ConnectionError, json.JSONDecodeError, OSError):
                self.running = False
                break

    def send_input(self, dx, dy):
        if not self.sock:
            return

        msg = json.dumps({"dx": dx, "dy": dy}) + "\n"
        try:
            self.sock.sendall(msg.encode())
        except OSError:
            self.running = False


# ---------------------- PYGAME LOOP ----------------------
pygame.init()
screen = pygame.display.set_mode((1000, 700))
pygame.display.set_caption("Multiplayer Client")
clock = pygame.time.Clock()

client = Client()

rooms = discover_rooms()
if rooms:
    print("Found rooms:", rooms)
    client.connect(rooms[0]["host"])   # auto-join first found
else:
    print("No rooms found.")

running = True
while running and client.running:
    dx = dy = 0

    for e in pygame.event.get():
        if e.type == pygame.QUIT:
            running = False

    keys = pygame.key.get_pressed()
    if keys[pygame.K_LEFT]:
        dx = -5
    if keys[pygame.K_RIGHT]:
        dx = 5
    if keys[pygame.K_UP]:
        dy = -5
    if keys[pygame.K_DOWN]:
        dy = 5

    # send input only if movement happened
    if dx or dy:
        client.send_input(dx, dy)

    # draw
    screen.fill((30, 30, 30))

    with client.lock:
        players_copy = list(client.players)

    for p in players_copy:
        pygame.draw.rect(screen, (0, 255, 0), (p["x"], p["y"], 40, 40))

    pygame.display.flip()
    clock.tick(60)

pygame.quit()

client.running = False
if client.sock:
    client.sock.close()

