# ====== Generar un código QR para un link ======

import qrcode

# URL que quieres codificar
url = "https://docs.google.com/forms/d/1USqheiO6UyeVFuUhGYheDa2Wy7xUOHvu40JZdEQKwE4/edit"  # cámbialo por tu link

# Crear el objeto QR
qr = qrcode.QRCode(
    version=1,  # controla el tamaño del QR (1 a 40)
    error_correction=qrcode.constants.ERROR_CORRECT_L,  # nivel de corrección de errores
    box_size=10,  # tamaño de cada cuadrado
    border=4,  # grosor del borde
)

# Agregar la URL al QR
qr.add_data(url)
qr.make(fit=True)

# Generar la imagen
img = qr.make_image(fill_color="black", back_color="white")

# Guardar el archivo
img.save("link_qr.png")

print("✅ QR generado y guardado como link_qr.png")
