# Lista de compras - potencia del cuerpo (6 nov 2026)

Base: `power_diagram.svg`. Convertidor DC-DC 60 V a 12 V (10 A, 120 W): el del usuario. Verificar en su ficha que la entrada minima sea <= 30 V (la bateria baja a ~30-33 V).
Bateria 36 V = hasta ~42 V cargada: todo lo que toque esa tension debe ser DC y >= 48 V.
Plazo: el concurso cierra el 15 nov; comprar en Amazon.se o tiendas de Skane con stock inmediato.
Precios y stock NO verificados.

## Imprescindible

| # | Componente | Especificacion | Cant. | Busqueda (sv / en) |
|---|---|---|---|---|
| 1 | Pack 3 modulos XL4015 5 A | entrada 4-38 V, salida ajustable | 1 pack | "XL4015 DC-DC step down 5A" |
| 2 | Fusibles mini de cuchilla **58 V DC** (Biltema 2000068264, pack de 15 A) | 15 A (F1) | 1 pack (ya tienes) | "flatstiftsakring mini 15 A" |
| 3 | Fusibles mini de cuchilla 58 V DC, otros valores | 5 A (F2 y F5) x4, 3 A (F3, F4) x4, 2 A (F6, opcional) x1 | surtido | "flatstiftsakring mini 58V 5A/3A/2A" - verificar que digan 58 V; a 12 V (F3-F6) tambien valen los de coche de 32 V |
| 4 | Portafusibles mini de cuchilla con cables | >= 15 A (F1, F2), 5 A para el resto | 1 + 5 | "sakringshallare flatstift mini" |
| 5 | Condensadores electroliticos | 1000 uF, 16 V | 4 | "1000uF 16V elektrolytkondensator" |
| 6 | Seta de paro de emergencia | 22 mm, contacto NC | 1 | "nodstopp 22mm svamp NC" / "emergency stop 22mm NC" |
| 7 | Rele/contactor DC | contactos >= 60 V DC y >= 20 A, bobina 12 V | 1 | "DC kontaktor 12V 100A" / "contactor 12V 48V DC e-bike" |
| 8 | Clavija jack DC con cable | 5,5 x 2,5 mm (verificar), + al centro | 1 | "DC-kontakt 5,5x2,5 med kabel" |
| 9 | Cable silicona 2,5 mm2 (14 AWG) rojo y negro | | 2 m c/u | "silikonkabel 14AWG rod svart" |
| 10 | Cable 1,5 mm2 (16 AWG) rojo y negro | | 2 m c/u | "silikonkabel 16AWG" |
| 11 | Cable 0,75-1 mm2 (18-20 AWG) | | 2 m | "silikonkabel 20AWG" |
| 12 | Cable de senal 0,25 mm2 colores | | 5 m | "kabelsats 22AWG flerfarg" |
| 13 | Regletas WAGO 221-413 (3 vias) | 18 segun `power_diagram` (W1-W18); con 221-415 (5 vias) la masa comun baja de 9 a 3 | 18 (ya tienes algunas) | "WAGO 221-413" / "WAGO 221-415" |
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
- F1 y F2 (36-42 V): fusibles DC de >= 48 V. Los mini de Biltema dicen "<58 V DC": valen. Los de coche normales son de 32 V: NO para F1/F2.
- Interruptor general: 48 V / 200 A (ya lo tienes); verificar que sea para DC.

## Fusibles (ver `power_diagram`)
| Ref | Valor | Donde | Para que |
|---|---|---|---|
| F1 | 15 A, 58 V | + de la bateria, antes del interruptor | Cortocircuito en todo el bus de 36 V y cables 14 AWG |
| F2 | 5 A, 58 V | Entrada (IN+) del convertidor 12 V (carga real ~2-3 A a 36 V) | Aisla la rama de 12 V de la de motores; protege su cable |
| F3 | 3 A | Entrada 12 V del XL4015 1 (servo giro) | Corto en ese buck o su servo (consumo normal ~1 A a 12 V) |
| F4 | 3 A | Entrada 12 V del XL4015 2 (servo cabeceo) | Igual que F3 |
| F5 | 5 A | 12 V de la Jetson | Corto en su cable/jack (Orin Nano ~2 A a 12 V) |
| F6 | 2 A (opcional) | Buck del hub USB | Solo si se monta ese buck |
Los fusibles de la rama de 12 V (F3-F6) evitan que un corto en una rama haga circular hasta 15 A por cables de 16-18 AWG.
