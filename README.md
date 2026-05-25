# 🍕 Napoli Pizzeria — Voice AI Order Agent

Este proyecto contiene el sistema completo del **Agente Virtual de Voz** para tomar pedidos telefónicos en Napoli Pizzeria.

El sistema funciona como un reemplazo directo para servicios como Loman AI o Maple, pero es de tu propiedad. El agente (llamado Sofia) puede conversar en **Inglés, Español y Ruso**, extraer los ítems del menú directamente de tu base de datos de Clover, enviar un SMS con un link de pago de Clover Hosted Checkout, y finalmente inyectar la orden pagada en tu Clover POS para que se imprima en la cocina.

## 📁 Estructura del Proyecto

```
napoli-voice-agent/
├── backend/
│   ├── main.py              # Servidor FastAPI (Endpoints para Vapi y Clover)
│   ├── clover_service.py    # Integración con Clover POS y Hosted Checkout
│   ├── sms_service.py       # Integración con Twilio para envío de SMS multilingüe
│   ├── webhook_handler.py   # Procesador de confirmaciones de pago de Clover
│   └── order_store.py       # Base de datos local (SQLite) para seguimiento de órdenes
├── config/
│   └── vapi_agent_config.json # Configuración completa del agente de voz (Prompt, herramientas)
├── data/
│   ├── clover_menu.json     # Menú extraído y optimizado para la IA
│   └── orders.db            # (Generado) Base de datos de órdenes
├── frontend/
│   └── index.html           # Dashboard de monitoreo en tiempo real
├── scripts/
│   ├── build_menu_json.py   # Script para actualizar el menú desde Clover
│   ├── setup_vapi_agent.py  # Script para subir la configuración a Vapi.ai
│   └── test_checkout.py     # Script para probar la generación de links de pago
├── .env                     # Variables de entorno (Credenciales)
├── requirements.txt         # Dependencias de Python
└── start.sh                 # Script de inicio rápido
```

## 🚀 Cómo Desplegar el Sistema

### 1. Requisitos Previos
* Un servidor Linux (Ubuntu recomendado) o plataforma como Render / Heroku.
* Python 3.11+ instalado.
* Una cuenta en [Twilio](https://www.twilio.com/) (Para enviar los SMS).
* Una cuenta en [Vapi.ai](https://vapi.ai/) (El motor de voz de la IA).

### 2. Configuración Inicial
1. Copia la carpeta `napoli-voice-agent` a tu servidor.
2. Abre el archivo `.env` y completa tus credenciales de Twilio y Vapi.ai. (Las de Clover ya están configuradas).
3. Asegúrate de que tu servidor tenga un dominio público con HTTPS (necesario para los webhooks). Actualiza la variable `BASE_URL` en el archivo `.env` con tu dominio (ej. `https://api.napolipizzeria.com`).

### 3. Configurar el Agente de Voz (Vapi.ai)
Ejecuta el script de configuración automática para crear el agente en Vapi.ai:
```bash
cd napoli-voice-agent
python3 scripts/setup_vapi_agent.py
```
*Este script subirá el prompt, las herramientas y la lógica de negocio a tu cuenta de Vapi.*

### 4. Configurar el Webhook en Clover
1. Ve a tu Dashboard de Clover > **Settings** > **Hosted Checkout**.
2. En la sección **Webhook URL**, ingresa: `https://TU_DOMINIO.com/webhook/payment`
3. Haz clic en "Generate" para obtener el **Signing Secret**.
4. Copia ese secreto y pégalo en tu archivo `.env` en la variable `CLOVER_WEBHOOK_SECRET`.

### 5. Iniciar el Servidor
Ejecuta el script de inicio:
```bash
./start.sh
```

El servidor iniciará en el puerto `8000`.

## 📊 Dashboard de Monitoreo
Una vez que el servidor esté corriendo, puedes acceder al dashboard de monitoreo ingresando a la URL de tu servidor en un navegador web.

Allí podrás ver en tiempo real:
* Llamadas en curso.
* Órdenes pendientes de pago.
* Órdenes pagadas y enviadas a la cocina.
* Links de pago generados.

## 🛠️ Cómo Actualizar el Menú
Si haces cambios en los precios o agregas nuevos ítems en tu Clover POS, solo necesitas ejecutar este script para que la IA aprenda el nuevo menú:
```bash
python3 scripts/build_menu_json.py
```

---
*Desarrollado a medida para Napoli Pizzeria.*
