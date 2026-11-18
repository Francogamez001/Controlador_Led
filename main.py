import network
import socket
import machine
import time
import json
import gc
import esp

esp.osdebug(0)
gc.collect()

SSID = "AcademiasIndetec"
PASSWORD = ""

led_r = machine.PWM(machine.Pin(25), freq=1000)
led_g = machine.PWM(machine.Pin(26), freq=1000)
led_b = machine.PWM(machine.Pin(27), freq=1000)

colores = ["#0000ff", "#ff0000", "#ffff00"]

tiempo_ciclo = 2000

indice = 0
ultimo_cambio = time.ticks_ms()

def convertir_color(hexadecimal):
    hexadecimal = hexadecimal.replace("#", "")

    if len(hexadecimal) != 6:
        raise ValueError("Color invalido")

    r = int(hexadecimal[0:2], 16)
    g = int(hexadecimal[2:4], 16)
    b = int(hexadecimal[4:6], 16)

    return r, g, b

def establecer_color(color):
    r, g, b = convertir_color(color)

    led_r.duty_u16(r * 257)
    led_g.duty_u16(g * 257)
    led_b.duty_u16(b * 257)

def actualizar_ciclo():
    global indice, ultimo_cambio

    ahora = time.ticks_ms()

    if time.ticks_diff(ahora, ultimo_cambio) >= tiempo_ciclo:
        indice = (indice + 1) % len(colores)

        establecer_color(colores[indice])

        ultimo_cambio = ahora

wlan = network.WLAN(network.STA_IF)
wlan.active(True)

print("Conectando a", SSID)

wlan.connect(SSID, PASSWORD)

intentos = 0

while not wlan.isconnected() and intentos < 20:
    print("Esperando conexion...")
    time.sleep(1)
    intentos += 1

if not wlan.isconnected():
    raise RuntimeError("No se pudo conectar al WiFi")

ip = wlan.ifconfig()[0]

print("Conexion exitosa")
print("IP:", ip)

def responder(cliente, codigo, contenido):
    respuesta = json.dumps(contenido)

    encabezado = (
        "HTTP/1.1 " + codigo + "\r\n"
        "Content-Type: application/json\r\n"
        "Access-Control-Allow-Origin: *\r\n"
        "Access-Control-Allow-Methods: GET, POST, OPTIONS\r\n"
        "Access-Control-Allow-Headers: Content-Type\r\n"
        "Content-Length: " + str(len(respuesta)) + "\r\n"
        "Connection: close\r\n"
        "\r\n"
    )

    cliente.send(encabezado.encode())
    cliente.send(respuesta.encode())

def procesar_solicitud(cliente):
    global colores, indice, ultimo_cambio

    cliente.settimeout(2)

    datos = b""

    while b"\r\n\r\n" not in datos:
        parte = cliente.recv(512)

        if not parte:
            return

        datos += parte

    encabezados, cuerpo = datos.split(b"\r\n\r\n", 1)

    lineas = encabezados.decode().split("\r\n")
    metodo, ruta, version = lineas[0].split(" ")

    longitud = 0

    for linea in lineas[1:]:
        if linea.lower().startswith("content-length:"):
            longitud = int(linea.split(":")[1].strip())

    while len(cuerpo) < longitud:
        parte = cliente.recv(512)

        if not parte:
            break

        cuerpo += parte

    if metodo == "OPTIONS":
        responder(cliente, "204 No Content", {})
        return

    if ruta == "/api/status" and metodo == "GET":
        responder(cliente, "200 OK", {
            "connected": True,
            "colors": colores,
            "ip": ip
        })
        return

    if ruta == "/api/colors" and metodo == "POST":
        try:
            datos_json = json.loads(cuerpo.decode())

            nuevos_colores = [
                datos_json["color1"],
                datos_json["color2"],
                datos_json["color3"]
            ]

            for color in nuevos_colores:
                convertir_color(color)

            colores = nuevos_colores
            indice = 0
            establecer_color(colores[indice])
            ultimo_cambio = time.ticks_ms()

            print("Nuevos colores recibidos:", colores)

            responder(cliente, "200 OK", {
                "success": True,
                "colors": colores
            })

        except Exception as error:
            print("Error:", error)

            responder(cliente, "400 Bad Request", {
                "success": False,
                "error": str(error)
            })

        return

    responder(cliente, "404 Not Found", {
        "error": "Ruta no encontrada"
    })

servidor = socket.socket()

servidor.setsockopt(
    socket.SOL_SOCKET,
    socket.SO_REUSEADDR,
    1
)

servidor.bind(("0.0.0.0", 80))
servidor.listen(2)
servidor.settimeout(0.1)

print("Servidor iniciado")
print("Abrir desde la red local:", "http://" + ip)

establecer_color(colores[0])

while True:

    actualizar_ciclo()

    try:
        cliente, direccion = servidor.accept()

        try:
            print("Solicitud desde:", direccion)
            procesar_solicitud(cliente)

        except Exception as error:
            print("Error de solicitud:", error)

        finally:
            cliente.close()

    except OSError:
        pass

    gc.collect()
