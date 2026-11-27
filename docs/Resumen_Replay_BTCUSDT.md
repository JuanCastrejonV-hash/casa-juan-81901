# Replay histórico de BTCUSDT

Juan Fernando Castrejón Villa · Gestión de bases de datos · Matrícula 81901

Se procesaron los 30 últimos periodos del conjunto de prueba, con primera señal el 2026-10-21 y último cierre el 2026-11-20, ambos en UTC. Los pronósticos se calcularon con el modelo congelado de BTCUSDT entrenado en T4. La diferencia máxima respecto de los pronósticos guardados en Colab fue 5.82e-10.

Ollama 0.40.16 ejecutó las 30 propuestas con `qwen3:0.6b` en CPU local, con 6 hilos.

Cada estrategia empezó con 50,000 USDT de saldo simulado. Se usaron los mismos días, comisión de 0%, deslizamiento adverso de 2 puntos básicos por ejecución y un máximo de 10% de exposición al par. Comprar y mantener usa esa exposición inicial. El deslizamiento está incorporado en los precios ejecutados. La simulación liquida las posiciones abiertas al final del periodo.

| Estrategia | Rendimiento neto | Caída máxima | Operaciones cerradas | Tasa de acierto | Rechazos | Comisiones | Latencia media |
|---|---:|---:|---:|---:|---:|---:|---:|
| Modelo sin LLM | -2.54% | 2.66% | 1 | 0.00% | 0 | 0.00 USDT | No aplica |
| Agente con Ollama | -2.54% | 2.66% | 1 | 0.00% | 29 | 0.00 USDT | 11.40 s |
| Comprar y mantener | -2.54% | 2.66% | 1 | 0.00% | 0 | 0.00 USDT | No aplica |

El agente propuso comprar 30 veces, mantener 0 veces y vender 0 veces. El simulador bloqueó 29 compras porque ya había una posición abierta. Las tres estrategias ejecutaron la misma compra inicial y liquidaron al mismo precio. El agente obtuvo el mismo rendimiento con mayor latencia en este periodo.

Ollama recibió la observación y las tres herramientas de lectura en cada ciclo. En el registro quedaron 0 llamadas a herramientas.

La primera ejecución quedó interrumpida en el cuarto ciclo por una respuesta con fecha incorrecta. El esquema de salida fija el símbolo y la fecha a partir de la observación y restringe la venta a posiciones existentes. Se repitieron las mismas velas desde carteras iniciales nuevas. Las 33 pruebas automatizadas pasaron tras el cambio.

Los CSV y las bases SQLite conservan las decisiones, órdenes Paper, patrimonio y eventos por estrategia. El archivo de verificación relaciona el replay con los resultados originales de Colab.
