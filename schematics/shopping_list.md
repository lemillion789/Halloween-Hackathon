# Lista de compras - potencia del cuerpo (6 nov 2026)

Base: `power_diagram.svg`. Convertidor 18-75 V a 12 V (15 A): prestado (SZDULI Y2-T601215).
Bateria 36 V = hasta ~42 V cargada: todo lo que toque esa tension debe ser DC y >= 48 V.
Plazo: el concurso cierra el 15 nov; comprar en Amazon.se o tiendas de Skane con stock inmediato.
Precios y stock NO verificados.

## Imprescindible

| # | Componente | Especificacion | Cant. | Busqueda (sv / en) |
|---|---|---|---|---|
| 1 | Pack 3 modulos XL4015 5 A | entrada 4-38 V, salida ajustable | 1 pack | "XL4015 DC-DC step down 5A" |
| 2 | Disyuntor DC (interruptor general + F1) | 16 A, >= 63 V DC, 1P o 2P | 1 | "DC-automatsakring 16A 63V" / "DC MCB 16A 63V" |
| 3 | Portafusibles 10x38 | apto DC | 1 | "sakringshallare 10x38" / "10x38 fuse holder DIN" |
| 4 | Fusibles 10x38 DC | 10 A, DC (los fotovoltaicos "PV" sirven) | 3 | "10x38 PV fuse 10A 1000VDC" |
| 5 | Condensadores electroliticos | 1000 uF, 16 V | 4 | "1000uF 16V elektrolytkondensator" |
| 6 | Seta de paro de emergencia | 22 mm, contacto NC | 1 | "nodstopp 22mm svamp NC" / "emergency stop 22mm NC" |
| 7 | Rele/contactor DC | contactos >= 60 V DC y >= 20 A, bobina 12 V | 1 | "DC kontaktor 12V 100A" / "contactor 12V 48V DC e-bike" |
| 8 | Clavija jack DC con cable | 5,5 x 2,5 mm (verificar), + al centro | 1 | "DC-kontakt 5,5x2,5 med kabel" |
| 9 | Cable silicona 2,5 mm2 (14 AWG) rojo y negro | | 2 m c/u | "silikonkabel 14AWG rod svart" |
| 10 | Cable 1,5 mm2 (16 AWG) rojo y negro | | 2 m c/u | "silikonkabel 16AWG" |
| 11 | Cable 0,75-1 mm2 (18-20 AWG) | | 2 m | "silikonkabel 20AWG" |
| 12 | Cable de senal 0,25 mm2 colores | | 5 m | "kabelsats 22AWG flerfarg" |
| 13 | Regletas WAGO 221 (3 y 5 vias) | | 6 | "WAGO 221-413" / "WAGO 221-415" |
| 14 | Terminales de anillo y punteras | surtido | 1 kit | "kabelskor sortiment" / "adernhylsor kit" |
| 15 | Resistencias 1 k y 2 k, 1/4 W | | 2 de cada | "motstandssats 1/4W" (verificar si ya las tienes) |
| 16 | Termorretractil y bridas | | 1 kit | "krympslang sortiment", "kabelbindare" |

## Opcional
| # | Componente | Cant. | Nota |
|---|---|---|---|
| 17 | Conector antichispa XT90-S | 1 | Segun el conector de tu bateria |
| 18 | Buck 5 V para hub/parlantes | 0 | Usar el tercer XL4015 del pack si la Jetson no alcanza |

## Ya lo tienes / no comprar
Convertidor de 12 V (prestado), Jetson, hub USB, adaptador de audio USB, parlantes, 2 ESP32 y servos, HC-SR04, protoboard de la cabeza, multimetro.

## Verificar antes de comprar
- Tamano y polaridad del jack de la Jetson (5,5 x 2,5 mm, + al centro).
- Que el conector de la bateria del hoverboard coincida con el antichispa elegido.
- Ficha del contactor: tension DC de los contactos.
- Disyuntor y fusibles: DC y >= 48 V, no AC ni de coche (32 V).
