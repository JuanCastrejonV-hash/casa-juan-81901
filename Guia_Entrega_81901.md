# Guía de entrega

**Juan Fernando Castrejón Villa · 81901 · Actuaría, 5.º semestre**

- [Cuaderno ejecutado en Google Colab](https://colab.research.google.com/drive/1rBr_In1QC-_EjRIY7omLMOP92adsXyxk?usp=sharing). El enlace se comprobó sin iniciar sesión. La copia .ipynb incluida conserva las salidas guardadas y corrige una sangría en la celda que muestra los CSV.
- **Informe y resultados.** Abre [el informe a dos columnas](docs/Informe_Juan_Fernando_Castrejon_Villa_Dos_Columnas.pdf) para revisar el método, los resultados de los 15 activos y la comparación con Ollama.
- **Evidencia de Colab.** Los archivos de artifacts/ y data/ están incorporados. evidencia/manifest_exportacion_colab.json contiene sus huellas originales.
- **Evidencia del agente.** docs/Resumen_Replay_BTCUSDT.md explica los 30 ciclos históricos. evidencia/replay_BTCUSDT/ contiene las propuestas, el CSV comparativo y las bases SQLite.
- **Tablero histórico.** Descomprime el ZIP y abre `Abrir_Casa_Juan_81901.html` en un navegador. Presiona **Reproducir ciclo** en la oficina para seguir el replay de BTCUSDT. En **Laboratorio**, usa **Generar y probar** para investigar cualquiera de los 15 activos. La vista histórica funciona sin instalar programas.
- **Metodología.** Los experimentos, los supuestos y las fuentes consultadas se documentan en [Investigación y laboratorio de Casa Juan](docs/Investigacion_y_Laboratorio_Casa_Juan.md).
- **Aplicación local.** Ejecuta `Iniciar_Windows.bat` o `Iniciar_Mac.command` y usa la clave `PAI_API_KEY` de tu archivo `.env`. Consulta el [README](README.md) para configurar MEXC y Ollama, consultar el mercado en vivo y ejecutar nuevas simulaciones.

DL redujo el RMSE frente a la regresión lineal en 14 de 15 activos. XLMUSDT reunió ambos criterios de la página 1, con un rendimiento neto de +26.51% en la simulación académica. El profesor puede contrastar ese criterio con lo que indica la página 13 sobre la candidatura.
