 Tarjeta de Crédito (VISA)

Número: 4051 8856 0044 6623
Fecha de expiración: Cualquier fecha futura (ej. 12 / 30).
CVV: 123
💳 Tarjeta de Débito (Redcompra / Webpay)

Número: 4051 8842 3993 7763
Fecha de expiración: 12 / 30.
(Nota: si Transbank en débito de pruebas te pide RUT y Clave de banco, puedes usar RUT 11.111.111-1 y clave 123).


¡Claro! Configurar Django por primera vez puede parecer un laberinto de comandos, pero una vez que tienes la estructura clara, es pan comido. Aquí tienes una plantilla de README.md profesional y lista para usar, que incluye los pasos esenciales de instalación.
🚀 Nombre de tu Proyecto Django
Una breve descripción de lo que hace tu increíble aplicación (ej: "Plataforma de gestión de inventarios" o "Blog personal con autenticación").
📋 Requisitos Previos
Antes de empezar, asegúrate de tener instalado:
 * Python 3.10+
 * pip (Administrador de paquetes de Python)
 * Virtualenv (Recomendado)
🛠️ Guía de Instalación Paso a Paso
Sigue estos pasos para tener el entorno de desarrollo funcionando localmente:
1. Clonar el repositorio
git clone https://github.com/tu-usuario/tu-repositorio.git
cd tu-repositorio

2. Crear y activar el entorno virtual
Es fundamental para mantener las dependencias aisladas.
 * En Windows:
   python -m venv venv
venv\Scripts\activate

 * En macOS/Linux:
   python3 -m venv venv
source venv/bin/activate

3. Instalar dependencias
pip install django
# O si ya tienes un archivo de requerimientos:
pip install -r requirements.txt

4. Configurar la Base de Datos
Aplica las migraciones iniciales para crear las tablas necesarias:
python manage.py migrate

5. Crear un superusuario (Admin)
Para acceder al panel de administración de Django:
python manage.py createsuperuser

6. Iniciar el servidor de desarrollo
python manage.py runserver

Visita http://127.0.0.1:8000/ en tu navegador para ver la aplicación.
🗂️ Estructura del Proyecto
 * core/: Configuración principal del proyecto.
 * apps/: Directorio que contiene las aplicaciones específicas (opcional).
 * static/: Archivos CSS, JS e imágenes.
 * templates/: Archivos HTML.
 * manage.py: Utilidad de línea de comandos para tareas administrativas.
🧪 Pruebas
Para ejecutar los tests del proyecto, usa:
python manage.py test

> Nota: No olvides crear un archivo .env para las variables de entorno sensibles (como SECRET_KEY o credenciales de DB) y añadirlo al .gitignore.
> 
¿Te gustaría que personalice alguna sección específica para una base de datos como PostgreSQL o que añada instrucciones para Docker?
