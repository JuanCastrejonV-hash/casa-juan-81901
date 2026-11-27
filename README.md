# Casa Juan

**Juan Fernando Castrejón Villa · Matrícula 81901**  
**jcv81901@lasallebajio.edu.mx · Actuaría · 5.º semestre**  
**Universidad De La Salle Bajío · Gestión de bases de datos**  
**Profesor Rubén Miguel Rodríguez Rangel**

Proyecto adaptado al protocolo `Protocolo_DL_Finanzas_Con_Agente_IA.pdf` y a la aclaración de trabajar con **15 activos**. El cuaderno anterior se conserva como anexo de estudio del libro; sus entrenamientos en CPU y sus objetivos en diferencias absolutas no se presentan como evidencia de esta práctica.

## Estado de la entrega

Se incluyen los históricos auditados de MEXC, los 15 modelos entrenados en NVIDIA T4, sus escaladores y las evaluaciones del conjunto de prueba (TE). El [cuaderno ejecutado en Colab](https://colab.research.google.com/drive/1rBr_In1QC-_EjRIY7omLMOP92adsXyxk?usp=sharing) se comprobó en lectura sin iniciar sesión. Su copia en `notebooks/` conserva las salidas de la sesión y corrige la sangría de la celda que muestra los CSV.

La aplicación React/TypeScript está compilada y el backend implementa autenticación, inferencia local, controles de riesgo, ejecución exclusivamente Paper y persistencia SQLite. Se verificaron 33 pruebas y se completaron 30 ciclos históricos de BTCUSDT con Ollama local. El cierre al 20 de noviembre de 2026 dio un rendimiento neto de -2.54% en las tres estrategias. La comparación, las propuestas y las bases Paper están en `evidencia/replay_BTCUSDT/`.

## Demostración rápida

1. Descomprime el ZIP y abre `Abrir_Casa_Juan_81901.html`. La vista **Histórico** inicia en BTCUSDT con la evidencia de la entrega.
2. En **Mercado → Gráfico y señal**, muestra las velas de MEXC Spot con sus fechas UTC, el cierre y la SMA20. En **Oficina**, pulsa **Reproducir ciclo** para seguir una decisión del agente.
3. En **Simulación → Operaciones**, elige **Con Ollama** para mostrar **Ganancia / pérdida**, las compras y ventas de **Órdenes ejecutadas** y su columna **PnL · USDT**. Puedes descargar el CSV desde esa tabla.
4. En **Simulación → Comparativa**, revisa patrimonio final, retorno y caída máxima de las tres estrategias. En **Control → Auditoría**, muestra el veto por posición abierta.

La vista histórica funciona con los archivos de mercado y el replay incluidos. Para consultar velas nuevas, abre la aplicación local y selecciona **En vivo**.

## Versiones y avances

| Versión o etapa | Avance verificable | Evidencia |
| --- | --- | --- |
| Cuaderno T4 | Descarga y auditoría de MEXC, entrenamiento de 15 modelos, evaluación cronológica y exportación con hashes. | [Cuaderno ejecutado](https://colab.research.google.com/drive/1rBr_In1QC-_EjRIY7omLMOP92adsXyxk?usp=sharing) y [verificación de la entrega](evidencia/verificacion_entrega.json) |
| API y aplicación web 1.0.0 | FastAPI, vista React, inferencia local, riesgo determinista, operaciones Paper y bitácora SQLite. | [Configuración](config/project.json), [paquete web](frontend/package.json) y [arquitectura](docs/Arquitectura_y_Demo_Casa_Juan.md) |
| Casa Juan 2.0.0 | Oficina animada con las etapas del agente, vista histórica reproducible y laboratorio que evalúa 144 configuraciones por activo. | [Verificación de Casa Juan](evidencia/verificacion_entrega.json) y [laboratorio](docs/Investigacion_y_Laboratorio_Casa_Juan.md) |
| Entrega del 27 de noviembre de 2026 | Repositorio público, CI de TypeScript y Python, informe y autoevaluación de 35 indicadores. | [Historial de Git](https://github.com/JuanCastrejonV-hash/casa-juan-81901/commits/main/) y [autoevaluación](docs/Evaluacion_Rubrica_Casa_Juan_81901.pdf) |

La inferencia verificada usó TensorFlow CPU 2.21.0, Keras 3.13.2 y scikit-learn 1.6.1. El [archivo de dependencias web](frontend/package-lock.json) fija React 19.3.1, TypeScript 5.9.3 y Vite 7.3.8. El replay de BTCUSDT usó Ollama 0.40.16 con `qwen3:0.6b`. [Evidencia de inferencia y Ollama](evidencia/replay_BTCUSDT/verificacion_inferencia.json)

## Revisión de la entrega

- [Guía de entrega](Guia_Entrega_81901.md)
- [Informe académico a dos columnas](docs/Informe_Juan_Fernando_Castrejon_Villa_Dos_Columnas.pdf) y [matriz de cumplimiento](docs/Matriz_Cumplimiento.csv)
- [Autoevaluación con los 35 indicadores](docs/Evaluacion_Rubrica_Casa_Juan_81901.pdf)

El flujo del agente, las rutas REST y la demostración de diez minutos están documentados junto a los controles Paper. [Arquitectura y demostración](docs/Arquitectura_y_Demo_Casa_Juan.md)

GitHub Actions comprueba los tipos de TypeScript, compila la interfaz y ejecuta las pruebas de Python. La ejecución verificada pasó las 33 pruebas. [Configuración de CI](.github/workflows/ci.yml) · [Ejecución verificada](https://github.com/JuanCastrejonV-hash/casa-juan-81901/actions/runs/46015722997)

## Los 15 pares

BTCUSDT, ETHUSDT, SOLUSDT, XRPUSDT, ADAUSDT, DOGEUSDT, AVAXUSDT, DOTUSDT, LINKUSDT, LTCUSDT, BCHUSDT, XLMUSDT, TRXUSDT, ETCUSDT y ATOMUSDT.

Son pares **configurados**. Su disponibilidad, reglas y profundidad histórica se consultan en MEXC antes de usarlos. Si un par no está disponible o tiene menos de 1,500 observaciones válidas, se registra el incidente y no se entrena. No se sustituyen automáticamente por otro activo ni se inventan fechas.

## Datos de mercado

**Histórico** muestra velas diarias reales descargadas del endpoint público `GET /api/v3/klines` de MEXC Spot. El archivo de origen conserva el par, el intervalo, la URL y la respuesta del mercado. Para BTCUSDT, el CSV contiene 2,499 velas auditadas. [Descarga de BTCUSDT](data/raw/BTCUSDT.json) · [CSV auditado](data/processed/BTCUSDT.csv)

**En vivo** solicita velas cerradas y cotizaciones públicas desde la app local. La vista reporta un error si la consulta falla. Para la demostración con el conjunto archivado, vuelve a **Histórico**. [Cliente de mercado](pai/data.py) · [Ruta de mercado](backend/app.py)

## Método del cuaderno

- Frecuencia diaria, calendario cripto continuo, UTC y velas cerradas.
- Objetivo: `close[t+1] / close[t] - 1`; entrada: 20 rendimientos conocidos hasta `t`.
- TR/VA/TE: 70/15/15 de los ejemplos según su fecha objetivo. Las mismas fechas se utilizan para comparar variables.
- Referencias cero y regresión lineal; escaladores ajustados solo con TR.
- MLP y LSTM con 16, 32 y 64 unidades, manteniendo el resto de la configuración. Mejor configuración base de cada red repetida con semillas 123, 7 y 42; se usa la semilla 123 prefijada, no la mejor semilla.
- Versión con dos indicadores: distancia a SMA20 y desviación estándar muestral de 20 rendimientos diarios, sin anualizar. No hay relleno hacia atrás.
- Tres ventanas expansivas dentro de TR. La parada temprana de cada fold usa una validación interna anterior al bloque evaluado.
- Hasta cinco umbrales positivos; comparación de señal con y sin filtro SMA20. Selección con rendimiento neto de VA y menor drawdown en empate.
- Configuración serializada antes de consultar TE. El archivo de bloqueo impide reentrenar y volver a seleccionar con el mismo TE. Una ejecución interrumpida después de abrir TE conserva el bloqueo.
- Pronóstico futuro con valor real vacío; prueba de recarga del modelo y escaladores.

La diferenciación fraccionaria, el COT y el pronóstico de varios pasos se documentan como ampliaciones opcionales. No son necesarios para el puntaje completo de la práctica.

## Instalar en el equipo

Python 3.11 o 3.12. Para recompilar la interfaz, usa Node 20.19 o posterior en la línea 20, o Node 22.12 en adelante. La distribución incluye `frontend/dist`. Las versiones de TensorFlow, Keras y scikit-learn en `requirements.txt` coinciden con las de los modelos de Colab.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python scripts/configurar.py
```

En Windows, activar con `.venv\Scripts\activate`.

El configurador crea `.env` con permisos privados y **no imprime las claves**. Abrirlo localmente, copiar únicamente `PAI_API_KEY` y usarla en la pantalla de acceso. No compartir `.env`, no incluirlo en el repositorio ni subirlo a Colab. El navegador usa una cookie HttpOnly y no guarda la clave en localStorage ni en variables VITE.

Los resultados de Colab ya se encuentran en la distribución. Para cargar el ZIP de Colab en otra copia del proyecto:

```bash
python scripts/importar_resultados.py /ruta/resultados_colab_81901.zip
```

La importación comprueba rutas y hashes y rechaza sobrescribir otra versión. Para un experimento nuevo se debe conservar la entrega anterior en otra carpeta.

### Ollama local

Instalar desde https://ollama.com/download. En una terminal:

```bash
OLLAMA_NO_CLOUD=1 OLLAMA_HOST=127.0.0.1:11434 ollama serve
```

En otra terminal:

```bash
ollama pull qwen3:1.7b
```

El modelo predeterminado se configura en `.env`. El replay incluido utilizó `qwen3:0.6b`. Para configurar esa variante, ejecuta `ollama pull qwen3:0.6b` y establece `OLLAMA_MODEL=qwen3:0.6b`. La aplicación verifica que el modelo esté descargado y sea local. El gateway rechaza claves ausentes o incorrectas. Las herramientas de lectura consultan el pronóstico, los indicadores y la cartera. Las justificaciones usan frases factuales con cifras y unidades calculadas por el servidor.

### Abrir la aplicación

```bash
python -m uvicorn backend.app:create_app --factory --host 127.0.0.1 --port 8000
```

Abrir http://127.0.0.1:8000. La documentación de endpoints está en `/docs`. También se incluyen `Iniciar_Mac.command` e `Iniciar_Windows.bat`, que preparan un entorno local si hace falta. La primera instalación necesita internet y puede tardar.

El tablero inicia en **Histórico**, con las velas y los pronósticos archivados. **Mercado** permite explorar los cierres y SMA20 de 30, 90 o 180 velas. **Escáner** filtra los 15 pares. **Operaciones**, **Comparativa** y **Auditoría** muestran los registros guardados, con exportación CSV. **Sistema** permite recorrer los pasos de cada decisión del replay de BTCUSDT.

Para consultar precios actuales, selecciona **En vivo**. En **Sistema**, verifica Ollama e inicia el agente Paper para el activo seleccionado o para todos los modelos verificados. Los controles para pausar y detener aparecen en esa misma vista. Para simular otro activo con datos archivados, selecciónalo y usa **Ejecutar 30 ciclos** en **Comparativa**. Se pueden liquidar posiciones simuladas explícitamente mediante el endpoint autenticado `POST /api/liquidate/{symbol}`; detener por sí solo conserva la posición.

En **Laboratorio**, **Idear con Ollama** propone reglas estructuradas usando la aplicación local. [Investigación y laboratorio de Casa Juan](docs/Investigacion_y_Laboratorio_Casa_Juan.md) describe su validación y el recorrido de la oficina.

## Dos simulaciones con supuestos diferentes

| Concepto | Práctica académica | Agente Paper |
|---|---:|---:|
| Capital inicial | 100,000 cotizados | 50,000 USDT en una cartera compartida |
| Costo por compra o venta | 0.10% | 0.0%, supuesto del protocolo |
| Exposición | 100% o efectivo | Máximo 10% por activo y 80% total |
| Deslizamiento | 0, supuesto académico | 2 puntos básicos adversos por ejecución |
| Ejecución histórica | Apertura siguiente a la emisión | Apertura siguiente, identificada como replay |
| Conexión actual | No aplica | Primera cotización pública obtenida después de inferir |

No se atribuye al modo actual la apertura que ya ocurrió durante la latencia del LLM. Las posiciones actuales se valoran con cotizaciones públicas y las históricas al cierre. Los límites diarios se conservan y al alcanzarse se pausan nuevas órdenes. En las comparaciones se aplica el mismo periodo, comisión, deslizamiento y límite de tamaño a modelo sin LLM, agente con LLM y pasiva. En el replay de un solo activo, comprar y mantener usa el 10% inicial permitido; en la práctica académica usa 100% como exige su apartado.

El LLM puede vetar o modificar la propuesta, pero no puede comprar si la señal congelada del modelo no se cumple ni modificar las reglas de riesgo. La referencia pasiva ignora la señal, por definición. Los porcentajes de costo anteriores son supuestos educativos; no se presentan como tarifas universales de MEXC.

## Operaciones y PnL

En **Simulación → Operaciones**, **Ganancia / pérdida** muestra el patrimonio menos el capital inicial. La columna **PnL · USDT** registra el resultado realizado de cada posición cerrada. **Órdenes ejecutadas** muestra fecha UTC, acción, precio y cantidad. Los vetos aparecen en **Decisiones**.

El replay histórico de BTCUSDT del 21 de octubre al 20 de noviembre de 2026 comenzó con **50,000.00 USDT**. Las tres estrategias cerraron con **48,730.91 USDT**, un **PnL neto de -1,269.09 USDT (-2.54%)**. El agente con Ollama registró estas operaciones Paper.

| Fecha UTC | Operación | Precio (USDT/BTC) | Cantidad (BTC) | PnL realizado (USDT) |
| --- | --- | ---: | ---: | ---: |
| 21 de octubre de 2026 | Compra | 83,046.78 | 0.06020703 | — |
| 20 de noviembre de 2026 | Venta al cierre del replay | 61,968.05 | 0.06020703 | -1,269.09 |

El motor vetó 29 compras adicionales por posición abierta. El registro de órdenes, las decisiones y la comparación se pueden contrastar con las bases Paper. [Órdenes](evidencia/replay_BTCUSDT/agente_con_llm_orders.csv) · [Decisiones](evidencia/replay_BTCUSDT/agente_con_llm_decisions.csv) · [Comparación](evidencia/replay_BTCUSDT/comparacion.csv)

## Pruebas y replay

```bash
python -m pytest -q
```

Las pruebas usan copias y fixtures sintéticos identificados. Cubren cuatro fallos de datos y los nueve escenarios del agente, más cronología, costos, límites y señales. Sus ciclos de integración no cuentan como ciclos de mercado. El replay productivo exige un modelo validado, sus datos congelados y Ollama real. Guarda tres bases SQLite separadas, CSV comparativos, propuestas y latencias. Una repetición interrumpida no se sobrescribe silenciosamente.

El resultado incluido se revisa en `docs/Resumen_Replay_BTCUSDT.md` o en `evidencia/replay_BTCUSDT/comparacion.csv`. `python scripts/replay.py --symbol BTCUSDT --cycles 30` devuelve el replay guardado cuando ya existe para el par. La verificación de esta entrega corresponde al replay histórico del 21 de octubre al 20 de noviembre de 2026, con fechas UTC.

`Win Rate` se calcula con operaciones cerradas de beneficio neto positivo. Si no hay operaciones cerradas, su valor es vacío/no definido. No equivale a acierto direccional. Las pruebas no hacen llamadas de órdenes reales; el cliente MEXC solo implementa una lista permitida de consultas GET públicas.

## Archivos y trazabilidad

```text
notebooks/       Práctica T4 y verificación local del agente
pai/             Datos, indicadores, entrenamiento y backtest académico
backend/         API privada, Ollama, riesgo, Paper y persistencia
frontend/        React/TypeScript, fuente y distribución compilada
config/          Catálogo y límites predeterminados
scripts/         Instalación, entrenamiento, importación y pruebas
tests/           Pruebas controladas
artifacts/       15 modelos, escaladores, experimentos y evaluación TE
data/            Respuestas de MEXC y muestras auditadas
evidencia/       Evidencia T4, pruebas, replay e incidentes
docs/            Informe, matriz y guía
anexos/          Avances previos del libro, diferenciados del protocolo
```

La cuenta actual se guarda en `var/paper.sqlite` y recupera estado al reiniciar, quedando pausada para evitar operaciones inesperadas. Esta base operativa se crea en el equipo del usuario y no se comparte junto con sus claves. La distribución contiene una base vacía de estructura y bases controladas cuando están identificadas como pruebas.

## Puntos que necesitan revisión académica

DL obtuvo un RMSE menor que la regresión lineal en 14 de 15 activos y menor que la referencia cero en 4 de 15. XLMUSDT fue el único par que además superó el 20% de rentabilidad neta en la simulación académica (+26.51%). La página 1 exige ambos criterios y la página 13 permite la candidatura sin rentabilidad positiva. La interpretación de ese requisito queda para revisión docente. Las tres estrategias del replay de BTCUSDT ejecutaron la misma compra y cierre. El motor bloqueó 29 compras adicionales propuestas por Ollama por existir ya una posición.

## Fuentes técnicas

- Protocolo del profesor, 15 páginas, recibido con esta actividad.
- Kaabar, *Deep Learning for Finance*, capítulos 7–11 proporcionados.
- API pública de MEXC: https://mexcdevelop.github.io/apidocs/spot_v3_en/.
- Ausencia de sandbox: https://www.mexc.com/es/mexc-api.
- Ollama local y autenticación: https://docs.ollama.com/api/authentication.
- Salidas estructuradas: https://docs.ollama.com/capabilities/structured-outputs.
- Modo sin nube: https://docs.ollama.com/faq.
- TensorFlow y dispositivo: https://www.tensorflow.org/guide/gpu.
- Disponibilidad de GPU Colab: https://research.google.com/colaboratory/faq.html.

Documentación verificada el 20 de noviembre de 2026. El contenido, los datos, la interpretación y la revisión académica corresponden al alumno; las métricas y la evidencia deben conservarse tal como fueron obtenidas.
