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
- Jetson / visión: sin empezar (deteccion de persona para el seguimiento).
- Reconocer disfraces (30 oct): `vision/` (ver README.md ahi; venv `vision/.venv/Scripts/python`). `costume_describer.py` describe fotos o la webcam (`--camera 0`, ESPACIO describe) y devuelve JSON `{"people":[{character, category, description, confidence}]}`. Backend segun el nombre del modelo: con "/" -> API de NVIDIA (build.nvidia.com, `NVIDIA_API_KEY`, por defecto `meta/llama-3.2-90b-vision-instruct`), con ":" -> Ollama local, `claude-*` -> API de Claude (`ANTHROPIC_API_KEY`). Medido en la laptop (GTX 1650 4 GB): Qwen3-VL 2B por Ollama 15/18 aciertos pero ~18 s/foto (16 s solo en leer imagen+prompt, ~1270 tokens fijos; reducir la imagen no ayuda) -> demasiado lento. Decision: para jugar el 31 oct con amigos se usa la API de NVIDIA (meta < 10 s); para el concurso (100 % offline) queda pendiente otra solucion (p. ej. CLIP para nombrar el personaje rapido + VLM en la Jetson). `benchmark.py` compara modelos sobre `test_images/` (fotos CC de Wikimedia, creditos en credits.json; bajar con `fetch_test_images.py`). Actualizacion (30 oct): Llama Vision no se puede usar en Suecia (licencia UE); modelo elegido `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning` (15/18, 1-3 s por persona). Varias personas: `vision/person_costume.py` (YOLO11n + ByteTrack, recorte por persona, VLM una vez por ID; en la laptop venv Linux `vision/.venv/bin/python`). Voz para la fiesta del 31 oct (solo laptop; el concurso usara otro modelo local): `vision/tts.py` (Kokoro-82M, voz bm_george + efectos pedalboard) y `vision/skull_lines.py` (relleno inmediato, frase de Nemotron segun el disfraz, frase sarcastica si no hay disfraz); se activa con `person_costume.py --camera 0 --speak`. Pendiente: probar con la C922 y varias personas disfrazadas, y solucion offline (VLM + TTS) para el concurso.
- Voz (STT/LLM/TTS): sin empezar
- Ojos TFT (ESP32): HECHO (26 oct). `firmware/eyes/` (ver README.md ahi). ESP32 clasico, 2x ST7735 verticales (ROTATION 2), ojos rojos inyectados en sangre, 12 expresiones. Interfaz serial 115200: `L x y` (mirar, -1..1), `M <mood>`, `B`, `D` demo. Moods: neutral angry happy surprised sleepy sad suspicious evil dead possessed dizzy scared. Pendiente: probar seguimiento real desde la Jetson (si mira al lado contrario, invertir signo de x/y). Nota: 3 buffers de 40 KB no caben en el heap; hay 2. IMU (27 oct, sin probar en hardware): modulo GY-521 (MPU-6050) por I2C en SDA=21 SCL=22 (TFT usan 18,23,16,4,5,17); comandos `I`, `I 1`/`I 0` (stream 20 Hz), `I C`; respuesta `IMU pitch roll ax ay az gx gy gz`; sacudida -> mood dizzy 3 s. LEDs rojos interiores (27 oct): 3 LEDs en GPIO32 via KSP2222A (base 1 k, 100 ohm por LED a 3V3), comandos `G 0..255`, `G P` latido suave, `G H [bpm]` corazon pum-pum (tarea FreeRTOS en core 0, 10 ms); se descarto el LED RGB. Sketch de prueba `firmware/led_test/`.
- Cuello / servos: esperando hardware (29 oct)
- Hoverboard: sin empezar (verificar placa y ST-Link)
- Carcasa 3D / calavera: soporte de ojos generado (26 oct) con `CAD/make_mount.py`; STEP editable en FreeCAD via `CAD/make_mount_step.py` (CadQuery, mismos parametros) (venv `CAD/.venv`, salida en `CAD/out/`: eye_mount.stl, tray_test.stl, assembly_preview.stl). TFT en vertical, pines arriba, angulo interno 130 deg (V hacia el frente), 4 postes M3 por pantalla, ranura para pines. Parametros al inicio del script (EYE_SPACING=64 y PILOT_D=2.5 son supuestos; medir cuencas y tornillos). Modelo de la pantalla: CAD/1.8 TFT Display ST7735 - 3898101 (PCB 57.4x34, agujeros 3 mm a 52x28.6). Con pines arriba usar ROTATION 0 en firmware/eyes; sin imprimir ni probar aun.
- Soporte PCB vertical (27 oct): `CAD/make_pcb_stand.py` -> `CAD/out/pcb_stand.step/.stl`. Soporte en L para PCB con agujeros M3 a 64 x 40.5 mm, postes 6 mm, piloto 2.5 mm (autorroscante). En Windows el venv es `CAD/.venv/Scripts/python`.
- Base giratoria (30 oct): `CAD/make_turntable.py` -> `CAD/out/turntable_base`, `turntable_top` (.step/.stl) y `turntable_assembly.stl`. Servo MG996R vertical colgado de sus orejas (M4 autorroscante), eje en el centro; anillo guia exterior 1 mm bajo el plato (GUIDE_GAP: subir si se pone rodamiento); plato con cuna en trapecio simetrico (cabeza: largo 140, lados 105 y 55; centroide sobre el eje) + disco R48 que tapa el anillo, se atornilla al horn redondo (plato 3 mm apoyado directo sobre el horn, avellanados para tornillos a ras), 2 pasacables. Version adelgazada: base 110 mm, paredes 2.5. El servo del giro lo controla el Arduino Mega (no el ESP32 de la cabeza). Cotas del servo y horn segun hoja tipica: medir FLANGE_Z, HORN_TOP y HORN_HOLES_R antes de imprimir. Sin imprimir.
- Documentación / artículo: sin empezar
