# Proyecto: Calavera robótica (element14 Halloween Hackathon 2026)

Contexto compartido para todas las sesiones/terminales. Cada terminal trabaja una parte distinta; si cambias una decisión o interfaz, actualiza este archivo.
Idioma de trabajo con el usuario: español. El artículo final de la competencia va en inglés.

## Concurso
- Organiza element14 Community. Reglas: `Halloween+Competition+2026+Terms+&+Conditions.pdf` (en esta carpeta).
- Abre 19 oct 2026. **Cierra 23:59 hora UK del domingo 15 nov 2026**. Ganadores 20 nov.
- Entrega: UN artículo tipo proyecto en la comunidad con (1) paso a paso, (2) cómo encaja con el tema Halloween, (3) video/fotos del proyecto **completo y funcionando**.
- Recomendado: imágenes >=640x480, esquemáticos, código, archivos 3D, lista de componentes con part numbers.
- Criterios (mismo peso): originalidad, innovación, mérito técnico.
- Prohibido: violencia realista (PEGI 18), drogas, contenido ofensivo. Los ganadores participan en publicidad.
- El perfil de element14 debe tener nombre, dirección y teléfono reales. Participante 18+.

## Idea
Calavera animatrónica que sigue a las personas, habla con personalidad y reacciona a gestos, **100 % offline** (LLM local en la Jetson). Opcional: montada sobre un hoverboard hackeado como base móvil.
Diferenciador frente a un "robot seguidor" genérico: personalidad + voz + gestos + ojos expresivos, todo local.

## Hardware disponible
- Jetson Orin Nano (cerebro: visión, STT, LLM, TTS). Verificar versión de RAM (8 GB vs 4 GB), almacenamiento y JetPack.
- Cámara Logitech C922 Pro (montada justo debajo de la cabeza; su micrófono puede servir para voz).
- 2 pantallas TFT 1.8" SPI 128x160 (ojos).
- 2 ESP32 "S1" + 1 ESP32-S3 (llega viernes 30 oct).
- 4 servos de 180° (llegan jueves 29 oct) para el cuello (giro y cabeceo).
- IMU, sensor ultrasónico, reguladores de voltaje.
- 2 parlantes USB pequeños.
- Cabeza de calavera de plástico hueca.
- Impresora 3D, equipo de soldar.
- Hoverboard (base móvil), 6 joycons (sin rol definido; control manual/gestos opcional).
- Por confirmar: ST-Link, modelo de placa del hoverboard, botón de paro y batería.

## Arquitectura prevista (puede cambiar)
- Jetson: captura de cámara, detección de persona, gestos (MediaPipe), STT (Whisper pequeño), LLM local pequeño (~3B cuantizado), TTS (Piper). Coordina todo.
- ESP32/S3: ojos TFT animados y control de servos del cuello; reciben comandos de la Jetson (serie o WiFi; por decidir).
- Hoverboard: firmware EFeru hoverboard-firmware-hack-FOC en modo UART, tracción diferencial (NO autobalanceo). Límite de velocidad en firmware y en software, ultrasonido como freno, paro físico que corte la batería.
- Alimentación: la Jetson acepta 7-25 V DC; si se usa la batería del hoverboard (36 V) hace falta regulador reductor.

## Restricciones y riesgos
- Memoria de la Jetson limitada: no cargar LLM, STT, TTS y visión en GPU a la vez sin medir.
- Latencia de voz: reacción visual inmediata (mirada/ojos) y voz que puede tardar; usar frases de relleno mientras piensa el LLM.
- El movimiento sobre hoverboard es opcional: decisión go/no-go el **8 nov**. El proyecto debe estar completo sin él.
- Seguridad: se demuestra en casa, con límite de velocidad y paro de emergencia.

## Prioridades
1. Imprescindible: cabeza que sigue a la persona (servos + cámara), ojos TFT expresivos, voz con personalidad (LLM local).
2. Muy bueno: gestos, movimiento sobre hoverboard.
3. Extra: joycons y reacciones complejas.

## Cronograma (~3 h/día)
- 26 oct: Jetson lista, cámara, detección de persona, ojos TFT en ESP32.
- 27-28 oct: pipeline de voz (mic -> Whisper -> LLM -> Piper -> parlantes), medir latencia.
- 29 oct: llegan servos; cuello 2 DOF con seguimiento.
- 30 oct: llega ESP32-S3; integrar ojos + servos + Jetson.
- 31 oct-2 nov: prueba real de Halloween y grabación de video.
- 3-7 nov: gestos, personalidad, carcasa/impresión 3D, hoverboard (firmware y movimiento).
- 8 nov: go/no-go del movimiento.
- 9-12 nov: pulido, esquemáticos, videos finales.
- 13-14 nov: redactar artículo en inglés.
- 15 nov: enviar con margen antes de las 23:59 UK.

## Convenciones para las sesiones
- Anotar abajo el estado de cada parte al terminar una sesión, para que las demás terminales lo sepan.
- Guardar part numbers de todo componente usado (se pide en el artículo).
- Tomar fotos/videos mientras se construye; sirven para el artículo.

## Estado por módulo
(Actualizar. Formato: módulo — estado — interfaces/decisiones — pendientes)
- Jetson / visión: sin empezar
- Voz (STT/LLM/TTS): sin empezar
- Ojos TFT (ESP32): HECHO (26 oct). `firmware/eyes/` (ver README.md ahi). ESP32 clasico, 2x ST7735 verticales (ROTATION 2), ojos rojos inyectados en sangre, 12 expresiones. Interfaz serial 115200: `L x y` (mirar, -1..1), `M <mood>`, `B`, `D` demo. Moods: neutral angry happy surprised sleepy sad suspicious evil dead possessed dizzy scared. Pendiente: probar seguimiento real desde la Jetson (si mira al lado contrario, invertir signo de x/y). Nota: 3 buffers de 40 KB no caben en el heap; hay 2.
- Cuello / servos: esperando hardware (29 oct)
- Hoverboard: sin empezar (verificar placa y ST-Link)
- Carcasa 3D / calavera: soporte de ojos generado (26 oct) con `CAD/make_mount.py`; STEP editable en FreeCAD via `CAD/make_mount_step.py` (CadQuery, mismos parametros) (venv `CAD/.venv`, salida en `CAD/out/`: eye_mount.stl, tray_test.stl, assembly_preview.stl). TFT en vertical, pines arriba, angulo interno 130 deg (V hacia el frente), 4 postes M3 por pantalla, ranura para pines. Parametros al inicio del script (EYE_SPACING=64 y PILOT_D=2.5 son supuestos; medir cuencas y tornillos). Modelo de la pantalla: CAD/1.8 TFT Display ST7735 - 3898101 (PCB 57.4x34, agujeros 3 mm a 52x28.6). Con pines arriba usar ROTATION 0 en firmware/eyes; sin imprimir ni probar aun.
- Documentación / artículo: sin empezar
