# Casa Juan · Oficina y laboratorio de estrategias

Juan Fernando Castrejón Villa · 81901 · Actuaría · Universidad De La Salle Bajío

## Recorrido en la oficina

Casa Juan presenta el proceso del agente como una oficina con seis estaciones. **Pai** valida datos y examina variables. **Wey** muestra el pronóstico y la propuesta de Ollama. **Cawn** explica el control de riesgo y el registro Paper. Los botones de cada escritorio abren la explicación correspondiente. La escena al atardecer y los personajes se diseñaron para esta entrega.

- **Histórico.** En **Oficina**, elige un ciclo de BTCUSDT y presiona **Reproducir ciclo**. El recorrido visual usa los 30 registros archivados. El número de ciclo, la fecha de la vela, el pronóstico, los motivos, la latencia registrada y el resultado corresponden al replay. La duración de la animación se usa para la demostración.
- **En vivo.** Inicia la aplicación local, verifica Ollama en **Control** y arranca el agente Paper. La oficina consulta la telemetría de validación, inferencia, Ollama, riesgo y registro. Las fases más breves pueden pasar entre dos actualizaciones de pantalla. Los controles de inicio, pausa y detención residen en el backend.
- **Revisión.** **Mercado** reúne el gráfico y el escáner. **Simulación** contiene órdenes, decisiones y la comparativa académica. **Control** contiene el estado del agente y la auditoría.

## Laboratorio de estrategias

Selecciona un activo y abre **Laboratorio**. Puedes generar y probar 144 configuraciones con la vista histórica, editar una regla a mano o pedir a Ollama local que proponga hasta cuatro configuraciones estructuradas. El archivo JSON del experimento conserva la regla, los costos, las fechas, el hash de la muestra, la clasificación y las operaciones de la evaluación.

| Familia | Entrada al cierre de la vela | Salida al cierre de la vela |
| --- | --- | --- |
| Tendencia | Distancia positiva a SMA por encima del umbral | Cierre en o debajo de la SMA |
| Ruptura | Superar el máximo de las velas previas más el umbral | Cierre en o debajo del mínimo de la mitad de la ventana |
| Impulso | Rendimiento de la ventana por encima del umbral | Rendimiento de la ventana en cero o negativo |
| Reversión | Caída por debajo de la SMA al menos por el umbral | Retorno del cierre a la SMA |

Se puede restringir la entrada a cierres sobre SMA50 o a volumen mayor a 1.25 veces el promedio de las 20 velas anteriores. Se usa el OHLCV diario archivado de los 15 activos, con cierres estrictamente anteriores a la fecha del primer objetivo del TE académico.

1. Las propuestas de Ollama reciben un resumen del primer 55% de la muestra. El generador local combina parámetros discretos por familia. El esquema de Ollama admite familia, ventana de 5 a 90 velas, umbral en puntos básicos y filtro.
2. El siguiente 25% se divide en tres ventanas consecutivas. Cada prueba empieza en efectivo y usa solo información conocida hasta el cierre de la vela anterior a la ejecución. El puntaje es la mediana de la diferencia entre el rendimiento neto y el drawdown máximo de cada ventana. Una candidata automática debe cerrar al menos tres operaciones repartidas en al menos dos ventanas.
3. El 20% cronológico final se usa para medir la regla elegida y una referencia de comprar y mantener. El laboratorio permite repetir el experimento y ver distintas reglas. Si se usa ese tramo para ajustar hipótesis en rondas posteriores, pasa a formar parte del proceso de selección.
4. La simulación abre posiciones largas con hasta el 10% del efectivo disponible y parte de 50,000 USDT. Aplica comisión y deslizamiento adverso por ejecución en ambas direcciones. La referencia inicia con la misma asignación y los mismos costos. La cartera remanente se liquida al último cierre del tramo. El drawdown usa las valuaciones al cierre y el saldo inicial. El resultado incluye una prueba con costos duplicados.

La comisión y el deslizamiento del laboratorio son supuestos configurables. El motor explora reglas diarias con unidades fraccionarias y un modelo simple de ejecución. Las reglas se ensayan como hipótesis y quedan en el laboratorio de investigación. Las operaciones del proyecto y los experimentos se registran como simulaciones.

## Material del curso y referencias consultadas

| Material del curso | Aplicación en Casa Juan |
| --- | --- |
| Protocolo de DL para Finanzas con agente IA, secciones 14 a 16 | Oficina con una estación por fase, datos diarios, propuesta estructurada, riesgo determinista, ejecución Paper, recuperación y auditoría |
| Kaabar, capítulos 7 a 9 y material de sesgo, varianza y regularización | Inferencia con el modelo entrenado y trazabilidad del escalador, cronología, comparación de ventanas y evaluación posterior |
| Kaabar, capítulos 10 y 11 | Estado, decisión y resultado observable del agente, indicadores y reglas explicables |
| Apuntes de análisis técnico, preguntas de aprendizaje automático e infografías | Promedios móviles, volumen, comparación de reglas y diagnóstico de sobreajuste |

- Freqtrade documenta verificaciones contra señales que cambian al recibir datos futuros. Se probó que alterar las velas del tramo final deja intacta la clasificación de Casa Juan. [Repositorio](https://github.com/freqtrade/freqtrade) y [análisis de anticipación](https://www.freqtrade.io/en/stable/lookahead-analysis/).
- Backtesting.py documenta ejecución en la apertura siguiente, comisiones y cierre de posiciones al final del periodo. [Repositorio](https://github.com/kernc/backtesting.py) y [referencia del simulador](https://kernc.github.io/backtesting.py/doc/backtesting/backtesting.html).
- LEAN documenta modelos de ejecución y deslizamiento. Se parametrizan costos y se mide el resultado de duplicarlos. [Repositorio](https://github.com/QuantConnect/Lean) y [deslizamiento](https://www.quantconnect.com/docs/v2/writing-algorithms/reality-modeling/slippage/key-concepts).
- La documentación de scikit-learn explica la importancia de respetar el orden de las observaciones. El trabajo de Bailey y coautores documenta el riesgo de sobreajustar al probar muchas configuraciones. [Validación temporal](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html) y [artículo de la AMS](https://www.ams.org/journals/notices/201405/rnoti-p458.pdf).
- Agent Office muestra el patrón de representar estados técnicos con personajes que caminan y trabajan. La oficina y la correspondencia entre personajes y fases de Casa Juan se elaboraron para este proyecto. [Agent Office](https://github.com/charliedouglas/agent-office).
- Los materiales públicos de Ross Cameron muestran el uso de un escáner de volumen y una revisión del gráfico. El laboratorio tomó el volumen relativo como filtro diario independiente. También se revisó una evaluación pública del *opening range breakout* difundido por Patrick Wieland. Esa hipótesis requiere datos intradía y se documenta como referencia. [Revisión pública de Ross Cameron](https://www.warriortrading.com/behind-trades-metrics-profitable-trader-ep-8/) y [evaluación pública de ORB](https://litmustrade.live/c/patrickwieland/).
- La salida estructurada de Ollama permite generar un objeto con un esquema JSON. El servidor valida las propuestas antes de enviarlas al simulador del laboratorio. [Documentación de Ollama](https://docs.ollama.com/capabilities/structured-outputs/).
