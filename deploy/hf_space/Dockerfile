# =============================================================================
# Zaha — API de inferencia en Hugging Face Spaces (SCRUM-63)
#
# Este Dockerfile vive en la RAIZ del repositorio del Space, no en el del
# proyecto. El contenido del Space lo arma `publicar.py`, que copia acá al lado
# solamente lo que la API necesita. Ver ese script para la lista exacta.
#
# POR QUE DOCKER Y NO EL SDK DE GRADIO
# Lo que se despliega es una API REST que consume la Edge Function de Supabase
# (SCRUM-64), no una demo con interfaz. Gradio agregaria una UI que nadie usa y
# una capa mas entre el pedido y onnxruntime.
# =============================================================================

FROM python:3.12-slim

# Spaces corre el contenedor como el usuario 1000, no como root. Si los archivos
# quedan de root, el proceso no puede leer el modelo y el Space arranca y muere
# sin un error que explique por que.
RUN useradd -m -u 1000 zaha
USER zaha
ENV PATH=/home/zaha/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /home/zaha/app

# Las dependencias primero, en su propia capa: el codigo cambia en cada despliegue
# y las dependencias casi nunca. Es requirements.txt (produccion), NO el -dev:
# sin torch, sin pandas, sin jupyter. Ver la cabecera de ese archivo.
COPY --chown=zaha requirements.txt ./
RUN pip install --no-cache-dir --user -r requirements.txt

COPY --chown=zaha src/ ./src/
COPY --chown=zaha models/ ./models/

# Spaces publica el 7860 por convencion.
EXPOSE 7860

# Sin --reload y con un solo worker. El Space free tiene 2 vCPU y 16 GB, y el
# modelo es una regresion logistica: el cuello de botella no es el calculo, es el
# arranque en frio cuando el Space se despierta. Mas workers solo multiplicarian
# la memoria del runtime de ONNX sin acelerar nada.
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "7860", "--workers", "1"]
